"""The board's art, at a glance (v29): every tower kind and element on one board, then a wave with every unit class,
armor, regeneration and resists, screenshotted at 2× (and zoomed crops), plus the frame rate of a busy wave.

    python tools/art/gallery.py                # screenshots land in tools/.build/shots/art
    python tools/art/gallery.py --perf 4       # also the frame times of a 160-unit wave, the CPU slowed 4×

The towers and the army are put straight into the state through window.siegeline (no rules are checked: it's a
picture, not a match). Headless Chromium rasterises in software, so its frame rates are a floor, not what a player sees.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, launch
from playwright.sync_api import sync_playwright

OUT = os.path.join(BUILD, 'shots', 'art'); os.makedirs(OUT, exist_ok=True)
PAGE = write_build('art.html', game_html())
TOWERS = '''[
 [2,2, {}], [2,4, {rate:0}], [2,6, {rate:5, range:6}], [2,8, {rate:4, splash:2}],
 [5,2, {slow:true}], [5,4, {rate:0, poison:true}], [5,6, {rate:5, range:7, chain:3, accuracy:3}], [5,8, {rate:4, splash:3, slow:true}],
 [8,2, {dps:8, chain:3}], [8,4, {rate:1, slow:true, poison:true}], [8,6, {rate:4, range:3, dps:6, accuracy:2}], [8,8, {rate:4, splash:1, poison:true}],
]'''
ARMY = '''(per) => { const sl = window.siegeline, S = sl.state; S.aFree = 999999; const C = ['#ffb547', '#e5472b', '#ff7b36', '#ff6fa8'];
  S.designs = [
    { name: 'Dart', color: C[0], hp: 2, speed: 6, armor: 0, regen: 0, resist: 'splash+frost', count: per, tl: { s: 0, e: 0.5, pos: null } },
    { name: 'Bug', color: C[1], hp: 5, speed: 3, armor: 2, regen: 2, resist: 'none', count: per, tl: { s: 0.1, e: 0.6, pos: null } },
    { name: 'Tank', color: C[2], hp: 8, speed: 1, armor: 3, regen: 0, resist: 'shock', count: Math.max(1, per >> 1), tl: { s: 0, e: 0.6, pos: null } },
    { name: 'Swarm', color: C[3], hp: 0, speed: 4, armor: 1, regen: 0, resist: 'none', count: per * 2, tl: { s: 0.05, e: 0.4, pos: null } },
  ]; sl.refresh(); }'''

def match(pg, per):
    pg.goto('file://' + PAGE); pg.wait_for_timeout(600)
    pg.evaluate('() => { const R = window.siegeline.rules; R.roughShare = 0.05; R.rockShare = 0.05; R.planSecs = 0; R.starterPresses = 0; }')
    pg.click('#info-go'); pg.click('#mode-local'); pg.wait_for_timeout(500); pg.click('#ov-hand'); pg.wait_for_timeout(100)
    pg.evaluate('''() => { const sl = window.siegeline, S = sl.state; S.dFree = 99999; const T = ''' + TOWERS + ''';
      let n = 0; for (const [c, r, o] of T) { const i = r * 16 + c; S.terrain[i] = 0; S.grid[i] = { t: 'tower', cfg: { range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: 0, ...o }, n: ++n, fee: 0, fresh: true, cd: 0, ang: Math.PI, kick: 0, dealt: 0 }; }
      for (const r of [0,1,3,5,7,9,10]) { const i = r * 16 + 11; if (!S.grid[i] && !S.terrain[i]) S.grid[i] = { t: 'wall', fresh: true }; }
      S.towerSeq = n; S.gridVer++; sl.refresh(); }''')
    pg.wait_for_timeout(700)

def board(pg):
    return pg.evaluate('() => { const r = document.querySelector("#board").getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }')

def wave(pg, per):
    pg.click('#def-lock'); pg.wait_for_timeout(500); pg.click('#ov-hand'); pg.wait_for_timeout(100)
    pg.evaluate(ARMY, per); pg.wait_for_timeout(300)
    pg.click('#atk-lock'); pg.wait_for_timeout(300)
    if not pg.is_visible('#ov-hand'): pg.click('#atk-lock')
    pg.wait_for_selector('#ov-hand', state='visible'); pg.wait_for_timeout(500)

ap = argparse.ArgumentParser(); ap.add_argument('--perf', type=float, default=0, help='also time a busy wave, the CPU slowed this many times (1 = not slowed)')
args = ap.parse_args()
with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=2); pg = ctx.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e))); pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    match(pg, 6)
    x, y, w, h = board(pg)
    pg.screenshot(path=f'{OUT}/towers.png'); pg.screenshot(path=f'{OUT}/towers_zoom.png', clip={'x': x + 60, 'y': y + 60, 'width': 600, 'height': 560})
    wave(pg, 6); pg.click('#ov-hand')
    for k, wt in enumerate((600, 2600, 2000, 2500, 2500)):
        pg.wait_for_timeout(wt)
        pg.screenshot(path=f'{OUT}/wave{k}.png'); pg.screenshot(path=f'{OUT}/wave{k}_zoom.png', clip={'x': x, 'y': y + 60, 'width': 640, 'height': 520})
    print(f'screenshots in {OUT}; errors: {errs[:6]}')
    if args.perf:
        match(pg, 40); wave(pg, 40)
        if args.perf > 1: ctx.new_cdp_session(pg).send('Emulation.setCPUThrottlingRate', {'rate': args.perf})
        pg.click('#ov-hand'); pg.wait_for_timeout(3000)
        ts = pg.evaluate('''() => new Promise(res => { const ts = []; const t0 = performance.now(); const f = t => { ts.push(t); if (t - t0 < 6000) requestAnimationFrame(f); else res(ts); }; requestAnimationFrame(f); })''')
        d = sorted(ts[i + 1] - ts[i] for i in range(len(ts) - 1))
        print(f'CPU ×{args.perf:g}: {len(d)} frames in 6 s, median {d[len(d) // 2]:.1f} ms, p95 {d[int(len(d) * 0.95)]:.1f} ms; '
              f'{pg.evaluate("() => window.siegeline.state.units.length")} units on the board')
    b.close()
