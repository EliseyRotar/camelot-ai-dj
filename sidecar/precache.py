"""Pre-build .npy audio caches for all tracks already in the DB.
Run this once after installing the cache system so existing tracks get cached
without needing a force re-scan."""
import os, time, numpy as np
from library import get_db
from analyzer import cache_audio_file, get_cached_audio

c = get_db()
cur = c.cursor()
cur.execute("SELECT id, filepath FROM tracks ORDER BY id")
tracks = cur.fetchall()
c.close()

print(f"Pre-caching {len(tracks)} tracks...")
done = 0
skipped = 0
failed = 0
t0 = time.time()
for t in tracks:
    tid = t['id']
    fp = t['filepath']
    if get_cached_audio(tid) is not None:
        skipped += 1
        continue
    if not os.path.exists(fp):
        print(f"  [{tid}] MISSING file: {fp}")
        failed += 1
        continue
    try:
        cache_audio_file(fp, tid)
        done += 1
        print(f"  [{tid}] cached: {os.path.basename(fp)}")
    except Exception as e:
        print(f"  [{tid}] FAILED: {e}")
        failed += 1

dt = time.time() - t0
print(f"\nDone in {dt:.1f}s.  cached={done}  already-cached={skipped}  failed={failed}")
print(f"Cache dir: {os.path.join(os.path.dirname(__file__), 'audio_cache')}")