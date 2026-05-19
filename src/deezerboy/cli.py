"""
Interface en ligne de commande pour DeezerBoy.
"""

import click
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

from .api import fetch_tracks
from .export import export_csv, export_excel, load_csv

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()


@click.group()
def cli():
    """🎵 DeezerBoy - Gérez votre univers musical Deezer"""
    pass


@cli.command()
@click.option(
    '--user-id',
    default=os.getenv('DEEZER_USER_ID', ''),
    help='Votre ID utilisateur Deezer (par défaut: depuis .env)'
)
@click.option(
    '--output',
    type=click.Path(),
    default=None,
    help='Chemin d\'export (par défaut: ~/Downloads/)'
)
@click.option(
    '--format',
    type=click.Choice(['csv', 'excel', 'both']),
    default='csv',
    help='Format d\'export'
)
def export(user_id: str, output: str | None, format: str):
    """📥 Récupère vos musiques et les exporte en CSV/Excel"""
    
    if not user_id:
        click.secho("❌ ID Deezer requis. Créez un fichier .env avec DEEZER_USER_ID=votre_id", fg='red')
        return
    
    try:
        click.secho("🎵 Récupération de vos musiques...", fg='cyan')
        df = fetch_tracks(user_id, full_version=True)
        
        output_path = Path(output) if output else None
        
        if format in ['csv', 'both']:
            export_csv(df, output_path)
        
        if format in ['excel', 'both']:
            export_excel(df, output_path)
        
        click.secho(f"✅ Succès! {len(df)} chansons exportées.", fg='green')
        
    except Exception as e:
        click.secho(f"❌ Erreur: {e}", fg='red')
        raise


@cli.command()
def app():
    """🚀 Lance l'interface Streamlit"""
    import subprocess
    import sys
    
    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "src/deezerboy/dashboard.py"],
            check=True
        )
    except FileNotFoundError:
        click.secho("❌ Streamlit n'est pas installé. Installez avec: uv pip install streamlit", fg='red')
    except KeyboardInterrupt:
        click.secho("\n👋 App fermée", fg='yellow')


@cli.command()
@click.option(
    '--path',
    type=click.Path(exists=True),
    default=None,
    help='Chemin du CSV (par défaut: ~/Downloads/track_list.csv)'
)
def stats(path: str | None):
    """📊 Affiche les statistiques du CSV"""
    
    csv_path = Path(path) if path else None
    df = load_csv(csv_path)
    
    if df is None:
        click.secho("❌ Aucun CSV trouvé", fg='red')
        return
    
    # Colonnes playlist
    from .api import COLUMNS_FULL
    playlist_cols = [col for col in df.columns if col not in COLUMNS_FULL and not col.startswith('artist_')]
    
    click.echo("\n" + "="*50)
    click.secho("📊 STATISTIQUES DEEZER", fg='cyan', bold=True)
    click.echo("="*50)
    click.echo(f"🎵 Chansons uniques:        {len(df):,}")
    click.echo(f"📚 Playlists:              {len(playlist_cols)}")
    click.echo(f"🎤 Artistes:               {df['artist'].nunique()}")
    click.echo(f"💿 Albums:                 {df['album'].nunique()}")
    click.echo(f"🎧 Durée totale:           {df['duration'].sum() / 3600:.0f} heures")
    click.echo(f"⏱️  Durée moyenne:         {df['duration'].mean() / 60:.0f} min")
    
    # BPM
    if 'bpm' in df.columns and (df['bpm'] > 0).sum() > 0:
        bpm_avg = df[df['bpm'] > 0]['bpm'].mean()
        click.echo(f"🎵 BPM moyen:              {bpm_avg:.0f}")
    
    click.echo("="*50 + "\n")


@cli.command()
def info():
    """ℹ️ Affiche les informations du projet"""
    click.secho("""
╔══════════════════════════════════════════════════════╗
║     🎵 DeezerBoy - Mon Univers Musical Deezer        ║
╚══════════════════════════════════════════════════════╝

📌 Commandes disponibles:

  deezerboy export      📥 Récupère et exporte vos musiques
  deezerboy app         🚀 Lance l'interface Streamlit
  deezerboy stats       📊 Affiche les statistiques
  deezerboy info        ℹ️  Affiche cette aide

📚 Exemples:

  # Exporter en CSV (il vous demande votre ID Deezer)
  deezerboy export

  # Exporter en Excel
  deezerboy export --format excel

  # Exporter dans un dossier spécifique
  deezerboy export --output ./data/

  # Afficher les statistiques
  deezerboy stats

  # Lancer l'interface Streamlit
  deezerboy app

🔑 Configuration:

  Créez un fichier .env à la racine:
  
    DEEZER_USER_ID=votre_id_utilisateur

  Trouvez votre ID sur: https://www.deezer.com/profile/VotreID

🆘 Aide supplémentaire:

  deezerboy [commande] --help

    """, fg='blue')


def main():
    """Point d'entrée principal"""
    cli()


if __name__ == '__main__':
    main()
