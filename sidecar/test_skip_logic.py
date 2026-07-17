"""Directly test the incremental-scan skip logic against the real DB + Music folder."""
import os, time
from library import get_track_by_filepath, has_features, get_db

music_dir = r"C:\Users\Admin\Music"
import glob
files = []
for ext in ("*.mp3", "*.wav", "*.flac"):
    files.extend(glob.glob(os.path.join(music_dir, "**", ext), recursive=True))
files.sort()

total = len(files)
skipped = 0
would_analyze = 0
t0 = time.time()
for f in files:
    try:
        st = os.stat(f)
        fsize, fmtime = st.st_size, st.st_mtime
    except OSError:
        fsize, fmtime = None, None
    existing = get_track_by_filepath(f)
    if (existing is not None
            and existing.get('filesize') == fsize
            and abs((existing.get('file_mtime') or 0) - (fmtime or 0)) < 1.0
            and has_features(existing['id'])):
        skipped += 1
    else:
        would_analyze += 1

dt = time.time() - t0
c = get_db(); cur = c.cursor(); cur.execute("SELECT COUNT(*) n FROM tracks"); db_count = cur.fetchone()['n']; c.close()
print(f"Files in {music_dir}: {total}")
print(f"Already analyzed (will SKIP): {skipped}")
print(f"New/changed (would ANALYZE): {would_analyze}")
print(f"Skip-decision time: {dt*1000:.1f}ms total ({dt*1000/max(1,total):.2f}ms per file)")
print(f"Tracks in DB: {db_count}")
if would_analyze == 0 and skipped > 0:
    print("PASS: a re-scan of this folder would skip every file instantly.")
else:
    print(f"NOTE: {would_analyze} file(s) need analysis (first scan or changed files).")