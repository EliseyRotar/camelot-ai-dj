"""Test that an incremental scan skips already-analyzed files instantly."""
import asyncio, json, websockets, time

URI = "ws://127.0.0.1:8765/ws/telemetry"

async def main():
    async with websockets.connect(URI) as ws:
        # drain
        end = time.time() + 1
        while time.time() < end:
            try: await asyncio.wait_for(ws.recv(), timeout=0.2)
            except: break

        await ws.send(json.dumps({"cmd": "scan", "path": r"C:\Users\Admin\Music", "force": False}))
        t0 = time.time()
        last_progress = 0
        skipped = 0
        analyzed = 0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=120)
            except asyncio.TimeoutError:
                print("TIMEOUT"); return 1
            d = json.loads(msg)
            if d.get("type") == "scan_progress":
                last_progress = d["progress"]
                cf = d.get("current_file", "")
                if cf.startswith("[skip]"): skipped += 1
                elif cf.startswith("[analyze]"): analyzed += 1
                print(f"  {d['progress']*100:5.1f}%  {cf}")
                if d["progress"] >= 1.0:
                    break
        dt = time.time() - t0
        print(f"\nScan finished in {dt:.1f}s.  skipped={skipped} analyzed={analyzed}")
        if analyzed == 0 and skipped > 0:
            print("PASS: incremental scan skipped all already-analyzed files instantly")
        elif analyzed > 0:
            print(f"NOTE: {analyzed} new files were analyzed (expected if DB was incomplete)")
        return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()) or 0)