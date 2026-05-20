#!/usr/bin/env python
"""
Script simple pour lancer rapidement l'export CSV.
Usage: python export_quick.py
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from src.deezerboy.api import fetch_tracks
from src.deezerboy.export import export_csv

# Charger .env
load_dotenv()

user_id = os.getenv("DEEZER_USER_ID", "")

if not user_id:
    print("DEEZER_USER_ID non trouvé dans .env")
    print("Creez un fichier .env avec: DEEZER_USER_ID=votre_id")
    exit(1)

print("Recuperation de vos musiques (avec enrichment)...")
try:
    df = fetch_tracks(user_id)  # full_version=True by default
    path = export_csv(df)
    print(f"Succes! {len(df)} chansons exportees dans {path}")
except Exception as e:
    print(f"Erreur: {e}")
    exit(1)
