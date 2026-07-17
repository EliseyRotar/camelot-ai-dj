/**
 * ws-client.js — Camelot Sidecar Bridge
 * Connects to the FastAPI sidecar WebSocket, dispatches telemetry to all UI modules,
 * and wires every button, knob, fader, and pad to engine commands.
 */
const CamelotWS = (() => {
  const WS_URL = 'ws://127.0.0.1:8765/ws/telemetry';
  let ws = null;
  let reconnectTimer = null;
  let _autopilotOn = false;
  let _activeTechnique = 'LongBlend';
  let _loadedTrackId = { a: null, b: null };
  const _dragging = { a: { fader: false, pitch: false, knob: false }, b: { fader: false, pitch: false, knob: false }, cross: false };

  const els = {};
  function el(id) { return els[id] || (els[id] = document.getElementById(id)); }

  function connect() {
    if (ws && ws.readyState <= 1) return;
    try {
      ws = new WebSocket(WS_URL);
    } catch (e) {
      reconnectTimer = setTimeout(connect, 3000);
      return;
    }

    ws.onopen = () => {
      clearTimeout(reconnectTimer);
      CamelotUI.setSidecarStatus('connected');
      AutopilotFeed.setStatus('READY');
      send({ cmd: 'get_library_full' });
      send({ cmd: 'get_status' });
    };

    ws.onmessage = (evt) => {
      try { handleMessage(JSON.parse(evt.data)); } catch (e) { console.warn('WS parse:', e); }
    };

    ws.onclose = () => {
      CamelotUI.setSidecarStatus('offline');
      AutopilotFeed.setStatus('OFFLINE', 'var(--vu-red)');
      reconnectTimer = setTimeout(connect, 3000);
    };

    ws.onerror = () => { try { ws.close(); } catch (e) {} };
  }

  function send(data) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(data));
  }

  function loadNextDeck(trackId) { send({ cmd: 'load_next_deck', track_id: trackId }); }
  function loadDeck(deck, trackId) { send({ cmd: 'load_deck', deck: deck, track_id: trackId }); }

  function handleMessage(msg) {
    switch (msg.type) {

      case 'telemetry': {
        const { deck_a, deck_b, master_bpm, active_deck, transition, stream_started } = msg;
        if (master_bpm) el('bpm-value').textContent = master_bpm.toFixed(2);
        if (active_deck) el('stat-active-deck').textContent = active_deck.toUpperCase();

        if (stream_started === true) CamelotUI.setSidecarStatus('streaming');
        else if (stream_started === false && ws && ws.readyState === 1) CamelotUI.setSidecarStatus('connected');

        if (deck_a) updateDeck('a', deck_a);
        if (deck_b) updateDeck('b', deck_b);

        if (transition) {
          // (no progress bar in this layout; technique status shown in footer)
          if (transition.active_technique) el('stat-technique').textContent = transition.active_technique;
          else if (!transition.active) el('stat-technique').textContent = _activeTechnique;
        }
        break;
      }

      case 'library': {
        if (msg.count !== undefined) el('stat-library').textContent = msg.count;
        send({ cmd: 'get_library_full' });
        break;
      }

      case 'library_full': {
        Library.setTracks(msg.tracks || []);
        break;
      }

      case 'recommendations': {
        AutopilotFeed.renderRecs(msg.recs);
        break;
      }

      case 'scan_progress': {
        CamelotUI.showScanOverlay(true);
        CamelotUI.setScanProgress(msg.progress, msg.current_file);
        if (msg.progress >= 1.0) {
          setTimeout(() => CamelotUI.showScanOverlay(false), 1200);
          send({ cmd: 'get_library' });
        }
        break;
      }

      case 'track_loaded': {
        const deckKey = (msg.deck || '').replace('deck_', '');
        updateDeckTrackInfo(deckKey, msg.track);
        _loadedTrackId[deckKey] = msg.track.id;
        Library.markLoaded(deckKey, msg.track.id);
        if (msg.features) {
          WaveformPainter.loadTrack(deckKey, msg.features.energy_curve, msg.features.vocal_curve, msg.features.beat_grid);
        } else {
          WaveformPainter.clearDeck(deckKey);
        }
        // Auto-request recommendations for the active deck
        const activeLetter = (el('stat-active-deck')?.textContent || 'A').toLowerCase();
        if (deckKey === activeLetter) send({ cmd: 'get_recommendations', track_id: msg.track.id });
        break;
      }

      case 'engine_state': {
        if (msg.autopilot_enabled !== undefined) {
          _autopilotOn = !!msg.autopilot_enabled;
          const btn = el('btn-autopilot');
          btn.dataset.active = _autopilotOn ? 'true' : 'false';
        }
        if (msg.armed_technique) {
          _activeTechnique = msg.armed_technique;
          syncTechniqueButtons();
          el('stat-technique').textContent = prettyTech(_activeTechnique);
        }
        if (msg.master_bpm) el('bpm-value').textContent = msg.master_bpm.toFixed(2);
        if (msg.active_deck) el('stat-active-deck').textContent = msg.active_deck.toUpperCase();
        break;
      }

      case 'technique_changed': {
        _activeTechnique = msg.technique;
        syncTechniqueButtons();
        el('stat-technique').textContent = prettyTech(_activeTechnique);
        break;
      }

      case 'autopilot_state': {
        _autopilotOn = !!msg.enabled;
        el('btn-autopilot').dataset.active = _autopilotOn ? 'true' : 'false';
        break;
      }

      case 'master_bpm': {
        if (msg.bpm) el('bpm-value').textContent = msg.bpm.toFixed(2);
        break;
      }

      case 'ack': break;
      case 'error': { console.warn('Sidecar:', msg.message); AutopilotFeed.setStatus('ERROR', 'var(--vu-red)'); break; }
      case 'status': { if (msg.status) { if (msg.status.master_bpm) el('bpm-value').textContent = msg.status.master_bpm.toFixed(2); if (msg.status.active_deck) el('stat-active-deck').textContent = msg.status.active_deck.toUpperCase(); } break; }
    }
  }

  function updateDeck(key, data) {
    const prefix = key === 'a' ? 'da' : 'db';
    // Skip telemetry-driven updates for controls the user is actively dragging
    if (data.gain !== undefined && !_dragging[key].fader) {
      Knobs.setValue(el(`${prefix}-gain-knob`), data.gain, false);
      const cap = el(`${prefix}-fader-cap`);
      if (cap) cap.style.top = ((1 - data.gain) * 100) + '%';
    }
    if (data.eq_high !== undefined && !Knobs.isDragging(el(`${prefix}-hi-knob`))) Knobs.setValue(el(`${prefix}-hi-knob`), data.eq_high, false);
    if (data.eq_mid !== undefined && !Knobs.isDragging(el(`${prefix}-mid-knob`))) Knobs.setValue(el(`${prefix}-mid-knob`), data.eq_mid, false);
    if (data.eq_low !== undefined && !Knobs.isDragging(el(`${prefix}-lo-knob`))) Knobs.setValue(el(`${prefix}-lo-knob`), data.eq_low, false);

    // Playhead + time
    if (data.play_progress !== undefined) {
      WaveformPainter.setPlayProgress(key, data.play_progress);
      const dur = data.duration || 0;
      const pos = data.play_progress * dur;
      el(`${prefix}-time-elapsed`).textContent = fmtTime(pos);
      el(`${prefix}-time-remaining`).textContent = '-' + fmtTime(dur - pos);
    }

    // VU
    if (data.rms !== undefined) {
      VUMeter.setLevel(key, data.rms);
      if (data.is_playing || data.rms > 0.01) VUMeter.stopIdle();
    }

    // Play button state
    const playBtn = el(`${prefix}-play`);
    if (playBtn && data.is_playing !== undefined) {
      playBtn.dataset.playing = data.is_playing ? 'true' : 'false';
      WaveformPainter.setPlaying(key, data.is_playing);
      JogWheel.setPlaying(key, data.is_playing);
    }
  }

  function updateDeckTrackInfo(key, track) {
    const prefix = key === 'a' ? 'da' : 'db';
    const title = el(`${prefix}-title`);
    const artist = el(`${prefix}-artist`);
    title.textContent = track.title || track.filepath?.split(/[\\/]/).pop() || 'Unknown';
    title.classList.remove('empty');
    artist.textContent = track.artist || '—';
    el(`${prefix}-key`).textContent = track.key_camelot || '--';
    el(`${prefix}-bpm`).textContent = track.bpm ? track.bpm.toFixed(2) : '---.--';
  }

  function fmtTime(sec) {
    if (!sec || sec < 0 || isNaN(sec)) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  function prettyTech(t) {
    return ({ LongBlend: 'Long Blend', BassSwap: 'Bass Swap', QuickCut: 'Quick Cut', EchoOut: 'Echo Out' })[t] || t;
  }

  function syncTechniqueButtons() {
    document.querySelectorAll('.tech-btn[data-tech]').forEach(b => {
      b.classList.toggle('armed', b.dataset.tech === _activeTechnique);
    });
  }

  // ── Wire all controls ─────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    // SCAN (shift-click = force re-analyze everything)
    el('btn-scan').addEventListener('click', (e) => {
      const force = e.shiftKey;
      const msg = force
        ? 'FORCE re-analyze all files. This will re-run librosa on every track (slow). Enter path:'
        : 'Scan music library folder (skips files already analyzed). Enter path:';
      const path = prompt(msg, 'C:\\Users\\Admin\\Music');
      if (path) send({ cmd: 'scan', path: path, force: force });
    });

    // AUTOPILOT toggle
    el('btn-autopilot').addEventListener('click', () => {
      _autopilotOn = !_autopilotOn;
      el('btn-autopilot').dataset.active = _autopilotOn ? 'true' : 'false';
      send({ cmd: 'set_autopilot', enabled: _autopilotOn });
    });

    // PLAY / CUE / SYNC per deck
    ['a', 'b'].forEach(d => {
      el(`d${d}-play`).addEventListener('click', () => send({ cmd: 'fire', deck: d }));
      el(`d${d}-cue`).addEventListener('click', () => send({ cmd: 'cue', deck: d }));
      el(`d${d}-sync`).addEventListener('click', (e) => {
        const on = e.currentTarget.dataset.active !== 'true';
        e.currentTarget.dataset.active = on ? 'true' : 'false';
        // Sync just sets the deck's bpm to master for now
        send({ cmd: 'set_master_bpm', bpm: parseFloat(el('bpm-value').textContent) });
      });
    });

    // EQ/Gain/Filter knobs per deck
    ['a', 'b'].forEach(d => {
      Knobs.bind(el(`d${d}-gain-knob`), v => send({ cmd: 'set_deck_eq', deck: d, band: 'gain', value: v }));
      Knobs.bind(el(`d${d}-hi-knob`),   v => send({ cmd: 'set_deck_eq', deck: d, band: 'high', value: v }));
      Knobs.bind(el(`d${d}-mid-knob`),  v => send({ cmd: 'set_deck_eq', deck: d, band: 'mid', value: v }));
      Knobs.bind(el(`d${d}-lo-knob`),   v => send({ cmd: 'set_deck_eq', deck: d, band: 'low', value: v }));
      // Filter knob — no backend support yet, just visual
      Knobs.bind(el(`d${d}-filter-knob`), () => {});
    });

    // Master gain knob (no backend support, visual only for now)
    Knobs.bind(el('master-gain-knob'), () => {});

    // Channel faders (drag)
    ['a', 'b'].forEach(d => {
      const fader = el(`d${d}-fader`);
      const cap = el(`d${d}-fader-cap`);
      let dragging = false;
      cap.addEventListener('mousedown', () => { dragging = true; _dragging[d].fader = true; });
      document.addEventListener('mouseup', () => { if (dragging) { dragging = false; _dragging[d].fader = false; } });
      document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const r = fader.querySelector('.fader-track').getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height));
        cap.style.top = ((1 - pct) * 100) + '%';
        send({ cmd: 'set_deck_eq', deck: d, band: 'gain', value: pct });
      });
    });

    // Pitch faders (drag)
    ['a', 'b'].forEach(d => {
      const pf = el(`d${d}-pitch`);
      const cap = el(`d${d}-pitch-cap`);
      const readout = el(`d${d}-pitch-readout`);
      let dragging = false;
      cap.addEventListener('mousedown', () => { dragging = true; _dragging[d].pitch = true; });
      document.addEventListener('mouseup', () => { if (dragging) { dragging = false; _dragging[d].pitch = false; } });
      document.addEventListener('mousemove', (e) => {
        if (!dragging) return;
        const r = pf.querySelector('.pitch-track').getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height));
        cap.style.top = (pct * 100) + '%';
        const pitchPct = (pct - 0.5) * 16; // -8% to +8%
        readout.textContent = (pitchPct >= 0 ? '+' : '') + pitchPct.toFixed(2) + '%';
      });
    });

    // Crossfader
    const xfader = el('crossfader');
    const xcap = el('crossfader-cap');
    let xdrag = false;
    xcap.addEventListener('mousedown', () => { xdrag = true; _dragging.cross = true; });
    document.addEventListener('mouseup', () => { if (xdrag) { xdrag = false; _dragging.cross = false; } });
    document.addEventListener('mousemove', (e) => {
      if (!xdrag) return;
      const r = xfader.querySelector('.crossfader-track').getBoundingClientRect();
      const pct = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
      xcap.style.left = (pct * 100) + '%';
      send({ cmd: 'set_deck_eq', deck: 'a', band: 'gain', value: 1.0 - pct });
      send({ cmd: 'set_deck_eq', deck: 'b', band: 'gain', value: pct });
    });

    // Technique buttons
    document.querySelectorAll('.tech-btn[data-tech]').forEach(btn => {
      btn.addEventListener('click', () => {
        _activeTechnique = btn.dataset.tech;
        syncTechniqueButtons();
        el('stat-technique').textContent = prettyTech(_activeTechnique);
        send({ cmd: 'set_technique', technique: _activeTechnique });
      });
    });

    el('tech-trigger').addEventListener('click', () => send({ cmd: 'trigger_transition' }));

    // Hot cue pads (visual only — light up when clicked)
    document.querySelectorAll('.pad').forEach(pad => {
      pad.addEventListener('click', () => {
        const isSet = pad.dataset.set === '1';
        if (isSet) { pad.dataset.set = '0'; }
        else { pad.dataset.set = '1'; }
      });
    });

    // Loop buttons (visual toggle)
    document.querySelectorAll('.loop-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        btn.parentElement.querySelectorAll('.loop-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    // Pad mode tabs
    document.querySelectorAll('.pad-mode').forEach(btn => {
      btn.addEventListener('click', () => {
        btn.parentElement.querySelectorAll('.pad-mode').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    // Library tree
    document.querySelectorAll('.tree-item').forEach(item => {
      item.addEventListener('click', () => {
        document.querySelectorAll('.tree-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
      });
    });

    // Start WS
    connect();
  });

  return { send, loadNextDeck, loadDeck };
})();
window.CamelotWS = CamelotWS;