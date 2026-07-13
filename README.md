# Camelot — AI DJ Mixing App

*Autonomous AI DJ software that mixes your local music library on its own — automatic beatmatching, harmonic transitions, and a professional DJ interface.*

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Status: Active](https://img.shields.io/badge/Status-Active-success.svg)

## Overview

Camelot is an autonomous AI DJ mixing app built for local audio files. It processes local audio assets via a native, single-threaded background analyzer optimization model designed to run efficiently on low-spec hardware. The engine handles beatmatching, harmonic mixing, and dynamic transitions while providing a professional, dark-environment layout.

## Interface

<!-- Placeholder for production layouts -->
*[Production UI Screenshot Reserved]*

## Features

- **Autopilot Engine:** Dynamically selects tracks based on harmonic compatibility (Camelot wheel), BPM proximity, and structural energy trajectories.
- **Phrase Detection:** Automatically aligns transitions on structural phrase boundaries, ensuring vocal clash avoidance.
- **Professional UI Canvas:** Dual waveform channels with frequency-split color coding (Low = Red, Mid = Green, High = Blue).
- **Multiple Transition Formulas:** Executes long blends, bass swaps, filter sweeps, and echo-outs autonomously.

## Architecture

Camelot uses a lightweight Tauri (Rust + WebView2) frontend communicating with a FastAPI Python sidecar over a local WebSocket. This separates the native UI rendering from the computationally intensive audio analysis and playback mixing engine, keeping execution fast and responsive on dual-core processors.

## Getting Started

*(Installation block placeholders - to be expanded as build tools are finalized)*
```bash
npm install
pip install -r sidecar/requirements.txt
npm run tauri dev
```

## Operational Guide

1. Place your `.mp3`, `.wav`, or `.flac` files into the local music library directory.
2. The Python sidecar will sequentially scan and analyze files, storing metrics in a local SQLite database.
3. Toggle "Autopilot" for autonomous mixing or use the UI decks for manual override parameters.

## Project Roadmap

- [ ] Core Engine (SQLite scanning, librosa feature extraction)
- [ ] UI Layout (Dual canvas, dark mode styling)
- [ ] Mixing Logic (SciPy phase vocoder, sounddevice streams)
- [ ] Autopilot Transitions (Harmonic scoring, phrase matching)
- [ ] Phase 2: AI Stem Separation Integration

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
