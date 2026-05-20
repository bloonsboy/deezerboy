"""🎵 DeezerBoy - Explorez votre univers musical Deezer"""

__version__ = "1.0.0"
__author__ = "Nathan"

from .api import COLUMNS_FULL, COLUMNS_SHORT, fetch_tracks
from .cli import cli, main
from .export import export_csv, export_excel, load_csv

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
