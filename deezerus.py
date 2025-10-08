import time
import requests
import logging
from tqdm import tqdm

import pandas as pd

COLUMNS_SHORT = ["id", "title", "artist", "album", "duration", "rank"] # base columns
COLUMNS_FULL = COLUMNS_SHORT + ["release_date", "bpm", "gain"] # extended columns

def fetch_with_retry(url: str, max_retries: int = 2, delay: int = 5) -> dict:
    """
    Fetch data from a URL with retry logic for handling quota limits.
    """
    for attempt in range(max_retries):
        response = requests.get(url)
        data = response.json()
        if "error" in data and data["error"].get("code") == 4:  # Quota limit exceeded
            logging.warning(f"Quota exceeded. Retry {attempt + 1}/{max_retries} in {delay}s...")
            time.sleep(delay)
        else:
            return data
    logging.error(f"Failed to fetch data from {url} after {max_retries} retries.")
    raise Exception("Max retries exceeded")


def get_playlist_ids(user_id: str, limit: int = 100) -> list[int]:
    """
    Retrieve all playlist IDs for a given user.
    """
    playlist_list = fetch_with_retry(f"https://api.deezer.com/user/{user_id}/playlists?limit={limit}")["data"]
    user = max([playlist['creator']['name'] for playlist in playlist_list], key=[playlist['creator']['name'] for playlist in playlist_list].count)
    playlist_ids = [playlist["id"] for playlist in playlist_list if playlist["creator"]["name"] == user]
    logging.info(f"Found {len(playlist_ids)} playlists for user {user}")
    return playlist_ids


def create_new_row(track: dict, playlist_title: str, full_version: bool) -> dict:
    """
    Create a new row for the DataFrame from track details.

    Args:
        track (dict): Track details from a playlist.
        playlist_title (str): Title of the playlist containing the track.
        full_version (bool): If True, fetch full track details; otherwise, fetch basic details.
    """
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
        }
        if full_version:
            new_track_info.update({
                "release_date": track_details.get("release_date"),
                "bpm": track_details.get("bpm"),
                "gain": track_details.get("gain"),
            })
            artists = [artist["name"] for artist in track_details.get("contributors", [])]
            for j, artist in enumerate(artists):
                new_track_info[f'artist_{j+1}'] = artist
            if new_track_info.get("artist") == new_track_info.get("artist_1"):
                new_track_info.pop("artist_1", None)
            new_track_info[playlist_title] = True
        
        return new_track_info

    except Exception as e:
        logging.error(f"Error processing track ID {track['id']}: {e}")

def create_dataframe(user_id: str, full_version: bool = False) -> pd.DataFrame:
    """
    Create a pandas DataFrame from a user ID.

    Args:
        user_id (str): Deezer user ID.
        full_version (bool): If True, fetch full track details; otherwise, fetch basic details.

    Returns:
        pd.DataFrame: DataFrame containing track details.
    """
    df_tracks = pd.DataFrame(columns=COLUMNS_FULL if full_version else COLUMNS_SHORT)
    playlists = get_playlist_ids(user_id)
    for pid in playlists:
        playlist = fetch_with_retry(f"https://api.deezer.com/playlist/{pid}?limit=2000")
        logging.info(f"Playlist '{playlist['title']}' contains {len(playlist['tracks']['data'])} tracks.")

        existing_track_ids = set(df_tracks['id'])
        new_rows = []
        for track in playlist.get("tracks", {}).get("data", []):
            if track['id'] in existing_track_ids:
                df_tracks.loc[df_tracks['id'] == track['id'], playlist['title']] = True
            else:
                new_row = create_new_row(track, playlist['title'], full_version)
                if new_row:
                    new_rows.append(new_row)
                    existing_track_ids.add(track['id'])

        if new_rows:
            new_tracks_df = pd.DataFrame(new_rows)
            df_tracks = pd.concat([df_tracks, new_tracks_df], ignore_index=True)

    return df_tracks
