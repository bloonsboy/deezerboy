"""
Module API pour récupérer les données Deezer.
"""

import time
import requests
import logging
from typing import Optional
from tqdm import tqdm
import pandas as pd

logger = logging.getLogger(__name__)

COLUMNS_SHORT = [
    "id",
    "title",
    "artist",
    "album",
    "duration",
    "rank",
    "isrc",
]
COLUMNS_FULL = COLUMNS_SHORT + ["release_date", "bpm", "gain", "genre"]


def fetch_with_retry(url: str, max_retries: int = 2, delay: int = 5) -> dict:
    """Récupère les données avec gestion des erreurs."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            data = response.json()

            if "error" in data and data["error"].get("code") == 4:
                logger.warning(
                    f"Quota dépassé. Tentative {attempt + 1}/{max_retries} dans {delay}s..."
                )
                time.sleep(delay)
            else:
                return data
        except requests.RequestException as e:
            logger.error(f"Erreur réseau: {e}")
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


def get_new_row(track: dict, playlist_title: str, full_version: bool) -> Optional[dict]:
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
            genre = get_genre(track_details)
            new_track_info.update(
                {
                    "release_date": track_details.get("release_date"),
                    "bpm": track_details.get("bpm"),
                    "gain": track_details.get("gain"),
                    "genre": genre,
                }
            )
            artists = [a["name"] for a in track_details.get("contributors", [])]
            for j, artist in enumerate(artists):
                new_track_info[f"artist_{j+1}"] = artist
            if new_track_info.get("artist") == new_track_info.get("artist_1"):
                new_track_info.pop("artist_1", None)

        new_track_info[playlist_title] = True
        return new_track_info

    except Exception as e:
        logger.error(f"❌ Erreur avec track {track.get('id')}: {e}")
        return None


def fetch_tracks(
    user_id: str, full_version: bool = True, progress_callback=None
) -> pd.DataFrame:
    """Récupère toutes les chansons d'un utilisateur depuis l'API Deezer."""
    logger.info(f"🎵 Récupération des données pour l'utilisateur {user_id}...")

    df_tracks = pd.DataFrame(columns=COLUMNS_FULL if full_version else COLUMNS_SHORT)
    playlists = get_playlist_ids(user_id)

    # Notifier le nombre total de playlists
    if progress_callback:
        progress_callback("start", 0, len(playlists))

    for idx, pid in enumerate(tqdm(playlists, desc="📚 Récupération des playlists")):
        playlist = fetch_with_retry(f"https://api.deezer.com/playlist/{pid}?limit=2000")
        logger.debug(
            f"Playlist '{playlist['title']}' contient {len(playlist['tracks']['data'])} chansons"
        )

        # Notifier la progression
        if progress_callback:
            progress_callback("progress", idx + 1, len(playlists), playlist["title"])

        existing_track_ids = set(df_tracks["id"])
        new_rows = []

        for track in playlist.get("tracks", {}).get("data", []):
            if track["id"] in existing_track_ids:
                df_tracks.loc[df_tracks["id"] == track["id"], playlist["title"]] = True
            else:
                new_row = get_new_row(track, playlist["title"], full_version)
                if new_row:
                    new_rows.append(new_row)
                    existing_track_ids.add(track["id"])

        if new_rows:
            new_tracks_df = pd.DataFrame(new_rows)
            df_tracks = pd.concat([df_tracks, new_tracks_df], ignore_index=True)

    # Trier les colonnes
    artist_specific_cols = sorted(
        [col for col in df_tracks.columns if col.startswith("artist_")]
    )
    base_cols = [col for col in df_tracks.columns if col not in artist_specific_cols]
    insert_pos = (
        base_cols.index("artist") + 1 if "artist" in base_cols else len(base_cols)
    )
    df_tracks = df_tracks[
        base_cols[:insert_pos] + artist_specific_cols + base_cols[insert_pos:]
    ]
    df_tracks = df_tracks.sort_values(
        by=["artist", "album", "title"], ascending=True
    ).reset_index(drop=True)

    logger.info(f"✅ {len(df_tracks)} chansons uniques récupérées")

    # Notifier la fin
    if progress_callback:
        progress_callback("complete", len(playlists), len(playlists))

    return df_tracks


def get_genres_lastfm(artist: str, title: str) -> Optional[str]:
    """Récupère les genres via Last.fm API."""
    try:
        import os
        from dotenv import load_dotenv

        load_dotenv()
        api_key = os.getenv("LASTFM_API_KEY")

        if not api_key:
            return None

        url = "http://ws.audioscrobbler.com/2.0/"
        params = {
            "method": "track.getInfo",
            "artist": artist,
            "track": title,
            "api_key": api_key,
            "format": "json",
        }

        response = requests.get(url, params=params, timeout=5)
        data = response.json()

        if "track" in data and "toptags" in data["track"]:
            tags = data["track"]["toptags"].get("tag", [])
            if isinstance(tags, list):
                genres = [t.get("name") for t in tags[:3]]
            else:
                genres = [tags.get("name")]
            return ", ".join(genres) if genres else None

        return None
    except Exception as e:
        logger.debug(f"Last.fm erreur: {e}")
        return None


def get_genres_musicbrainz(artist: str, title: str, isrc: str = None) -> Optional[str]:
    """Récupère les genres via MusicBrainz API (open-source)."""
    try:
        # Chercher par ISRC si disponible (plus précis)
        if isrc:
            url = f"https://musicbrainz.org/ws/2/isrc/{isrc}"
            params = {"fmt": "json"}
            response = requests.get(url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                if "recordings" in data and data["recordings"]:
                    recording = data["recordings"][0]
                    if "tags" in recording:
                        genres = [t["name"] for t in recording["tags"][:3]]
                        return ", ".join(genres) if genres else None

        # Fallback: chercher par artiste + titre
        url = "https://musicbrainz.org/ws/2/recording/"
        query = f'artist:"{artist}" AND recording:"{title}"'
        params = {"query": query, "fmt": "json", "limit": 1}
        response = requests.get(url, params=params, timeout=5)

        if response.status_code == 200:
            data = response.json()
            if "recordings" in data and data["recordings"]:
                recording = data["recordings"][0]
                if "tags" in recording:
                    genres = [t["name"] for t in recording["tags"][:3]]
                    return ", ".join(genres) if genres else None

        return None
    except Exception as e:
        logger.debug(f"MusicBrainz erreur: {e}")
        return None


def get_genres_deezer(track_data: dict) -> Optional[str]:
    """Fallback: récupère le genre via l'album Deezer."""
    try:
        if track_data.get("album") and track_data["album"].get("id"):
            album_data = fetch_with_retry(
                f"https://api.deezer.com/album/{track_data['album']['id']}"
            )
            if album_data.get("genres") and album_data["genres"].get("data"):
                genres = [g.get("name") for g in album_data["genres"]["data"]]
                return ", ".join(genres) if genres else None
        return None
    except Exception as e:
        logger.debug(f"Deezer genre erreur: {e}")
        return None


def get_genre(track_data: dict) -> Optional[str]:
    """Récupère le genre via Last.fm → MusicBrainz → Deezer (fallback)."""
    try:
        artist = track_data.get("artist", {})
        if isinstance(artist, dict):
            artist_name = artist.get("name", "")
        else:
            artist_name = str(artist)

        title = track_data.get("title", "")
        isrc = track_data.get("isrc", "")

        # Essayer Last.fm en priorité
        genre = get_genres_lastfm(artist_name, title)
        if genre:
            logger.debug(f"✅ Genre Last.fm trouvé: {genre}")
            return genre

        # Fallback MusicBrainz
        genre = get_genres_musicbrainz(artist_name, title, isrc)
        if genre:
            logger.debug(f"✅ Genre MusicBrainz trouvé: {genre}")
            return genre

        # Fallback Deezer
        genre = get_genres_deezer(track_data)
        if genre:
            logger.debug(f"✅ Genre Deezer trouvé: {genre}")
            return genre

        logger.debug(f"Aucun genre trouvé pour {artist_name} - {title}")
        return None

    except Exception as e:
        logger.debug(f"Erreur lors de la récupération du genre: {e}")
        return None


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
    except Exception as e:
        logger.error(f"❌ Erreur lors de la recherche: {e}")
        return []


def add_track_to_df(
    df: pd.DataFrame, track_id: int, full_version: bool = True
) -> pd.DataFrame:
    """Ajoute une chanson au DataFrame."""
    try:
        # Vérifier si la chanson existe déjà
        if not df.empty and track_id in df["id"].values:
            logger.warning(f"La chanson {track_id} existe déjà dans le CSV")
            return df

        # Récupérer les détails de la chanson
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
            genre = get_genre(track_data)
            new_track_info.update(
                {
                    "release_date": track_data.get("release_date"),
                    "bpm": track_data.get("bpm"),
                    "gain": track_data.get("gain"),
                    "genre": genre,
                }
            )
            # Ajouter les colonnes manquantes du DataFrame
            for col in df.columns:
                if col not in new_track_info:
                    new_track_info[col] = (
                        False if col.startswith(("artist_", "POJ", "CTP")) else None
                    )

        # Créer un nouveau DataFrame avec la chanson
        new_df = pd.DataFrame([new_track_info])

        # Concaténer avec le DataFrame existant
        result_df = pd.concat([df, new_df], ignore_index=True)

        # Supprimer les doublons en fonction de l'ID
        result_df = result_df.drop_duplicates(subset=["id"], keep="first").reset_index(
            drop=True
        )

        logger.info(
            f"✅ Chanson ajoutée: {new_track_info['title']} - {new_track_info['artist']}"
        )
        return result_df

    except Exception as e:
        logger.error(f"❌ Erreur lors de l'ajout de la chanson: {e}")
        return df
