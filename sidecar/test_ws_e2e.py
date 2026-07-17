"""End-to-end smoke test: connects to the running sidecar via WebSocket and exercises every command."""
import asyncio
import json
import websockets
import time
import os
import sys

URI = "ws://127.0.0.1:8765/ws/telemetry"

async def main():
    print(f"Connecting to {URI} ...")
    async with websockets.connect(URI) as ws:
        # Read initial hello messages
        for _ in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                d = json.loads(msg)
                print(f"<- {d.get('type')}: {json.dumps(d)[:140]}")
            except asyncio.TimeoutError:
                break

        async def send(cmd):
            print(f"-> {cmd}")
            await ws.send(json.dumps(cmd))

        async def recv_expect(types, timeout=3.0):
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

        # 1) get_library
        await send({"cmd": "get_library"})
        r = await recv_expect(['library'])
        print(f"   library count: {r['count'] if r else 'NONE'}")

        # 2) get_status
        await send({"cmd": "get_status"})
        r = await recv_expect(['status'])
        print(f"   status stream_started: {r['status']['stream_started'] if r else 'NONE'}")

        # 3) set_autopilot
        await send({"cmd": "set_autopilot", "enabled": True})
        r = await recv_expect(['autopilot_state'])
        print(f"   autopilot_state: {r['enabled'] if r else 'NONE'}")

        # 4) set_technique
        await send({"cmd": "set_technique", "technique": "BassSwap"})
        r = await recv_expect(['technique_changed'])
        print(f"   technique_changed: {r['technique'] if r else 'NONE'}")

        # 5) set_master_bpm
        await send({"cmd": "set_master_bpm", "bpm": 124.0})
        r = await recv_expect(['master_bpm'])
        print(f"   master_bpm: {r['bpm'] if r else 'NONE'}")

        # 6) start_engine
        await send({"cmd": "start_engine"})
        r = await recv_expect(['ack'])
        print(f"   start_engine ack: {r['cmd'] if r else 'NONE'}")

        # 7) wait for telemetry
        r = await recv_expect(['telemetry'], timeout=4.0)
        if r:
            print(f"   telemetry: stream_started={r['stream_started']} active_deck={r['active_deck']} master_bpm={r['master_bpm']}")
            print(f"             deck_a.rms={r['deck_a']['rms']:.4f} deck_b.rms={r['deck_b']['rms']:.4f}")
            assert r['stream_started'] is True, "Stream should be started"
            assert r['active_deck'] == 'A'
        else:
            print("   NO TELEMETRY RECEIVED")
            return 1

        # 8) fire deck A (no track loaded - should still ack)
        await send({"cmd": "fire", "deck": "a"})
        r = await recv_expect(['ack', 'error'])
        print(f"   fire a: {r}")

        # 9) cue deck A
        await send({"cmd": "cue", "deck": "a"})
        r = await recv_expect(['ack'])
        print(f"   cue a: {r['cmd']}")

        # 10) set_deck_eq
        await send({"cmd": "set_deck_eq", "deck": "a", "band": "low", "value": 0.5})
        r = await recv_expect(['telemetry'], timeout=2.0)
        if r:
            print(f"   deck_a.eq_low after set: {r['deck_a']['eq_low']}")

        # 11) trigger_transition (no tracks loaded - should still arm & run)
        await send({"cmd": "trigger_transition"})
        r = await recv_expect(['ack'])
        print(f"   trigger_transition ack: {r['cmd'] if r else 'NONE'}")

        # 12) get_recommendations (no tracks in DB - will error)
        await send({"cmd": "get_recommendations", "track_id": 1})
        r = await recv_expect(['recommendations', 'error'], timeout=3.0)
        print(f"   recs response: {r.get('type') if r else 'NONE'}")

        # 13) stop_engine
        await send({"cmd": "stop_engine"})
        r = await recv_expect(['ack'])
        print(f"   stop_engine: {r['cmd'] if r else 'NONE'}")

        print("\nALL WS COMMANDS EXERCISED OK")
        return 0

if __name__ == "__main__":
    try:
        rc = asyncio.run(main())
    except ConnectionRefusedError:
        print("Could not connect - is the sidecar running?")
        rc = 1
    sys.exit(rc or 0)