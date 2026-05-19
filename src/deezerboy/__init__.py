"""🎵 DeezerBoy - Explorez votre univers musical Deezer"""

__version__ = "1.0.0"
__author__ = "Nathan"

from .api import fetch_tracks, COLUMNS_FULL, COLUMNS_SHORT
from .export import export_csv, export_excel, load_csv
from .cli import cli, main

__all__ = [
    "fetch_tracks",
    "export_csv",
    "export_excel",
    "load_csv",
    "cli",
    "main",
    "COLUMNS_FULL",
    "COLUMNS_SHORT",
]
