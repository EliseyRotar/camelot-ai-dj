/**
 * autopilot-feed.js — Renders top-5 recommendation cards in the mixer center
 * Only repaints when the recommendation set actually changes.
 */
const AutopilotFeed = (() => {
  let _lastJson = '';

  function renderRecs(recs) {
    const json = JSON.stringify(recs);
    if (json === _lastJson) return;
    _lastJson = json;

    const list = document.getElementById('rec-list');
    if (!recs || recs.length === 0) {
      list.innerHTML = '<div class="rec-empty">No compatible tracks found in library</div>';
      return;
    }

    list.innerHTML = recs.map((rec, i) => {
      const t = rec.track;
      const score = Math.round(rec.score);
      const scoreColor = score > 70 ? 'var(--vu-green)' : score > 40 ? 'var(--vu-yellow)' : 'var(--vu-red)';
      const title = escapeHtml(t.title || t.filepath?.split(/[\\/]/).pop() || '—');
      return `
        <div class="rec-card" data-track-id="${t.id}">
          <span class="rec-rank">${i + 1}</span>
          <span class="rec-title">${title}</span>
          <span class="rec-score" style="color:${scoreColor}">${score}</span>
          <span class="rec-key">${t.key_camelot || '--'}</span>
          <span class="rec-bpm">${t.bpm ? t.bpm.toFixed(0) : '---'}</span>
        </div>`;
    }).join('');

    list.querySelectorAll('.rec-card').forEach(card => {
      card.addEventListener('click', () => {
        const id = parseInt(card.dataset.trackId, 10);
        if (window.CamelotWS) CamelotWS.loadNextDeck(id);
      });
    });
  }

  function setStatus(msg, color) {
    const el = document.getElementById('ap-status');
    if (el) { el.textContent = msg; el.style.color = color || 'var(--vu-green)'; }
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  return { renderRecs, setStatus };
})();
window.AutopilotFeed = AutopilotFeed;