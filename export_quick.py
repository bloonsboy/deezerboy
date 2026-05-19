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
    print("❌ DEEZER_USER_ID non trouvé dans .env")
    print("📝 Créez un fichier .env avec: DEEZER_USER_ID=votre_id")
    exit(1)

print("🎵 Récupération de vos musiques...")
try:
    df = fetch_tracks(user_id)
    path = export_csv(df)
    print(f"✅ Succès! {len(df)} chansons exportées dans {path}")
except Exception as e:
    print(f"❌ Erreur: {e}")
    exit(1)
