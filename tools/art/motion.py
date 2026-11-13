"""Turrets with weight and units banking into corners (v32): plays a wave on the starter maze of a fixed map with one
tower of each kind beside the route and an army of fast and slow units, at 1x, and reports how far each drawn barrel
was off its target when the shot left (AIMSTAT: the simulation's exact angle at the shot against the angle drawn), by
kind. With --video it records the wave (MP4 through ffmpeg) and a zoomed clip of a corner.

    python tools/art/motion.py                 # the barrel errors
    python tools/art/motion.py --video         # ... and tools/.build/shots/art/motion.mp4, motion_corner.mp4
"""
import os, sys, argparse, subprocess, shutil, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, launch
from playwright.sync_api import sync_playwright

OUT = os.path.join(BUILD, 'shots', 'art'); os.makedirs(OUT, exist_ok=True)
ap = argparse.ArgumentParser(); ap.add_argument('--video', action='store_true'); ap.add_argument('--secs', type=float, default=16)
ap.add_argument('--speed', type=int, default=1)
a = ap.parse_args()
HOOK = ('window.__m = { startMap, buildStarter, recompute, drawTerrain, towerKind, get AIMSTAT() { return typeof AIMSTAT === "undefined" ? null : AIMSTAT; }, '
        'get S() { return S; } };\n')
PAGE = write_build('motion.html', game_html().replace('window.siegeline = {', HOOK + 'window.siegeline = {', 1))
SETUP = r'''() => { const P = window.__m, sl = window.siegeline; let S = P.S; sl.rules.fixedGates = true;
  for (let i = 0; i < 176; i++) { S.grid[i] = null; S.seenGrid[i] = null; }
  P.startMap(0x7d2a); P.buildStarter(); P.drawTerrain(); S = P.S;
  const kinds = [{}, { rate: 0 }, { rate: 5, range: 4 }, { splash: 2, rate: 4 }, { chain: 3 }, { rate: 5, range: 5, slow: true }];
  const on = new Set(S.path), walls = []; S.grid.forEach((g, i) => { if (g && g.t === 'wall' && [i - 1, i + 1, i - 16, i + 16].some(j => on.has(j))) walls.push(i); });
  const pick = []; for (const i of walls) if (pick.every(j => Math.abs((j % 16) - (i % 16)) + Math.abs(((j / 16) | 0) - ((i / 16) | 0)) >= 3)) pick.push(i);
  let n = 0; for (const [k, o] of kinds.entries()) { const i = pick[(k * 3) % pick.length]; if (i == null) continue;
    S.grid[i] = { t: 'tower', cfg: { range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: 0, ...o }, n: ++n, fee: 0, fresh: true, cd: 0, ang: Math.PI, kick: 0, dealt: 0 }; }
  S.towerSeq = n; S.gridVer++; P.recompute(); sl.refresh(); }'''
ARMY = r'''() => { const sl = window.siegeline, S = sl.state; S.aFree = 99999; const C = ['#ffb547', '#e5472b', '#ff7b36', '#ff6fa8'];
  S.designs = [
    { name: 'Talon', color: C[3], hp: 5, speed: 7, armor: 0, regen: 0, resist: 'none', count: 5, tl: { s: 0, e: 0.5, pos: null } },
    { name: 'Dart', color: C[0], hp: 3, speed: 5, armor: 1, regen: 0, resist: 'none', count: 8, tl: { s: 0.05, e: 0.6, pos: null } },
    { name: 'Ogive', color: C[2], hp: 4, speed: 3, armor: 0, regen: 0, resist: 'none', count: 6, tl: { s: 0, e: 0.5, pos: null } },
    { name: 'Bastion', color: C[1], hp: 8, speed: 0, armor: 2, regen: 1, resist: 'none', count: 3, tl: { s: 0, e: 0.3, pos: null } },
  ]; sl.refresh(); }'''

with sync_playwright() as p:
    b = launch(p)
    opts = dict(viewport={'width': 1280, 'height': 800}, device_scale_factor=1)
    vdir = os.path.join(BUILD, 'motion_video')
    if a.video: shutil.rmtree(vdir, ignore_errors=True); opts['record_video_dir'] = vdir; opts['record_video_size'] = {'width': 1280, 'height': 800}
    ctx = b.new_context(**opts); pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('file://' + PAGE); pg.wait_for_timeout(500)
    pg.evaluate('() => { const R = window.siegeline.rules; R.planSecs = 0; R.planSecsFirst = 0; R.fixedGates = true; }')
    pg.click('#info-go'); pg.click('#mode-local'); pg.wait_for_timeout(500); pg.click('#ov-hand'); pg.wait_for_timeout(200)
    pg.evaluate(SETUP); pg.wait_for_timeout(300)
    pg.click('#def-lock'); pg.wait_for_timeout(500); pg.click('#ov-hand'); pg.wait_for_timeout(200)
    pg.evaluate(ARMY); pg.wait_for_timeout(200)
    pg.click('#atk-lock'); pg.wait_for_timeout(300)
    if not pg.is_visible('#ov-hand'): pg.click('#atk-lock')
    pg.wait_for_selector('#ov-hand', state='visible'); pg.wait_for_timeout(400)
    t0 = pg.evaluate('() => performance.now()')
    pg.click('#ov-hand')
    if a.speed > 1: pg.click(f'#pane-wave [data-speed="{a.speed}"]')
    pg.wait_for_timeout(int(a.secs * 1000))
    st = pg.evaluate('''() => { const A = window.__m.AIMSTAT; if (!A) return null; return { n: A.n, err: A.err.slice() }; }''')
    ctx.close(); b.close()
    if st:
        import statistics
        e = sorted(x * 57.2958 for x in st['err'])
        if e:
            q = lambda f: e[min(len(e) - 1, int(f * len(e)))]
            print(f'{st["n"]} shots: barrel off its target when the shot left: median {q(0.5):.1f}°, 90% within {q(0.9):.1f}°, 95% within {q(0.95):.1f}°, '
                  f'{100 * sum(x <= 5 for x in e) / len(e):.0f}% within 5°, worst {e[-1]:.0f}°')
    print('errors', errs[:4])
    if a.video:
        vids = glob.glob(os.path.join(vdir, '*.webm'))
        if vids and shutil.which('ffmpeg'):
            out = os.path.join(OUT, 'motion.mp4')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vids[0], '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '24', out], check=False)
            # a close-up of the entry's corner, where the first units turn (the board at 1280x800, middle-row gates)
            corner = os.path.join(OUT, 'motion_corner.mp4')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', vids[0], '-vf', 'crop=400:300:16:300,scale=1200:900:flags=lanczos', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '22', corner], check=False)
            print('video', out, corner)
