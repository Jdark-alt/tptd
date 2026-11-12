"""Specimen sheets of the board's art, drawn with the game's own functions and light (v31).

    python tools/art/sheet.py towers            # every attack type × element × damage × fire rate, plus the extremes
    python tools/art/sheet.py towers --phone    # the same at a phone's cell size (390 px wide)

Writes tools/.build/shots/art/sheet_towers.png (or sheet_towers_phone.png). Each tile is one tower on a patch of the board's floor
under its own light, captioned with what it is, so someone who knows the rules can check that every setting reads off
the picture: the silhouette (shooter, Mortar, Tesla), the barrels or chevrons (fire rate), the length of what points at
the target (range), the lights at the foot (damage), the scope (accuracy), Frost on the left and Poison on the right.
The page is a copy of index.html with a few internals exposed; nothing in the game changes.
"""
import os, sys, argparse, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, launch
from playwright.sync_api import sync_playwright

OUT = os.path.join(BUILD, 'shots', 'art'); os.makedirs(OUT, exist_ok=True)
HOOK = ('window.__art = { drawTowerShape, towerName, towerLamps, towerShape, chainOf, TS, view, ART, lightBegin, lamp, lightEnd, '
        'defaultTower, towerCost };\n')

# A floor patch, a tower in the middle, its own lights: the board in miniature (see drawTerrain and boardLights).
SHEET_JS = r'''
([spec, W, CELL, dpr]) => {
  const A = window.__art, phone = W < 600, PXW = phone ? Math.floor((W - 28 - 3 * 6) / 4) : CELL * 1.5, TILE = PXW / CELL; // a phone: four a row, the tower at its real size
  const css = `
    #sheet { position: fixed; inset: 0 auto auto 0; width: ${W}px; z-index: 99999; background: #07090c; color: #c8d6e2;
      font-family: var(--f-ui, ui-monospace, monospace); padding: ${W < 600 ? 14 : 30}px; box-sizing: border-box; }
    #sheet h1 { font-family: var(--f-display, monospace); font-size: ${W < 600 ? 24 : 34}px; letter-spacing: 3px; margin: 0 0 4px; color: #e9f2f8; }
    #sheet .sub { font-size: 11px; letter-spacing: 1.2px; text-transform: uppercase; color: #6f8193; margin-bottom: 14px; line-height: 1.5; }
    #sheet h2 { font-size: 12px; letter-spacing: 2px; text-transform: uppercase; margin: 22px 0 10px; padding-top: 12px; border-top: 1px solid #1c2630; color: #e9f2f8; }
    #sheet .grid { display: grid; grid-template-columns: repeat(auto-fill, ${PXW}px); gap: ${W < 600 ? 8 : 12}px ${W < 600 ? 6 : 10}px; }
    #sheet .sp canvas { width: ${PXW}px; height: ${PXW}px; display: block; border-radius: 4px; border: 1px solid #1a232c; }
    #sheet .cap { font-size: ${W < 600 ? 8.5 : 10.5}px; line-height: 1.3; margin-top: 4px; color: #dbe6ef; overflow-wrap: anywhere; }
    #sheet .cap i { display: block; font-style: normal; color: #7a8c9d; }
    #sheet .key { font-size: 11px; color: #9fb0c0; line-height: 1.6; margin: 0 0 6px; font-family: var(--f-body, sans-serif); }
  `;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  const sheet = document.createElement('div'); sheet.id = 'sheet'; document.body.appendChild(sheet);
  const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
  const old = [A.view.cs, A.view.dpr, A.view.rot]; A.view.cs = CELL; A.view.dpr = dpr; A.view.rot = false; A.ART.lo = false;
  function floor(c) {
    const g = c.createLinearGradient(0, 0, TILE, TILE); g.addColorStop(0, '#10161c'); g.addColorStop(1, '#0a0d11'); c.fillStyle = g; c.fillRect(0, 0, TILE, TILE);
    const px = 1 / CELL, ds = Math.max(px * 0.9, 0.012), o = (TILE / 2 - 0.5) % 1, P = [o - 1, o, o + 1];
    for (const q of P) for (const r of P) { c.fillStyle = 'rgba(150,182,206,0.045)'; for (let y = 1; y < 6; y++) for (let x = 1; x < 6; x++) c.fillRect(q + x / 6 - ds, r + y / 6 - ds, 2 * ds, 2 * ds); }
    c.beginPath(); for (const v of [o, o + 1]) { c.moveTo(v, 0); c.lineTo(v, TILE); c.moveTo(0, v); c.lineTo(TILE, v); }
    c.lineWidth = px; c.strokeStyle = 'rgba(150,172,190,0.06)'; c.stroke();
  }
  const T = 1.3;
  function tile(o) {
    const cfg = { ...A.defaultTower(), ...o.cfg }, cv = document.createElement('canvas'); cv.width = cv.height = Math.round(PXW * dpr);
    const c = cv.getContext('2d'); c.setTransform(CELL * dpr, 0, 0, CELL * dpr, 0, 0); floor(c);
    const m = TILE / 2; A.drawTowerShape(c, cfg, m, m, o.ang ?? -0.6, o.kick || 0, !!o.off, T, { cell: 9000 + Math.random() * 999 | 0 });
    const lc = A.lightBegin(TILE, TILE, '138,148,166');
    if (o.off) A.lamp(lc, m, m, 2.1, '150,120,230', 0.35);
    else for (const [dx, dy, r, rgb, a] of A.towerLamps(cfg)) A.lamp(lc, m + dx, m + dy, r, rgb, a);
    A.lightEnd(c, 0.14);
    const box = el('div', 'sp'); box.append(cv, el('div', 'cap', `${o.title || A.towerName(cfg)}<i>${o.note || ''}</i>`));
    return box;
  }
  sheet.append(el('h1', null, 'TPTD'), el('div', 'sub', spec.sub));
  for (const sec of spec.sections) {
    sheet.append(el('h2', null, sec.title));
    if (sec.key) sheet.append(el('p', 'key', sec.key));
    const g = el('div', 'grid'); for (const o of sec.tiles) g.append(tile(o)); sheet.append(g);
  }
  [A.view.cs, A.view.dpr, A.view.rot] = old;
  return sheet.offsetHeight;
}
'''

def tower_spec():
    TS = {'rate': [4, 2.5, 1.6, 1, 0.6, 0.4], 'dps': [9, 13, 18, 24, 30, 38, 48, 60, 75], 'range': [1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]}
    types = [('Shooter', {}), ('Mortar', {'splash': 2}), ('Tesla', {'chain': 3})]
    elems = [('', {}), ('Frost', {'slow': True}), ('Poison', {'poison': True}), ('Frost + Poison', {'slow': True, 'poison': True})]
    sections = []
    for tname, t in types:
        for rname, rate in (('slowest fire rate, 0.4/s', 5), ('fastest fire rate, 4/s', 0)):
            tiles = []
            for ename, e in elems:
                for dname, dps in (('9/s', 0), ('75/s', 8)):
                    cfg = {**t, **e, 'rate': rate, 'dps': dps, 'range': 3}
                    tiles.append({'cfg': cfg, 'note': f'damage {dname} · {TS["rate"][rate]}/s'})
            sections.append({'title': f'{tname} · {rname}', 'tiles': tiles})
    ext = []
    for tname, t in types:
        for rg in (0, 7): ext.append({'cfg': {**t, 'range': rg, 'rate': 3}, 'note': f'range {TS["range"][rg]} cells'})
        for ac in (0, 3): ext.append({'cfg': {**t, 'accuracy': ac, 'rate': 3}, 'note': f'accuracy {[80, 87, 94, 100][ac]}%'})
    sections.append({'title': 'Range and accuracy, shortest and longest, none and the top step', 'tiles': ext})
    steps = [{'cfg': {'rate': 3}, 'note': 'fire rate 1/s (the middle)'}, {'cfg': {'rate': 2, 'dps': 4}, 'note': '1.6/s'}]
    steps += [{'cfg': {'splash': s, 'rate': 4}, 'note': f'splash {[0, 0.5, 0.9, 1.3][s]} cells: {s} ring{"s" if s > 1 else ""}'} for s in (1, 2, 3)]
    steps += [{'cfg': {'chain': j, 'rate': 3}, 'note': f'{j} jump{"s" if j > 1 else ""}: {j} node{"s" if j > 1 else ""} lit'} for j in (1, 2, 3)]
    steps += [{'cfg': {'rate': 3, 'dps': d}, 'note': f'damage {TS["dps"][d]}/s: {1 + d // 2} light{"s" if d > 1 else ""}'} for d in (0, 2, 4, 6, 8)]
    steps += [{'cfg': {'rate': 5, 'range': 5, 'dps': 6}, 'kick': 0.95, 'ang': 0, 'note': 'firing'},
              {'cfg': {'chain': 2, 'rate': 1, 'slow': True}, 'off': True, 'note': 'knocked out'},
              {'cfg': {'splash': 1, 'poison': True, 'rate': 4}, 'off': True, 'note': 'knocked out'}]
    sections.append({'title': 'The other steps', 'tiles': steps})
    key = ('Silhouette: the attack type (octagon shooter, round Mortar, three-cornered Tesla). Barrels (shooters) or chevrons on the back '
           '(Mortar, Tesla): fire rate, one chevron slow, three fast. What points at the target: range. Lights at the foot: damage. '
           'Scope on the left of the turret: accuracy. Rings on the dish: splash. Lit corner nodes: chain jumps. '
           'Ice and a snowflake on the left: Frost. Canisters and a drop on the right: Poison.')
    sections[0]['key'] = key
    return {'sub': 'Towers · v31 · every setting in its own place', 'sections': sections}

ap = argparse.ArgumentParser()
ap.add_argument('what', choices=['towers'])
ap.add_argument('--phone', action='store_true', help='at a phone’s cell size, 390 px wide')
args = ap.parse_args()
src = game_html()
assert 'window.siegeline = {' in src
PAGE = write_build('sheet.html', src.replace('window.siegeline = {', HOOK + 'window.siegeline = {', 1))
W, CELL, DPR = (390, 30, 3) if args.phone else (1500, 80, 2)
name = 'sheet_towers' + ('_phone' if args.phone else '')
with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={'width': W, 'height': 900}, device_scale_factor=DPR)
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('file://' + PAGE); pg.wait_for_timeout(500)
    h = pg.evaluate(SHEET_JS, [tower_spec(), W, CELL, DPR])
    pg.set_viewport_size({'width': W, 'height': h}); pg.wait_for_timeout(300)
    out = os.path.join(OUT, name + '.png')
    pg.screenshot(path=out, clip={'x': 0, 'y': 0, 'width': W, 'height': h})
    print(f'{out}: {W}×{h} at {DPR}×; errors: {errs[:4]}')
    b.close()
