# DeezerBoy

DeezerBoy exporte votre bibliotheque Deezer en CSV ou Excel et permet de consulter des statistiques dans le terminal ou via une interface Streamlit.

## Prerequis

- Python 3.11 ou plus
- Un fichier `.env` a la racine du projet

## Installation

### Avec `uv`

```bash
uv sync
source .venv/bin/activate
```

### Avec `pip`

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Configuration

Creez un fichier `.env` a la racine :

```env
DEEZER_USER_ID=123456789
LASTFM_API_KEY=
```

- `DEEZER_USER_ID` est obligatoire.
- `LASTFM_API_KEY` est optionnelle. Elle permet d'enrichir les genres, tags,
  popularité et artistes similaires via Last.fm.
- Les réponses Last.fm sont mises en cache localement dans
  `~/.cache/deezerboy/lastfm_cache.json` pour éviter les appels répétés.

Pour trouver votre ID Deezer :

1. Connectez-vous sur `https://www.deezer.com`
2. Ouvrez votre profil
3. Recuperez le nombre dans l'URL `https://www.deezer.com/profile/123456789`

## Commandes

Une fois l'environnement active :

```bash
deezerboy export
deezerboy stats
deezerboy app
```

Si `deezerboy export` ne fonctionne pas, lancez le binaire du projet directement :

```bash
.venv/bin/deezerboy export
```

## Exemples utiles

```bash
deezerboy export --format excel
deezerboy export --format both --output ./exports
deezerboy export --user-id 123456789
deezerboy stats --path ./exports/track_list.csv
deezerboy app
```

## Sorties

- Export par defaut dans `~/Downloads/`
- Fichiers disponibles : CSV, Excel, ou les deux
- Interface web Streamlit sur `http://localhost:8501`

## Depannage

### `deezerboy: command not found`

L'environnement virtuel n'est pas active ou le package n'est pas installe.

```bash
source .venv/bin/activate
pip install -e .
```

### `DEEZER_USER_ID` introuvable

Verifiez que le fichier `.env` existe a la racine du projet et contient bien :

```env
DEEZER_USER_ID=123456789
```

### Python trop ancien

Le projet demande Python 3.11+. Avec une version plus ancienne, le CLI peut echouer au demarrage.
