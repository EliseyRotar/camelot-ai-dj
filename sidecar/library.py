import sqlite3
import os
import numpy as np

DB_PATH = os.path.join(os.path.dirname(__file__), "camelot.sqlite")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Tracks metadata table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            title TEXT,
            artist TEXT,
            duration REAL,
            bpm REAL,
            key_camelot TEXT,
            lufs_integrated REAL,
            filesize INTEGER,
            file_mtime REAL
        )
    """)

    # Migrate: add filesize/file_mtime columns if missing (existing DBs)
    cols = [r[1] for r in cursor.execute("PRAGMA table_info(tracks)").fetchall()]
    if 'filesize' not in cols:
        cursor.execute("ALTER TABLE tracks ADD COLUMN filesize INTEGER")
    if 'file_mtime' not in cols:
        cursor.execute("ALTER TABLE tracks ADD COLUMN file_mtime REAL")

    # Track features table for heavy BLOBs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS track_features (
            track_id INTEGER PRIMARY KEY,
            beat_grid_blob BLOB,
            energy_curve_blob BLOB,
            vocal_curve_blob BLOB,
            FOREIGN KEY (track_id) REFERENCES tracks(id)
        )
    """)

    conn.commit()
    conn.close()

def get_track_by_filepath(filepath: str):
    """Returns the existing track row for a filepath, or None."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tracks WHERE filepath = ?", (filepath,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def has_features(track_id: int) -> bool:
    """Returns True if the track_features row exists and has a beat_grid_blob."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT beat_grid_blob FROM track_features WHERE track_id = ?", (track_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None and row['beat_grid_blob'] is not None

def add_track(metadata, features):
    """
    metadata: dict containing filepath, title, artist, duration, bpm, key_camelot, lufs_integrated,
              filesize (optional int), file_mtime (optional float)
    features: dict containing beat_grid (np.array), energy_curve (np.array), vocal_curve (np.array)
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR REPLACE INTO tracks (filepath, title, artist, duration, bpm, key_camelot, lufs_integrated, filesize, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metadata['filepath'], metadata.get('title', ''), metadata.get('artist', ''),
            metadata['duration'], metadata['bpm'], metadata['key_camelot'], metadata['lufs_integrated'],
            metadata.get('filesize'), metadata.get('file_mtime')
        ))

        track_id = cursor.lastrowid
        if not track_id:
            cursor.execute("SELECT id FROM tracks WHERE filepath = ?", (metadata['filepath'],))
            track_id = cursor.fetchone()['id']

        beat_grid_blob = features['beat_grid'].astype(np.float32).tobytes() if features.get('beat_grid') is not None else None
        energy_curve_blob = features['energy_curve'].astype(np.float32).tobytes() if features.get('energy_curve') is not None else None
        vocal_curve_blob = features['vocal_curve'].astype(np.float32).tobytes() if features.get('vocal_curve') is not None else None

        cursor.execute("""
            INSERT OR REPLACE INTO track_features (track_id, beat_grid_blob, energy_curve_blob, vocal_curve_blob)
            VALUES (?, ?, ?, ?)
        """, (track_id, beat_grid_blob, energy_curve_blob, vocal_curve_blob))

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error adding track {metadata['filepath']}: {e}")
    finally:
        conn.close()

def get_track_features(track_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM track_features WHERE track_id = ?", (track_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        'beat_grid': np.frombuffer(row['beat_grid_blob'], dtype=np.float32) if row['beat_grid_blob'] else None,
        'energy_curve': np.frombuffer(row['energy_curve_blob'], dtype=np.float32) if row['energy_curve_blob'] else None,
        'vocal_curve': np.frombuffer(row['vocal_curve_blob'], dtype=np.float32) if row['vocal_curve_blob'] else None
    }

# Initialize on load
init_db()

