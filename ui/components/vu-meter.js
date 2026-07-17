/**
 * vu-meter.js — Segmented vertical VU meters driven by telemetry RMS
 * Stereo pair (L/R) per deck + master VU. Peak-hold indicator.
 */
const VUMeter = (() => {
  const meters = { a: null, b: null, master: null };
  const peaks = { a: 0, b: 0, master: 0 };
  const peakTimes = { a: 0, b: 0, master: 0 };

  function init() {
    meters.a = document.getElementById('vu-a');
    meters.b = document.getElementById('vu-b');
    meters.master = document.querySelector('.master-vu');
  }

  function setLevel(deck, level) {
    const m = meters[deck];
    if (!m) return;
    const pct = Math.max(0, Math.min(1, level)) * 100;
    const bars = m.querySelectorAll('.vu-bar');
    bars.forEach((bar, i) => {
      bar.style.height = pct + '%';
    });
    // Peak hold
    const now = performance.now();
    if (pct > peaks[deck]) {
      peaks[deck] = pct;
      peakTimes[deck] = now;
    } else if (now - peakTimes[deck] > 800) {
      peaks[deck] = Math.max(0, peaks[deck] - 2);
    }
    const peakEl = m.querySelector('.vu-peak');
    if (peakEl) peakEl.style.bottom = peaks[deck] + '%';
  }

  // Idle jitter for aesthetics (cleared by ws-client when real signal arrives)
  let _idleT = 0;
  let _idleInterval = null;
  function startIdle() {
    _idleInterval = setInterval(() => {
      _idleT += 0.05;
      const v = Math.abs(Math.sin(_idleT) * 0.04 + Math.random() * 0.015);
      setLevel('a', v);
      setLevel('b', v * 0.9);
    }, 80);
  }
  function stopIdle() {
    if (_idleInterval) { clearInterval(_idleInterval); _idleInterval = null; }
  }

  document.addEventListener('DOMContentLoaded', () => {
    init();
    startIdle();
  });

  return { init, setLevel, startIdle, stopIdle };
})();
window.VUMeter = VUMeter;