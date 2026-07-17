# Camelot — AI DJ Mixing App

*Autonomous AI DJ software that mixes your local music library on its own — automatic beatmatching, harmonic transitions, and a professional DJ interface.*

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Status: Active](https://img.shields.io/badge/Status-Active-success.svg)

## Overview

Camelot is an autonomous AI DJ mixing app built for local audio files. It processes local audio assets via a native, single-threaded background analyzer optimization model designed to run efficiently on low-spec hardware. The engine handles beatmatching, harmonic mixing, and dynamic transitions while providing a professional, dark-environment layout.

## Features

- **Autopilot Engine:** Dynamically selects tracks based on harmonic compatibility (Camelot wheel), BPM proximity, and structural energy trajectories.
- **Phrase Detection:** Automatically aligns transitions on structural phrase boundaries, ensuring vocal clash avoidance.
- **Professional UI Canvas:** Dual waveform channels with frequency-split color coding (Low = Red, Mid = Green, High = Blue).
- **Multiple Transition Formulas:** Executes long blends, bass swaps, quick cuts, and echo-outs autonomously.
- **LUFS Auto-Gain:** Tracks normalize themselves to a target integrated LUFS (-14) on load.
- **Load-Time Stretching:** Phase vocoder time-stretch runs once at load (via librosa), so the audio callback never drops a frame.

## Architecture

Camelot uses a Tauri (Rust + WebView2) frontend that automatically spawns a Python sidecar (FastAPI over local WebSocket) for audio analysis and playback. The UI is a fixed 1366×768 canvas-painted dark interface. For development without a Rust toolchain, the sidecar also serves the UI directly — just open it in any browser.

```
┌─────────────────────────┐    WebSocket (127.0.0.1:8765)   ┌─────────────────────────┐
│  Tauri Shell (Rust)     │ ─────────────────────────────── │  Python Sidecar          │
│  ui/ (HTML/Canvas/JS)   │                                 │  FastAPI + sounddevice    │
│  WebView2 host          │                                 │  analyzer.py / autopilot │
│  spawns sidecar on boot │                                 │  mixing_engine.py        │
└─────────────────────────┘                                 │  SQLite (camelot.sqlite)│
                                                            └─────────────────────────┘
```

## Phase Status

| Phase | Module | Status |
|-------|--------|--------|
| 1a | `analyzer.py`, `library.py` (SQLite + librosa) | Done |
| 1b | `mixing_engine.py` (load-time stretch, FFT EQ, LUFS norm) | Done |
| 1c | `autopilot.py` (3-axis scoring, vocal clash, lookahead) | Done |
| 1d | `techniques.py` (LongBlend / BassSwap / QuickCut / EchoOut) | Done |
| 1e | Tauri + WebView2 UI (canvas waveforms, VU meters, autopilot feed) | Done (browser mode); Tauri build requires MSVC |
| 2 | `stems/` (Demucs stem separation on a second machine) | Planned |

## Quick Start (Browser Mode — no Rust toolchain needed)

This is the fastest way to run the app on any Windows machine, including a low-spec Celeron.

### Prerequisites
- Python 3.10+ (the venv at `sidecar/.venv` is already configured on the dev machine)
- Any modern browser

### Run
```powershell
.\start.ps1          # or double-click start.bat
```
This launches the Python sidecar and opens the UI at `http://127.0.0.1:8765/`. The footer will read `SIDECAR: CONNECTED` (green) once the WebSocket is live.

### Manual start
```powershell
cd sidecar
.\.venv\Scripts\python.exe main.py
# then open http://127.0.0.1:8765/ in your browser
```

## Quick Start (Native Tauri App — requires Rust + MSVC)

### Prerequisites
- [Rust 1.70+](https://rustup.rs/) and Cargo
- [Node.js 18+](https://nodejs.org/)
- [Microsoft Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (preinstalled on Windows 11)
- Python 3.10+ with `sidecar/.venv` populated from `sidecar/requirements.txt`

### Build & Run
```bash
npm install
npm run tauri:dev      # launches the native Tauri window + sidecar
npm run tauri:build    # produces a distributable .exe/.msi
```

When the native window opens, Rust automatically spawns the Python sidecar from `sidecar/main.py` using the venv interpreter if present. Closing the window kills the sidecar.

## Using the App

1. Click **SCAN** in the header and pick a folder containing `.mp3`, `.wav`, or `.flac` files.
   - The scan is **incremental**: files already analyzed (matched by size + mtime) are skipped instantly, so re-scanning a folder is fast.
   - **Shift+click SCAN** to force a full re-analysis of every file (use this if you changed the files or want to re-run the analyzer).
2. The sidecar analyzes each new track sequentially (librosa beat tracking, key detection, LUFS, RMS energy, vocal heuristic) and stores features in `sidecar/camelot.sqlite`. Results persist across restarts — you only scan once.
3. Click **LOAD** on a deck to open the library picker and choose a track, or click a row in the bottom library table to load it onto the inactive deck. The deck loads, time-stretches to the master BPM, normalizes to -14 LUFS, and paints the waveform.
4. Click **PLAY** (the circular green button) to start a deck, **CUE** to stop it.
5. Click a recommendation card in the Autopilot panel (center mixer) to load that track onto the inactive deck.
6. Pick a technique (LONG BLEND / BASS SWAP / QUICK CUT / ECHO OUT) in the footer and click **▶ TRIGGER** to execute the transition.
7. Toggle **AUTOPILOT** in the top bar to let the engine pick transitions for you.

## Testing

```powershell
cd sidecar
.\.venv\Scripts\python.exe test_analyzer.py              # Phase 1a: analyzer + DB
.\.venv\Scripts\python.exe test_autopilot.py             # Phase 1c: scoring matrix
.\.venv\Scripts\python.exe test_mixing_techniques.py     # Phase 1d: BassSwap state edges
.\.venv\Scripts\python.exe test_ws_e2e.py               # WebSocket command surface
.\.venv\Scripts\python.exe test_integration.py           # Full pipeline: scan→load→fire→transition
```

## Project Roadmap

- [x] Phase 1a: Core Engine (SQLite scanning, librosa feature extraction)
- [x] Phase 1b: Mixing Logic (load-time phase vocoder, FFT EQ, LUFS auto-gain)
- [x] Phase 1c: Autopilot (harmonic scoring, phrase matching, vocal clash)
- [x] Phase 1d: Mixing Techniques (long blend, bass swap, quick cut, echo out)
- [x] Phase 1e: Tauri + WebView2 UI (dual canvas, VU meters, autopilot feed)
- [ ] Phase 2: AI Stem Separation (Demucs on a second machine)

## License

This project is licensed under the MIT License.