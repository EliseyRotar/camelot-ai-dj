import time
import numpy as np
import soundfile as sf
import os
from analyzer import analyze_track
from library import add_track, get_track_features

def create_dummy_audio(filepath: str, duration_sec: int = 10, sr: int = 22050):
    print(f"Generating {duration_sec}s sine wave test file...")
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    # A simple 440Hz sine wave (A4 note)
    y = 0.5 * np.sin(2 * np.pi * 440 * t)
    # Add a pseudo-beat every 0.5 seconds
    beat_indices = np.arange(0, len(y), int(sr * 0.5))
    y[beat_indices] = 1.0
    sf.write(filepath, y, sr)
    print(f"Saved to {filepath}")

def main():
    test_file = "test_audio.wav"
    try:
        create_dummy_audio(test_file)
        
        print("\nStarting extraction...")
        start_time = time.time()
        result = analyze_track(test_file)
        end_time = time.time()
        
        print(f"\nExtraction completed in {end_time - start_time:.2f} seconds.")
        print("Metadata extracted:")
        for k, v in result['metadata'].items():
            print(f"  {k}: {v}")
            
        print("\nFeatures extracted (shapes):")
        for k, v in result['features'].items():
            if v is not None:
                print(f"  {k}: {v.shape}")
                
        print("\nTesting SQLite serialization...")
        add_track(result['metadata'], result['features'])
        print("Track added to database successfully.")
        
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"\nCleaned up {test_file}")

if __name__ == "__main__":
    main()
