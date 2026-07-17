import time
import numpy as np
import soundfile as sf
import os
from mixing_engine import engine, MASTER_SR

def create_dummy_audio(filepath: str, freq: float, duration_sec: int = 5, bpm: float = 120.0):
    print(f"Generating {duration_sec}s sine wave test file ({freq}Hz)...")
    t = np.linspace(0, duration_sec, int(MASTER_SR * duration_sec), endpoint=False)
    y = 0.5 * np.sin(2 * np.pi * freq * t)
    
    # Add beat clicks
    beat_interval = 60.0 / bpm
    beat_indices = np.arange(0, len(y), int(MASTER_SR * beat_interval))
    y[beat_indices] = 1.0
    
    sf.write(filepath, y, MASTER_SR)
    print(f"Saved to {filepath}")
    return filepath

def main():
    file_a = "test_deck_a.wav"
    file_b = "test_deck_b.wav"
    
    try:
        create_dummy_audio(file_a, 440.0, duration_sec=5, bpm=120.0)
        create_dummy_audio(file_b, 880.0, duration_sec=5, bpm=125.0)
        
        # Start stream
        engine.start_stream()
        
        # Load tracks (Mocking the SQLite track_id as 0 for fallback)
        print("\nLoading Deck A...")
        engine.deck_a.load_track(file_a, track_id=0, original_bpm=120.0, original_lufs=-20.0, target_bpm=120.0)
        
        print("\nLoading Deck B (stretching 125 -> 120 BPM)...")
        engine.deck_b.load_track(file_b, track_id=0, original_bpm=125.0, original_lufs=-20.0, target_bpm=120.0)
        
        print("\nFiring Deck A...")
        engine.deck_a.fire_on_beat(0.0)
        
        time.sleep(2)
        
        print("\nFiring Deck B (Crossfading)...")
        # Lower Deck A's High EQ and raise Deck B
        engine.deck_a.eq_high = 0.1
        engine.deck_b.fire_on_beat(0.0)
        
        time.sleep(3)
        
    except Exception as e:
        print(f"Test failed: {e}")
    finally:
        engine.stop_stream()
        if os.path.exists(file_a): os.remove(file_a)
        if os.path.exists(file_b): os.remove(file_b)
        print("Cleaned up test files.")

if __name__ == "__main__":
    main()
