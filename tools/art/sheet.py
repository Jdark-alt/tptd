"""Specimen sheets of the board's art, drawn with the game's own functions and light (v31).

    python tools/art/sheet.py towers            # every attack type × element × damage × fire rate, plus the extremes
    python tools/art/sheet.py towers --phone    # the same at a phone's cell size (390 px wide)
    python tools/art/sheet.py units             # v31 item 3: three families of abstract unit shapes (unit_families.js)
    python tools/art/sheet.py units --video     # ... and an 8 s clip of them marching (MP4, needs ffmpeg)

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
HOOK = ('window.__art = { drawTowerShape, towerName, towerLamps, towerShape, chainOf, TS, US, COLORS, view, ART, lightBegin, lamp, lightEnd, '
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

UNITS_JS = r'''
([W, CELL, dpr, famKeys]) => {
  const A = window.__art, UF = window.UNIT_FAM, TW = 2.4, TH = 1.35, phone = W < 600;
  const css = `
    #sheet { position: fixed; inset: 0 auto auto 0; width: ${W}px; z-index: 99999; background: #07090c; color: #c8d6e2;
      font-family: var(--f-ui, ui-monospace, monospace); padding: ${phone ? 14 : 30}px; box-sizing: border-box; }
    #sheet h1 { font-family: var(--f-display, monospace); font-size: 34px; letter-spacing: 3px; margin: 0 0 4px; color: #e9f2f8; }
    #sheet .sub { font-size: 11px; letter-spacing: 1.2px; text-transform: uppercase; color: #6f8193; margin-bottom: 8px; line-height: 1.5; }
    #sheet .intro { font: 13px/1.55 var(--f-body, sans-serif); color: #9fb0c0; max-width: 980px; margin: 0 0 6px; }
    #sheet h2 { font-size: 15px; letter-spacing: 2.5px; text-transform: uppercase; margin: 28px 0 4px; padding-top: 14px; border-top: 1px solid #1c2630; color: #e9f2f8; }
    #sheet h2 b { color: var(--warm, #ff8a3d); margin-right: 10px; }
    #sheet .key { font: 12.5px/1.5 var(--f-body, sans-serif); color: #9fb0c0; margin: 0 0 12px; max-width: 980px; }
    #sheet .row { display: flex; gap: 8px; align-items: flex-start; margin-bottom: 8px; }
    #sheet .rl { width: 104px; flex: none; font-size: 10.5px; letter-spacing: 1.2px; text-transform: uppercase; color: #8ea0b1; line-height: 1.45; padding-top: 22px; }
    #sheet .rl b { display: block; color: #e9f2f8; font-size: 11.5px; }
    #sheet canvas.t { display: block; border-radius: 4px; border: 1px solid #1a232c; }
    #sheet .cap { font-size: 10px; line-height: 1.3; margin-top: 4px; color: #dbe6ef; }
    #sheet .cap i { display: block; font-style: normal; color: #7a8c9d; }
    #sheet .lane { margin: 6px 0 0 112px; }
    #sheet .lane canvas { display: block; border-radius: 5px; border: 1px solid #1a232c; }
    #sheet .lanecap { font-size: 10px; letter-spacing: 1px; text-transform: uppercase; color: #7a8c9d; margin: 6px 0 0 112px; }
  `;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
  const sheet = document.createElement('div'); sheet.id = 'sheet'; document.body.appendChild(sheet);
  const el = (t, c, h) => { const e = document.createElement(t); if (c) e.className = c; if (h != null) e.innerHTML = h; return e; };
  const old = [A.view.cs, A.view.dpr, A.view.rot]; A.view.dpr = dpr; A.view.rot = false;
  const HP = A.US.hp.steps, SP = A.US.speed.steps, COL = A.COLORS, T = 1.37;
  const Rof = i => 0.11 + 0.21 * Math.sqrt((HP[i] - 50) / 850); // the game's unitRadius
  function floor(c, w, h, cell) {
    const g = c.createLinearGradient(0, 0, w, h); g.addColorStop(0, '#10161c'); g.addColorStop(1, '#0a0d11'); c.fillStyle = g; c.fillRect(0, 0, w, h);
    const px = 1 / cell, ds = Math.max(px * 0.9, 0.012);
    for (let q = -1; q < w + 1; q++) for (let r = -1; r < h + 1; r++) { c.fillStyle = 'rgba(150,182,206,0.045)'; for (let y = 1; y < 6; y++) for (let x = 1; x < 6; x++) c.fillRect(q + x / 6 - ds, r + y / 6 - ds, 2 * ds, 2 * ds); }
    c.beginPath(); for (let q = 0; q <= w; q++) { c.moveTo(q, 0); c.lineTo(q, h); } for (let r = 0; r <= h; r++) { c.moveTo(0, r); c.lineTo(w, r); }
    c.lineWidth = px; c.strokeStyle = 'rgba(150,172,190,0.05)'; c.stroke();
  }
  // a patch of board with units on it, lit as the board is (the units after the light, as in the game)
  function scene(w, h, cell, units, lane) {
    A.view.cs = cell;
    const cv = document.createElement('canvas'); cv.width = Math.round(w * cell * dpr); cv.height = Math.round(h * cell * dpr);
    cv.style.width = Math.round(w * cell) + 'px'; cv.style.height = Math.round(h * cell) + 'px';
    const c = cv.getContext('2d'); c.setTransform(cell * dpr, 0, 0, cell * dpr, 0, 0); floor(c, w, h, cell);
    if (lane) { c.beginPath(); c.moveTo(0, h / 2); c.lineTo(w, h / 2); c.lineWidth = 0.5; c.strokeStyle = 'rgba(160,200,225,0.04)'; c.stroke(); c.setLineDash([0.18, 0.14]); c.lineWidth = 1.4 / cell; c.strokeStyle = 'rgba(160,200,225,0.35)'; c.stroke(); c.setLineDash([]); }
    const lc = A.lightBegin(w, h, '128,138,156');
    for (const u of units) { A.lamp(lc, u.x, u.y, u.R * 4 + 0.3, UF.rgb(u.col), 0.32 + 0.1 * u.s / 7); A.lamp(lc, u.x + 0.3, u.y, u.R * 3, '255,236,210', 0.18); }
    A.lightEnd(c, 0.16);
    for (const u of units) UF.drawUnit(c, u, T + u.x * 0.37, 1 / cell);
    return cv;
  }
  sheet.append(el('h1', null, 'TPTD'), el('div', 'sub', 'Units · v31 · three families to pick from'));
  sheet.append(el('p', 'intro', 'Shape is speed only, eight steps from 0.7 to 2.8 cells a second. Size is health, as now. Colour is the army colour. Every shape faces right, the way they march, with a lit front. Faster steps trail more light, hover higher (the shadow sits further off) and pulse faster. Armour is steel brackets on a ring round the unit (the front, then the sides, then all round), regeneration a pulsing green cross at the heart, resists motes circling it; frosted, poisoned and hit units are tinted. None of this is in the game yet.'));
  const TWpx = phone ? 0 : Math.floor((W - 60 - 112 - 7 * 8) / 8), cell = TWpx / TW;
  for (const fk of famKeys) {
    const fam = UF.FAM[fk];
    sheet.append(el('h2', null, `<b>${'ABC'[famKeys.indexOf(fk)]}</b>${fam.name}`));
    sheet.append(el('p', 'key', { sharpen: 'Solid and blocky when slow, stretching and sharpening into a blade, then a needle with a comet tail when fast.', fragment: 'Slow units are one dense whole; faster ones break into more shards flying in tight formation, held by hairlines to a glowing heart, as if speed pulls the body apart.', energy: 'Slow units are heavy stacked plates and rings with a slow pulse; fast units are bright cores behind a shield of light, trailing streaks and sparks.' }[fk]));
    // the eight steps at small, mid and max health
    const head = el('div', 'row'); head.append(el('div', 'rl', ''));
    for (let s = 0; s < 8; s++) head.append(Object.assign(el('div', 'cap', `<b style="color:#e9f2f8">${SP[s]} cells/s</b><i>${fam.words[s]}</i>`), { style: `width:${TWpx}px` }));
    sheet.append(head);
    [[0, 'Smallest', '50 HP'], [5, 'Middle', '275 HP'], [9, 'Largest', '900 HP']].forEach(([hi, a, b], row) => {
      const r = el('div', 'row'); r.append(el('div', 'rl', `<b>${a}</b>${b}`));
      for (let s = 0; s < 8; s++) { const cv = scene(TW, TH, cell, [{ fam: fk, s, R: Rof(hi), col: COL[(s + row) % 4], ang: 0, x: 1.45, y: TH / 2 }]); cv.className = 't'; r.append(cv); }
      sheet.append(r);
    });
    // the markers, each on a different shape and size
    const MK = [[0, 9, { armor: 3 }, 'Armour 3', 'all round'], [1, 2, { armor: 1 }, 'Armour 1', 'the front'], [2, 5, { regen: 2 }, 'Regeneration', 'a green cross'], [3, 6, { res: ['splash', 'poison', 'frost', 'shock'] }, 'Four resists', 'motes'],
      [4, 7, { armor: 2 }, 'Armour 2', 'front and sides'], [5, 5, { slow: true }, 'Frosted', 'iced over'], [6, 6, { poison: true }, 'Poisoned', 'bubbles'], [7, 3, { flash: true, armor: 3, regen: 3 }, 'Hit', 'armour 3, regen']];
    const r = el('div', 'row'); r.append(el('div', 'rl', '<b>Markers</b>on any shape'));
    for (const [s, hi, o, a, b] of MK) { const box = el('div'); const cv = scene(TW, TH, cell, [{ fam: fk, s, R: Rof(hi), col: COL[s % 4], ang: 0, x: 1.4, y: TH / 2, ...o }]); cv.className = 't'; box.append(cv, el('div', 'cap', `${a}<i>${b}</i>`)); r.append(box); }
    sheet.append(r);
    // on the board: all eight marching, the fast ones further along
    const LW = 19.5, LH = 2.0, lcell = (W - 60 - 112) / LW, U = [];
    for (let s = 0; s < 8; s++) U.push({ fam: fk, s, R: Rof([4, 6, 2, 5, 3, 7, 1, 8][s]), col: COL[s % 4], ang: 0, x: 1.0 + SP[s] * 6.3, y: LH / 2 + [-0.45, 0.4, -0.3, 0.45, -0.4, 0.3, -0.35, 0.4][s] });
    for (let k = 0; k < 4; k++) U.push({ fam: fk, s: 6, R: Rof(0), col: COL[1], ang: 0, x: 2.5 + SP[6] * 6.3 + k * 0.42, y: LH / 2 - 0.02 + (k % 2 ? 0.16 : -0.16) });
    const lane = el('div', 'lane'); lane.append(scene(LW, LH, lcell, U, true)); sheet.append(lane);
    sheet.append(el('div', 'lanecap', 'On the board, all eight a few seconds after leaving together: slowest on the left'));
  }
  [A.view.cs, A.view.dpr, A.view.rot] = old;
  return sheet.offsetHeight;
}
'''

# The families marching: three lanes, every speed step, drawn frame by frame at a fixed time step (smooth whatever the
# machine), then put together by ffmpeg.
VIDEO_JS = r'''
([W, H, dpr, famKeys]) => {
  const A = window.__art, UF = window.UNIT_FAM, SP = A.US.speed.steps, HP = A.US.hp.steps, COL = A.COLORS;
  const Rof = i => 0.11 + 0.21 * Math.sqrt((HP[i] - 50) / 850);
  const cv = document.createElement('canvas'); cv.width = W * dpr; cv.height = H * dpr;
  cv.style.cssText = `position:fixed;left:0;top:0;width:${W}px;height:${H}px;z-index:99999;background:#07090c`;
  document.body.appendChild(cv); const c = cv.getContext('2d');
  const LW = 17, LH = 2.4, gap = 0.55, top = 0.55, cell = W / (LW + 0.6), rows = famKeys.length;
  A.view.cs = cell; A.view.dpr = dpr; A.view.rot = false; A.ART.lo = false;
  // each lane: two of every speed, staggered, plus a pack of small fast ones
  const lanes = famKeys.map((fk, li) => { const U = []; for (let s = 0; s < 8; s++) for (let k = 0; k < 2; k++) U.push({ fam: fk, s, hi: [3, 7, 5, 9, 2, 6, 4, 8][(s + k * 3) % 8], col: COL[(s + k) % 4], x0: (s * 2.3 + k * 9.1) % LW, y: (k ? 0.62 : -0.62) * (s % 2 ? 1 : 0.55) }); return { fk, U }; });
  window.__frame = t => {
    c.setTransform(dpr, 0, 0, dpr, 0, 0); c.fillStyle = '#07090c'; c.fillRect(0, 0, W, H);
    c.font = '600 12px Geist Mono, ui-monospace, monospace'; c.fillStyle = '#e9f2f8';
    lanes.forEach((L, li) => {
      const oy = (top + li * (LH + gap)) * cell, ox = 0.3 * cell;
      c.setTransform(dpr, 0, 0, dpr, 0, 0); c.fillText(`${'ABC'[li]}  ${UF.FAM[L.fk].name.toUpperCase()}`, ox, oy - 8);
      c.setTransform(cell * dpr, 0, 0, cell * dpr, ox * dpr, oy * dpr);
      c.save(); c.beginPath(); c.rect(0, 0, LW, LH); c.clip();
      const g = c.createLinearGradient(0, 0, LW, LH); g.addColorStop(0, '#10161c'); g.addColorStop(1, '#0a0d11'); c.fillStyle = g; c.fillRect(0, 0, LW, LH);
      c.beginPath(); for (let q = 0; q <= LW; q++) { c.moveTo(q, 0); c.lineTo(q, LH); } for (let r = 0; r <= LH; r++) { c.moveTo(0, r); c.lineTo(LW, r); } c.lineWidth = 1 / cell; c.strokeStyle = 'rgba(150,172,190,0.06)'; c.stroke();
      c.beginPath(); c.moveTo(0, LH / 2); c.lineTo(LW, LH / 2); c.setLineDash([0.18, 0.14]); c.strokeStyle = 'rgba(160,200,225,0.3)'; c.stroke(); c.setLineDash([]);
      const us = L.U.map(u => ({ ...u, R: Rof(u.hi), ang: 0, x: ((u.x0 + SP[u.s] * t) % (LW + 3)) - 1.5, y: LH / 2 + u.y }));
      const lc = A.lightBegin(LW, LH, '120,130,148');
      for (const u of us) A.lamp(lc, u.x, u.y, u.R * 4 + 0.3, UF.rgb(u.col), 0.34);
      A.lightEnd(c, 0.16);
      for (const u of us) UF.drawUnit(c, u, t + u.x0, 1 / cell);
      c.restore();
    });
    c.setTransform(dpr, 0, 0, dpr, 0, 0); c.fillStyle = '#7a8c9d'; c.font = '11px Geist Mono, ui-monospace, monospace';
    c.fillText('Real speed: 0.7 to 2.8 cells a second. Size is health, colour the army colour.', 0.3 * cell, H - 10);
  };
  return true;
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
ap.add_argument('what', choices=['towers', 'units'])
ap.add_argument('--phone', action='store_true', help='at a phone’s cell size, 390 px wide')
ap.add_argument('--video', action='store_true', help='units: an 8 s MP4 of the families marching instead of the sheet')
args = ap.parse_args()
src = game_html()
assert 'window.siegeline = {' in src
FAMJS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'unit_families.js'), encoding='utf-8').read()
PAGE = write_build('sheet.html', src.replace('window.siegeline = {', HOOK + 'window.siegeline = {', 1).replace('</body>', '<script>' + FAMJS + '</script></body>', 1))
W, CELL, DPR = (390, 30, 3) if args.phone else (1500, 80, 2)
name = f'sheet_{args.what}' + ('_phone' if args.phone else '')
with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={'width': W, 'height': 900}, device_scale_factor=DPR)
    pg = ctx.new_page(); errs = []
    pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.goto('file://' + PAGE); pg.wait_for_timeout(500)
    if args.video:
        import subprocess, tempfile, shutil
        VW, VH, FPS, SECS = 1280, 720, 30, 8
        pg.set_viewport_size({'width': VW, 'height': VH})
        pg.evaluate(VIDEO_JS, [VW, VH, 1, ['sharpen', 'fragment', 'energy']])
        tmp = tempfile.mkdtemp()
        for k in range(FPS * SECS):
            pg.evaluate(f'() => window.__frame({k / FPS})')
            pg.screenshot(path=os.path.join(tmp, f'f{k:04d}.png'))
        out = os.path.join(OUT, 'units_marching.mp4')
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(tmp, 'f%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out], check=True)
        shutil.rmtree(tmp)
        print(f'{out}: {SECS} s at {FPS} fps; errors: {errs[:4]}')
        b.close(); sys.exit(0)
    h = pg.evaluate(SHEET_JS, [tower_spec(), W, CELL, DPR]) if args.what == 'towers' else pg.evaluate(UNITS_JS, [W, CELL, DPR, ['sharpen', 'fragment', 'energy']])
    pg.set_viewport_size({'width': W, 'height': h}); pg.wait_for_timeout(300)
    out = os.path.join(OUT, name + '.png')
    pg.screenshot(path=out, clip={'x': 0, 'y': 0, 'width': W, 'height': h})
    print(f'{out}: {W}×{h} at {DPR}×; errors: {errs[:4]}')
    b.close()
