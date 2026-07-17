"""Test the auto_start command and measure deck load time end-to-end."""
import asyncio, json, websockets, time

URI = "ws://127.0.0.1:8765/ws/telemetry"

async def main():
    async with websockets.connect(URI) as ws:
        # drain
        end = time.time() + 1
        while time.time() < end:
            try: await asyncio.wait_for(ws.recv(), timeout=0.2)
            except: break

        print("=== Sending auto_start ===")
        t0 = time.time()
        await ws.send(json.dumps({"cmd": "auto_start"}))

        # Collect messages for up to 60s
        messages = []
        end = time.time() + 60
        while time.time() < end:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                d = json.loads(msg)
                messages.append(d)
                t_elapsed = time.time() - t0
                if d.get("type") == "status_message":
                    print(f"  [{t_elapsed:5.1f}s] status: {d['message']}")
                elif d.get("type") == "track_loaded":
                    print(f"  [{t_elapsed:5.1f}s] loaded deck={d['deck']} title={d['track']['title']!r}")
                elif d.get("type") == "ack" and d.get("cmd") == "auto_start":
                    print(f"  [{t_elapsed:5.1f}s] AUTO START COMPLETE")
                    break
                elif d.get("type") == "error":
                    print(f"  [{t_elapsed:5.1f}s] ERROR: {d['message']}")
                    break
                elif d.get("type") == "telemetry":
                    da = d.get("deck_a", {})
                    if da.get("is_playing"):
                        print(f"  [{t_elapsed:5.1f}s] deck A playing! rms={da.get('rms', 0):.3f}")
                        # Wait a bit more then break
                        end = min(end, time.time() + 3)
            except asyncio.TimeoutError:
                continue

        dt = time.time() - t0
        print(f"\nTotal auto_start time: {dt:.1f}s")

        # Check telemetry shows audio playing
        playing_a = any(m.get("type") == "telemetry" and m.get("deck_a", {}).get("is_playing") for m in messages)
        loaded_b = any(m.get("type") == "track_loaded" and m.get("deck") == "b" for m in messages)
        print(f"Deck A playing: {playing_a}")
        print(f"Deck B loaded: {loaded_b}")
        if playing_a:
            print("PASS: auto_start loaded and played Deck A")
        else:
            print("FAIL: Deck A did not start playing")
        return 0 if playing_a else 1

if __name__ == "__main__":
    import sys; sys.exit(asyncio.run(main()) or 0)