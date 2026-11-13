"""Screens for before/after comparisons (v32): the start screen, a mid-wave board, the defender's tower card, the
attacker's army panel, its design editor, and the round summary, at desktop size and on a 390 px phone.

    python tools/art/panels.py --tag before        # tools/.build/shots/art/panels_before_*.png
    python tools/art/panels.py --tag after --only board,summary

It plays one pass-and-play round on a fixed map (seed 0x7d2a, middle-row gates where the build has the rule) with a
fixed defense and army put into the state, so two builds show the same scene. Nothing in the game changes.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, launch
from playwright.sync_api import sync_playwright

OUT = os.path.join(BUILD, 'shots', 'art'); os.makedirs(OUT, exist_ok=True)
ap = argparse.ArgumentParser(); ap.add_argument('--tag', default='after'); ap.add_argument('--only', default='')
ap.add_argument('--gates', default='fixed', help="'fixed' (middle rows) or 'map' (v32: the map's own gates)")
args = ap.parse_args()
ONLY = set(filter(None, args.only.split(',')))
want = lambda k: not ONLY or k in ONLY
HOOK = 'window.__p = { startMap, buildStarter, recompute, drawTerrain, get S() { return S; } };\n'
src = game_html()
PAGE = write_build('panels.html', src.replace('window.siegeline = {', HOOK + 'window.siegeline = {', 1))

SETUP = r'''(fixed) => { const R = window.siegeline.rules; R.planSecs = 0; R.planSecsFirst = 0; if (fixed) R.fixedGates = true; }'''
DEFENSE = r'''() => { const P = window.__p, sl = window.siegeline; let S = P.S;
  for (let i = 0; i < S.grid.length; i++) { S.grid[i] = null; S.seenGrid[i] = null; } // the match's own starter maze goes
  P.startMap(0x7d2a); P.buildStarter(); P.drawTerrain(); S = P.S; S.dFree = 260;
  const T = [[{}, 0], [{ rate: 0 }, 1], [{ splash: 2, rate: 4 }, 2], [{ slow: true }, 3], [{ chain: 3 }, 4], [{ poison: true, rate: 5, dps: 4 }, 5]];
  const walls = []; S.grid.forEach((g, i) => { if (g && g.t === 'wall') walls.push(i); });
  // towers on starter walls the route passes, spread out
  const on = new Set(S.path), pick = [];
  for (const i of walls) { const c = i % 16; const near = [i - 1, i + 1, i - 16, i + 16].filter(j => on.has(j)).length;
    if (near && pick.every(j => Math.abs((j % 16) - c) + Math.abs(((j / 16) | 0) - ((i / 16) | 0)) >= 3)) pick.push(i); }
  let n = 0;
  for (const [o, k] of T) { const i = pick[(k * 5) % pick.length]; if (i == null || (S.grid[i] && S.grid[i].t === 'tower')) continue;
    S.grid[i] = { t: 'tower', cfg: { range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: 0, ...o }, n: ++n, fee: 0, fresh: true, cd: 0, ang: Math.PI, kick: 0, dealt: 0 }; }
  S.towerSeq = n; S.gridVer++; P.recompute(); sl.refresh();
  return S.grid.map((g, i) => g && g.t === 'tower' ? i : -1).filter(i => i >= 0); }'''
ARMY = r'''() => { const sl = window.siegeline, S = sl.state; S.aFree = 40; const C = ['#ffb547', '#e5472b', '#ff7b36', '#ff6fa8'];
  S.designs = [
    { name: 'Runner', color: C[0], hp: 2, speed: 6, armor: 0, regen: 0, resist: 'none', count: 8, tl: { s: 0, e: 0.4, pos: null } },
    { name: 'Brute', color: C[1], hp: 6, speed: 2, armor: 2, regen: 1, resist: 'none', count: 4, tl: { s: 0.05, e: 0.5, pos: null } },
    { name: 'Swarm', color: C[2], hp: 0, speed: 4, armor: 0, regen: 0, resist: 'splash', count: 12, tl: { s: 0.1, e: 0.35, pos: null } },
    { name: 'Lancer', color: C[3], hp: 4, speed: 7, armor: 1, regen: 0, resist: 'frost+shock', count: 3, tl: { s: 0.2, e: 0.6, pos: null } },
  ]; sl.refresh(); }'''

def go(pg, vp):
    pg.set_viewport_size(vp)
    pg.goto('file://' + PAGE); pg.wait_for_timeout(700)

with sync_playwright() as p:
    b = launch(p); errs = []
    for label, vp in (('desk', {'width': 1440, 'height': 900}), ('phone', {'width': 390, 'height': 844})):
        ctx = b.new_context(viewport=vp, device_scale_factor=2, reduced_motion='no-preference'); pg = ctx.new_page()
        pg.on('pageerror', lambda e: errs.append(str(e)))
        name = lambda k: f'{OUT}/panels_{args.tag}_{k}_{label}.png'
        go(pg, vp)
        pg.evaluate(SETUP, args.gates == 'fixed')
        pg.click('#info-go'); pg.wait_for_timeout(1800)
        if want('menu'): pg.screenshot(path=name('menu'))
        pg.click('#mode-local'); pg.wait_for_timeout(700); pg.click('#ov-hand'); pg.wait_for_timeout(300)
        if pg.is_visible('#hints-btn, [data-act=hints]'): pass
        towers = pg.evaluate(DEFENSE); pg.wait_for_timeout(1200)
        if want('build'): pg.screenshot(path=name('build'))
        if want('card') and towers:
            x, y = pg.evaluate('(i) => window.siegeline.cellToClient(i)', towers[2 % len(towers)])
            pg.mouse.click(x, y); pg.wait_for_timeout(900)
            pg.screenshot(path=name('card'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
        pg.click('#def-lock'); pg.wait_for_timeout(600)
        if pg.is_visible('#ov-hand'): pg.click('#ov-hand'); pg.wait_for_timeout(300)
        pg.evaluate(ARMY); pg.wait_for_timeout(900)
        if want('army'): pg.screenshot(path=name('army'))
        if want('editor'):
            pg.click('#pane-atk .urow >> nth=1'); pg.wait_for_timeout(900); pg.screenshot(path=name('editor'))
            pg.keyboard.press('Escape'); pg.wait_for_timeout(300)
        pg.click('#atk-lock'); pg.wait_for_timeout(400)
        if not pg.is_visible('#ov-hand'): pg.click('#atk-lock'); pg.wait_for_timeout(400)
        if pg.is_visible('#ov-hand'): pg.click('#ov-hand')
        pg.wait_for_timeout(9000)
        if want('board'):
            pg.screenshot(path=name('board'))
            r = pg.evaluate('() => { const r = document.querySelector("#board").getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; }')
            if label == 'desk': pg.screenshot(path=name('boardzoom'), clip={'x': r[0], 'y': r[1], 'width': r[2] * 0.55, 'height': r[3] * 0.6})
        if want('summary'):
            pg.evaluate('() => window.siegeline.advance(200)')
            pg.wait_for_selector('#ov-sum', state='visible', timeout=30000); pg.wait_for_timeout(1500)
            pg.screenshot(path=name('summary'))
        ctx.close()
    b.close()
print(f'panels in {OUT}; errors: {errs[:6]}')
