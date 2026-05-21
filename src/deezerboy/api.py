from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

logger = logging.getLogger(__name__)
load_dotenv()

COLUMNS_SHORT = ["id", "title", "artist", "album", "duration", "rank", "isrc"]
COLUMNS_FULL = COLUMNS_SHORT + [
    "release_date", "genre", "tags",
    "artist_listeners", "artist_playcount",
    "track_listeners", "track_playcount", "similar_artists",
]

LASTFM_CACHE_PATH = Path.home() / ".cache" / "deezerboy" / "lastfm_cache.json"
LASTFM_CACHE_TTL = 60 * 60 * 24 * 30
_LASTFM_CACHE: dict[str, dict[str, Any]] | None = None


def fetch_with_retry(url: str, max_retries: int = 2, delay: int = 5) -> dict:
    for attempt in range(max_retries):
        try:
            data = requests.get(url, timeout=10).json()
            if "error" in data and data["error"].get("code") == 4:
                logger.warning(f"Quota dépassé. Tentative {attempt + 1}/{max_retries} dans {delay}s...")
                time.sleep(delay)
            else:
                return data
        except requests.RequestException as exc:
            logger.error(f"Erreur réseau: {exc}")
            if attempt < max_retries - 1:
                time.sleep(delay)
    raise Exception(f"Impossible de récupérer {url} après {max_retries} tentatives")


def get_playlist_ids(user_id: str, limit: int = 100) -> list[int]:
    playlists = fetch_with_retry(
        f"https://api.deezer.com/user/{user_id}/playlists?limit={limit}"
    )["data"]
    names = [p["creator"]["name"] for p in playlists]
    owner = max(names, key=names.count)
    ids = [p["id"] for p in playlists if p["creator"]["name"] == owner]
    logger.info(f"✅ {len(ids)} playlists trouvées")
    return ids


def _load_lastfm_cache() -> dict[str, dict[str, Any]]:
    global _LASTFM_CACHE
    if _LASTFM_CACHE is not None:
        return _LASTFM_CACHE
    try:
        _LASTFM_CACHE = (
            json.loads(LASTFM_CACHE_PATH.read_text(encoding="utf-8"))
            if LASTFM_CACHE_PATH.exists()
            else {}
        )
    except Exception:
        _LASTFM_CACHE = {}
    return _LASTFM_CACHE


def _save_lastfm_cache(cache: dict) -> None:
    LASTFM_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LASTFM_CACHE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LASTFM_CACHE_PATH)


def _lastfm_request(method: str, params: dict[str, Any]) -> Optional[dict[str, Any]]:
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return None

    cache = _load_lastfm_cache()
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    cache_key = json.dumps({"method": method, "params": clean}, sort_keys=True, ensure_ascii=False)
    now = time.time()

    entry = cache.get(cache_key)
    if entry and now - entry.get("timestamp", 0) < LASTFM_CACHE_TTL:
        return entry["data"]

    try:
        resp = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={**params, "method": method, "api_key": api_key, "format": "json"},
            timeout=8,
        )
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            return None
        cache[cache_key] = {"timestamp": now, "data": data}
        _save_lastfm_cache(cache)
        return data
    except Exception:
        return None


def _extract_tags(source: dict | None, key: str) -> list[str]:
    if not source:
        return []
    node = source.get(key, {})
    if not isinstance(node, dict):
        return []
    raw = (node.get("toptags") or node.get("tags") or {}).get("tag", [])
    if isinstance(raw, dict):
        raw = [raw]
    seen: list[str] = []
    for tag in raw:
        name = tag.get("name") if isinstance(tag, dict) else None
        if name and name not in seen:
            seen.append(name)
    return seen


def _normalize_artist_name(track_data: dict) -> str:
    artist = track_data.get("artist", {})
    return artist.get("name", "") if isinstance(artist, dict) else str(artist)


def get_lastfm_metadata(artist: str, title: str) -> dict[str, Any]:
    track_data = _lastfm_request("track.getInfo", {"artist": artist, "track": title, "autocorrect": 1})
    artist_data = _lastfm_request("artist.getInfo", {"artist": artist, "autocorrect": 1})

    tags = _extract_tags(track_data, "track") or _extract_tags(artist_data, "artist")

    artist_node = artist_data.get("artist", {}) if artist_data else {}
    track_node = track_data.get("track", {}) if track_data else {}
    if not isinstance(artist_node, dict):
        artist_node = {}
    if not isinstance(track_node, dict):
        track_node = {}

    stats = artist_node.get("stats") or {}
    similar_raw = artist_node.get("similar", {}).get("artist", [])
    if isinstance(similar_raw, dict):
        similar_raw = [similar_raw]
    similar = [s["name"] for s in similar_raw if isinstance(s, dict) and s.get("name")]

    return {
        "genre": tags[0] if tags else None,
        "tags": "; ".join(tags[:5]) or None,
        "artist_listeners": stats.get("listeners"),
        "artist_playcount": stats.get("playcount"),
        "track_listeners": track_node.get("listeners"),
        "track_playcount": track_node.get("playcount"),
        "similar_artists": "; ".join(similar[:5]) or None,
    }


def _get_musicbrainz_enrichment(
    artist: str,
    title: str,
    isrc: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"release_date": None, "genre": None, "artists": []}

    try:
        recording = None
        inc = "artist-credits+releases+tags"

        if isrc:
            resp = requests.get(
                f"https://musicbrainz.org/ws/2/isrc/{isrc}",
                params={"fmt": "json", "inc": inc},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("recordings"):
                    recording = data["recordings"][0]

        if not recording:
            resp = requests.get(
                "https://musicbrainz.org/ws/2/recording/",
                params={
                    "query": f'artist:"{artist}" AND recording:"{title}"',
                    "fmt": "json",
                    "limit": "1",
                    "inc": inc,
                },
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("recordings"):
                    recording = data["recordings"][0]

        if not recording:
            return result

        result["release_date"] = recording.get("first-release-date") or None

        tags = recording.get("tags", [])
        if tags:
            result["genre"] = ", ".join(t["name"] for t in tags[:3])

        result["artists"] = [
            credit.get("name") or credit["artist"].get("name")
            for credit in recording.get("artist-credit", [])
            if isinstance(credit, dict) and "artist" in credit
        ]

    except Exception as exc:
        logger.debug(f"MusicBrainz erreur: {exc}")

    return result


def get_genres_deezer(track_data: dict) -> Optional[str]:
    try:
        album = track_data.get("album")
        if album and album.get("id"):
            data = fetch_with_retry(f"https://api.deezer.com/album/{album['id']}")
            genres = data.get("genres", {}).get("data", [])
            return ", ".join(g["name"] for g in genres) or None
        return None
    except Exception as exc:
        logger.debug(f"Deezer genre erreur: {exc}")
        return None


def _get_album_release_date(deezer_track_data: dict) -> Optional[str]:
    """Get release date from Deezer album data as fallback."""
    try:
        album = deezer_track_data.get("album")
        if album and album.get("id"):
            album_data = fetch_with_retry(f"https://api.deezer.com/album/{album['id']}")
            # Try different date fields that Deezer might provide
            release_date = album_data.get("release_date") or album_data.get("date")
            if release_date:
                # Deezer might return just year, or full date
                return release_date
        return None
    except Exception as exc:
        logger.debug(f"Deezer album release date error: {exc}")
        return None


def _get_all_tags(artist_name: str, title: str, track_data: dict) -> Optional[str]:
    """Collect tags from track, album, and artist sources."""
    all_tags = set()

    # Get Last.fm tags (track and artist)
    lastfm_tags = []
    track_data_lf = _lastfm_request("track.getInfo", {"artist": artist_name, "track": title, "autocorrect": 1})
    artist_data_lf = _lastfm_request("artist.getInfo", {"artist": artist_name, "autocorrect": 1})

    lastfm_tags.extend(_extract_tags(track_data_lf, "track"))
    lastfm_tags.extend(_extract_tags(artist_data_lf, "artist"))
    all_tags.update(tag.strip() for tag in lastfm_tags if tag.strip())

    # Get MusicBrainz tags from recording
    mb_result = _get_musicbrainz_enrichment(artist_name, title, track_data.get("isrc"))
    # Note: MusicBrainz tags are already processed in _get_musicbrainz_enrichment for genre,
    # but we could extract them separately if needed for tags field

    # Get Deezer album tags (if available)
    try:
        album = track_data.get("album")
        if album and album.get("id"):
            album_data = fetch_with_retry(f"https://api.deezer.com/album/{album['id']}")
            # Deezer album might have genres/tags - checking available fields
            genres = album_data.get("genres", {}).get("data", [])
            for genre in genres:
                if isinstance(genre, dict) and genre.get("name"):
                    all_tags.add(genre["name"].strip())
    except Exception:
        pass  # Ignore errors in fetching album tags

    if all_tags:
        # Return top tags joined by semicolon (limit to reasonable number)
        return "; ".join(sorted(all_tags)[:10])
    return None


def _get_track_enrichment(track_data: dict) -> dict[str, Any]:
    artist_name = _normalize_artist_name(track_data)
    title = track_data.get("title", "")
    isrc = track_data.get("isrc", "")

    lastfm = get_lastfm_metadata(artist_name, title)
    mb = _get_musicbrainz_enrichment(artist_name, title, isrc)

    # Get release date with fallback: MusicBrainz -> Deezer album
    release_date = mb.get("release_date") or _get_album_release_date(track_data)

    genre = lastfm.get("genre") or mb.get("genre") or get_genres_deezer(track_data)

    result: dict[str, Any] = {
        "release_date": release_date,
        "genre": genre,
        "tags": _get_all_tags(artist_name, title, track_data),
        "artist_listeners": lastfm.get("artist_listeners"),
        "artist_playcount": lastfm.get("artist_playcount"),
        "track_listeners": lastfm.get("track_listeners"),
        "track_playcount": lastfm.get("track_playcount"),
        "similar_artists": lastfm.get("similar_artists"),
    }

    for idx, name in enumerate(mb.get("artists", []), start=1):
        result[f"artist_{idx}"] = name
    if result.get("artist_1") == artist_name:
        result.pop("artist_1", None)

    return result


def get_new_row(track: dict, playlist_title: str, full_version: bool) -> Optional[dict]:
    try:
        row = {
            "id": track.get("id"),
            "title": track.get("title"),
            "artist": track.get("artist", {}).get("name"),
            "album": track.get("album", {}).get("title"),
            "duration": track.get("duration"),
            "rank": track.get("rank"),
            "isrc": track.get("isrc"),
        }
        if full_version:
            row.update(_get_track_enrichment(track))
        row[playlist_title] = True
        return row
    except Exception as exc:
        logger.error(f"❌ Erreur avec track {track.get('id')}: {exc}")
        return None


def fetch_tracks(
    user_id: str,
    full_version: bool = True,
    progress_callback=None,
) -> pd.DataFrame:
    logger.info(f"Retrieving data for user {user_id}...")

    df = pd.DataFrame(columns=COLUMNS_FULL if full_version else COLUMNS_SHORT)
    playlists = get_playlist_ids(user_id)

    if progress_callback:
        progress_callback("start", 0, len(playlists))

    for idx, pid in enumerate(tqdm(playlists, desc="Fetching playlists")):
        playlist = fetch_with_retry(f"https://api.deezer.com/playlist/{pid}?limit=2000")

        if progress_callback:
            progress_callback("progress", idx + 1, len(playlists), playlist["title"])

        existing_ids = set(df["id"])
        new_rows = []

        for track in playlist.get("tracks", {}).get("data", []):
            if track["id"] in existing_ids:
                df.loc[df["id"] == track["id"], playlist["title"]] = True
            else:
                row = get_new_row(track, playlist["title"], full_version)
                if row:
                    new_rows.append(row)
                    existing_ids.add(track["id"])

        if new_rows:
            df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)

    artist_cols = sorted(c for c in df.columns if c.startswith("artist_"))
    base = [c for c in df.columns if c not in artist_cols]
    pos = base.index("artist") + 1 if "artist" in base else len(base)
    df = df[base[:pos] + artist_cols + base[pos:]]
    df = df.sort_values(["artist", "album", "title"]).reset_index(drop=True)

    logger.info(f"✅ {len(df)} chansons uniques récupérées")

    if progress_callback:
        progress_callback("complete", len(playlists), len(playlists))

    return df


def search_music(query: str, limit: int = 20) -> list[dict]:
    try:
        data = fetch_with_retry(f"https://api.deezer.com/search?q={query}&limit={limit}")
        results = [
            {
                "id": t.get("id"),
                "title": t.get("title"),
                "artist": t.get("artist", {}).get("name"),
                "album": t.get("album", {}).get("title"),
                "duration": t.get("duration"),
            }
            for t in data.get("data", [])
        ]
        logger.info(f"✅ {len(results)} résultats trouvés pour '{query}'")
        return results
    except Exception as exc:
        logger.error(f"❌ Erreur lors de la recherche: {exc}")
        return []


def add_track_to_df(df: pd.DataFrame, track_id: int, full_version: bool = True) -> pd.DataFrame:
    try:
        if not df.empty and track_id in df["id"].values:
            logger.warning(f"La chanson {track_id} existe déjà dans le CSV")
            return df

        track_data = fetch_with_retry(f"https://api.deezer.com/track/{track_id}")
        row = {
            "id": track_data.get("id"),
            "title": track_data.get("title"),
            "artist": track_data.get("artist", {}).get("name"),
            "album": track_data.get("album", {}).get("title"),
            "duration": track_data.get("duration"),
            "rank": track_data.get("rank"),
            "isrc": track_data.get("isrc"),
        }

        if full_version:
            row.update(_get_track_enrichment(track_data))
            for col in df.columns:
                if col not in row:
                    row[col] = False if col.startswith(("artist_", "POJ", "CTP")) else None

        result = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        result = result.drop_duplicates(subset=["id"], keep="first").reset_index(drop=True)
        logger.info(f"✅ Chanson ajoutée: {row['title']} - {row['artist']}")
        return result

    except Exception as exc:
        logger.error(f"❌ Erreur lors de l'ajout de la chanson: {exc}")
        return df
