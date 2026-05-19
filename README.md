# 🎵 DeezerBoy

Explorez et analysez votre bibliothèque musicale Deezer avec des statistiques détaillées et visualisations interactives.

## 🚀 Démarrage Rapide (3 étapes)

### 1. Installation

```bash
# Avec uv (recommandé - 30 sec)
uv sync

# Ou avec pip
pip install -e .
```

### 2. Configuration

Créez un fichier `.env` à la racine :

```env
DEEZER_USER_ID=123456789
```

**Comment trouver votre ID Deezer?**
1. Allez sur https://www.deezer.com et connectez-vous
2. Cliquez sur votre profil
3. L'URL ressemble à: `https://www.deezer.com/profile/123456789`
4. Copiez l'ID (les chiffres)

### 3. Utilisation

```bash
# Créer le CSV
deezerboy export

# Analyser les données
deezerboy stats

# Interface web
deezerboy app
```

---

## 📋 Commandes Disponibles

| Commande | Description |
|----------|-------------|
| `deezerboy export` | 📥 Récupère et exporte vos musiques en CSV |
| `deezerboy app` | 🚀 Lance l'interface Streamlit |
| `deezerboy stats` | 📊 Affiche les statistiques |
| `deezerboy info` | ℹ️ Affiche l'aide |

---

## 📖 Installation Détaillée

### Option A: uv (Recommandé)

```bash
# Installer uv si vous ne l'avez pas
curl -LsSf https://astral.sh/uv/install.sh | sh

# Créer l'environment
uv sync

# Activer (Linux/Mac)
source .venv/bin/activate

# Activer (Windows)
.venv\Scripts\activate
```

### Option B: pip

```bash
pip install -e .
```

---

## 🎯 Utilisation Complète

### Créer le CSV (Terminal)

```bash
# Simple - récupère l'ID depuis .env
deezerboy export

# Ou spécifier directement
deezerboy export --user-id 123456789

# Autres formats
deezerboy export --format excel
deezerboy export --format both

# Chemin personnalisé
deezerboy export --output ./my_music/
```

**Résultat:** Fichier CSV créé dans `~/Downloads/` (par défaut)

### Analyser les Données (Terminal)

```bash
# Afficher les stats du CSV
deezerboy stats

# Depuis un CSV personnalisé
deezerboy stats --path ./my_music/track_list.csv
```

### Interface Web (Streamlit)

```bash
deezerboy app
```

Accédez à http://localhost:8501 dans votre navigateur.

**Fonctionnalités:**
- 📂 Charger un CSV
- 🔄 Récupérer depuis l'API
- 📊 Visualisations interactives
- 💾 Export (CSV/Excel)

---

## 🆘 Troubleshooting

### "Command 'deezerboy' not found"

```bash
# Vérifiez que l'environment est activé
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Réinstallez
uv sync
# ou
pip install -e .
```

### "DEEZER_USER_ID not found"

Créez le fichier `.env` à la racine avec:

```env
DEEZER_USER_ID=votre_id
```

### "API Error" ou "Quota exceeded"

L'API Deezer a des limites. Attendez 5-10 minutes et réessayez.

### "ModuleNotFoundError"

```bash
# Réinstallez les dépendances
uv sync --refresh
# ou
pip install -e .
```

---

## 📊 Données Collectées

Chaque chanson contient:
- **Basiques:** `id`, `title`, `artist`, `album`
- **Infos:** `duration`, `rank` (popularité Deezer)
- **Avancé:** `isrc`, `preview`, `release_date`, `bpm`, `gain`
- **Playlists:** True/False pour chaque playlist

---

## 📁 Structure du Projet

```
deezerboy/
├── pyproject.toml              # Config uv et dépendances
├── README.md                   # Cette documentation
├── .env                        # Variables d'environnement (à créer)
├── .env.example               # Template
├── src/
│   └── deezerboy/
│       ├── __init__.py         # Package init
│       ├── api.py              # Module API Deezer
│       ├── export.py           # Export CSV/Excel
│       ├── cli.py              # Interface CLI
│       └── dashboard.py        # App Streamlit
└── export.bat                  # Raccourci Windows
```

---

## 💡 Astuces & Utilisation Avancée

### Mise à Jour Régulière

```bash
# Mettre à jour le CSV tous les mois
deezerboy export

# Vérifier les stats
deezerboy stats
```

### Analyser les données en Python

```python
from deezerboy import load_csv, fetch_tracks
import pandas as pd

# Charger le CSV
df = load_csv()

# Ou récupérer depuis l'API
df = fetch_tracks("123456789")

# Analyser
print(f"Total chansons: {len(df)}")
print(f"Artistes: {df['artist'].nunique()}")
```

### Export multi-formats

```bash
deezerboy export --format both --output ./backups/
```

---

## 🔧 Dépendances

- Python 3.11+
- pandas, numpy, requests
- plotly, streamlit
- click, python-dotenv

Installation automatique avec `uv sync` ou `pip install -e .`

---

## 🚀 Prochaines Étapes

1. ✅ Installer: `uv sync`
2. ✅ Configuration: Créer `.env`
3. ✅ Export: `deezerboy export`
4. ✅ Analyser: `deezerboy stats`
5. ✅ Explorer: `deezerboy app`

---

**Besoin d'aide?** Lancez `deezerboy info` 🎵
