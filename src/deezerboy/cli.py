import logging
import os
import subprocess
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from .api import COLUMNS_FULL, fetch_tracks
from .export import export_csv, export_excel, load_csv

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
load_dotenv()


@click.group()
def cli():
    """🎵 DeezerBoy - Gérez votre univers musical Deezer"""


@cli.command()
@click.option(
    "--user-id",
    default=os.getenv("DEEZER_USER_ID", ""),
    help="ID utilisateur Deezer (par défaut: depuis .env)",
)
@click.option("--output", type=click.Path(), default=None, help="Chemin d'export")
@click.option(
    "--format",
    type=click.Choice(["csv", "excel", "both"]),
    default="csv",
    help="Format d'export",
)
def export(user_id: str, output: str | None, format: str):
    """📥 Récupère vos musiques et les exporte en CSV/Excel"""
    if not user_id:
        click.secho("❌ ID Deezer requis. Ajoutez DEEZER_USER_ID dans .env", fg="red")
        return
    try:
        click.secho("🎵 Récupération de vos musiques...", fg="cyan")
        df = fetch_tracks(user_id, full_version=True)
        path = Path(output) if output else None
        if format in ["csv", "both"]:
            export_csv(df, path)
        if format in ["excel", "both"]:
            export_excel(df, path)
        click.secho(f"✅ Succès! {len(df)} chansons exportées.", fg="green")
    except Exception as exc:
        click.secho(f"❌ Erreur: {exc}", fg="red")
        raise


@cli.command()
def app():
    """🚀 Lance l'interface Streamlit"""
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "src/deezerboy/dashboard.py"],
            check=True,
        )
    except FileNotFoundError:
        click.secho("❌ Streamlit non installé. Lancez: make install", fg="red")
    except KeyboardInterrupt:
        click.secho("\n👋 App fermée", fg="yellow")


@cli.command()
@click.option("--path", type=click.Path(exists=True), default=None)
def stats(path: str | None):
    """📊 Affiche les statistiques du CSV"""
    df = load_csv(Path(path) if path else None)
    if df is None:
        click.secho("❌ Aucun CSV trouvé", fg="red")
        return

    playlist_cols = [
        c for c in df.columns if c not in COLUMNS_FULL and not c.startswith("artist_")
    ]
    click.echo("\n" + "=" * 50)
    click.secho("📊 STATISTIQUES DEEZER", fg="cyan", bold=True)
    click.echo("=" * 50)
    click.echo(f"🎵 Chansons uniques:   {len(df):,}")
    click.echo(f"📚 Playlists:          {len(playlist_cols)}")
    click.echo(f"🎤 Artistes:           {df['artist'].nunique()}")
    click.echo(f"💿 Albums:             {df['album'].nunique()}")
    click.echo(f"🎧 Durée totale:       {df['duration'].sum() / 3600:.0f}h")
    click.echo(f"⏱️  Durée moyenne:     {df['duration'].mean() / 60:.0f} min")
    click.echo("=" * 50 + "\n")


@cli.command()
def info():
    """ℹ️ Affiche les informations du projet"""
    click.secho("""
╔══════════════════════════════════════════════════════╗
║     🎵 DeezerBoy - Mon Univers Musical Deezer        ║
╚══════════════════════════════════════════════════════╝

  deezerboy export      📥 Récupère et exporte vos musiques
  deezerboy app         🚀 Lance l'interface Streamlit
  deezerboy stats       📊 Affiche les statistiques
  deezerboy info        ℹ️  Affiche cette aide

  deezerboy export --format excel
  deezerboy export --output ./data/
  deezerboy stats

🔑 Créez un fichier .env:
  DEEZER_USER_ID=votre_id
  LASTFM_API_KEY=votre_clé
    """, fg="blue")


def main():
    cli()


if __name__ == "__main__":
    main()
