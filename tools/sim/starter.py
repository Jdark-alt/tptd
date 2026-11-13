"""The starter maze and the gates over many maps (v32): what the free maze every match starts with looks like.

  python tools/sim/starter.py --maps 1000                 # stats over map seeds 1..1000
  python tools/sim/starter.py --maps 1000 --show 4        # ... and draw the first few as text
  python tools/sim/starter.py --maps 1000 --rules '{"fixedGates": true}'

Each map is the one ai.js runMatch plays on seed s (startMap with Math.imul(s, 2654435761)), with its starter maze
(buildStarter). Per map: the gate rows (v32 picks them per match; v31 and earlier is the middle row), the starter's
walls and route length, the room the computer's mazes have on the map (mazeRoom, as a share of what they force on an
empty board with the same gates), how many starter walls the route passes on both sides (a wall cell with route
cells on two opposite sides of it), the longest straight line of such walls (a hairpin's spine), and the most route
cells one default tower covers from a starter wall (each pass of the route counts). Works on any build since v21: the
gates are read from the page if it has them, else the middle row.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import sim_page, launch
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument('--maps', type=int, default=1000)
ap.add_argument('--seed0', type=int, default=1)
ap.add_argument('--rules', default='{}')
ap.add_argument('--show', type=int, default=0, help='draw this many maps as text (# starter wall, R rock, : rough, E entry, K keep, o route)')
ap.add_argument('--out', default='', help='write one JSON line per map')
ap.add_argument('--nohair', action='store_true', help='draw only maps without a corner hairpin (with --show)')
a = ap.parse_args()

JS = r'''([seed0, n, rules]) => {
  const I = window.siegeline._i, COLS = 16, ROWS = 11, N = COLS * ROWS, out = [];
  for (let s = seed0; s < seed0 + n; s++) {
    Object.assign(I.RULES, window.__baseRules, rules);
    I.S = I.newState(); const S = I.S;
    const t0 = performance.now();
    I.startMap(Math.imul(s, 2654435761) >>> 0); I.buildStarter(); I.recompute();
    const ms = performance.now() - t0;
    const g = I.gates ? I.gates() : [80, 95], E = g[0], K = g[1];
    const P = S.path || [], on = new Set(P), solid = i => !!S.grid[i];
    const starter = []; S.grid.forEach((c, i) => { if (c && c.t === 'wall') starter.push(i); });
    // a wall passed on both sides: route cells on two opposite sides of it
    const both = i => { const c = i % COLS, r = (i / COLS) | 0;
      return (c > 0 && c < COLS - 1 && on.has(i - 1) && on.has(i + 1)) ? 'h' : (r > 0 && r < ROWS - 1 && on.has(i - COLS) && on.has(i + COLS)) ? 'v' : ''; };
    const dp = new Set(starter.filter(i => both(i)));
    // the longest straight line of such walls: a hairpin's spine (a 'h' cell has route left and right, so its spine runs up-down)
    let spine = 0, short = 0;
    for (const i of dp) {
      const ax0 = both(i) === 'h' ? COLS : 1; // the start of a maximal line: no double-passed wall before it
      if (!(dp.has(i - ax0) && both(i - ax0) === both(i))) { let k = 1; for (let j = i + ax0; dp.has(j) && both(j) === both(i); j += ax0) k++; if (k >= 3 && k <= 6) short++; }
    }
    for (const i of dp) {
      const ax = both(i) === 'h' ? COLS : 1;
      let k = 1; for (let j = i + ax; dp.has(j) && both(j) === both(i) && (ax === 1 ? ((j % COLS) !== 0) : j < N); j += ax) k++;
      spine = Math.max(spine, k);
    }
    // the most route one default tower covers from a starter wall (every route cell in range, so a second pass counts again)
    const cfg = I.defaultTower(), R = I.TS.range.steps[cfg.range], r2 = (R + 1e-9) * (R + 1e-9);
    let cover = 0;
    for (const w of starter) { const wx = w % COLS, wy = (w / COLS) | 0; let k = 0;
      for (const p of P) { const dx = (p % COLS) - wx, dy = ((p / COLS) | 0) - wy; if (dx * dx + dy * dy <= r2) k++; }
      cover = Math.max(cover, k); }
    const hair = I.hairpins ? I.hairpins().filter(tp => tp.every(i => S.grid[i])).length : 0; // corner hairpins built whole (v32)
    const room = I.mazeRoom(S.terrain), empty = I.mazeRoom(new Uint8Array(N));
    out.push({ seed: s, entry: (E / COLS) | 0, exit: (K / COLS) | 0, walls: S.starter, len: I.pathLen(S.path), room: room / empty, roomSteps: room, emptyRoom: empty,
      dp: dp.size, spine, short, hair, cover, ms: Math.round(ms), T: [...S.terrain], G: S.grid.map(c => (c ? (c.t === 'wall' ? 1 : c.t === 'rock' ? 2 : 3) : 0)), P });
  }
  return out;
}'''

def draw(m):
    on = set(m['P']); rows = []
    for r in range(11):
        row = ''
        for c in range(16):
            i = r * 16 + c
            row += ('E' if (c == 0 and r == m['entry']) else 'K' if (c == 15 and r == m['exit']) else
                    '#' if m['G'][i] == 1 else 'R' if m['G'][i] == 2 else 'o' if i in on else ':' if m['T'][i] == 1 else '.')
        rows.append('    ' + row)
    return '\n'.join(rows)

def pct(xs, q): xs = sorted(xs); return xs[min(len(xs) - 1, int(q * len(xs)))]

page = sim_page()
with sync_playwright() as p:
    b = launch(p); pg = b.new_page(); pg.goto('file://' + page); pg.wait_for_timeout(300)
    res = []
    for k in range(a.seed0, a.seed0 + a.maps, 50):
        res += pg.evaluate(JS, [k, min(50, a.seed0 + a.maps - k), json.loads(a.rules)])
    b.close()
if a.out:
    with open(a.out, 'w') as f:
        for m in res: f.write(json.dumps({k: v for k, v in m.items() if k not in ('T', 'G', 'P')}) + '\n')
n = len(res)
def line(name, key, fmt='{:.0f}'):
    xs = [m[key] for m in res]
    print(f'  {name:34s} min {fmt.format(min(xs))}  p10 {fmt.format(pct(xs, 0.1))}  median {fmt.format(pct(xs, 0.5))}  mean {fmt.format(sum(xs) / n)}  max {fmt.format(max(xs))}')
print(f'{n} maps (seeds {a.seed0}-{a.seed0 + n - 1}), rules {a.rules}')
pairs = {}
for m in res: pairs[(m['entry'], m['exit'])] = pairs.get((m['entry'], m['exit']), 0) + 1
print('  gate rows (entry, exit): ' + ', '.join(f'{e}/{x} {c}' for (e, x), c in sorted(pairs.items())))
line('starter walls', 'walls'); line('starter route length', 'len')
line('room (share of empty board)', 'room', '{:.2f}'); line('empty-board room (steps)', 'emptyRoom')
line('walls passed on both sides', 'dp'); line('longest double-passed spine', 'spine'); line('double-passed spines of 3-6', 'short'); line('best tower cover from a wall', 'cover')
line('build time (ms)', 'ms')
print(f'  starter under 25 walls: {sum(m["walls"] < 25 for m in res)}; route under 35: {sum(m["len"] < 35 for m in res)}; '
      f'room under 80%: {sum(m["room"] < 0.8 for m in res)}; a spine of 4+: {sum(m["spine"] >= 4 for m in res)}; a 3-6 spine: {sum(m["short"] >= 1 for m in res)}; a corner hairpin: {sum(m.get("hair", 0) >= 1 for m in res)}')
worst = sorted(res, key=lambda m: m['len'])[:3]
print('  shortest starter routes: ' + ', '.join(f'seed {m["seed"]} ({m["len"]}, gates {m["entry"]}/{m["exit"]}, {m["walls"]} walls)' for m in worst))
for m in [m for m in res if not a.nohair or not m.get('hair')][:a.show]:
    print(f'  seed {m["seed"]}: gates {m["entry"]}/{m["exit"]}, {m["walls"]} walls, route {m["len"]}, spine {m["spine"]}, cover {m["cover"]}\n' + draw(m))
