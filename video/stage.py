"""Build stage.html: the kit page re-laid-out for a 1280x720 stage, with a virtual clock, a drawn cursor and a drawn caret."""
import re, pathlib
HERE = pathlib.Path(__file__).parent
src = (HERE.parent / 'index.html').read_text()

CSS = """
<style id="stage">
  html, body { width: 1600px; height: 900px; overflow: hidden; }
  .board { max-width: none; width: 1280px; height: 720px; margin: 90px 160px; padding: 34px 34px 26px; column-gap: 0;
           grid-template-columns: 1fr 1.4fr 1fr; grid-template-rows: auto 1fr 1.12fr; }
  .head { grid-column: 1 / -1; grid-row: 1; }
  .cell { min-height: 0; padding: 0; }
  .cell.hero { grid-column: 2; grid-row: 2; min-height: 0; }
  .cell.tall { grid-column: 2; grid-row: 3; }
  .board > figure:nth-of-type(2) { grid-column: 1; grid-row: 2; }
  .board > figure:nth-of-type(3) { grid-column: 1; grid-row: 3; }
  .board > figure:nth-of-type(5) { grid-column: 3; grid-row: 2; }
  .board > figure:nth-of-type(6) { grid-column: 3; grid-row: 3; }
  .field input { caret-color: transparent; }
  #cur { position: fixed; left: 0; top: 0; z-index: 99; width: 22px; height: 22px; pointer-events: none; will-change: transform;
         filter: drop-shadow(0 2px 3px rgba(0,0,0,.35)); transform-origin: 0 0; }
  #caret { position: absolute; z-index: 4; top: 14px; width: 1.5px; height: 20px; border-radius: 1px; background: var(--ink); pointer-events: none; opacity: 0; }
</style>
"""
CUR = """
<svg id="cur" viewBox="0 0 22 22"><path d="M3 2 L3 17.2 L7.1 13.6 L9.9 19.9 L12.5 18.8 L9.7 12.6 L15.2 12.4 Z" fill="#111" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>
"""
CLOCK = """
<script>
(() => {
  let vt = 1000, q = [], id = 0;
  window.requestAnimationFrame = f => { q.push([++id, f]); return id; };
  window.cancelAnimationFrame = i => { q = q.filter(e => e[0] !== i); };
  performance.now = () => vt;
  const seen = new WeakSet();
  let caretT = 0, lastVal = null, lastPos = -1;
  const mctx = document.createElement('canvas').getContext('2d');
  window.__step = (dt, x, y, down) => {
    vt += dt;
    const run = q; q = [];
    for (const [, f] of run) f(vt);
    for (const a of document.getAnimations()) {
      if (!seen.has(a)) { seen.add(a); a.pause(); a.currentTime = dt; }
      else a.currentTime += dt;
      const end = a.effect.getComputedTiming().endTime;
      if (a.currentTime >= end) a.finish();
    }
    const cur = document.getElementById('cur');
    cur.style.transform = `translate(${x - 3}px, ${y - 2}px) scale(${down ? .9 : 1})`;
    // drawn caret
    const input = document.querySelector('#field input');
    let c = document.getElementById('caret');
    if (!c) { c = document.createElement('i'); c.id = 'caret'; input.parentElement.appendChild(c); }
    if (document.activeElement === input) {
      const cs = getComputedStyle(input), pos = input.selectionEnd ?? 0;
      if (input.value !== lastVal || pos !== lastPos) { caretT = 0; lastVal = input.value; lastPos = pos; }
      mctx.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const text = input.value.slice(0, pos);
      const cx = parseFloat(cs.paddingLeft) + mctx.measureText(text).width + (parseFloat(cs.letterSpacing) || 0) * text.length - input.scrollLeft;
      c.style.left = cx + 'px';
      caretT += dt;
      c.style.opacity = (caretT % 1060) < 600 ? .9 : 0;
    } else { c.style.opacity = 0; lastVal = null; }
  };
})();
</script>
"""
n = src.count('Math.min(2, devicePixelRatio || 1)')
assert n == 2, n
out = src.replace('Math.min(2, devicePixelRatio || 1)', '(devicePixelRatio || 1)')
assert out.count('</head>') == 1 and out.count('<main class="board">') == 1
out = out.replace('</head>', CSS + CLOCK + '</head>').replace('<main class="board">', CUR + '<main class="board">')
(HERE / 'stage.html').write_text(out)
print('stage.html written')
