import librosa
import numpy as np
import pyloudnorm as pyln
import os
import re
from typing import Dict, Any

# Krumhansl-Schmuckler key profiles
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Camelot mapping:
# Major keys: C=8B, C#=3B, D=10B, D#=5B, E=12B, F=7B, F#=2B, G=9B, G#=4B, A=11B, A#=6B, B=1B
CAMELOT_MAJOR = ['8B', '3B', '10B', '5B', '12B', '7B', '2B', '9B', '4B', '11B', '6B', '1B']
# Minor keys: C=5A, C#=12A, D=7A, D#=2A, E=9A, F=4A, F#=11A, G=6A, G#=1A, A=8A, A#=3A, B=10A
CAMELOT_MINOR = ['5A', '12A', '7A', '2A', '9A', '4A', '11A', '6A', '1A', '8A', '3A', '10A']

def get_camelot_key(chromagram: np.ndarray) -> str:
    # chromagram is shape (12, T). We sum over time to get a single chroma vector.
    chroma_vector = np.sum(chromagram, axis=1)
    
    max_corr = -1.0
    best_key = ""
    
    # We iterate over the 12 possible key shifts
    for i in range(12):
        # Shift profiles to test different root notes
        major_prof = np.roll(KS_MAJOR, i)
        minor_prof = np.roll(KS_MINOR, i)
        
        corr_major = np.corrcoef(chroma_vector, major_prof)[0, 1]
        corr_minor = np.corrcoef(chroma_vector, minor_prof)[0, 1]
        
        if corr_major > max_corr:
            max_corr = corr_major
            best_key = CAMELOT_MAJOR[i]
            
        if corr_minor > max_corr:
            max_corr = corr_minor
            best_key = CAMELOT_MINOR[i]
            
    return best_key

def _extract_metadata_from_path(filepath: str) -> Dict[str, str]:
    """Try to read tags via mutagen; fall back to parsing the filename."""
    title = ""
    artist = ""
    try:
        from mutagen import File as MutagenFile
        m = MutagenFile(filepath, easy=True)
        if m is not None:
            title = (m.get('title') or [''])[0] if m.get('title') else ''
            artist = (m.get('artist') or [''])[0] if m.get('artist') else ''
    except Exception:
        pass

    if not title:
        base = os.path.splitext(os.path.basename(filepath))[0]
        # Common patterns: "Artist - Title", "Artist_-_Title"
        m = re.match(r'^(.+?)\s*[-_–]+\s*(.+)$', base)
        if m:
            artist = artist or m.group(1).strip().replace('_', ' ')
            title = m.group(2).strip().replace('_', ' ')
        else:
            title = base
    return {'title': title, 'artist': artist}


def analyze_track(filepath: str, sr: int = 22050) -> Dict[str, Any]:
    """Analyzes an audio file and returns its metadata and downsampled features."""
    # File stats for incremental-scan skip logic
    try:
        file_stat = os.stat(filepath)
        filesize = file_stat.st_size
        file_mtime = file_stat.st_mtime
    except OSError:
        filesize = None
        file_mtime = None

    # Load audio
    y, _ = librosa.load(filepath, sr=sr, mono=True)
    duration = librosa.get_duration(y=y, sr=sr)

    # File-derived metadata
    tags = _extract_metadata_from_path(filepath)

    # LUFS calculation
    meter = pyln.Meter(sr) # explicitly use librosa's sr
    y_reshaped = y.reshape(-1, 1)
    try:
        lufs_integrated = float(meter.integrated_loudness(y_reshaped))
    except ValueError:
        lufs_integrated = -70.0

    # BPM and Beat Grid
    bpm_val, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(bpm_val)[0])
    beat_grid = librosa.frames_to_time(beat_frames, sr=sr)

    # Camelot Key Detection (using chroma_stft for performance)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    key_camelot = get_camelot_key(chroma)

    # Downsampled Features (1-second chunks)
    hop_length = sr
    rms = librosa.feature.rms(y=y, hop_length=hop_length, frame_length=hop_length)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop_length, n_fft=hop_length)[0]
    mfccs = librosa.feature.mfcc(y=y, sr=sr, hop_length=hop_length, n_mfcc=13, n_fft=hop_length)
    mfcc_var = np.var(mfccs, axis=0)

    cent_norm = centroid / (np.max(centroid) + 1e-6)
    mfcc_norm = mfcc_var / (np.max(mfcc_var) + 1e-6)
    vocal_curve = (cent_norm + mfcc_norm) / 2.0

    return {
        'metadata': {
            'filepath': filepath,
            'title': tags['title'],
            'artist': tags['artist'],
            'duration': duration,
            'bpm': bpm,
            'key_camelot': key_camelot,
            'lufs_integrated': lufs_integrated,
            'filesize': filesize,
            'file_mtime': file_mtime,
        },
        'features': {
            'beat_grid': beat_grid.astype(np.float32),
            'energy_curve': rms.astype(np.float32),
            'vocal_curve': vocal_curve.astype(np.float32)
        }
    }

