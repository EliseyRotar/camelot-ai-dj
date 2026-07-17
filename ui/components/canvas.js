/**
 * canvas.js — Stacked 3-band waveform + overview waveform painter
 * Renders the Serato-signature stacked colored waveforms.
 */
const WaveformPainter = (() => {
  const COLORS = {
    bg: '#0a0a0c',
    high: '#48cae4',
    mid: '#80ed99',
    low: '#ff7b54',
    beat: 'rgba(255,255,255,0.18)',
    bar: 'rgba(255,255,255,0.45)',
    playhead: '#ffffff',
    overview: 'rgba(200,200,210,0.5)',
    overviewEdge: 'rgba(255,255,255,0.15)',
  };

  const decks = {
    a: { detail: null, overview: null, dcx: null, ocx: null, energy: null, vocal: null, beats: null, progress: 0, scrollOffset: 0, playing: false },
    b: { detail: null, overview: null, dcx: null, ocx: null, energy: null, vocal: null, beats: null, progress: 0, scrollOffset: 0, playing: false },
  };

  function init() {
    decks.a.detail = document.getElementById('detail-a');
    decks.a.overview = document.getElementById('overview-a');
    decks.b.detail = document.getElementById('detail-b');
    decks.b.overview = document.getElementById('overview-b');

    Object.keys(decks).forEach(k => {
      const d = decks[k];
      d.dcx = d.detail.getContext('2d');
      d.ocx = d.overview.getContext('2d');
      resize(d.detail);
      resize(d.overview);
      d.energy = new Float32Array(64).fill(0.05);
      d.vocal = new Float32Array(64).fill(0);
      d.beats = [];
    });

    window.addEventListener('resize', () => {
      Object.keys(decks).forEach(k => {
        resize(decks[k].detail);
        resize(decks[k].overview);
      });
    });

    requestAnimationFrame(paint);
  }

  function resize(canvas) {
    const r = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(r.width * dpr);
    canvas.height = Math.floor(r.height * dpr);
    canvas.getContext('2d').setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function loadTrack(deck, energyCurve, vocalCurve, beatGrid) {
    const d = decks[deck];
    if (!energyCurve || energyCurve.length === 0) { clearDeck(deck); return; }
    const max = Math.max(...energyCurve, 0.001);
    d.energy = new Float32Array(energyCurve.map(v => v / max));
    d.vocal = new Float32Array(vocalCurve || []);
    d.beats = beatGrid || [];
    d.progress = 0;
    d.scrollOffset = 0;
  }

  function clearDeck(deck) {
    const d = decks[deck];
    d.energy = new Float32Array(64).fill(0.05);
    d.vocal = new Float32Array(64).fill(0);
    d.beats = [];
    d.progress = 0;
    d.scrollOffset = 0;
    d.playing = false;
  }

  function setPlayProgress(deck, frac) {
    const d = decks[deck];
    d.progress = Math.max(0, Math.min(1, frac));
    // Move overview playhead
    const ov = document.getElementById(`${deck === 'a' ? 'da' : 'db'}-overview-playhead`);
    if (ov) ov.style.left = (d.progress * 100) + '%';
  }

  function setPlaying(deck, playing) {
    decks[deck].playing = playing;
  }

  function drawDetail(d) {
    const { detail, dcx, energy, vocal, beats, progress, playing } = d;
    const W = detail.clientWidth;
    const H = detail.clientHeight;
    if (W <= 0 || H <= 0) return;

    dcx.fillStyle = COLORS.bg;
    dcx.fillRect(0, 0, W, H);

    if (!energy || energy.length === 0) return;

    // 3 stacked bands: HI (top third), MID (middle third), LO (bottom third)
    const bandH = H / 3;
    const N = 200; // number of bars across the width
    const barW = W / N;

    // Use the energy array scrolled by progress so it appears to flow past the playhead
    const totalLen = energy.length;
    if (playing) {
      d.scrollOffset = (progress * totalLen) % totalLen;
    }
    const offset = d.scrollOffset;

    for (let i = 0; i < N; i++) {
      const sampleIdx = Math.floor(((i / N) * totalLen + offset) % totalLen);
      const amp = energy[sampleIdx] || 0;
      const x = i * barW;

      // HI band (top)
      let h = amp * bandH * 0.9;
      dcx.fillStyle = COLORS.high;
      dcx.globalAlpha = 0.85;
      dcx.fillRect(x, bandH - h, Math.max(1, barW - 0.5), h);

      // MID band (middle)
      h = amp * bandH * 0.85;
      dcx.fillStyle = COLORS.mid;
      dcx.globalAlpha = 0.8;
      dcx.fillRect(x, bandH + (bandH - h) / 2, Math.max(1, barW - 0.5), h);

      // LO band (bottom)
      h = amp * bandH * 0.95;
      dcx.fillStyle = COLORS.low;
      dcx.globalAlpha = 0.9;
      dcx.fillRect(x, 2 * bandH + (bandH - h) / 2, Math.max(1, barW - 0.5), h);
    }
    dcx.globalAlpha = 1;

    // Vocal overlay — thin purple line across the middle band
    if (vocal && vocal.length > 1) {
      dcx.strokeStyle = 'rgba(179,136,255,0.6)';
      dcx.lineWidth = 1.2;
      dcx.beginPath();
      const vN = Math.min(N, vocal.length);
      for (let i = 0; i < vN; i++) {
        const x = (i / vN) * W;
        const y = bandH * 1.5 - (vocal[i] || 0) * bandH * 0.8;
        if (i === 0) dcx.moveTo(x, y); else dcx.lineTo(x, y);
      }
      dcx.stroke();
    }

    // Band separator lines
    dcx.strokeStyle = 'rgba(0,0,0,0.4)';
    dcx.lineWidth = 1;
    dcx.beginPath();
    dcx.moveTo(0, bandH); dcx.lineTo(W, bandH);
    dcx.moveTo(0, bandH * 2); dcx.lineTo(W, bandH * 2);
    dcx.stroke();

    // Beatgrid (faint vertical lines)
    if (beats && beats.length > 1) {
      const totalDur = beats[beats.length - 1] + 2;
      dcx.strokeStyle = COLORS.beat;
      dcx.lineWidth = 1;
      for (let i = 0; i < beats.length; i++) {
        const x = (beats[i] / totalDur) * W;
        const isBar = i % 4 === 0;
        dcx.globalAlpha = isBar ? 0.5 : 0.2;
        dcx.beginPath();
        dcx.moveTo(x, 0);
        dcx.lineTo(x, H);
        dcx.stroke();
      }
      dcx.globalAlpha = 1;
    }

    // Center playhead is rendered as a DOM element overlay (see index.html .detail-playhead)
  }

  function drawOverview(d) {
    const { overview, ocx, energy, progress } = d;
    const W = overview.clientWidth;
    const H = overview.clientHeight;
    if (W <= 0 || H <= 0) return;

    ocx.fillStyle = COLORS.bg;
    ocx.fillRect(0, 0, W, H);

    if (!energy || energy.length === 0) return;

    const N = Math.min(energy.length, 400);
    const barW = W / N;
    const accent = d === decks.a ? '#1a8cff' : '#ff5a1f';

    for (let i = 0; i < N; i++) {
      const idx = Math.floor((i / N) * energy.length);
      const amp = energy[idx] || 0;
      const x = i * barW;
      const h = amp * H * 0.85;
      ocx.fillStyle = amp > 0.5 ? accent : COLORS.overview;
      ocx.globalAlpha = 0.7;
      ocx.fillRect(x, (H - h) / 2, Math.max(1, barW - 0.3), h);
    }
    ocx.globalAlpha = 1;

    // Played-region dim
    const px = progress * W;
    ocx.fillStyle = 'rgba(0,0,0,0.4)';
    ocx.fillRect(0, 0, px, H);
  }

  function paint() {
    drawDetail(decks.a);
    drawDetail(decks.b);
    drawOverview(decks.a);
    drawOverview(decks.b);
    requestAnimationFrame(paint);
  }

  document.addEventListener('DOMContentLoaded', () => init());

  return { init, loadTrack, clearDeck, setPlayProgress, setPlaying };
})();
window.WaveformPainter = WaveformPainter;