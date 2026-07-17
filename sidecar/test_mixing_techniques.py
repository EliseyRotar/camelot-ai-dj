import time
import numpy as np
from mixing_engine import engine, MASTER_SR, BLOCK_SIZE
from techniques import BassSwap

def main():
    print("Initializing test for Bass Swap transition...")
    
    # Mock some data for the decks
    # Deck A is currently active
    engine.deck_a.is_playing = True
    engine.deck_a.audio = np.ones(MASTER_SR * 10, dtype=np.float32) # 10 seconds of DC audio
    
    engine.deck_b.is_playing = True
    engine.deck_b.audio = np.ones(MASTER_SR * 10, dtype=np.float32)
    
    # 1 bar at 120 BPM = 4 beats = 2 seconds = 44100 samples
    duration_samples = int(MASTER_SR * 2.0)
    
    bass_swap = BassSwap(duration_samples=duration_samples)
    engine.trigger_transition(bass_swap)
    
    outdata = np.zeros((BLOCK_SIZE, 1), dtype=np.float32)
    time_info = None
    status = None
    
    # Tick 1: Immediate bass swap
    engine.audio_callback(outdata, BLOCK_SIZE, time_info, status)
    print(f"Tick 1 (Start) - Deck A (Out) Low EQ: {engine.deck_a.eq_low}")
    print(f"Tick 1 (Start) - Deck B (In) Low EQ: {engine.deck_b.eq_low}")
    print(f"Tick 1 (Start) - Deck A Mid EQ: {engine.deck_a.eq_mid}")
    
    assert engine.deck_a.eq_low == 0.0, "Deck A Low EQ did not instantly cut!"
    assert engine.deck_b.eq_low == 1.0, "Deck B Low EQ did not instantly boost!"
    
    # Tick loop until halfway (1 second / 22050 samples)
    ticks_to_half = (MASTER_SR * 1) // BLOCK_SIZE
    for _ in range(ticks_to_half):
        engine.audio_callback(outdata, BLOCK_SIZE, time_info, status)
        
    print(f"Tick {ticks_to_half} (Halfway) - Deck A Mid EQ: {engine.deck_a.eq_mid:.2f}")
    print(f"Tick {ticks_to_half} (Halfway) - Deck B Mid EQ: {engine.deck_b.eq_mid:.2f}")
    
    assert abs(engine.deck_a.eq_mid - 0.5) < 0.1, "Mid EQ did not crossfade correctly!"
    
    # Finish transition
    while engine.transition_manager.active_technique is not None:
        engine.audio_callback(outdata, BLOCK_SIZE, time_info, status)
        
    print("Transition Finished!")
    print(f"Final - Active Deck is now: {engine.active_deck}")
    
    assert engine.active_deck == 'B', "Active deck did not swap to B!"
    
    print("\nAll BassSwap assertions passed!")

if __name__ == "__main__":
    main()
