"""Full integration test: generate real audio files, scan them into the DB, load via WS, fire, and transition."""
import asyncio
import json
import websockets
import time
import numpy as np
import soundfile as sf
import os
import sys
import tempfile
import shutil

URI = "ws://127.0.0.1:8765/ws/telemetry"
SR = 22050

async def main():
    tmpdir = tempfile.mkdtemp(prefix="camelot_test_")
    print(f"Test dir: {tmpdir}")

    # Generate 3 distinct test tracks (different pitch/bpm/duration)
    def make_track(path, freq, bpm, duration_sec, lufs_target_db):
        t = np.linspace(0, duration_sec, int(SR * duration_sec), endpoint=False)
        # Layer of sine + harmonic for a richer signal
        y = 0.5 * np.sin(2 * np.pi * freq * t)
        y += 0.2 * np.sin(2 * np.pi * freq * 2 * t)
        # Beat clicks
        beat_interval = 60.0 / bpm
        for beat_t in np.arange(0, duration_sec, beat_interval):
            idx = int(beat_t * SR)
            if idx < len(y):
                y[idx] = 0.95
        # Rough LUFS adjustment via simple gain (analyzer will compute true LUFS)
        gain = 10 ** (lufs_target_db / 20.0)
        y = np.clip(y * gain, -1.0, 1.0).astype(np.float32)
        sf.write(path, y, SR)
        return path

    p_a = make_track(os.path.join(tmpdir, "track_a_120bpm.wav"), 220.0, 120.0, 12.0, -18.0)
    p_b = make_track(os.path.join(tmpdir, "track_b_122bpm.wav"), 330.0, 122.0, 12.0, -20.0)
    p_c = make_track(os.path.join(tmpdir, "track_c_118bpm.wav"), 440.0, 118.0, 12.0, -14.0)
    print(f"Generated 3 test tracks in {tmpdir}")

    async with websockets.connect(URI) as ws:
        async def send(cmd):
            print(f"-> {cmd['cmd']}")
            await ws.send(json.dumps(cmd))

        async def recv_types(types, timeout=10.0):
            end = time.time() + timeout
            while time.time() < end:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                d = json.loads(msg)
                if d.get('type') in types:
                    return d
            return None

        # Drain initial
        await recv_types(['library', 'engine_state'], timeout=2.0)

        # 1) SCAN
        print("\n=== STEP 1: SCAN ===")
        await send({"cmd": "scan", "path": tmpdir})
        # Wait for scan_progress=1.0
        last_progress = 0.0
        while True:
            r = await recv_types(['scan_progress'], timeout=60.0)
            if r is None:
                print("   SCAN TIMEOUT")
                return 1
            last_progress = r['progress']
            print(f"   scan progress: {r['progress']*100:.0f}% - {r['current_file']}")
            if r['progress'] >= 1.0:
                break
        print("   SCAN COMPLETE")

        # 2) Verify library count
        await send({"cmd": "get_library"})
        r = await recv_types(['library'])
        n_tracks = r['count']
        print(f"   Library now has {n_tracks} tracks")
        assert n_tracks == 3, f"Expected 3 tracks, got {n_tracks}"
        await send({"cmd": "get_library_full"})
        r = await recv_types(['library_full'])
        tracks = r['tracks']
        for t in tracks:
            print(f"   - id={t['id']} {t['title'] or t['filepath']} bpm={t['bpm']:.1f} key={t['key_camelot']} lufs={t['lufs_integrated']:.1f}")

        # 3) Load track 1 onto deck A
        print("\n=== STEP 2: LOAD DECK A ===")
        await send({"cmd": "load_deck", "deck": "a", "track_id": tracks[0]['id']})
        r = await recv_types(['track_loaded'], timeout=30.0)
        print(f"   loaded: {r['track']['title']} -> deck {r['deck']}, features: energy_len={len(r['features']['energy_curve'])}")
        assert r['deck'] == 'a'

        # 4) Load track 2 onto deck B
        print("\n=== STEP 3: LOAD DECK B ===")
        await send({"cmd": "load_deck", "deck": "b", "track_id": tracks[1]['id']})
        r = await recv_types(['track_loaded'], timeout=30.0)
        print(f"   loaded: {r['track']['title']} -> deck {r['deck']}")

        # 5) Get recommendations for track 1
        print("\n=== STEP 4: RECOMMENDATIONS ===")
        await send({"cmd": "get_recommendations", "track_id": tracks[0]['id']})
        r = await recv_types(['recommendations'], timeout=10.0)
        print(f"   got {len(r['recs'])} recommendations")
        for i, rec in enumerate(r['recs']):
            print(f"   {i+1}. {rec['track']['title']} score={rec['score']:.1f} key={rec['track']['key_camelot']} bpm={rec['track']['bpm']:.1f}")

        # 6) Start the audio stream
        print("\n=== STEP 5: START ENGINE ===")
        await send({"cmd": "start_engine"})
        await recv_types(['ack'])
        r = await recv_types(['telemetry'], timeout=3.0)
        assert r['stream_started'] is True
        print(f"   stream_started={r['stream_started']}")

        # 7) Fire both decks and verify RMS > 0
        print("\n=== STEP 6: FIRE DECKS ===")
        await send({"cmd": "fire", "deck": "a"})
        await recv_types(['ack'])
        await asyncio.sleep(0.5)
        await send({"cmd": "fire", "deck": "b"})
        await recv_types(['ack'])

        # Collect telemetry for 1s
        print("   collecting telemetry for 1.5s...")
        rms_a_samples = []
        rms_b_samples = []
        end = time.time() + 1.5
        while time.time() < end:
            r = await recv_types(['telemetry'], timeout=1.0)
            if r:
                rms_a_samples.append(r['deck_a']['rms'])
                rms_b_samples.append(r['deck_b']['rms'])
        print(f"   deck_a rms samples: {[f'{x:.3f}' for x in rms_a_samples[:5]]}... max={max(rms_a_samples):.3f}")
        print(f"   deck_b rms samples: {[f'{x:.3f}' for x in rms_b_samples[:5]]}... max={max(rms_b_samples):.3f}")
        assert max(rms_a_samples) > 0.01, "Deck A produced no audio!"
        assert max(rms_b_samples) > 0.01, "Deck B produced no audio!"

        # 8) Trigger a LongBlend transition
        print("\n=== STEP 7: TRANSITION (LongBlend) ===")
        await send({"cmd": "set_technique", "technique": "LongBlend"})
        await recv_types(['technique_changed'])
        await send({"cmd": "trigger_transition"})
        await recv_types(['ack'])
        # Wait for transition to start
        r = await recv_types(['telemetry'], timeout=2.0)
        assert r['transition']['active'] is True, "Transition did not start"
        print(f"   transition active: {r['transition']['active_technique']} progress={r['transition']['progress']*100:.0f}%")
        print(f"   deck_a gain={r['deck_a']['gain']:.2f} deck_b gain={r['deck_b']['gain']:.2f}")

        # 9) Stop everything
        print("\n=== STEP 8: STOP ===")
        await send({"cmd": "cue", "deck": "a"})
        await send({"cmd": "cue", "deck": "b"})
        await send({"cmd": "stop_engine"})
        await recv_types(['ack'])

        print("\n=== FULL PIPELINE TEST PASSED ===")
        return 0

if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except Exception as e:
        import traceback
        traceback.print_exc()
        rc = 1
    finally:
        # Cleanup tmpdir handled by OS on reboot; leave for inspection
        pass
    sys.exit(rc or 0)