/**
 * theme.js — view toggling, scan overlay, global UI helpers
 */
const CamelotUI = (() => {
  function setView(view) {
    document.getElementById('app').dataset.view = view;
    document.querySelectorAll('.toggle-btn[data-view]').forEach(b => {
      b.classList.toggle('active', b.dataset.view === view);
    });
  }

  function showScanOverlay(show) {
    const ov = document.getElementById('scan-overlay');
    if (show) ov.classList.add('visible');
    else ov.classList.remove('visible');
  }

  function setScanProgress(pct, file) {
    document.getElementById('scan-bar-fill').style.width = (pct * 100).toFixed(0) + '%';
    document.getElementById('scan-current-file').textContent = file || '';
  }

  function setSidecarStatus(state) {
    const dot = document.getElementById('sidecar-dot');
    const txt = document.getElementById('stat-sidecar');
    dot.classList.remove('connected', 'streaming');
    if (state === 'connected') {
      dot.classList.add('connected');
      txt.textContent = 'CONNECTED';
    } else if (state === 'streaming') {
      dot.classList.add('streaming');
      txt.textContent = 'STREAMING';
    } else {
      txt.textContent = 'OFFLINE';
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.toggle-btn[data-view]').forEach(btn => {
      btn.addEventListener('click', () => setView(btn.dataset.view));
    });
  });

  return { setView, showScanOverlay, setScanProgress, setSidecarStatus };
})();
window.CamelotUI = CamelotUI;