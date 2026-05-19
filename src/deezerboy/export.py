"""
Module pour exporter les données musicales en CSV, Excel, etc.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Ordre des colonnes de playlists
PLAYLIST_ORDER = [
    "POJ",
    "CTP",
    "RKJ",
    "VCL",
    "POE",
    "RKE",
    "RPE",
    "POF",
    "IDF",
    "RPF",
    "POK",
    "DEM",
    "BRZ",
    "FNK",
    "JAF",
    "LOF",
    "MSC",
    "AUG",
    "?XD",
    "SLV",
    "NTV",
    "CHV",
    "PCV",
    "CTV",
    "HPV",
    "FCV",
    "HUV",
    "PDV",
    "SMR",
    "FAE",
    "FAF",
    "FAJ",
    "FAV",
    "Coups de cœur",
    "ONE",
    "CMF",
    "CUH",
    "GMG",
    "LRB",
    "ANS",
    "RCN",
    "SNC",
    "PTN",
    "SGM",
    "100",
    "ADD",
    "Full - part 4",
]


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Réordonne les colonnes avec playlists dans l'ordre spécifié."""
    from .api import COLUMNS_FULL

    # Colonnes de base (dans l'ordre)
    base_cols = [col for col in COLUMNS_FULL if col in df.columns]

    # Playlists en ordre spécifié
    playlist_cols = [col for col in PLAYLIST_ORDER if col in df.columns]

    # Autres colonnes non prévues
    other_cols = [
        col for col in df.columns if col not in base_cols and col not in playlist_cols
    ]

    # Ordre final
    final_cols = base_cols + playlist_cols + other_cols

    return df[final_cols]


def export_csv(df: pd.DataFrame, output_path: Path | None = None) -> Path:
    """Exporte les données en CSV."""
    # Réordonner les colonnes
    df = reorder_columns(df)

    if output_path is None:
        output_path = (
            Path.home()
            / "Downloads"
            / f"deezer_tracks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"✅ CSV exporté: {output_path}")
    return output_path


def export_excel(df: pd.DataFrame, output_path: Path | None = None) -> Path:
    """Exporte les données en Excel."""
    # Réordonner les colonnes
    df = reorder_columns(df)

    if output_path is None:
        output_path = (
            Path.home()
            / "Downloads"
            / f"deezer_tracks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False, sheet_name="Tracks")
    logger.info(f"✅ Excel exporté: {output_path}")
    return output_path


def get_default_csv_path() -> Path:
    """Récupère le chemin par défaut du CSV."""
    return Path.home() / "Downloads" / "track_list.csv"


def load_csv(path: Path | None = None) -> pd.DataFrame | None:
    """Charge un CSV existant."""
    if path is None:
        # Chercher dans l'ordre de priorité
        local_path = Path("track_list.csv")
        if local_path.exists():
            logger.info(f"✅ CSV trouvé: {local_path}")
            return pd.read_csv(local_path)

        downloads_path = get_default_csv_path()
        if downloads_path.exists():
            logger.info(f"✅ CSV trouvé: {downloads_path}")
            return pd.read_csv(downloads_path)
    else:
        if path.exists():
            logger.info(f"✅ CSV trouvé: {path}")
            return pd.read_csv(path)

    logger.warning("⚠️ Aucun CSV trouvé")
    return None
