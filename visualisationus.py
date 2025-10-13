import pandas as pd
import os
from pathlib import Path
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import plotly.express as px
import logging

from deezerus import get_track_list, COLUMNS_FULL

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
THEME = dbc.themes.CYBORG
PLOTLY_TEMPLATE = "plotly_dark"


def load_data():
    filename = "track_list.csv"
    local_path = filename
    downloads_path = Path.home() / "Downloads" / filename

    if os.path.exists(local_path):
        logging.info(f"File found in local directory: '{os.path.abspath(local_path)}'")
        return pd.read_csv(local_path)
    elif os.path.exists(downloads_path):
        logging.info(f"File found in Downloads folder: '{downloads_path}'")
        return pd.read_csv(downloads_path)
    else:
        logging.warning("CSV file not found. Fetching data from the API...")
        df_from_api = get_track_list(
            user_id=os.getenv("DEEZER_USER_ID"), full_version=True
        )
        df_from_api.to_csv(Path.home() / "Downloads" / "track_list.csv", index=False)
        logging.info(
            f"Data fetched and saved to '{Path.home() / 'Downloads' / 'track_list.csv'}'."
        )
        return df_from_api


def format_duration(seconds: int) -> str:
    hours = seconds / 3600
    return f"{hours:,.1f} hours"


def artist_score(
    df: pd.DataFrame,
    playlist_cols: list,
    heart_playlist: str = "Coups de cœur",
) -> pd.DataFrame:
    HEART_BONUS = 4
    if heart_playlist not in playlist_cols:
        logging.warning(
            f"'{heart_playlist}' playlist not found. Using simple count for artist scores."
        )
        artist_scores = df["artist"].value_counts().reset_index()
        artist_scores.columns = ["artist", "score"]
        return artist_scores

    artist_scores = (
        df.groupby("artist")
        .apply(lambda x: len(x) + (x[heart_playlist].sum() * HEART_BONUS))
        .reset_index(name="score")
    )
    return artist_scores.sort_values("score", ascending=False)


def calculate_playlist_similarity(df, playlist_cols):
    """Calcule la similarité entre les playlists en utilisant l'indice de Jaccard."""
    similarity_matrix = pd.DataFrame(
        index=playlist_cols, columns=playlist_cols, dtype=float
    )
    for p1 in playlist_cols:
        for p2 in playlist_cols:
            if p1 == p2:
                similarity_matrix.loc[p1, p2] = 1.0
                continue
            set1 = set(df[df[p1] == True].index)
            set2 = set(df[df[p2] == True].index)
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            similarity_matrix.loc[p1, p2] = intersection / union if union > 0 else 0.0
    return similarity_matrix


df = load_data()
df.fillna({col: False for col in df.columns if df[col].dtype == "bool"}, inplace=True)
playlist_cols = [
    col
    for col in df.columns
    if col not in COLUMNS_FULL and not col.startswith("artist_")
]

total_tracks = len(df)
total_playlists = len(playlist_cols)
total_listening_time = format_duration(df["duration"].sum())
duplicate_track_list = df[df.duplicated(subset=playlist_cols, keep=False)].sort_values(
    by="artist"
)
duplicate_tracks = len(duplicate_track_list)/2
artist_scores_df = artist_score(
    df, playlist_cols, heart_playlist="Coups de cœur"
)
top_20_artists = artist_scores_df.head(20)
similarity_df = calculate_playlist_similarity(df, playlist_cols)
pairs = similarity_df.unstack().reset_index()
pairs.columns = ["Playlist_A", "Playlist_B", "similarite"]
pairs = pairs[pairs["Playlist_A"] != pairs["Playlist_B"]]
pairs["pair_key"] = pairs.apply(
    lambda row: tuple(sorted((row["Playlist_A"], row["Playlist_B"]))), axis=1
)
pairs = pairs.drop_duplicates(subset=["pair_key"]).drop(columns=["pair_key"])
top_10_similar_playlists = pairs.sort_values("similarite", ascending=False).head(10)
top_10_similar_playlists["pair_label"] = (
    top_10_similar_playlists["Playlist_A"]
    + " & "
    + top_10_similar_playlists["Playlist_B"]
)

df["duration_min"] = df["duration"] / 60


# --- 4. CREATING PLOTLY FIGURES ---
fig_top_artists = px.bar(
    top_20_artists,
    x="score",
    y="artist",
    orientation="h",
    title="🏆 My Top 20 Artists (by Score)",
    template=PLOTLY_TEMPLATE,
).update_layout(yaxis={"categoryorder": "total ascending"})

fig_top_10_similar = px.bar(
    top_10_similar_playlists,
    x="similarite",
    y="pair_label",
    orientation="h",
    title="🤝 Top 10 des paires de playlists les plus proches",
    text="similarite",
    template=PLOTLY_TEMPLATE,
)
fig_top_10_similar.update_traces(texttemplate="%{text:.2f}", textposition="outside")
fig_top_10_similar.update_layout(
    yaxis_title="",
    xaxis_title="Indice de Similarité (Jaccard)",
    yaxis={"categoryorder": "total ascending"},
)


fig_duration = px.histogram(
    df,
    x="duration_min",
    nbins=100,
    title="⏳ Track Duration Distribution (minutes)",
    template=PLOTLY_TEMPLATE,
)

app = dash.Dash(__name__, external_stylesheets=[THEME])
kpi_card_style = "text-center m-2"

app.layout = dbc.Container(
    [
        dbc.Row(
            dbc.Col(html.H1("Mon Univers Musical Deezer", className="text-center my-4"))
        ),
        dbc.Row(
            [
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H3("🎵"),
                                html.H4(f"{total_tracks:,}"),
                                html.P("Morceaux Uniques"),
                            ]
                        ),
                        className=kpi_card_style,
                    )
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H3("📚"),
                                html.H4(total_playlists),
                                html.P("Playlists"),
                            ]
                        ),
                        className=kpi_card_style,
                    )
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H3("🎧"),
                                html.H4(total_listening_time),
                                html.P("Temps d'écoute total"),
                            ]
                        ),
                        className=kpi_card_style,
                    )
                ),
                dbc.Col(
                    dbc.Card(
                        dbc.CardBody(
                            [
                                html.H3("🔄"),
                                html.H4(f"{duplicate_tracks:,}"),
                                html.P("Morceaux en commun"),
                            ]
                        ),
                        className=kpi_card_style,
                    )
                ),
            ],
            className="justify-content-center mb-4",
        ),
        # ON REMPLACE L'ANCIEN GRAPHIQUE PAR LE NOUVEAU
        dbc.Row(
            [
                dbc.Col(dcc.Graph(figure=fig_top_10_similar), width=12, lg=6),
                dbc.Col(dcc.Graph(figure=fig_top_artists), width=12, lg=6),
            ],
            className="mb-4",
        ),
        dbc.Row([dbc.Col(dcc.Graph(figure=fig_duration), width=12)]),
    ],
    fluid=True,
)


# --- 5. RUN THE SERVER (unchanged) ---
def run_server():
    app.run(debug=True, port=8050, jupyter_mode="external")
