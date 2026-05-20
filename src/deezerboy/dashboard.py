import logging
import os
import time
from datetime import datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
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
        ["📊 Stats", "🎤 Artistes", "📚 Playlists", "🎵 Chansons", "➕ Ajouter", "💾 Export"]
    )

    with tabs[0]:
        st.header("📊 Statistiques Globales")
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

    with tabs[1]:
        st.header("🎤 Artistes")
        top_n = st.slider("Nombre d'artistes:", 5, 50, 20)
        scores_df = artist_score(df, playlist_cols)
        top_artists = scores_df.head(top_n)

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
