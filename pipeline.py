import re
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy
import pandas as pd
import matplotlib.pyplot as plt
import mysql.connector
import os

# --- Configuration ---
SPOTIPY_CLIENT_ID = '83b6c48820634873be33d64e092ace6f3' # Replace with your Client ID
SPOTIPY_CLIENT_SECRET = '32de2b3defbe4ce7addf19d33d558a49' # Replace with your Client Secret

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', 'root'),
    'database': os.getenv('MYSQL_DATABASE', 'spotify_db')
}

TRACK_URLS_FILE = 'track_urls.txt'

# --- Spotify API Setup ---
def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=SPOTIPY_CLIENT_ID,
        client_secret=SPOTIPY_CLIENT_SECRET
    ))

# --- Database Setup ---
def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def create_database_and_table():
    conn = None
    cursor = None
    try:
        # Connect without specifying a database to create it
        temp_db_config = DB_CONFIG.copy()
        db_name = temp_db_config.pop('database')
        conn = mysql.connector.connect(**temp_db_config)
        cursor = conn.cursor()

        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"Database '{db_name}' ensured to exist.")
        cursor.close()
        conn.close()

        # Reconnect with the database specified
        conn = get_db_connection()
        cursor = conn.cursor()

        create_table_query = """
        CREATE TABLE IF NOT EXISTS spotify_tracks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            track_name VARCHAR(255),
            artist VARCHAR(255),
            album VARCHAR(255),
            popularity INT,
            duration_minutes FLOAT
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        print("Table 'spotify_tracks' ensured to exist.")
    except mysql.connector.Error as err:
        print(f"Error setting up database/table: {err}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# --- Data Ingestion ---
def ingest_spotify_data(sp_client, track_urls_file):
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        with open(track_urls_file, 'r') as file:
            track_urls = file.readlines()

        for track_url in track_urls:
            track_url = track_url.strip()
            if not track_url:
                continue

            try:
                track_id_match = re.search(r'track/([a-zA-Z0-9]+)', track_url)
                if not track_id_match:
                    print(f"Skipping invalid URL format: {track_url}")
                    continue
                track_id = track_id_match.group(1)

                track = sp_client.track(track_id)

                track_data = {
                    'Track Name': track['name'],
                    'Artist': track['artists'][0]['name'],
                    'Album': track['album']['name'],
                    'Popularity': track['popularity'],
                    'Duration (minutes)': track['duration_ms'] / 60000
                }

                insert_query = """
                INSERT INTO spotify_tracks (track_name, artist, album, popularity, duration_minutes)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    track_name = VALUES(track_name),
                    artist = VALUES(artist),
                    album = VALUES(album),
                    popularity = VALUES(popularity),
                    duration_minutes = VALUES(duration_minutes)
                """
                cursor.execute(insert_query, (
                    track_data['Track Name'],
                    track_data['Artist'],
                    track_data['Album'],
                    track_data['Popularity'],
                    track_data['Duration (minutes)']
                ))
                connection.commit()
                print(f"Inserted/Updated: {track_data['Track Name']} by {track_data['Artist']}")

            except Exception as e:
                print(f"Error processing URL: {track_url}, Error: {e}")

    except mysql.connector.Error as err:
        print(f"Database error during ingestion: {err}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    print("Data ingestion complete.")

# --- Data Analysis and Visualization ---
def analyze_and_visualize_data():
    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True) # Return rows as dictionaries

        # Fetch all data for analysis
        cursor.execute("SELECT * FROM spotify_tracks")
        tracks_data = cursor.fetchall()
        if not tracks_data:
            print("No data found in 'spotify_tracks' for analysis.")
            return

        df = pd.DataFrame(tracks_data)
        print("\n--- Data Analysis ---")
        print(df.head())

        # 1. Top 5 Most Popular Tracks
        print("\nTop 5 Most Popular Tracks:")
        top_popular = df.sort_values(by='popularity', ascending=False).head(5)
        print(top_popular[['track_name', 'artist', 'popularity']])

        # 2. Average Popularity
        avg_popularity = df['popularity'].mean()
        print(f"\nAverage Popularity of Tracks: {avg_popularity:.2f}")

        # 3. Distribution of Popularity
        plt.figure(figsize=(10, 6))
        df['popularity'].hist(bins=10, edgecolor='black')
        plt.title('Distribution of Track Popularity')
        plt.xlabel('Popularity Score')
        plt.ylabel('Number of Tracks')
        plt.grid(axis='y', alpha=0.75)
        plt.show()

        # 4. Track Duration vs. Popularity (Scatter Plot)
        plt.figure(figsize=(10, 6))
        plt.scatter(df['duration_minutes'], df['popularity'], alpha=0.7)
        plt.title('Track Duration vs. Popularity')
        plt.xlabel('Duration (minutes)')
        plt.ylabel('Popularity')
        plt.grid(True)
        plt.show()

    except mysql.connector.Error as err:
        print(f"Database error during analysis: {err}")
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
    print("Data analysis and visualization complete.")

# --- Main Pipeline Execution ---
if __name__ == "__main__":
    print("Starting Spotify Data Pipeline...")

    # 1. Ensure database and table exist
    create_database_and_table()

    # 2. Get Spotify Client
    sp = get_spotify_client()

    # 3. Ingest data
    ingest_spotify_data(sp, TRACK_URLS_FILE)

    # 4. Analyze and visualize data
    analyze_and_visualize_data()

    print("Spotify Data Pipeline finished.")
