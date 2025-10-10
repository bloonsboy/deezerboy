import pandas as pd
import os
from pathlib import Path
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import plotly.express as px
from wordcloud import WordCloud
import io
import base64
import logging

from deezerus import get_track_list

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
THEME = dbc.themes.CYBORG
PLOTLY_TEMPLATE = "plotly_dark"

def load_data():
    filename = 'track_list.csv'
    local_path = filename
    downloads_path = Path.home() / 'Downloads' / filename

    if os.path.exists(local_path):
        logging.info(f"File found in local directory: '{os.path.abspath(local_path)}'")
        return pd.read_csv(local_path)
    elif os.path.exists(downloads_path):
        logging.info(f"File found in Downloads folder: '{downloads_path}'")
        return pd.read_csv(downloads_path)
    else:
        logging.warning("CSV file not found. Fetching data from the API...")
        df_from_api = get_track_list(user_id=os.getenv("DEEZER_USER_ID"), full_version=True)
        df_from_api.to_csv(Path.home() / "Downloads" / "track_list.csv", index=False)
        logging.info(f"Data fetched and saved to '{Path.home() / 'Downloads' / 'track_list.csv'}'.")
        return df_from_api

def format_duration(seconds):
    hours = seconds / 3600
    return f"{hours:,.1f} hours"

def calculate_artist_score(df, playlist_cols, heart_playlist='Coups de cœur'):
    """
    Calculates a "preference" score for each artist.
    Score = (Total number of tracks) + (Bonus for each track in the 'Coups de cœur' playlist)
    """
    HEART_BONUS = 15  # Increase to give more weight to favorites

    # Check if the "Coups de cœur" playlist exists
    if heart_playlist not in playlist_cols:
        print(f"⚠️ Playlist '{heart_playlist}' not found. Score will be based solely on track count.")
        # Simple count if the playlist does not exist
        artist_scores = df['artist'].value_counts().reset_index()
        artist_scores.columns = ['artist', 'score']
        return artist_scores

    # Score calculation
    artist_scores = df.groupby('artist').apply(
        lambda x: len(x) + (x[heart_playlist].sum() * HEART_BONUS)
    ).reset_index(name='score')
    
    return artist_scores.sort_values('score', ascending=False)

def calculate_playlist_similarity(df, playlist_cols):
    """
    Calculates the similarity between playlists using the Jaccard index.
    Jaccard(A, B) = |A ∩ B| / |A ∪ B|
    """
    similarity_matrix = pd.DataFrame(index=playlist_cols, columns=playlist_cols, dtype=float)
    
    for p1 in playlist_cols:
        for p2 in playlist_cols:
            if p1 == p2:
                similarity_matrix.loc[p1, p2] = 1.0
                continue
            
            set1 = set(df[df[p1] == True].index)
            set2 = set(df[df[p2] == True].index)
            
            intersection = len(set1.intersection(set2))
            union = len(set1.union(set2))
            
            if union == 0:
                similarity_matrix.loc[p1, p2] = 0.0
            else:
                similarity_matrix.loc[p1, p2] = intersection / union
                
    return similarity_matrix

# --- 1. DATA LOADING AND PREPARATION ---
df = load_data()
df.fillna({col: False for col in df.columns if df[col].dtype == 'bool'}, inplace=True)

# Identify playlist columns
base_cols = ["id", "title", "artist", "album", "duration", "rank", "isrc", "release_date", "bpm", "gain"]
playlist_cols = [col for col in df.columns if col not in base_cols and not col.startswith('artist_')]

# --- 2. CALCULATING KPIs (Key Performance Indicators) ---
total_tracks = len(df)
total_playlists = len(playlist_cols)
total_listening_time = format_duration(df['duration'].sum())
# A "duplicate" is a track present in more than one playlist
df['playlist_count'] = df[playlist_cols].sum(axis=1)
duplicate_tracks = (df['playlist_count'] > 1).sum()

# --- 3. PREPARING DATA FOR PLOTS ---
# Artist scores
# Important: Change 'Coups de cœur' to the exact name of your favorites playlist if it's different.
artist_scores_df = calculate_artist_score(df, playlist_cols, heart_playlist='Coups de cœur')
top_20_artists = artist_scores_df.head(20)

# Playlist similarity
similarity_df = calculate_playlist_similarity(df, playlist_cols)

# Duration distribution
df['duration_min'] = df['duration'] / 60

# --- 4. CREATING PLOTLY FIGURES ---
fig_top_artists = px.bar(
    top_20_artists,
    x='score',
    y='artist',
    orientation='h',
    title="🏆 My Top 20 Artists (by Score)",
    template=PLOTLY_TEMPLATE
).update_layout(yaxis={'categoryorder':'total ascending'})

fig_similarity = px.imshow(
    similarity_df,
    text_auto=".2f",
    title="🤝 Playlist Similarity (Jaccard Index)",
    color_continuous_scale='Blues',
    template=PLOTLY_TEMPLATE
)

fig_duration = px.histogram(
    df,
    x="duration_min",
    nbins=50,
    title="⏳ Track Duration Distribution (minutes)",
    template=PLOTLY_TEMPLATE
)

# --- 5. DASH APP LAYOUT ---
app = dash.Dash(__name__, external_stylesheets=[THEME])

kpi_card_style = "text-center m-2"

app.layout = dbc.Container([
    # Title
    dbc.Row(
        dbc.Col(html.H1("My Deezer Music Universe", className="text-center my-4"), width=12)
    ),
    
    # KPIs
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([html.H3("🎵"), html.H4(f"{total_tracks:,}"), html.P("Unique Tracks")]), className=kpi_card_style)),
        dbc.Col(dbc.Card(dbc.CardBody([html.H3("📚"), html.H4(total_playlists), html.P("Playlists")]), className=kpi_card_style)),
        dbc.Col(dbc.Card(dbc.CardBody([html.H3("🎧"), html.H4(total_listening_time), html.P("Total Listening Time")]), className=kpi_card_style)),
        dbc.Col(dbc.Card(dbc.CardBody([html.H3("🔄"), html.H4(f"{duplicate_tracks:,}"), html.P("Shared Tracks")]), className=kpi_card_style)),
    ], className="justify-content-center mb-4"),
    
    # Main plots
    dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_similarity), width=12, lg=6),
        dbc.Col(dcc.Graph(figure=fig_top_artists), width=12, lg=6),
    ], className="mb-4"),
    
    # Secondary plot
    dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_duration), width=12),
    ]),
    
], fluid=True)


# --- 5. RUN THE SERVER (unchanged) ---
def run_server():
    app.run(debug=True, port=8050, jupyter_mode="external")