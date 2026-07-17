import uvicorn
import asyncio
import json
import os
import glob
import time
import numpy as np
from typing import Set
from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from analyzer import analyze_track
from library import add_track, get_db, get_track_features, get_track_by_filepath, has_features
from mixing_engine import engine, MASTER_SR, BLOCK_SIZE
from techniques import LongBlend, BassSwap, QuickCut, EchoOut

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Serve the UI statically from ../ui so the app works without Tauri ─────
_UI_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "ui"))
if os.path.isdir(_UI_DIR):
    app.mount("/styles", StaticFiles(directory=os.path.join(_UI_DIR, "styles")), name="styles")
    app.mount("/components", StaticFiles(directory=os.path.join(_UI_DIR, "components")), name="components")

@app.get("/", response_class=HTMLResponse)
def serve_index():
    idx = os.path.join(_UI_DIR, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx)
    return HTMLResponse("<h1>UI not found at ../ui/index.html</h1>", status_code=404)

@app.get("/ws-client.js")
def serve_ws_client():
    f = os.path.join(_UI_DIR, "ws-client.js")
    if os.path.isfile(f):
        return FileResponse(f, media_type="application/javascript")
    return HTMLResponse("not found", status_code=404)

TELEMETRY_HZ = 30.0
TELEMETRY_INTERVAL = 1.0 / TELEMETRY_HZ


class ScanRequest(BaseModel):
    directory_path: str


# ── WebSocket Connection Registry ──────────────────────────────────────────
_ws_clients: Set[WebSocket] = set()

# ── Application State ───────────────────────────────────────────────────────
_app_state = {
    "autopilot_enabled": False,
    "armed_technique": "LongBlend",
    "loaded_track_id_a": None,
    "loaded_track_id_b": None,
}


async def broadcast(msg: dict):
    dead = set()
    for client in _ws_clients:
        try:
            await client.send_json(msg)
        except Exception:
            dead.add(client)
    if dead:
        _ws_clients.difference_update(dead)


def get_track_row(track_id: int) -> dict | None:
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ── HTTP REST endpoints (legacy + useful for testing) ──────────────────────
@app.post("/api/scan")
def trigger_scan(req: ScanRequest, background_tasks: BackgroundTasks):
    if not os.path.isdir(req.directory_path):
        return {"error": "Invalid directory path"}
    background_tasks.add_task(scan_directory_task, req.directory_path)
    return {"message": "Scan started in background"}


@app.get("/api/library")
def get_library():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM tracks ORDER BY id")
    tracks = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"tracks": tracks}


@app.get("/api/get_recommendations/{track_id}")
def api_get_recommendations(track_id: int):
    from autopilot import get_recommendations
    try:
        recs = get_recommendations(track_id, lookahead_depth=1)
        return {"recommendations": recs}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/status")
def status():
    return {
        "stream_started": engine._stream_started,
        "active_deck": engine.active_deck,
        "master_bpm": engine.master_bpm,
        "autopilot": _app_state["autopilot_enabled"],
        "armed_technique": _app_state["armed_technique"],
        "deck_a": {
            "loaded": len(engine.deck_a.audio) > 0,
            "playing": engine.deck_a.is_playing,
            "title": engine.deck_a.title,
            "playhead": engine.deck_a.playhead / MASTER_SR,
            "duration": engine.deck_a.duration,
        },
        "deck_b": {
            "loaded": len(engine.deck_b.audio) > 0,
            "playing": engine.deck_b.is_playing,
            "title": engine.deck_b.title,
            "playhead": engine.deck_b.playhead / MASTER_SR,
            "duration": engine.deck_b.duration,
        },
        "ws_clients": len(_ws_clients),
    }


def scan_directory_task(directory_path: str, force: bool = False):
    print(f"Starting sequential scan of {directory_path} (force={force})...")
    patterns = ["*.mp3", "*.wav", "*.flac"]
    files = []
    for ext in patterns:
        files.extend(glob.glob(os.path.join(directory_path, "**", ext), recursive=True))
    files.sort()

    skipped = 0
    analyzed = 0
    for idx, filepath in enumerate(files):
        if not force:
            try:
                file_stat = os.stat(filepath)
                fsize = file_stat.st_size
                fmtime = file_stat.st_mtime
            except OSError:
                fsize = None
                fmtime = None
            existing = get_track_by_filepath(filepath)
            if (existing is not None
                    and existing.get('filesize') == fsize
                    and abs((existing.get('file_mtime') or 0) - (fmtime or 0)) < 1.0
                    and has_features(existing['id'])):
                skipped += 1
                print(f"[{idx+1}/{len(files)}] skip: {filepath}")
                continue
        print(f"[{idx+1}/{len(files)}] analyzing: {filepath}")
        try:
            result = analyze_track(filepath)
            add_track(result['metadata'], result['features'])
            analyzed += 1
        except Exception as e:
            print(f"Error analyzing {filepath}: {e}")
    print(f"Scan complete. {analyzed} analyzed, {skipped} skipped.")


# ── Deck loading helpers (run in thread pool so asyncio stays responsive) ──
def _load_deck_blocking(deck_name: str, track_id: int):
    deck = engine.deck_a if deck_name.lower() == "a" else engine.deck_b
    row = get_track_row(track_id)
    if row is None:
        print(f"load_deck: track {track_id} not found")
        return None

    filepath = row['filepath']
    original_bpm = float(row['bpm']) if row['bpm'] else 0.0
    original_lufs = float(row['lufs_integrated']) if row['lufs_integrated'] else -23.0
    title = row.get('title') or os.path.basename(filepath)
    artist = row.get('artist') or ''
    target_bpm = engine.master_bpm

    deck.load_track(
        filepath=filepath,
        track_id=track_id,
        original_bpm=original_bpm,
        original_lufs=original_lufs,
        target_bpm=target_bpm,
        title=title,
        artist=artist,
    )
    if deck_name.lower() == "a":
        _app_state["loaded_track_id_a"] = track_id
    else:
        _app_state["loaded_track_id_b"] = track_id
    return {
        "deck": deck_name.lower(),
        "track": row,
        "features": _get_features_payload(track_id),
    }


def _get_features_payload(track_id: int):
    f = get_track_features(track_id)
    if f is None:
        return None
    out = {}
    for k in ('energy_curve', 'vocal_curve', 'beat_grid'):
        v = f.get(k)
        if v is not None and len(v) > 0:
            # Downsample curves for UI (max ~256 points) to keep WS payloads small
            arr = np.asarray(v, dtype=np.float32)
            if len(arr) > 256:
                step = len(arr) // 256
                arr = arr[::step][:256]
            out[k] = arr.tolist()
        else:
            out[k] = []
    return out


# ── WebSocket endpoint ─────────────────────────────────────────────────────
@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await websocket.accept()
    _ws_clients.add(websocket)
    print(f"UI client connected. Total: {len(_ws_clients)}")

    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as n FROM tracks")
        count = c.fetchone()['n']
        conn.close()
        await websocket.send_json({"type": "library", "count": count})
        await websocket.send_json({
            "type": "engine_state",
            "autopilot_enabled": _app_state["autopilot_enabled"],
            "armed_technique": _app_state["armed_technique"],
            "master_bpm": engine.master_bpm,
            "active_deck": engine.active_deck,
        })

        while True:
            raw = await websocket.receive_text()
            try:
                cmd = json.loads(raw)
                await handle_ws_command(cmd, websocket)
            except Exception as e:
                print(f"WS command error: {e}")

    except Exception as e:
        print(f"WS connection closed: {e}")
    finally:
        _ws_clients.discard(websocket)
        print(f"UI client disconnected. Total: {len(_ws_clients)}")


async def handle_ws_command(cmd: dict, websocket: WebSocket):
    action = cmd.get('cmd')

    if action == 'get_library':
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) as n FROM tracks")
        count = c.fetchone()['n']
        conn.close()
        await websocket.send_json({"type": "library", "count": count})

    elif action == 'get_library_full':
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT * FROM tracks ORDER BY id")
        tracks = [dict(r) for r in c.fetchall()]
        conn.close()
        await websocket.send_json({"type": "library_full", "tracks": tracks})

    elif action == 'scan':
        path = cmd.get('path', '.')
        force = bool(cmd.get('force', False))
        if not os.path.isdir(path):
            await websocket.send_json({"type": "error", "message": "Invalid directory"})
            return
        asyncio.create_task(_ws_scan_task(path, force=force))
        await websocket.send_json({"type": "scan_progress", "progress": 0, "current_file": "Starting..."})

    elif action == 'get_recommendations':
        track_id = cmd.get('track_id')
        if track_id is None:
            await websocket.send_json({"type": "error", "message": "track_id required"})
            return
        try:
            from autopilot import get_recommendations
            loop = asyncio.get_event_loop()
            recs = await loop.run_in_executor(None, get_recommendations, track_id, 1)
            await websocket.send_json({"type": "recommendations", "recs": recs})
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})

    elif action == 'load_deck':
        track_id = cmd.get('track_id')
        deck_name = cmd.get('deck', 'a')
        if track_id is None:
            await websocket.send_json({"type": "error", "message": "track_id required"})
            return
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _load_deck_blocking, deck_name, track_id)
            if result is None:
                await websocket.send_json({"type": "error", "message": f"Track {track_id} not found"})
                return
            await broadcast({"type": "track_loaded", **result})
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})

    elif action == 'load_next_deck':
        track_id = cmd.get('track_id')
        if track_id is None:
            await websocket.send_json({"type": "error", "message": "track_id required"})
            return
        # Pick the inactive deck (the one that is not active_deck)
        inactive = "b" if engine.active_deck == "A" else "a"
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, _load_deck_blocking, inactive, track_id)
            if result is None:
                await websocket.send_json({"type": "error", "message": f"Track {track_id} not found"})
                return
            await broadcast({"type": "track_loaded", **result})
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})

    elif action == 'fire':
        deck = cmd.get('deck', 'a').lower()
        target_beat = cmd.get('beat_time', -1.0)
        d = engine.deck_a if deck == 'a' else engine.deck_b
        d.fire_on_beat(target_beat)
        await websocket.send_json({"type": "ack", "cmd": "fire", "deck": deck, "playhead": d.playhead})

    elif action == 'cue':
        deck = cmd.get('deck', 'a').lower()
        d = engine.deck_a if deck == 'a' else engine.deck_b
        d.cue()
        await websocket.send_json({"type": "ack", "cmd": "cue", "deck": deck})

    elif action == 'set_technique':
        name = cmd.get('technique', 'LongBlend')
        valid = {"LongBlend", "BassSwap", "QuickCut", "EchoOut"}
        if name not in valid:
            await websocket.send_json({"type": "error", "message": f"Unknown technique: {name}"})
            return
        engine.armed_technique = name
        _app_state["armed_technique"] = name
        await broadcast({"type": "technique_changed", "technique": name})

    elif action == 'trigger_transition':
        engine.trigger_transition()
        await websocket.send_json({"type": "ack", "cmd": "trigger_transition"})

    elif action == 'set_autopilot':
        on = bool(cmd.get('enabled', False))
        _app_state["autopilot_enabled"] = on
        await broadcast({"type": "autopilot_state", "enabled": on})
        print(f"Autopilot {'ENABLED' if on else 'DISABLED'}")

    elif action == 'set_master_bpm':
        bpm = float(cmd.get('bpm', 120.0))
        engine.master_bpm = max(40.0, min(250.0, bpm))
        await broadcast({"type": "master_bpm", "bpm": engine.master_bpm})

    elif action == 'set_deck_eq':
        deck = cmd.get('deck', 'a').lower()
        band = cmd.get('band', '')
        val = float(cmd.get('value', 1.0))
        val = max(0.0, min(1.0, val))
        d = engine.deck_a if deck == 'a' else engine.deck_b
        if band == 'low':
            d.eq_low = val
        elif band == 'mid':
            d.eq_mid = val
        elif band == 'high':
            d.eq_high = val
        elif band == 'gain':
            d.gain = val

    elif action == 'start_engine':
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, engine.start_stream)
        await websocket.send_json({"type": "ack", "cmd": "start_engine"})

    elif action == 'stop_engine':
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, engine.stop_stream)
        await websocket.send_json({"type": "ack", "cmd": "stop_engine"})

    elif action == 'get_status':
        await websocket.send_json({"type": "status", "status": status()})

    else:
        await websocket.send_json({"type": "error", "message": f"Unknown command: {action}"})


# ── Telemetry broadcaster ───────────────────────────────────────────────────
async def _telemetry_loop():
    while True:
        await asyncio.sleep(TELEMETRY_INTERVAL)
        if not _ws_clients:
            continue

        da = engine.deck_a
        db = engine.deck_b
        tm = engine.transition_manager

        payload = {
            "type": "telemetry",
            "master_bpm": engine.master_bpm,
            "active_deck": engine.active_deck,
            "stream_started": engine._stream_started,
            "deck_a": {
                "title": da.title,
                "gain": round(da.gain, 3),
                "eq_low": round(da.eq_low, 3),
                "eq_mid": round(da.eq_mid, 3),
                "eq_high": round(da.eq_high, 3),
                "is_playing": da.is_playing,
                "play_progress": min(1.0, da.playhead / max(1, len(da.audio))) if len(da.audio) else 0.0,
                "duration": da.duration,
                "rms": min(1.0, da.last_rms * 2.0),
                "loaded": len(da.audio) > 0,
            },
            "deck_b": {
                "title": db.title,
                "gain": round(db.gain, 3),
                "eq_low": round(db.eq_low, 3),
                "eq_mid": round(db.eq_mid, 3),
                "eq_high": round(db.eq_high, 3),
                "is_playing": db.is_playing,
                "play_progress": min(1.0, db.playhead / max(1, len(db.audio))) if len(db.audio) else 0.0,
                "duration": db.duration,
                "rms": min(1.0, db.last_rms * 2.0),
                "loaded": len(db.audio) > 0,
            },
            "transition": {
                "active": tm.active_technique is not None,
                "active_technique": tm.active_technique.__class__.__name__ if tm.active_technique else None,
                "progress": (tm.active_technique.current_sample / max(1, tm.active_technique.duration_samples))
                            if tm.active_technique else 0.0,
            },
        }
        await broadcast(payload)


@app.on_event("startup")
async def _startup():
    asyncio.create_task(_telemetry_loop())
    print("Telemetry loop started.")


@app.on_event("shutdown")
async def _shutdown():
    engine.stop_stream()


# ── Async scan with progress broadcast (incremental) ───────────────────────
async def _ws_scan_task(directory_path: str, force: bool = False):
    patterns = ["*.mp3", "*.wav", "*.flac"]
    files = []
    for ext in patterns:
        files.extend(glob.glob(os.path.join(directory_path, "**", ext), recursive=True))
    files.sort()

    total = len(files)
    if total == 0:
        await broadcast({"type": "scan_progress", "progress": 1.0, "current_file": "No audio files found."})
        return

    # Single-worker executor so the Celeron doesn't thrash on concurrent librosa
    loop = asyncio.get_event_loop()
    import concurrent.futures
    single_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    skipped = 0
    analyzed = 0
    failed = 0

    for idx, filepath in enumerate(files):
        fname = os.path.basename(filepath)

        # ── Incremental skip: avoid re-analyzing unchanged files ──
        if not force:
            try:
                file_stat = os.stat(filepath)
                fsize = file_stat.st_size
                fmtime = file_stat.st_mtime
            except OSError:
                fsize = None
                fmtime = None

            existing = get_track_by_filepath(filepath)
            if (existing is not None
                    and existing.get('filesize') is not None
                    and existing.get('file_mtime') is not None
                    and existing['filesize'] == fsize
                    and abs((existing['file_mtime'] or 0) - (fmtime or 0)) < 1.0
                    and has_features(existing['id'])):
                skipped += 1
                # Still broadcast progress so the UI bar moves and shows it's not frozen
                await broadcast({
                    "type": "scan_progress",
                    "progress": (idx + 1) / total,
                    "current_file": f"[skip] {fname}  (already analyzed)"
                })
                continue

        # ── Analyze ──
        await broadcast({
            "type": "scan_progress",
            "progress": idx / total,
            "current_file": f"[analyze] {fname}"
        })
        try:
            result = await loop.run_in_executor(single_pool, analyze_track, filepath)
            add_track(result['metadata'], result['features'])
            analyzed += 1
        except Exception as e:
            failed += 1
            print(f"Error analyzing {filepath}: {e}")

    single_pool.shutdown(wait=False)

    summary = f"Done. {analyzed} analyzed, {skipped} skipped, {failed} failed."
    await broadcast({"type": "scan_progress", "progress": 1.0, "current_file": summary})
    conn = get_db()
    c2 = conn.cursor()
    c2.execute("SELECT COUNT(*) as n FROM tracks")
    count = c2.fetchone()['n']
    conn.close()
    await broadcast({"type": "library", "count": count})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)