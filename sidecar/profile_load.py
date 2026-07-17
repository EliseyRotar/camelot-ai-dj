"""Profile every stage of Deck.load_track on a real MP3 from the library."""
import time, os, librosa, numpy as np
from library import get_db

c = get_db()
cur = c.cursor()
cur.execute("SELECT filepath, bpm, lufs_integrated FROM tracks WHERE filepath LIKE '%.mp3' ORDER BY id LIMIT 1")
row = cur.fetchone()
c.close()
if not row:
    print("No mp3 in DB"); raise SystemExit

path = row['filepath']
bpm = row['bpm'] or 120.0
lufs = row['lufs_integrated'] or -23.0
size_mb = os.path.getsize(path) / 1e6
print(f"File: {os.path.basename(path)}")
print(f"  size: {size_mb:.1f} MB, bpm: {bpm:.1f}, lufs: {lufs:.1f}")

def timed(label, fn):
    t0 = time.time(); r = fn(); dt = time.time() - t0
    print(f"  {label:42s} {dt:6.2f}s")
    return r

print("\n=== Deck.load_track stage-by-stage ===")
y, sr = timed("1. librosa.load (decode + resample)", lambda: librosa.load(path, sr=22050, mono=True))
print(f"     -> {len(y)} samples = {len(y)/22050:.1f}s of audio")

norm_gain = 10 ** ((-14.0 - lufs) / 20.0)
y2 = timed("2. LUFS normalize (numpy multiply)", lambda: y * norm_gain)

rate = 128.0 / bpm if bpm > 0 else 1.0
if abs(rate - 1.0) > 0.01:
    y3 = timed(f"3. time_stretch (rate={rate:.3f})", lambda: librosa.effects.time_stretch(y2, rate=rate))
else:
    y3 = y2
    print("3. time_stretch: skipped (rate ~= 1)")

_ = timed("4. beat_track (recompute on stretched)", lambda: librosa.beat.beat_track(y=y3, sr=22050))

# The Deck.load_track also calls get_track_features from DB — time that
from library import get_track_features
_ = timed("5. get_track_features (DB read)", lambda: get_track_features(1))

print("\n=== What the DB already has (no need to recompute) ===")
from library import get_track_features
f = get_track_features(1)
if f:
    print(f"  beat_grid: {'YES' if f['beat_grid'] is not None else 'NO'} ({len(f['beat_grid']) if f['beat_grid'] is not None else 0} entries)")
    print(f"  energy_curve: {'YES' if f['energy_curve'] is not None else 'NO'}")
    print(f"  vocal_curve: {'YES' if f['vocal_curve'] is not None else 'NO'}")