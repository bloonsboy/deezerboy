"""
Module API pour récupérer les données Deezer.
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from tqdm import tqdm

logger = logging.getLogger(__name__)

load_dotenv()

COLUMNS_SHORT = [
    "id",
    "title",
    "artist",
    "album",
    "duration",
    "rank",
    "isrc",
]
COLUMNS_FULL = COLUMNS_SHORT + [
    "release_date",
    "bpm",
    "gain",
    "genre",
    "lastfm_genre",
    "lastfm_tags",
    "lastfm_primary_tag",
    "lastfm_artist_listeners",
    "lastfm_artist_playcount",
    "lastfm_track_listeners",
    "lastfm_track_playcount",
    "lastfm_bio_summary",
    "lastfm_similar_artists",
    "lastfm_source",
]

LASTFM_CACHE_PATH = Path.home() / ".cache" / "deezerboy" / "lastfm_cache.json"
LASTFM_CACHE_TTL = 60 * 60 * 24 * 30
_LASTFM_CACHE: dict[str, dict[str, Any]] | None = None


def fetch_with_retry(url: str, max_retries: int = 2, delay: int = 5) -> dict:
    """Récupère les données avec gestion des erreurs."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            if "error" in data and data["error"].get("code") == 4:
                logger.warning(
                    "Quota dépassé. Tentative "
                    f"{attempt + 1}/{max_retries} dans {delay}s..."
                )
                time.sleep(delay)
            else:
                return data
        except requests.RequestException as exc:
            logger.error(f"Erreur réseau: {exc}")
            if attempt < max_retries - 1:
                time.sleep(delay)

    raise Exception(f"Impossible de récupérer {url} après {max_retries} tentatives")


def get_playlist_ids(user_id: str, limit: int = 100) -> list[int]:
    """Récupère tous les IDs des playlists d'un utilisateur."""
    playlist_list = fetch_with_retry(
        f"https://api.deezer.com/user/{user_id}/playlists?limit={limit}"
    )["data"]
    user = max(
        [p["creator"]["name"] for p in playlist_list],
        key=[p["creator"]["name"] for p in playlist_list].count,
    )
    playlist_ids = [p["id"] for p in playlist_list if p["creator"]["name"] == user]
    logger.info(f"✅ {len(playlist_ids)} playlists trouvées")
    return playlist_ids


def _load_lastfm_cache() -> dict[str, dict[str, Any]]:
    """Charge le cache Last.fm en mémoire."""
    global _LASTFM_CACHE

    if _LASTFM_CACHE is not None:
        return _LASTFM_CACHE

    if LASTFM_CACHE_PATH.exists():
        try:
            with LASTFM_CACHE_PATH.open("r", encoding="utf-8") as handle:
                _LASTFM_CACHE = json.load(handle)
        except Exception as exc:
            logger.debug(f"Cache Last.fm illisible: {exc}")
            _LASTFM_CACHE = {}
    else:
        _LASTFM_CACHE = {}

    return _LASTFM_CACHE


def _save_lastfm_cache(cache: dict[str, dict[str, Any]]) -> None:
    """Sauvegarde le cache Last.fm sur disque."""
    LASTFM_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = LASTFM_CACHE_PATH.with_suffix(".tmp")

    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, ensure_ascii=False, indent=2)

    tmp_path.replace(LASTFM_CACHE_PATH)


def _lastfm_cache_key(method: str, params: dict[str, Any]) -> str:
    """Construit une clé de cache stable pour Last.fm."""
    clean_params = {
        key: value for key, value in params.items() if value not in (None, "")
    }
    payload = {"method": method, "params": clean_params}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _lastfm_request(
    method: str,
    params: dict[str, Any],
    ttl_seconds: int = LASTFM_CACHE_TTL,
) -> Optional[dict[str, Any]]:
    """Appelle Last.fm avec cache disque."""
    api_key = os.getenv("LASTFM_API_KEY")
    if not api_key:
        return None

    cache = _load_lastfm_cache()
    cache_key = _lastfm_cache_key(method, params)
    now = time.time()

    cached = cache.get(cache_key)
    if cached:
        timestamp = cached.get("timestamp", 0)
        if now - timestamp < ttl_seconds:
            return cached.get("data")

    url = "https://ws.audioscrobbler.com/2.0/"
    request_params = {
        **params,
        "method": method,
        "api_key": api_key,
        "format": "json",
    }

    try:
        response = requests.get(url, params=request_params, timeout=8)
        data = response.json()

        if response.status_code != 200 or "error" in data:
            logger.debug(f"Last.fm erreur {method}: {data.get('message', 'unknown')}")
            return None

        cache[cache_key] = {"timestamp": now, "data": data}
        _save_lastfm_cache(cache)
        return data
    except Exception as exc:
        logger.debug(f"Last.fm erreur {method}: {exc}")
        return None


def _normalize_artist_name(track_data: dict) -> str:
    artist = track_data.get("artist", {})
    if isinstance(artist, dict):
        return artist.get("name", "")
    return str(artist)


def _extract_tags(source: dict | None, key: str) -> list[str]:
    """Extrait une liste propre de tags depuis un bloc Last.fm."""
    if not source:
        return []

    node = source.get(key, {})
    if not isinstance(node, dict):
        return []

    tags_block = node.get("toptags") or node.get("tags") or {}
    tags = tags_block.get("tag", []) if isinstance(tags_block, dict) else []

    if isinstance(tags, dict):
        tags = [tags]

    cleaned: list[str] = []
    for tag in tags:
        name = tag.get("name") if isinstance(tag, dict) else None
        if name and name not in cleaned:
            cleaned.append(name)

    return cleaned


def _extract_summary(source: dict | None, key: str) -> Optional[str]:
    """Extrait un résumé lisible depuis une réponse Last.fm."""
    if not source:
        return None

    node = source.get(key, {})
    if not isinstance(node, dict):
        return None

    bio = node.get("bio", {})
    if not isinstance(bio, dict):
        return None

    summary = bio.get("summary")
    if not summary:
        return None

    summary = html.unescape(summary)
    summary = re.sub(r"<[^>]+>", "", summary)
    summary = summary.strip()
    return summary or None


def _lastfm_track_and_artist_info(
    artist: str,
    title: str,
) -> tuple[dict | None, dict | None]:
    """Récupère les réponses track et artist de Last.fm."""
    track_data = _lastfm_request(
        "track.getInfo",
        {"artist": artist, "track": title, "autocorrect": 1},
    )
    artist_data = _lastfm_request(
        "artist.getInfo",
        {"artist": artist, "autocorrect": 1},
    )
    return track_data, artist_data


def get_lastfm_metadata(artist: str, title: str) -> dict[str, Any]:
    """Récupère les métadonnées Last.fm utiles pour une piste."""
    track_data, artist_data = _lastfm_track_and_artist_info(artist, title)

    track_tags = _extract_tags(track_data, "track")
    artist_tags = _extract_tags(artist_data, "artist")

    tags: list[str] = []
    for tag in track_tags + artist_tags:
        if tag not in tags:
            tags.append(tag)

    artist_node = artist_data.get("artist", {}) if artist_data else {}
    track_node = track_data.get("track", {}) if track_data else {}

    if isinstance(artist_node, dict):
        artist_stats = artist_node.get("stats", {})
        similar_block = artist_node.get("similar", {})
    else:
        artist_stats = {}
        similar_block = {}

    similar_artists: list[str] = []
    if isinstance(similar_block, dict):
        similar_list = similar_block.get("artist", [])
    else:
        similar_list = []
    if isinstance(similar_list, dict):
        similar_list = [similar_list]
    for item in similar_list:
        name = item.get("name") if isinstance(item, dict) else None
        if name and name not in similar_artists:
            similar_artists.append(name)

    source_parts = []
    if track_data:
        source_parts.append("track")
    if artist_data:
        source_parts.append("artist")

    artist_listeners = None
    artist_playcount = None
    if isinstance(artist_stats, dict):
        artist_listeners = artist_stats.get("listeners")
        artist_playcount = artist_stats.get("playcount")

    track_listeners = None
    track_playcount = None
    if isinstance(track_node, dict):
        track_listeners = track_node.get("listeners")
        track_playcount = track_node.get("playcount")

    return {
        "lastfm_genre": tags[0] if tags else None,
        "lastfm_tags": ", ".join(tags[:5]) if tags else None,
        "lastfm_primary_tag": tags[0] if tags else None,
        "lastfm_artist_listeners": artist_listeners,
        "lastfm_artist_playcount": artist_playcount,
        "lastfm_track_listeners": track_listeners,
        "lastfm_track_playcount": track_playcount,
        "lastfm_bio_summary": _extract_summary(artist_data, "artist"),
        "lastfm_similar_artists": (
            ", ".join(similar_artists[:5]) if similar_artists else None
        ),
        "lastfm_source": "+".join(source_parts) if source_parts else None,
    }


def get_genres_lastfm(artist: str, title: str) -> Optional[str]:
    """Récupère les genres via Last.fm API."""
    try:
        metadata = get_lastfm_metadata(artist, title)
        return metadata.get("lastfm_genre")
    except Exception as exc:
        logger.debug(f"Last.fm erreur: {exc}")
        return None


def get_genres_musicbrainz(
    artist: str,
    title: str,
    isrc: str | None = None,
) -> Optional[str]:
    """Récupère les genres via MusicBrainz API (open-source)."""
    try:
        if isrc:
            url = f"https://musicbrainz.org/ws/2/isrc/{isrc}"
            params = {"fmt": "json"}
            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if data.get("recordings"):
                    recording = data["recordings"][0]
                    if recording.get("tags"):
                        genres = [t["name"] for t in recording["tags"][:3]]
                        return ", ".join(genres) if genres else None

        url = "https://musicbrainz.org/ws/2/recording/"
        query = f'artist:"{artist}" AND recording:"{title}"'
        params = {"query": query, "fmt": "json", "limit": "1"}
        response = requests.get(url, params=params, timeout=5)

        if response.status_code == 200:
            data = response.json()
            if data.get("recordings"):
                recording = data["recordings"][0]
                if recording.get("tags"):
                    genres = [t["name"] for t in recording["tags"][:3]]
                    return ", ".join(genres) if genres else None

        return None
    except Exception as exc:
        logger.debug(f"MusicBrainz erreur: {exc}")
        return None


def get_genres_deezer(track_data: dict) -> Optional[str]:
    """Fallback: récupère le genre via l'album Deezer."""
    try:
        album = track_data.get("album")
        if album and album.get("id"):
            album_data = fetch_with_retry(f"https://api.deezer.com/album/{album['id']}")
            if album_data.get("genres") and album_data["genres"].get("data"):
                genres = [g.get("name") for g in album_data["genres"]["data"]]
                return ", ".join(genres) if genres else None
        return None
    except Exception as exc:
        logger.debug(f"Deezer genre erreur: {exc}")
        return None


def get_genre(track_data: dict) -> Optional[str]:
    """Récupère le genre via Last.fm → MusicBrainz → Deezer (fallback)."""
    try:
        artist_name = _normalize_artist_name(track_data)
        title = track_data.get("title", "")
        isrc = track_data.get("isrc", "")

        genre = get_genres_lastfm(artist_name, title)
        if genre:
            logger.debug(f"✅ Genre Last.fm trouvé: {genre}")
            return genre

        genre = get_genres_musicbrainz(artist_name, title, isrc)
        if genre:
            logger.debug(f"✅ Genre MusicBrainz trouvé: {genre}")
            return genre

        genre = get_genres_deezer(track_data)
        if genre:
            logger.debug(f"✅ Genre Deezer trouvé: {genre}")
            return genre

        logger.debug(f"Aucun genre trouvé pour {artist_name} - {title}")
        return None

    except Exception as exc:
        logger.debug(f"Erreur lors de la récupération du genre: {exc}")
        return None


def _get_track_enrichment(track_data: dict) -> dict[str, Any]:
    """Construit les champs enrichis pour une piste."""
    artist_name = _normalize_artist_name(track_data)
    title = track_data.get("title", "")

    lastfm_metadata = get_lastfm_metadata(artist_name, title)
    genre = lastfm_metadata.get("lastfm_genre")

    if not genre:
        genre = get_genres_musicbrainz(
            artist_name,
            title,
            track_data.get("isrc", ""),
        )
        if not genre:
            genre = get_genres_deezer(track_data)

    return {
        "genre": genre,
        **lastfm_metadata,
    }


def get_new_row(
    track: dict,
    playlist_title: str,
    full_version: bool,
) -> Optional[dict]:
    """Crée une ligne de données pour une chanson."""
    try:
        track_details = track
        if full_version:
            details = fetch_with_retry(f"https://api.deezer.com/track/{track['id']}")
            if details:
                track_details = details

        new_track_info = {
            "id": track_details.get("id"),
            "title": track_details.get("title"),
            "artist": track_details.get("artist", {}).get("name"),
            "album": track_details.get("album", {}).get("title"),
            "duration": track_details.get("duration"),
            "rank": track_details.get("rank"),
            "isrc": track_details.get("isrc"),
        }

        if full_version:
            new_track_info.update(
                {
                    "release_date": track_details.get("release_date"),
                    "bpm": track_details.get("bpm"),
                    "gain": track_details.get("gain"),
                }
            )
            new_track_info.update(_get_track_enrichment(track_details))

            artists = [a["name"] for a in track_details.get("contributors", [])]
            for index, artist_name in enumerate(artists):
                new_track_info[f"artist_{index + 1}"] = artist_name

            if new_track_info.get("artist") == new_track_info.get("artist_1"):
                new_track_info.pop("artist_1", None)

        new_track_info[playlist_title] = True
        return new_track_info

    except Exception as exc:
        logger.error(f"❌ Erreur avec track {track.get('id')}: {exc}")
        return None


def fetch_tracks(
    user_id: str,
    full_version: bool = True,
    progress_callback=None,
) -> pd.DataFrame:
    """Récupère toutes les chansons d'un utilisateur depuis l'API Deezer."""
    logger.info(f"🎵 Récupération des données pour l'utilisateur {user_id}...")

    df_tracks = pd.DataFrame(columns=COLUMNS_FULL if full_version else COLUMNS_SHORT)
    playlists = get_playlist_ids(user_id)

    if progress_callback:
        progress_callback("start", 0, len(playlists))

    for idx, pid in enumerate(tqdm(playlists, desc="📚 Récupération des playlists")):
        playlist = fetch_with_retry(f"https://api.deezer.com/playlist/{pid}?limit=2000")
        logger.debug(
            f"Playlist '{playlist['title']}' contient "
            f"{len(playlist['tracks']['data'])} chansons"
        )

        if progress_callback:
            progress_callback(
                "progress",
                idx + 1,
                len(playlists),
                playlist["title"],
            )

        existing_track_ids = set(df_tracks["id"])
        new_rows = []

        for track in playlist.get("tracks", {}).get("data", []):
            if track["id"] in existing_track_ids:
                df_tracks.loc[
                    df_tracks["id"] == track["id"],
                    playlist["title"],
                ] = True
            else:
                new_row = get_new_row(track, playlist["title"], full_version)
                if new_row:
                    new_rows.append(new_row)
                    existing_track_ids.add(track["id"])

        if new_rows:
            new_tracks_df = pd.DataFrame(new_rows)
            df_tracks = pd.concat(
                [df_tracks, new_tracks_df],
                ignore_index=True,
            )

    artist_specific_cols = sorted(
        [col for col in df_tracks.columns if col.startswith("artist_")]
    )
    base_cols = [col for col in df_tracks.columns if col not in artist_specific_cols]
    if "artist" in base_cols:
        insert_pos = base_cols.index("artist") + 1
    else:
        insert_pos = len(base_cols)
    df_tracks = df_tracks[
        base_cols[:insert_pos] + artist_specific_cols + base_cols[insert_pos:]
    ]
    df_tracks = df_tracks.sort_values(
        by=["artist", "album", "title"],
        ascending=True,
    ).reset_index(drop=True)

    logger.info(f"✅ {len(df_tracks)} chansons uniques récupérées")

    if progress_callback:
        progress_callback("complete", len(playlists), len(playlists))

    return df_tracks


def search_music(query: str, limit: int = 20) -> list[dict]:
    """Recherche de la musique par titre ou artiste."""
    try:
        url = f"https://api.deezer.com/search?q={query}&limit={limit}"
        data = fetch_with_retry(url)
        results = []

        for track in data.get("data", []):
            track_info = {
                "id": track.get("id"),
                "title": track.get("title"),
                "artist": track.get("artist", {}).get("name"),
                "album": track.get("album", {}).get("title"),
                "duration": track.get("duration"),
            }
            results.append(track_info)

        logger.info(f"✅ {len(results)} résultats trouvés pour '{query}'")
        return results
    except Exception as exc:
        logger.error(f"❌ Erreur lors de la recherche: {exc}")
        return []


def add_track_to_df(
    df: pd.DataFrame,
    track_id: int,
    full_version: bool = True,
) -> pd.DataFrame:
    """Ajoute une chanson au DataFrame."""
    try:
        if not df.empty and track_id in df["id"].values:
            logger.warning(f"La chanson {track_id} existe déjà dans le CSV")
            return df

        track_data = fetch_with_retry(f"https://api.deezer.com/track/{track_id}")

        new_track_info = {
            "id": track_data.get("id"),
            "title": track_data.get("title"),
            "artist": track_data.get("artist", {}).get("name"),
            "album": track_data.get("album", {}).get("title"),
            "duration": track_data.get("duration"),
            "rank": track_data.get("rank"),
            "isrc": track_data.get("isrc"),
        }

        if full_version:
            new_track_info.update(
                {
                    "release_date": track_data.get("release_date"),
                    "bpm": track_data.get("bpm"),
                    "gain": track_data.get("gain"),
                }
            )
            new_track_info.update(_get_track_enrichment(track_data))

            for col in df.columns:
                if col not in new_track_info:
                    new_track_info[col] = (
                        False if col.startswith(("artist_", "POJ", "CTP")) else None
                    )

        new_df = pd.DataFrame([new_track_info])
        result_df = pd.concat([df, new_df], ignore_index=True)

        result_df = result_df.drop_duplicates(subset=["id"], keep="first").reset_index(
            drop=True
        )

        logger.info(
            f"✅ Chanson ajoutée: {new_track_info['title']} - "
            f"{new_track_info['artist']}"
        )
        return result_df

    except Exception as exc:
        logger.error(f"❌ Erreur lors de l'ajout de la chanson: {exc}")
        return df
