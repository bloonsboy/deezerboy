# DeezerBoy

Exporte votre bibliothèque Deezer en CSV ou Excel et explore vos statistiques via le terminal ou une interface Streamlit.

## Prérequis

- Python 3.11+
- [`just`](https://just.systems) — command runner cross-platform (Linux, Mac, Windows)

### Installer `just`

| OS      | Commande                    |
|---------|-----------------------------|
| Windows | `winget install Casey.Just` |
| Mac     | `brew install just`         |
| Linux   | `cargo install just`        |

## Installation

```bash
just install
```

Cela :
- installe les dépendances via `uv sync --extra dev` (ou `pip install -e ".[dev]"` si uv absent)
- crée un `.env` depuis `.env.example` s'il n'existe pas encore

## Configuration

Renseignez le fichier `.env` créé à la racine :

```env
DEEZER_USER_ID=123456789
LASTFM_API_KEY=votre_clé
```

- `DEEZER_USER_ID` : obligatoire. Trouvez votre ID dans l'URL de votre profil Deezer : `https://www.deezer.com/profile/123456789`
- `LASTFM_API_KEY` : optionnelle. Permet d'enrichir les données (genre, tags, popularité, artistes similaires). Créez une clé sur [last.fm/api](https://www.last.fm/api).

## Commandes

```bash
just install   # Installation et setup initial
just run       # Lance l'interface Streamlit
just export    # Exporte en CSV dans ~/Downloads/
just stats     # Affiche les statistiques en terminal
just lint      # Vérifie le code avec ruff
just clean     # Supprime les __pycache__
```

Les commandes `deezerboy` restent disponibles directement :

```bash
deezerboy export --format excel
deezerboy export --format both --output ./exports
deezerboy export --user-id 123456789
deezerboy stats --path ./exports/track_list.csv
```

## Données exportées

Chaque piste contient les champs suivants :

| Champ               | Source        | Description                          |
|---------------------|---------------|--------------------------------------|
| `id`                | Deezer        | Identifiant unique                   |
| `title`             | Deezer        | Titre                                |
| `artist`            | Deezer        | Artiste principal                    |
| `artist_1`, `_2`... | MusicBrainz   | Artistes crédités (featuring, etc.)  |
| `album`             | Deezer        | Album                                |
| `duration`          | Deezer        | Durée en secondes                    |
| `rank`              | Deezer        | Popularité Deezer                    |
| `isrc`              | Deezer        | Code ISRC                            |
| `release_date`      | MusicBrainz   | Date de sortie                       |
| `genre`             | Last.fm / MusicBrainz / Deezer | Genre principal (cascade de fallback) |
| `tags`              | Last.fm        | Tags (séparés par `;`)               |
| `artist_listeners`  | Last.fm        | Auditeurs uniques de l'artiste       |
| `artist_playcount`  | Last.fm        | Écoutes totales de l'artiste         |
| `track_listeners`   | Last.fm        | Auditeurs uniques de la piste        |
| `track_playcount`   | Last.fm        | Écoutes totales de la piste          |
| `similar_artists`   | Last.fm        | Artistes similaires (séparés par `;`)|

Les colonnes de playlists (`POJ`, `CTP`, etc.) sont ajoutées avec `True`/`False` pour chaque piste.

## Flux d'enrichissement

Pour chaque piste unique, deux appels sont faits (en plus de la récupération des playlists) :

1. **Last.fm** — `track.getInfo` + `artist.getInfo` → genre, tags, stats d'écoute, artistes similaires
   - Résultats mis en cache 30 jours dans `~/.cache/deezerboy/lastfm_cache.json`
2. **MusicBrainz** — un seul appel via ISRC (ou recherche artiste/titre en fallback) → `release_date`, artistes crédités, genre (fallback)

Si aucun genre n'est trouvé, un dernier appel à l'API album Deezer est effectué.

## Dépannage

**`deezerboy: command not found`** — activez le venv ou relancez `just install`.

```bash
source .venv/bin/activate
```

**`DEEZER_USER_ID` introuvable** — vérifiez que `.env` existe à la racine et contient `DEEZER_USER_ID=votre_id`.

**Python trop ancien** — le projet requiert Python 3.11+. Vérifiez avec `python --version`.
