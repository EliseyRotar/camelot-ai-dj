import numpy as np
import os
from library import init_db, add_track, get_db
from autopilot import get_recommendations

def create_mock_track(idx: int, bpm: float, key: str, energy_level: float, vocal_level: float):
    metadata = {
        'filepath': f"mock_track_{idx}.wav",
        'title': f"Track {idx}",
        'artist': f"Artist {idx}",
        'duration': 180.0,
        'bpm': bpm,
        'key_camelot': key,
        'lufs_integrated': -14.0
    }
    
    # 20 chunks of features
    features = {
        'beat_grid': np.linspace(0, 180, 360, dtype=np.float32),
        'energy_curve': np.full(20, energy_level, dtype=np.float32),
        'vocal_curve': np.full(20, vocal_level, dtype=np.float32)
    }
    
    return metadata, features

def main():
    print("Initializing test database...")
    init_db()
    
    # Track 1: Currently Playing (120 BPM, 8A, Medium Energy, Low Vocals)
    m1, f1 = create_mock_track(1, 120.0, '8A', 0.5, 0.1)
    
    # Track 2: Perfect Harmonic Match, same BPM, higher energy (Best choice)
    m2, f2 = create_mock_track(2, 120.0, '8B', 0.8, 0.1)
    
    # Track 3: Perfect Harmonic Match, huge BPM delta (Bad choice)
    m3, f3 = create_mock_track(3, 140.0, '8A', 0.5, 0.1)
    
    # Track 4: Bad Harmonic Match, same BPM
    m4, f4 = create_mock_track(4, 120.0, '2B', 0.5, 0.1)
    
    # Track 5: Good Harmonic Match, same BPM, but CLASHING VOCALS (Vocal Penalty)
    m5, f5 = create_mock_track(5, 120.0, '9A', 0.5, 0.9) # 9A is +1 step from 8A
    # Note: To trigger vocal penalty, current track must also have high vocals. 
    # Let's make track 1 have high vocals at the end
    f1['vocal_curve'][-5:] = 0.9
    
    tracks = [(m1, f1), (m2, f2), (m3, f3), (m4, f4), (m5, f5)]
    
    for m, f in tracks:
        add_track(m, f)
        
    # Get ID of track 1
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tracks WHERE filepath = 'mock_track_1.wav'")
    t1_id = cursor.fetchone()['id']
    conn.close()
    
    print("\nGetting Recommendations for Track 1 (120BPM, 8A, High ending vocals)...")
    recs = get_recommendations(t1_id, lookahead_depth=1)
    
    for rank, rec in enumerate(recs):
        t = rec['track']
        print(f"{rank+1}. {t['title']} | Score: {rec['score']:.1f} | Key: {t['key_camelot']} | BPM: {t['bpm']}")
        
    # Cleanup DB
    os.remove("camelot.sqlite")
    print("\nDatabase cleaned up.")

if __name__ == "__main__":
    main()
