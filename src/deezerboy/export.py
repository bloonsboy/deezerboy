import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

PLAYLIST_ORDER = [
    "POJ", "CTP", "RKJ", "VCL", "POE", "RKE", "RPE", "POF", "IDF", "RPF",
    "POK", "DEM", "BRZ", "FNK", "JAF", "LOF", "MSC", "AUG", "?XD", "SLV",
    "NTV", "CHV", "PCV", "CTV", "HPV", "FCV", "HUV", "PDV", "SMR", "FAE",
    "FAF", "FAJ", "FAV", "Coups de cœur", "ONE", "CMF", "CUH", "GMG", "LRB",
    "ANS", "RCN", "SNC", "PTN", "SGM", "100", "ADD", "Full - part 4",
]


def reorder_columns(df: pd.DataFrame) -> pd.DataFrame:
    from .api import COLUMNS_FULL
    base = [c for c in COLUMNS_FULL if c in df.columns]
    playlists = [c for c in PLAYLIST_ORDER if c in df.columns]
    other = [c for c in df.columns if c not in base and c not in playlists]
    return df[base + playlists + other]


def _default_path(ext: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path.home() / "Downloads" / f"deezer_tracks_{ts}.{ext}"


def export_csv(df: pd.DataFrame, output_path: Path | None = None) -> Path:
    df = reorder_columns(df)
    path = output_path or _default_path("csv")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    logger.info(f"CSV exported: {path}")
    return path


def export_excel(df: pd.DataFrame, output_path: Path | None = None) -> Path:
    df = reorder_columns(df)
    path = output_path or _default_path("xlsx")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False, sheet_name="Tracks")
    logger.info(f"✅ Excel exporté: {path}")
    return path


def get_default_csv_path() -> Path:
    return Path.home() / "Downloads" / "track_list.csv"


def load_csv(path: Path | None = None) -> pd.DataFrame | None:
    candidates = [path] if path else [Path("track_list.csv"), get_default_csv_path()]
    for p in candidates:
        if p and p.exists():
            logger.info(f"✅ CSV trouvé: {p}")
            return pd.read_csv(p)
    logger.warning("⚠️ Aucun CSV trouvé")
    return None
