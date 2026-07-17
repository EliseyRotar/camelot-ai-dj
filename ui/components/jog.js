/**
 * jog.js — Jog wheel rotation animation + scratch interaction
 * The platter rotates slowly during playback; drag to "scratch".
 */
const JogWheel = (() => {
  const jogs = { a: null, b: null };
  const state = {
    a: { rotation: 0, targetVel: 0, dragging: false, lastAngle: 0 },
    b: { rotation: 0, targetVel: 0, dragging: false, lastAngle: 0 },
  };

  function init() {
    jogs.a = document.getElementById('da-jog');
    jogs.b = document.getElementById('db-jog');
    setupDrag('a');
    setupDrag('b');
    requestAnimationFrame(tick);
  }

  function setupDrag(deck) {
    const wheel = jogs[deck];
    if (!wheel) return;
    const indicator = document.getElementById(`${deck === 'a' ? 'da' : 'db'}-jog-indicator`);

    function angleFrom(e) {
      const r = wheel.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      return Math.atan2(e.clientY - cy, e.clientX - cx) * 180 / Math.PI;
    }

    wheel.addEventListener('mousedown', (e) => {
      state[deck].dragging = true;
      state[deck].lastAngle = angleFrom(e);
      e.preventDefault();
    });

    document.addEventListener('mousemove', (e) => {
      if (!state[deck].dragging) return;
      const a = angleFrom(e);
      let delta = a - state[deck].lastAngle;
      if (delta > 180) delta -= 360;
      if (delta < -180) delta += 360;
      state[deck].rotation += delta;
      state[deck].lastAngle = a;
      if (indicator) indicator.style.transform = `translateX(-50%) rotate(${state[deck].rotation}deg)`;
    });

    document.addEventListener('mouseup', () => {
      state[deck].dragging = false;
    });
  }

  function setPlaying(deck, playing) {
    // ~33 RPM = 2 deg per frame at 60fps
    state[deck].targetVel = playing ? 2.0 : 0;
  }

  function tick() {
    ['a', 'b'].forEach(deck => {
      if (!state[deck].dragging && state[deck].targetVel > 0) {
        state[deck].rotation += state[deck].targetVel;
        const ind = document.getElementById(`${deck === 'a' ? 'da' : 'db'}-jog-indicator`);
        if (ind) ind.style.transform = `translateX(-50%) rotate(${state[deck].rotation}deg)`;
      }
    });
    requestAnimationFrame(tick);
  }

  document.addEventListener('DOMContentLoaded', init);
  return { init, setPlaying };
})();
window.JogWheel = JogWheel;