/**
 * library.js — Bottom library table with sortable track list
 * Fetches the full library via WS and renders a Serato-style table.
 */
const Library = (() => {
  let _tracks = [];
  let _filter = '';
  let _loadedA = null;
  let _loadedB = null;
  let _playing = null;

  function render() {
    const body = document.getElementById('lib-table-body');
    const filtered = _tracks.filter(t => {
      if (!_filter) return true;
      const s = _filter.toLowerCase();
      return (t.title || '').toLowerCase().includes(s) ||
             (t.artist || '').toLowerCase().includes(s) ||
             (t.filepath || '').toLowerCase().includes(s);
    });

    document.getElementById('lib-count').textContent = `${_tracks.length} tracks`;
    document.getElementById('stat-library').textContent = _tracks.length;

    if (filtered.length === 0) {
      body.innerHTML = '<div class="table-empty">' + (_tracks.length === 0 ? 'No tracks loaded. Click SCAN to analyze a music folder.' : 'No matches.') + '</div>';
      return;
    }

    body.innerHTML = filtered.map((t, i) => {
      const cls = ['lib-row'];
      if (t.id === _loadedA) cls.push('loaded-a');
      if (t.id === _loadedB) cls.push('loaded-b');
      if (t.id === _playing) cls.push('playing');
      const title = escapeHtml(t.title || t.filepath?.split(/[\\/]/).pop() || '—');
      const artist = escapeHtml(t.artist || '—');
      const dur = fmtTime(t.duration);
      return `<div class="${cls.join(' ')}" data-id="${t.id}">
        <div class="col col-num">${i + 1}</div>
        <div class="col col-title">${title}</div>
        <div class="col col-artist">${artist}</div>
        <div class="col col-bpm">${t.bpm ? t.bpm.toFixed(1) : '---'}</div>
        <div class="col col-key">${t.key_camelot || '--'}</div>
        <div class="col col-time">${dur}</div>
        <div class="col col-lufs">${t.lufs_integrated ? t.lufs_integrated.toFixed(0) : '--'}</div>
      </div>`;
    }).join('');

    body.querySelectorAll('.lib-row').forEach(row => {
      row.addEventListener('click', () => {
        const id = parseInt(row.dataset.id, 10);
        // Load to the inactive deck by default
        if (window.CamelotWS) CamelotWS.loadNextDeck(id);
      });
    });
  }

  function setTracks(tracks) {
    _tracks = tracks || [];
    render();
  }

  function markLoaded(deck, trackId) {
    if (deck === 'a') _loadedA = trackId;
    else _loadedB = trackId;
    render();
  }

  function markPlaying(trackId) {
    _playing = trackId;
    render();
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmtTime(sec) {
    if (!sec || isNaN(sec)) return '--:--';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  }

  document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('lib-search-input');
    input.addEventListener('input', () => { _filter = input.value; render(); });
  });

  return { setTracks, markLoaded, markPlaying, render };
})();
window.Library = Library;