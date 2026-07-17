/**
 * knobs.js — Rotary knob component with vertical-drag interaction
 * Drag up/down to change value, double-click to reset.
 * Knob rotation: -135deg (min) to +135deg (max), 270deg sweep.
 */
const Knobs = (() => {
  const SWEEP = 270;
  const activeKnob = { el: null, startY: 0, startVal: 0 };
  const draggingKnobs = new Set();

  function isDragging(knob) { return draggingKnobs.has(knob); }
  function isAnyDragging() { return draggingKnobs.size > 0; }

  function valueToRotation(v) {
    // v: 0..1 -> rotation from -135 to +135
    return (v - 0.5) * SWEEP;
  }

  function applyRotation(knob, value) {
    const ind = knob.querySelector('.knob-indicator');
    if (ind) ind.style.transform = `translateX(-50%) rotate(${valueToRotation(value)}deg)`;
    knob.dataset.value = value;
  }

  function getValue(knob) {
    return parseFloat(knob.dataset.value || '0.5');
  }

  function setValue(knob, value, emit = true) {
    value = Math.max(0, Math.min(1, value));
    applyRotation(knob, value);
    if (emit && knob._onChange) knob._onChange(value);
  }

  function bind(knob, onChange) {
    knob._onChange = onChange;
    applyRotation(knob, getValue(knob));

    knob.addEventListener('mousedown', (e) => {
      activeKnob.el = knob;
      activeKnob.startY = e.clientY;
      activeKnob.startVal = getValue(knob);
      draggingKnobs.add(knob);
      e.preventDefault();
    });

    knob.addEventListener('dblclick', () => {
      // EQ knobs reset to 0.5 (center), gain to 0.75, filter to 0.5
      const def = knob.classList.contains('eq-knob') || knob.classList.contains('filter-knob') ? 0.5 : 0.75;
      setValue(knob, def);
    });

    knob.addEventListener('wheel', (e) => {
      const delta = -Math.sign(e.deltaY) * 0.03;
      setValue(knob, getValue(knob) + delta);
      e.preventDefault();
    }, { passive: false });
  }

  document.addEventListener('mousemove', (e) => {
    if (!activeKnob.el) return;
    const dy = activeKnob.startY - e.clientY;
    const newVal = activeKnob.startVal + (dy * 0.005);
    setValue(activeKnob.el, newVal);
  });

  document.addEventListener('mouseup', () => {
    if (activeKnob.el) draggingKnobs.delete(activeKnob.el);
    activeKnob.el = null;
  });

  function initAll() {
    // All knobs get default rotation applied
    document.querySelectorAll('.knob').forEach(k => {
      applyRotation(k, getValue(k));
    });
  }

  document.addEventListener('DOMContentLoaded', initAll);

  return { bind, getValue, setValue, applyRotation, isDragging, isAnyDragging };
})();
window.Knobs = Knobs;