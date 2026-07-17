from library import get_db
c = get_db()
cur = c.cursor()
cur.execute("SELECT COUNT(*) n FROM tracks")
print("tracks in DB:", cur.fetchone()["n"])
cur.execute("SELECT id, title, bpm, key_camelot, lufs_integrated FROM tracks LIMIT 5")
for r in cur.fetchall():
    bpm = round(r["bpm"], 1) if r["bpm"] else 0
    lufs = round(r["lufs_integrated"], 1) if r["lufs_integrated"] else 0
    print(f"  id={r['id']} title={r['title']!r} bpm={bpm} key={r['key_camelot']} lufs={lufs}")
# Check features exist
cur.execute("SELECT COUNT(*) n FROM track_features")
print("features rows:", cur.fetchone()["n"])
c.close()