import logging
import os
import time
from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

from deezerboy.api import COLUMNS_FULL, add_track_to_df, fetch_tracks, search_music
from deezerboy.export import export_csv, load_csv

load_dotenv()

st.set_page_config(
    page_title="🎵 Mon Univers Musical Deezer",
    page_icon="🎵",
    layout="wide",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@st.cache_data
def load_data_cached():
    return load_csv()


def get_playlist_cols(df: pd.DataFrame) -> list[str]:
    return [
        c for c in df.columns
        if c not in COLUMNS_FULL and not c.startswith("artist_")
    ]


def format_duration(seconds: int) -> str:
    if pd.isna(seconds):
        return "N/A"
    return f"{seconds / 3600:,.1f}h"


def artist_score(
    df: pd.DataFrame,
    playlist_cols: list,
    heart_playlist: str = "Coups de cœur",
) -> pd.DataFrame:
    HEART_BONUS = 4
    if heart_playlist not in playlist_cols:
        scores = df["artist"].value_counts().reset_index()
        scores.columns = ["artist", "score"]
        return scores
    scores = (
        df.groupby("artist")
        .apply(lambda x: len(x) + x[heart_playlist].sum() * HEART_BONUS)
        .reset_index(name="score")
    )
    return scores.sort_values("score", ascending=False)


st.title("🎵 Mon Univers Musical Deezer")

with st.sidebar:
    st.header("⚙️ Configuration")
    mode = st.radio(
        "Sélectionnez:",
        ["📂 Charger CSV", "🔄 API Deezer"],
        label_visibility="collapsed",
    )
    df = None

    if mode == "📂 Charger CSV":
        uploaded_file = st.file_uploader("Charger un CSV", type="csv")
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.success("✅ Fichier chargé!")
        else:
            df = load_data_cached()
            if df is not None:
                st.success("✅ CSV trouvé!")
            else:
                st.info("📥 Chargez un CSV ou utilisez l'API")
    else:
        user_id = st.text_input(
            "ID Deezer:", value=os.getenv("DEEZER_USER_ID", "")
        )
        if st.button("🔄 Récupérer"):
            if user_id:
                progress_bar = st.progress(0)
                status_text = st.empty()
                playlist_info = st.empty()

                def progress_callback(status, current, total, playlist_name=""):
                    if status == "start":
                        playlist_info.info(f"🎵 {total} playlists trouvées")
                    elif status == "progress":
                        progress_bar.progress(int(current / total * 100))
                        status_text.info(
                            f"📥 Playlist {current}/{total}: {playlist_name}"
                        )
                    elif status == "complete":
                        progress_bar.progress(100)
                        status_text.success("✅ Récupération terminée!")

                try:
                    df = fetch_tracks(user_id, progress_callback=progress_callback)
                    status_text.info("💾 Export du CSV...")
                    export_csv(df)
                    status_text.success("✅ Données récupérées et exportées!")
                    st.session_state.df = df
                    time.sleep(1)
                    progress_bar.empty()
                    status_text.empty()
                except Exception as exc:
                    progress_bar.empty()
                    status_text.error(f"❌ Erreur: {exc}")
            else:
                st.warning("Entrez votre ID")


if df is not None:
    df = df.fillna(False)
    playlist_cols = get_playlist_cols(df)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🎵 Chansons", f"{len(df):,}")
    col2.metric("📚 Playlists", len(playlist_cols))
    col3.metric("🎧 Durée", f"{df['duration'].sum() / 3600:.0f}h")
    col4.metric(
        "🔄 Doublons",
        f"{len(df[df.duplicated(subset=['isrc'], keep=False)]) // 2:.0f}",
    )

    st.divider()

    tabs = st.tabs(
        ["📊 Stats", "🏷️ Tags", "🔗 Similar", "🎤 Artistes", "📚 Playlists", "🎵 Chansons", "➕ Ajouter", "💾 Export"]
    )

    with tabs[0]:
        st.header("📊 Statistiques Globales")

        # Row 1: Duration and Genres
        col1, col2 = st.columns(2)

        with col1:
            fig = px.histogram(
                df.assign(duration_min=df["duration"] / 60),
                x="duration_min",
                nbins=50,
                title="⏳ Distribution des durées",
                color_discrete_sequence=["#667eea"],
            )
            fig.update_layout(
                height=400, xaxis_title="Minutes", yaxis_title="Chansons"
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            genre_counts = df["genre"].dropna().value_counts().head(15)
            if not genre_counts.empty:
                fig = px.bar(
                    genre_counts,
                    title="🎸 Top Genres",
                    color_discrete_sequence=["#764ba2"],
                )
                fig.update_layout(height=400, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

        # Row 2: Additional visualizations
        col3, col4 = st.columns(2)

        with col3:
            # Top tracks by playcount (if available)
            if 'track_playcount' in df.columns and df['track_playcount'].notna().any():
                top_tracks = df.nlargest(10, 'track_playcount')[['title', 'artist', 'track_playcount']]
                fig = px.bar(
                    top_tracks,
                    x='track_playcount',
                    y='title',
                    orientation='h',
                    title="🔥 Top 10 Tracks (Playcount)",
                    color='track_playcount',
                    color_continuous_scale="Viridis"
                )
                fig.update_layout(height=400, yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
            else:
                # Alternative: Top tracks by duration
                top_duration = df.nlargest(10, 'duration')[['title', 'artist', 'duration']]
                fig = px.bar(
                    top_duration,
                    x='duration',
                    y='title',
                    orientation='h',
                    title="⏱️ Top 10 Tracks (Duration)",
                    color='duration',
                    color_continuous_scale="Plasma"
                )
                fig.update_layout(height=400, yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig, use_container_width=True)

        with col4:
            # Artist diversity pie chart
            artist_counts = df['artist'].value_counts().head(10)
            fig = px.pie(
                values=artist_counts.values,
                names=artist_counts.index,
                title="👥 Répartition des Artistes (Top 10)",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    with tabs[1]:
        st.header("🏷️ Analyse des Tags")

        if 'tags' in df.columns and df['tags'].notna().any():
            # Process tags - split by semicolon and flatten
            tags_series = df['tags'].dropna().str.split(';').explode().str.strip()
            tags_series = tags_series[tags_series != '']  # Remove empty strings

            if not tags_series.empty:
                tag_counts = tags_series.value_counts().head(20)

                col1, col2 = st.columns(2)

                with col1:
                    fig = px.bar(
                        x=tag_counts.values,
                        y=tag_counts.index,
                        orientation='h',
                        title="🏷️ Top 20 Tags",
                        labels={'x': 'Fréquence', 'y': 'Tag'},
                        color=tag_counts.values,
                        color_continuous_scale="Viridis"
                    )
                    fig.update_layout(height=500, yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    # Tag co-occurrence network (simplified - showing most common pairs)
                    # For simplicity, let's show tag distribution as a pie chart
                    fig = px.pie(
                        values=tag_counts.head(10).values,
                        names=tag_counts.head(10).index,
                        title="🥧 Distribution des Tags (Top 10)",
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    fig.update_layout(height=500)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Aucun tag trouvé dans les données")
        else:
            st.info("Colonne 'tags' non disponible (activez LASTFM_API_KEY dans .env pour récupérer les tags)")

    with tabs[2]:
        st.header("🔗 Artistes Similaires")

        if 'similar_artists' in df.columns and df['similar_artists'].notna().any():
            # Process similar artists - split by semicolon and flatten
            similar_series = df['similar_artists'].dropna().str.split(';').explode().str.strip()
            similar_series = similar_series[similar_series != '']  # Remove empty strings

            if not similar_series.empty:
                # Count occurrences of each similar artist
                similar_counts = similar_series.value_counts().head(15)

                col1, col2 = st.columns(2)

                with col1:
                    fig = px.bar(
                        x=similar_counts.values,
                        y=similar_counts.index,
                        orientation='h',
                        title="🔗 Top 15 Artistes Similaires",
                        labels={'x': 'Nombre d\'occurrences', 'y': 'Artiste similaire'},
                        color=similar_counts.values,
                        color_continuous_scale="Plasma"
                    )
                    fig.update_layout(height=500, yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)

                with col2:
                    # Show artists with most similar artist connections
                    # Get unique artists from our library that have similar artists listed
                    artists_with_similar = df[df['similar_artists'].notna()]['artist'].unique()
                    if len(artists_with_similar) > 0:
                        st.write(f"**{len(artists_with_similar)}** artistes de votre bibliothèque ont des artistes similaires listés")

                        # Show some examples
                        sample_artists = df[df['similar_artists'].notna()][['artist', 'similar_artists']].head(5)
                        for _, row in sample_artists.iterrows():
                            similar_list = [s.strip() for s in str(row['similar_artists']).split(';') if s.strip()]
                            if similar_list:
                                st.write(f"🎵 **{row['artist']}** → {', '.join(similar_list[:3])}{'...' if len(similar_list) > 3 else ''}")
                    else:
                        st.info("Aucun artiste avec des similaires trouvé")
            else:
                st.info("Aucun artiste similaire trouvé dans les données")
        else:
            st.info("Colonne 'similar_artists' non disponible (activez LASTFM_API_KEY dans .env pour récupérer les artistes similaires)")

    with tabs[1]:
        st.header("🎤 Artistes")
        top_n = st.slider("Nombre d'artistes:", 5, 50, 20)
        scores_df = artist_score(df, playlist_cols)
        top_artists = scores_df.head(top_n)

        # First row: bar chart and metrics
        col1, col2 = st.columns([2, 1])
        with col1:
            fig = px.bar(
                top_artists,
                x="score",
                y="artist",
                orientation="h",
                title=f"🏆 Top {top_n} Artistes",
                color="score",
                color_continuous_scale="Viridis",
            )
            fig.update_layout(
                height=600, yaxis={"categoryorder": "total ascending"}
            )
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.metric("Total artistes", len(scores_df))
            st.metric("Score moyen", f"{scores_df['score'].mean():.1f}")

        # Second row: additional artist insights
        st.subheader("📈 Insights supplémentaires sur les artistes")
        col3, col4 = st.columns(2)

        with col3:
            # Number of tracks per artist (top 10)
            artist_track_counts = df['artist'].value_counts().head(10)
            fig = px.bar(
                x=artist_track_counts.values,
                y=artist_track_counts.index,
                orientation='h',
                title="🎵 Nombre de pistes par artiste (Top 10)",
                labels={'x': 'Nombre de pistes', 'y': 'Artiste'},
                color=artist_track_counts.values,
                color_continuous_scale="Blues"
            )
            fig.update_layout(height=400, yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig, use_container_width=True)

        with col4:
            # Scatter plot of artist listeners vs playcount (if Last.fm data available)
            if 'artist_listeners' in df.columns and 'artist_playcount' in df.columns:
                # Filter out rows where either is null
                scatter_df = df[['artist', 'artist_listeners', 'artist_playcount']].dropna()
                if not scatter_df.empty:
                    # We need to aggregate by artist to avoid duplicate points
                    artist_stats = scatter_df.groupby('artist').agg({
                        'artist_listeners': 'mean',
                        'artist_playcount': 'mean'
                    }).reset_index()
                    fig = px.scatter(
                        artist_stats,
                        x='artist_listeners',
                        y='artist_playcount',
                        size='artist_playcount',
                        hover_name='artist',
                        title="👥 Auditeurs vs Écoutes des artistes",
                        labels={
                            'artist_listeners': 'Auditeurs uniques (Last.fm)',
                            'artist_playcount': 'Écoutes totales (Last.fm)'
                        },
                        color_continuous_scale="Viridis"
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Données Last.fm insuffisantes pour le graphique de dispersion")
            else:
                st.info("Données Last.fm non disponibles (activez LASTFM_API_KEY dans .env)")

    with tabs[2]:
        st.header("📚 Playlists")
        playlist_df = pd.DataFrame(
            [(p, df[df[p]].shape[0]) for p in playlist_cols],
            columns=["Playlist", "Chansons"],
        )
        fig = px.bar(
            playlist_df.sort_values("Chansons", ascending=True),
            y="Playlist",
            x="Chansons",
            orientation="h",
            title="Taille des Playlists",
            color="Chansons",
            color_continuous_scale="Blues",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        st.header("🎵 Catalogue")
        col1, col2 = st.columns(2)
        with col1:
            artist_filter = st.multiselect(
                "Artiste:", df["artist"].unique()[:100]
            )
        with col2:
            sort_by = st.selectbox("Trier par:", ["Titre", "Artiste", "Durée"])

        df_filtered = df.copy()
        if artist_filter:
            df_filtered = df_filtered[df_filtered["artist"].isin(artist_filter)]

        sort_map = {"Titre": "title", "Artiste": "artist", "Durée": "duration"}
        df_filtered = df_filtered.sort_values(sort_map[sort_by])
        st.dataframe(
            df_filtered[["title", "artist", "album", "duration"]],
            use_container_width=True,
            hide_index=True,
        )

    with tabs[4]:
        st.header("🔍 Ajouter de la Musique")
        col1, col2 = st.columns([3, 1])
        with col1:
            search_query = st.text_input(
                "🔎 Rechercher une chanson",
                placeholder="Ex: Blinding Lights The Weeknd",
            )
        with col2:
            search_button = st.button("🔍 Chercher")

        if search_button and search_query:
            with st.spinner("Recherche en cours..."):
                results = search_music(search_query, limit=10)

            if results:
                st.success(f"✅ {len(results)} résultats trouvés")
                for idx, track in enumerate(results):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"**{track['title']}** - {track['artist']}")
                        st.caption(
                            f"Album: {track['album']} | Durée: {track['duration']}s"
                        )
                    with col2:
                        key = f"add_{idx}_{track['id']}"
                        if st.button("➕ Ajouter", key=key):
                            try:
                                df_updated = add_track_to_df(
                                    df, track["id"], full_version=True
                                )
                                st.session_state.df = df_updated
                                new = df_updated[
                                    df_updated["id"] == track["id"]
                                ].iloc[0]
                                st.success(
                                    f"✅ {track['title']} ajouté! "
                                    f"Genre: **{new.get('genre', 'N/A')}**"
                                )
                            except Exception as exc:
                                st.error(f"❌ Erreur: {exc}")
                    with col3:
                        if track.get("preview"):
                            st.audio(
                                track["preview"],
                                format="audio/mp3",
                                key=f"preview_{idx}",
                            )
            else:
                st.warning("❌ Aucun résultat trouvé")

    with tabs[5]:
        st.header("💾 Export")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 CSV",
                df.to_csv(index=False),
                f"deezer_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
            )
        with col2:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Tracks")
            buf.seek(0)
            st.download_button(
                "📥 Excel",
                buf,
                f"deezer_{datetime.now().strftime('%Y%m%d')}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

else:
    st.warning("⚠️ Chargez un CSV ou récupérez depuis l'API")
