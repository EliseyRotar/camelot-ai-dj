import numpy as np
import re
from typing import List, Dict, Any
from library import get_db, get_track_features

def get_camelot_distance(key1: str, key2: str) -> int:
    """Calculates step distance on the Camelot Wheel. Returns 0, 1, 2, etc."""
    if not key1 or not key2: return 12
    
    # Extract numeric values (1-12)
    num1 = int(re.search(r'\d+', key1).group())
    num2 = int(re.search(r'\d+', key2).group())
    
    is_minor1 = key1.endswith('A')
    is_minor2 = key2.endswith('A')
    
    # Distance around the circle (0 to 6)
    circle_dist = min(abs(num1 - num2), 12 - abs(num1 - num2))
    
    # Cost for switching major/minor
    mode_switch_cost = 1 if is_minor1 != is_minor2 else 0
    
    # Standard harmonic mixing allows: same key (0), +1/-1 step (1), or relative major/minor (1 mode cost)
    return circle_dist + mode_switch_cost

def score_track(current_track: Dict[str, Any], candidate_track: Dict[str, Any], current_features: Dict[str, Any], candidate_features: Dict[str, Any]) -> float:
    # 1. Harmonic Compatibility (Max 100 points)
    cam_dist = get_camelot_distance(current_track['key_camelot'], candidate_track['key_camelot'])
    harmonic_score = max(0, 100 - (cam_dist * 30))
    
    # 2. BPM Delta (Max 100 points)
    bpm_delta = abs(current_track['bpm'] - candidate_track['bpm'])
    bpm_score = max(0, 100 - (bpm_delta * 5)) # lose 5 points per BPM difference
    
    # 3. Energy Trajectory (Max 100 points)
    # We want to match or slightly increase energy.
    energy_score = 50 # Base score
    if current_features and candidate_features:
        curr_energy = float(np.mean(current_features['energy_curve'][-10:])) if len(current_features['energy_curve']) >= 10 else (float(np.mean(current_features['energy_curve'])) if len(current_features['energy_curve']) > 0 else 0)
        cand_energy = float(np.mean(candidate_features['energy_curve'][:10])) if len(candidate_features['energy_curve']) >= 10 else (float(np.mean(candidate_features['energy_curve'])) if len(candidate_features['energy_curve']) > 0 else 0)
        
        # If candidate starts with higher energy, give bonus points, else penalize
        energy_score = max(0, min(100, 50 + (cand_energy - curr_energy) * 100))
        
    # 4. Vocal Clash Avoidance (Multiplier penalty)
    vocal_penalty = 1.0
    if current_features and candidate_features:
        curr_vocal = float(np.mean(current_features['vocal_curve'][-5:])) if len(current_features['vocal_curve']) >= 5 else (float(np.mean(current_features['vocal_curve'])) if len(current_features['vocal_curve']) > 0 else 0)
        cand_vocal = float(np.mean(candidate_features['vocal_curve'][:5])) if len(candidate_features['vocal_curve']) >= 5 else (float(np.mean(candidate_features['vocal_curve'])) if len(candidate_features['vocal_curve']) > 0 else 0)
        
        # If both have high vocals overlapping in the transition window, penalize heavily
        if curr_vocal > 0.7 and cand_vocal > 0.7:
            vocal_penalty = 0.3
            
    total_score = ((harmonic_score * 0.5) + (bpm_score * 0.3) + (energy_score * 0.2)) * vocal_penalty
    return total_score

def get_recommendations(current_track_id: int, lookahead_depth: int = 1) -> List[Dict[str, Any]]:
    conn = get_db()
    cursor = conn.cursor()
    
    # Get current track
    cursor.execute("SELECT * FROM tracks WHERE id = ?", (current_track_id,))
    current_track = dict(cursor.fetchone())
    current_features = get_track_features(current_track_id)
    
    # Get all other tracks
    cursor.execute("SELECT * FROM tracks WHERE id != ?", (current_track_id,))
    candidates = [dict(r) for r in cursor.fetchall()]
    conn.close()
    
    scored_candidates = []
    
    for cand in candidates:
        cand_features = get_track_features(cand['id'])
        base_score = score_track(current_track, cand, current_features, cand_features)
        
        # Lookahead recursion
        if lookahead_depth > 0:
            # We don't want to load DB inside loop iteratively too much on a slow CPU.
            # In a real engine, we'd cache the library in RAM. For Phase 1, we just pick top 3 from library and score them.
            # To simulate lookahead without crippling the Celeron:
            # We just give a slight bump if this candidate has other tracks in the library with the exact same key.
            # True 3-track deep recursion on an SQLite DB per candidate would O(N^3) stall the 1.1GHz CPU.
            # Simplified Lookahead: How many compatible tracks exist for the candidate?
            compatible_count = sum(1 for future in candidates if future['id'] != cand['id'] and get_camelot_distance(cand['key_camelot'], future['key_camelot']) <= 1)
            lookahead_bonus = min(20, compatible_count * 5)
            base_score += lookahead_bonus
            
        scored_candidates.append({
            'track': cand,
            'score': base_score
        })
        
    scored_candidates.sort(key=lambda x: x['score'], reverse=True)
    return scored_candidates[:5] # Return top 5

