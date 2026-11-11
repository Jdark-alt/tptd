"""Pass-and-play suite: building, tuning, pricing, sappers (bridges and knock-outs), the timeline, test runs, win/loss,
   phone layout, and terrain (rough ground and rock). The fixed scenarios switch terrain off; the terrain checks come last.
   python tools/tests/test_local.py   (screenshots land in tools/.build/shots/local)"""
import os, sys, json, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, ROOT, TOOLS, launch
from playwright.sync_api import sync_playwright

OUT = os.path.join(BUILD, 'shots', 'local'); os.makedirs(OUT, exist_ok=True)
HARNESS = write_build('local.html', game_html())

COLS = 16
fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
def idx(c, r): return r * COLS + c
def S(page, expr): return page.evaluate('() => { const S = window.siegeline.state; return ' + expr + '; }')
def click_cell(page, c, r):
    x, y = page.evaluate(f'() => window.siegeline.cellToClient({idx(c,r)})'); page.mouse.click(x, y)
def toast(page): return page.evaluate("() => document.querySelector('#toast').textContent")
def hand(page):
    page.wait_for_timeout(480); page.click('#ov-hand'); page.wait_for_timeout(60)
def set_slider(page, sel, v):
    """Sets a slider to step index v (the fire rate's slider runs the other way, slow to fast: v21.1)."""
    page.evaluate(f"""() => {{ const i = document.querySelector('{sel}'); i.value = i.dataset.flip ? +i.max - {v} : {v}; i.dispatchEvent(new Event('input', {{bubbles:true}})); i.dispatchEvent(new Event('change', {{bubbles:true}})); }}""")
def no_terrain(page):
    """The fixed scenarios click known cells, so their matches start without rough ground or rock, and without the
    planning clock (it has checks of its own), so a slow machine never sends a plan early."""
    page.evaluate('() => { const R = window.siegeline.rules; R.roughShare = 0; R.rockShare = 0; R.planSecs = 0; R.starterPresses = 0; }')
def sure_sappers(page):
    """The fixed scenarios check what sappers do on arrival, so theirs get top health and always arrive."""
    page.evaluate('() => { window.siegeline.rules.sapper.hp = 9; }')
def atk_step(page, n):
    """The attacker's steps since v21: Army, Sabotage, Wave as tabs (Next only on the first two)."""
    page.click(f'#atk-steps [data-step="{n}"]'); page.wait_for_timeout(60)
def atk_back(page): atk_step(page, S(page, 'S.step') - 1)
def details(page, ov='#ov-sum'):
    """Open the summary's Details (closed by default since v21)."""
    t = page.locator(f'{ov} [data-act=details]')
    if t.count() and t.get_attribute('aria-expanded') != 'true': t.click()
def advance_until(page, cond, most=40):
    """Play the wave half a second at a time until cond holds (or most seconds pass); returns whether it held."""
    return page.evaluate(f'() => {{ const sl = window.siegeline; for (let k = 0; k < {most * 2}; k++) {{ const S = sl.state; if ({cond}) return true; sl.advance(0.5); }} const S = sl.state; return !!({cond}); }}')
def hints_off(page):
    """The fixed scenarios click known cells; with hints on, a glowing tile would place the hint's whole set."""
    if page.get_attribute('#def-steps [data-act=hints]', 'aria-pressed') == 'true': page.click('#def-steps [data-act=hints]')
def route_len(page):
    import re
    return int(re.search(r'Path\s+(\d+)', page.inner_text('#d-route'), re.I).group(1))
def spot(page, prefer_col=None):
    """A wall the attacker may bridge (seen, beside the seen route), as (c, r); one in prefer_col if there is one."""
    cells = page.evaluate('() => { const S = window.siegeline.state; return S.seenGrid.map((g, i) => i).filter(i => window.siegeline.canBridgeAt(i)); }')
    pick = next((i for i in cells if prefer_col is not None and i % COLS == prefer_col and 0 < i // COLS < 9), cells[0] if cells else None)
    return (pick % COLS, pick // COLS) if pick is not None else None
def drag(page, x0, y0, x1, y1, steps=8):
    page.mouse.move(x0, y0); page.mouse.down()
    for k in range(1, steps + 1): page.mouse.move(x0 + (x1 - x0) * k / steps, y0 + (y1 - y0) * k / steps)
    page.mouse.up()

with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
    page.goto('file://' + HARNESS); page.wait_for_timeout(500); no_terrain(page)
    check(page.is_visible('#ov-info'), 'info overlay on load')
    page.click('#info-go'); page.click('#mode-local'); hand(page)
    check(S(page, 'S.phase') == 'defend' and S(page, 'S.step') == 0 and ''.join(page.inner_text('#def-steps').lower().split()).startswith('build') and page.locator('#def-steps [data-step]').count() == 0
          and page.is_visible('#def-lock') and page.inner_text('#def-lock').lower() == 'lock in', 'v21: the defender has one screen, Build, with Lock in in its footer (no Ready step)')
    check(page.get_attribute('#def-steps [data-act=hints]', 'aria-pressed') == 'true' and page.is_visible('#def-steps [data-act=hints]'), 'Hints switch beside the panel title, on by default')
    hints_off(page)
    check(S(page, 'S.terrain.every(v => !v) && S.grid.every(g => !g)'), 'terrain shares at 0: a map without rough ground or rock')
    tops = page.evaluate("() => [...document.querySelectorAll('#def-body .toolrow > *, #def-body .helprow > *')].map(b => (b.dataset.tool || b.dataset.act) + ':' + Math.round(b.getBoundingClientRect().top))")
    rows = [t.split(':')[1] for t in tops]
    check([t.split(':')[0] for t in tops] == ['wall', 'tower', 'remove', 'shape', 'maze', 'tune', 'undo'] and len(set(rows[:4])) == 1 and len(set(rows[4:])) == 1 and int(rows[4]) > int(rows[0]),
          f'v21.1: the tool row (Wall, Tower, Remove, Shapes), and Auto-maze, Auto-tune, Undo in a row of their own under it {tops}')
    check(route_len(page) == 15 and 'under fire' not in page.inner_text('#d-route').lower(), 'route length shown; time under fire hidden with hints off')
    for r in range(0, 10): click_cell(page, 7, r)
    g0 = S(page, 'S.dFree')
    click_cell(page, 7, 10)
    check(S(page, f'S.grid[{idx(7,10)}]') is None and toast(page) == 'Path must stay open' and S(page, 'S.dFree') == g0, 'blocking wall rejected')
    check(route_len(page) > 15, f'route length updates ({page.inner_text("#d-route")})')
    page.screenshot(path=f'{OUT}/d0_maze.png')
    # towers, on the same build step
    page.click('.tool[data-tool=tower]')
    check(S(page, 'S.step') == 0 and S(page, 'S.tool') == 'tower', 'the Tower tool is on the same build step')
    check(page.inner_text('#d-tprice') == '40 coins', 'first tower costs 40')
    click_cell(page, 9, 5)
    check(S(page, f'S.grid[{idx(9,5)}].fee') == 0 and page.is_visible('#te-price'), 'first tower: no fee, editor opens')
    # v19 (spec test 1): a Basic tower still costs 40, and at the 100% accuracy step 64; the labels give the per-shot chance
    # v21: each slider row shows a short value; the full label is its tooltip
    tt = lambda k: page.get_attribute(f'#te-{k}-row', 'data-tip') or ''
    check(page.inner_text('#te-price') == '40' and page.inner_text('#te-accuracy-v') == '80%' and page.inner_text('#te-rate-v') == '1/s · 18/hit'
          and tt('accuracy').startswith('80% · 80% per shot at this fire rate') and tt('rate').startswith('1 per second · 18 per hit · 80% accurate'),
          f'a Basic tower costs 40 at 80% accuracy; short values on the rows, the detail in their tooltips ({page.inner_text("#te-accuracy-v")} / {tt("accuracy")[:40]})')
    set_slider(page, '#te-accuracy', 3)
    check(page.inner_text('#te-price') == '64' and tt('accuracy').startswith('100% · 100% per shot at this fire rate'), f'the 100% accuracy step on a Basic tower costs 64 ({page.inner_text("#te-price")})')
    set_slider(page, '#te-rate', 1)
    check(tt('accuracy').startswith('100% · 95% per shot at this fire rate') and tt('rate').startswith('2.5 per second · 7.2 per hit · 95% accurate') and page.inner_text('#te-rate-v') == '2.5/s · 7.2/hit',
          f'fire rate shifts the per-shot accuracy ({tt("accuracy")[:40]} / {tt("rate")[:40]})')
    check(page.evaluate("() => +document.querySelector('#te-rate').value") == 4 and S(page, f'S.grid[{idx(9,5)}].cfg.rate') == 1,
          'v21.1: the fire rate slider runs slow to fast: 2.5 shots a second sits right of 1 a second')
    page.evaluate("() => { const i = document.querySelector('#te-rate'); i.value = 5; i.dispatchEvent(new Event('input', {bubbles:true})); i.dispatchEvent(new Event('change', {bubbles:true})); }")
    check(page.inner_text('#te-rate-v').startswith('4/s') and 'maxed' in page.get_attribute('#te-rate-row', 'class'), 'raising it to the right end fires fastest (4/s), and the maxed slider glows')
    page.evaluate("() => { const i = document.querySelector('#te-rate'); i.value = 3.4; i.dispatchEvent(new Event('input', {bubbles:true})); i.dispatchEvent(new Event('change', {bubbles:true})); }")
    check(page.inner_text('#te-rate-v').startswith('1.6/s') and page.evaluate("() => +document.querySelector('#te-rate').value") == 3, 'a slider let go between steps snaps to the nearest one')
    w0 = page.evaluate("() => [...document.querySelectorAll('#def-ctx .strack')].map(t => Math.round(t.getBoundingClientRect().width))")
    for v in (0, 2, 5): set_slider(page, '#te-rate', v); set_slider(page, '#te-range', v)
    w1 = page.evaluate("() => [...document.querySelectorAll('#def-ctx .strack')].map(t => Math.round(t.getBoundingClientRect().width))")
    check(len(set(w0)) == 1 and w0 == w1, f'every slider track has the same length, whatever the values ({w0} / {w1})')
    set_slider(page, '#te-range', 2); set_slider(page, '#te-rate', 1)
    set_slider(page, '#te-accuracy', 1)
    check(tt('accuracy').startswith('87% · 82% per shot at this fire rate'), f'the spec’s example label: 87% · 82% per shot at 2.5/s ({tt("accuracy")[:40]})')
    set_slider(page, '#te-accuracy', 0); set_slider(page, '#te-rate', 3)
    up = page.evaluate(f'() => {{ const sl = window.siegeline, c = sl.state.grid[{idx(9,5)}].cfg; return sl.towerCost({{...c, dps: c.dps + 1}}) - sl.towerCost(c); }}')
    check(page.inner_text('#te-dps-n') == f'+{up}' and 'poor' not in page.get_attribute('#te-dps-n', 'class'), f'slider shows what the next step costs ({page.inner_text("#te-dps-n")})')
    check(page.inner_text('#te-rate-n').lower() == 'free', 'the free slider says Free instead of a step price')
    fr = S(page, 'S.dFree')
    page.evaluate('() => { window.siegeline.state.dFree = 5; window.siegeline.refresh(); }')
    check('poor' in page.get_attribute('#te-dps-n', 'class') and 'poor' in page.get_attribute('#def-ctx [data-fx=poison]', 'class'), 'step price turns red when unaffordable (the effect chip too)')
    page.evaluate(f'() => {{ window.siegeline.state.dFree = {fr}; window.siegeline.refresh(); }}')
    set_slider(page, '#te-splash', 3)
    check(page.inner_text('#te-splash-n') == 'Max', 'top of a slider shows Max')
    set_slider(page, '#te-splash', 0)
    set_slider(page, '#te-range', 5); r_only = int(page.inner_text('#te-price'))
    set_slider(page, '#te-range', 2); set_slider(page, '#te-dps', 5); d_only = int(page.inner_text('#te-price'))
    set_slider(page, '#te-range', 5); both = int(page.inner_text('#te-price'))
    check(both - 40 > (r_only - 40) + (d_only - 40), f'stacked upgrades cost more ({both-40} > {r_only-40}+{d_only-40})')
    check(page.locator('[data-act=tips]').count() == 0 and 'in proportion to its reach' in tt('range').lower(), 'v21: no Tips button; a slider’s hint is in its tooltip (and under “?”)')
    set_slider(page, '#te-range', 2); set_slider(page, '#te-dps', 2)
    page.screenshot(path=f'{OUT}/d1_editor.png')
    page.click('[data-act=close]')
    check(page.inner_text('#d-tprice') == '50 coins', 'second tower costs 40 + 10 fee')
    click_cell(page, 13, 5); page.click('[data-act=close]')
    check(page.inner_text('#d-tprice') == '60 coins', 'third tower costs 40 + 20 fee')
    click_cell(page, 4, 3); page.click('[data-act=close]')
    check(S(page, f'S.grid[{idx(4,3)}].fee') == 20, 'third tower fee recorded')
    fr = S(page, 'S.dFree')
    page.click('.tool[data-tool=remove]'); click_cell(page, 4, 3)
    check(S(page, 'S.dFree') == fr + 60, 'removing refunds tuning + build fee')
    page.click('.tool[data-tool=tower]'); click_cell(page, 4, 3); page.click('[data-act=close]')
    # moving the oldest tower (no fee, tuned) and rebuilding it with the same tuning leaves the coins where they were
    fr, cfg = S(page, 'S.dFree'), S(page, f'S.grid[{idx(9,5)}].cfg')
    tuned = page.evaluate(f'() => window.siegeline.towerCost(window.siegeline.state.grid[{idx(9,5)}].cfg)')
    page.click('.tool[data-tool=remove]'); click_cell(page, 9, 5)
    check(S(page, 'S.dFree') == fr + tuned + 20 and S(page, f'S.grid[{idx(4,3)}].fee') == 0,
          'removing the oldest tower refunds its tuning and the top fee (20); the newest takes over its fee')
    for src, dst in (((9, 5), (9, 4)), ((9, 4), (9, 5))):
        if src != (9, 5): page.click('.tool[data-tool=remove]'); click_cell(page, *src)
        page.click('.tool[data-tool=tower]'); click_cell(page, *dst)
        set_slider(page, '#te-range', 2); set_slider(page, '#te-dps', 2); page.click('[data-act=close]')
        check(S(page, f'S.grid[{idx(*dst)}].cfg') == cfg and S(page, 'S.dFree') == fr, f'tower moved to {dst} with the same tuning: coins unchanged ({S(page, "S.dFree")} vs {fr})')
    check(sorted(S(page, 'S.grid.filter(g => g && g.t === "tower").map(g => g.fee)')) == [0, 10, 20], 'fees still 0, 10, 20 between the towers')
    chips = page.evaluate("() => [...document.querySelectorAll('#d-tstrip .tchip')].map(c => c.textContent)")
    want = S(page, 'S.grid.filter(g => g && g.t === "tower").sort((a, b) => a.n - b.n).map(g => "T" + g.n + window.siegeline.towerValue(g))')
    check(chips == want, f'v21: the tower strip has a chip per tower, its number and price ({chips})')
    page.screenshot(path=f'{OUT}/d2_towers.png')
    check(page.is_hidden('#def-test'), 'no Test in round 1: there is no last wave yet')
    page.click('#def-lock'); hand(page)
    # attacker
    check(S(page, 'S.phase') == 'attack' and S(page, 'S.seenGrid.every(g=>!g)'), 'attacker sees nothing in round 1')
    check(S(page, 'S.designs.map(d=>window.siegeline.unitCost(d)).join()') == '20,35,6', 'Runner 20, Brute 35, Swarm 6')
    for _ in range(5): page.click('.step.plus[data-i="0"]')
    for _ in range(2): page.click('.step.plus[data-i="1"]')
    for _ in range(10): page.click('.step.plus[data-i="2"]')
    check(S(page, 'S.aFree') == 300 - 100 - 70 - 60, f'army bought ({S(page, "S.aFree")})')
    page.click('.rpick[data-i="1"]')
    check(page.is_visible('#ue-price'), 'designer opens')
    # v19 (spec test 9): no dodge anywhere: no Dodge row in the designer, no dodge field in a design or an encoded army
    check(page.locator('#ue-dodge').count() == 0 and 'dodge' not in page.inner_text('#roster').lower(), 'the designer has no Dodge slider')
    enc = page.evaluate('() => window.siegeline.encodeArmy(window.siegeline.state.designs)')
    check(all(len(a) == 11 for a in enc) and S(page, 'S.designs.every(d => !("dodge" in d))'), f'an encoded army has no dodge slot (11 fields: {enc[0]})')
    for k, v in (('hp', 2), ('speed', 5), ('armor', 0)): set_slider(page, f'#ue-{k}', v)
    check(S(page, '[S.designs[1].hp, S.designs[1].speed, S.designs[1].armor, S.designs[1].regen, S.designs[1].resist].join()') == '2,5,0,0,none' and page.inner_text('#ue-price') == '16',
          f'the Ghost, Health 112 and Speed 1.9 and nothing else, costs 16 ({page.inner_text("#ue-price")})')
    for k, v in (('hp', 6), ('speed', 1), ('armor', 1)): set_slider(page, f'#ue-{k}', v)  # back to a Brute
    up = page.evaluate('() => { const sl = window.siegeline, d = sl.state.designs[1]; return (sl.unitCost({...d, hp: d.hp + 1}) - sl.unitCost(d)) * d.count; }')
    check(page.inner_text('#ue-hp-n') == f'+{up}', f'unit slider prices the next step for every unit of the design ({page.inner_text("#ue-hp-n")})')
    page.click('#roster [data-act=close]')
    page.screenshot(path=f'{OUT}/a0_army.png')
    page.click('#atk-next')
    check(S(page, 'S.step') == 1 and 'sabotage' in page.inner_text('#atk-steps [aria-current=step]').lower() and page.inner_text('#a-chg-note') == 'No sabotage this wave.',
          'Sabotage is step 2, before the wave, and says “No sabotage this wave.” in round 1')
    check(page.is_hidden('#atk-test'), 'no attacker Test in round 1: nothing seen yet')
    page.click('#atk-next'); page.wait_for_timeout(300)
    check(S(page, 'S.step') == 2 and page.locator('#wv-rows .wv-grp').count() == 3 and page.is_visible('#wv-play'), 'v22: the Wave step shows a release row per group and ▶ PLAY WAVE under the map')
    check(S(page, 'S.designs[0].tl.e') == 0.3, 'default timeline window is 6 seconds')
    check(page.is_hidden('#atk-test'), 'v22: no attacker Test on the Wave step (the forecast plays the wave)')
    # the bar's left end is the latest release (20 s at the left, the gate on the right): drag it to the left end
    row0 = '#wv-rows .wv-grp[data-id] >> nth=0'
    hb = page.locator(f'{row0} >> .bar .h.l').bounding_box(); tb = page.locator(f'{row0} >> .track').bounding_box()
    drag(page, hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2, tb['x'] + 1, hb['y'] + hb['height'] / 2)
    e0 = S(page, 'S.designs[0].tl.e')
    check(e0 > 0.95 and S(page, 'S.designs[0].tl.s') == 0, f'dragging the bar’s left end stretches the group to 20 s, the first release kept ({e0:.2f})')
    # one dot of the swarm to the middle: only that unit's release changes
    p0 = S(page, 'S.designs[2].tl.pos.slice()')
    row2 = '#wv-rows .wv-grp[data-id] >> nth=2'
    db = page.locator(f'{row2} >> .dot >> nth=0').bounding_box(); tb2 = page.locator(f'{row2} >> .track').bounding_box()
    drag(page, db['x'] + db['width'] / 2, db['y'] + db['height'] / 2, tb2['x'] + tb2['width'] * 0.5, db['y'] + db['height'] / 2)
    p1 = S(page, 'S.designs[2].tl.pos.slice()')
    moved = [round(v, 3) for v in p1 if all(abs(v - u) > 1e-9 for u in p0)]
    check(len(moved) == 1 and abs(moved[0] - 0.5) < 0.04 and sorted(p0[1:]) == [v for v in p1 if abs(v - moved[0]) > 1e-9], f'v22 test 3: a dot dragged on its own changes only that unit’s release ({moved})')
    # the whole group: drag the swarm's bar 5 s toward the gate; its spread stays, and it leaves sooner
    s0, e0 = S(page, 'Math.min(...S.designs[2].tl.pos)'), S(page, 'Math.max(...S.designs[2].tl.pos)')
    page.mouse.move(5, 5); page.wait_for_timeout(30)  # off the dot just dragged: a hovered dot is enlarged and would take the press
    page.evaluate("() => { const S = window.siegeline.state; S.designs[2].tl = { s: 0.4, e: 0.6, pos: null }; window.siegeline.refresh(); }")
    bb = page.locator(f'{row2} >> .bar').bounding_box(); y = bb['y'] + 2  # the bar's top edge, clear of the unit dots
    tb2 = page.locator(f'{row2} >> .track').bounding_box()
    T = 11.0  # both still on the way: 3 s after the old first release, 8 s after the new one
    before = page.evaluate(f'() => window.siegeline.wave.at(2, 0, {T})')
    drag(page, bb['x'] + bb['width'] / 2, y, bb['x'] + bb['width'] / 2 + tb2['width'] * 0.25, y)
    s1, e1 = S(page, 'Math.min(...S.designs[2].tl.pos)'), S(page, 'Math.max(...S.designs[2].tl.pos)')
    after = page.evaluate(f'() => window.siegeline.wave.at(2, 0, {T})')
    check(abs((0.4 - s1) * 20 - 5) < 0.3 and abs((e1 - s1) - 0.2) < 1e-6 and before and after and 'w' in before and 'w' in after and after['w'] > before['w'] + 4,
          f'v22 test 2: a bar dragged toward the gate leaves sooner, its spread kept, and its units are further along the route at the same clock time ({0.4 * 20:.1f}s → {s1 * 20:.1f}s; walked {before} → {after})')
    bb = page.locator(f'{row2} >> .bar').bounding_box()
    drag(page, bb['x'] + bb['width'] / 2, y, tb2['x'] + tb2['width'] + 200, y)
    drag(page, page.locator(f'{row2} >> .bar').bounding_box()['x'] + 3, y, tb2['x'] - 300, y)
    check(S(page, 'Math.max(...S.designs[2].tl.pos) <= 1 && Math.min(...S.designs[2].tl.pos) >= 0 && Math.max(...S.designs[2].tl.pos) > 0.999'),
          'v22 test 4: a group dragged past either end stops at 0 s or 20 s')
    page.screenshot(path=f'{OUT}/a1_wave.png')
    page.click('[data-wv=rush]')
    check(S(page, 'S.designs.every(d => !d.count || Math.max(...d.tl.pos) <= 0.12 + 1e-9)'), 'All at once bunches every track')
    page.click('[data-wv=even]')
    check(S(page, 'S.designs.every(d => !d.count || (d.tl.s === 0 && d.tl.e === 1))'), 'Even spreads every track')
    page.click('[data-wv=rush]')
    check(page.is_hidden('#atk-next') and page.inner_text('#atk-lock').lower() == 'lock in' and len(page.evaluate("() => [...document.querySelectorAll('#atk-steps [data-step]')]")) == 3,
          'v21: three steps (Army, Sabotage, Wave); the Wave step has Lock in and no Next')
    army = S(page, 'S.designs.reduce((v,d)=>v+d.count*window.siegeline.unitCost(d),0)')
    page.click('#atk-lock'); hand(page)
    check(S(page, 'S.phase') == 'wave' and S(page, 'S.wave.x') == army, 'wave strength = army value')
    check(S(page, 'Math.max(...S.spawnList.map(e=>e.t))') <= 0.12 * 20 + 0.1, 'spawn times follow the timeline (all within 2.4s)')
    page.wait_for_timeout(2500)
    page.screenshot(path=f'{OUT}/w0_wave.png')
    page.evaluate('() => window.siegeline.advance(200)')
    page.wait_for_timeout(150)
    L = S(page, 'S.last')
    check(S(page, 'S.phase') == 'summary', 'round 1 ends')
    check(abs(S(page, 'S.keep') - (1000 - L['Y'])) < 1e-6 and page.inner_text('#v-keep') == str(int(-(-S(page, 'S.keep') // 1))), 'keep display shows remaining keep')
    print('  round 1', {k: L[k] for k in ['X', 'Y', 'breach', 'dGain', 'aGain']})
    page.screenshot(path=f'{OUT}/w1_summary.png')
    match = 'JSON.stringify([S.round, S.keep, S.dFree, S.aFree, S.phase, S.totals, S.grid.map(g => g ? (g.t === "wall" ? "w" : "t" + g.off) : 0)])'
    before = S(page, match)
    page.click('#sum-replay')
    check(S(page, 'S.phase') == 'wave' and page.evaluate('() => window.siegeline.replaying') and page.is_hidden('#ov-sum'), 'summary Replay plays the wave again')
    check(page.inner_text('#wave-title').lower().startswith('replay') and page.is_visible('#replay-bar'), 'replay is labelled and has its controls')
    page.evaluate('() => window.siegeline.advance(200)')
    R = S(page, 'S.wave')
    check([R['x'], R['y'], R['kills'], R['leaks']] == [L['X'], L['Y'], L['kills'], L['leaks']], f'replay matches the real wave exactly ({R["y"]} vs {L["Y"]})')
    page.screenshot(path=f'{OUT}/w1_replay_done.png')
    page.click('#rp-again'); page.wait_for_timeout(100)
    check(S(page, 'S.wave.y') == 0 and S(page, 'S.units.length + S.spawnList.length') > 0, 'Restart plays it from the top')
    page.click('#rp-close')
    check(S(page, match) == before and page.is_visible('#ov-sum') and not page.evaluate('() => window.siegeline.replaying'), 'closing the replay returns to the summary, match untouched')
    page.click('#sum-next'); hand(page)

    # round 2: defender rebuilds tower at (13,5) (fresh) and adds one at (2,2)
    page.click('.tool[data-tool=remove]'); click_cell(page, 13, 5)
    page.click('.tool[data-tool=tower]'); click_cell(page, 13, 5); page.click('[data-act=close]')
    check(S(page, f'S.grid[{idx(13,5)}].fresh') is False, 'tower torn down and rebuilt on the same cell is not new')
    page.click('#def-lock'); hand(page)
    page.evaluate('() => { window.siegeline.state.aFree = 500; }'); sure_sappers(page)
    page.click('#atk-next')
    page.wait_for_timeout(300)
    check(S(page, 'S.step') == 1 and 'no sabotage' not in page.inner_text('#a-chg-note').lower(), 'Sabotage open in round 2')
    check(page.is_visible('[data-sabo=bridge]') and page.is_visible('[data-sabo=tower]') and 'tap a marked wall or tower' in page.inner_text('#a-chg-note').lower(),
          'Sabotage shows two one-line cards, bridge a wall and knock out a tower, and one line of what to do')
    check('sapper' in page.get_attribute('[data-sabo=bridge]', 'data-tip').lower() and page.inner_text('#a-sabo-bridge') == '25', f'the bridge card’s price, and its tooltip says a sapper carries it ({page.inner_text("#a-sabo-bridge")})')
    page.click('[data-sabo=bridge]')
    check(page.get_attribute('[data-sabo=bridge]', 'aria-pressed') == 'true' and 'marked wall' in page.inner_text('#a-chg-note'), 'picking Bridge a wall explains it and marks the walls')
    page.click('[data-sabo=tower]')
    check(page.get_attribute('[data-sabo=tower]', 'aria-pressed') == 'true' and page.get_attribute('[data-sabo=bridge]', 'aria-pressed') == 'false'
          and 'marked tower' in page.inner_text('#a-chg-note'), 'picking Knock out a tower switches the card')
    page.click('[data-sabo=tower]')
    check(page.get_attribute('[data-sabo=tower]', 'aria-pressed') == 'false', 'tapping the picked card again unpicks it')
    # the knock-out goes on a tower whose range the seen route walks through (units steer round tower range when they can)
    RANGES = [1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5]
    route = page.evaluate('() => window.siegeline.seenRoute()')
    towers = page.evaluate('() => window.siegeline.state.seenGrid.map((g, i) => g && g.t === "tower" ? [i, g.cfg.range] : null).filter(Boolean)')
    near = lambda i, R: min(((j % COLS - i % COLS) ** 2 + (j // COLS - i // COLS) ** 2) ** 0.5 for j in route) <= R - 0.3
    T95 = next(i for i, rg in towers if near(i, RANGES[rg]))
    # sabotage counts a tower by its slider price (C), not its build fee
    val = lambda i: page.evaluate(f'() => window.siegeline.towerCost(window.siegeline.state.seenGrid[{i}].cfg)')
    values = page.evaluate('() => window.siegeline.state.seenGrid.filter(g => g && g.t === "tower").map(g => window.siegeline.towerCost(g.cfg))')
    v95, cap = val(T95), sum(values) / 2
    p95 = int(15 + 0.2 * v95 + 0.5)
    click_cell(page, T95 % COLS, T95 // COLS)
    check(f'send a sapper · {p95} coins' in page.inner_text('#atk-ctx').lower(), f'tapping a seen tower opens the knock-out card: 15 + 20% of its slider price {v95} ({p95})')
    check(f'knock-out cap: 0 of {int(cap)}' in page.inner_text('#a-cap-card').lower() and S(page, 'parseFloat(document.querySelector("#a-cap-card .ext").style.width)') > 0,
          f'the tapped tower previews its slider price on the cap bar ({page.inner_text("#a-cap-card")})')
    page.click('#atk-ctx [data-act=plant]')
    check(S(page, f'S.charges.get({T95}).kind') == 'tower' and S(page, f'S.charges.get({T95}).cost') == p95 and S(page, 'S.aFree') == 500 - p95, f'knock-out planned for {p95}')
    page.screenshot(path=f'{OUT}/a2_sabotage.png')
    page.click('#atk-ctx [data-act=close]')
    over = next(i for i, _ in towers if i != T95 and v95 + val(i) > cap)
    click_cell(page, over % COLS, over // COLS); page.wait_for_timeout(100)
    by = int(v95 + val(over) - cap + 0.999)
    check(f'over the cap by {by}' in page.inner_text('#atk-ctx').lower() and not page.is_visible('#atk-ctx [data-act=plant]') and 'over' in page.get_attribute('#a-cap-card .ext', 'class'),
          f'a second tower over the cap is refused, and the bar says by how much ({v95} + {val(over)} > half of {sum(values)})')
    page.click('#atk-ctx [data-act=close]')
    check(page.locator('#a-cap').count() == 0, 'v21: the cap bar shows only in a tapped tower’s card')
    click_cell(page, T95 % COLS, T95 // COLS); page.wait_for_timeout(60)
    cap_l = page.inner_text('#a-cap-card').lower()
    check((f'knock-out cap: {v95} of {int(cap)}' in cap_l or 'cap reached' in cap_l) and f'{p95} coins' in cap_l and page.is_visible('#atk-ctx [data-act=unplant]')
          and S(page, 'parseFloat(document.querySelector("#a-cap-card .fill").style.width)') > 0, f'the targeted tower’s card: the cap bar filled with it, its coins, and Call off ({cap_l})')
    page.click('#atk-ctx [data-act=close]')
    # a wall away from the route can't take a bridge: bridges are shortcuts on the route
    away = page.evaluate(f'() => {{ const S = window.siegeline.state; for (let r = 0; r < 10; r++) {{ const i = r * {COLS} + 7; if (S.seenGrid[i] && S.seenGrid[i].t === "wall" && !window.siegeline.canBridgeAt(i)) return i; }} return -1; }}')
    a0 = S(page, 'S.aFree')
    if away >= 0:
        click_cell(page, away % COLS, away // COLS)
        check(S(page, 'S.charges.size') == 1 and S(page, 'S.aFree') == a0 and toast(page) == 'Bridges must connect to the current path.', f'a wall off the route is refused ({toast(page)})')
    else: print('SKIP every wall in column 7 touches the route')
    BW = spot(page, 7); bw = idx(*BW)
    click_cell(page, *BW)
    check(S(page, f'S.charges.get({bw}).kind') == 'bridge' and S(page, f'S.charges.get({bw}).cost') == 25 and S(page, 'S.aFree') == 500 - p95 - 25,
          f'the bridge (on {BW}, beside the route) costs 25: a knock-out planned with it doesn’t raise its price')
    at = S(page, f'S.charges.get({bw}).at')
    check(at in S(page, 'window.siegeline.state.seenGrid && (() => { const S = window.siegeline.state; return [...S.seenGrid.keys()].filter(i => !S.seenGrid[i]); })()')
          and abs(at % COLS - bw % COLS) + abs(at // COLS - bw // COLS) == 1, f'its sapper’s tile is an open cell beside the wall ({at % COLS}, {at // COLS})')
    check(page.get_attribute('[data-sabo=bridge]', 'aria-pressed') == 'true' and page.inner_text('#a-sabo-bridge').startswith('Planned'),
          'tapping a wall picks the bridge card, which then shows the bridge planned')
    check('one bridge per wave' in page.inner_text('#a-chg-note').lower() and 'off' in page.get_attribute('[data-sabo=bridge]', 'class'), 'with one planned the bridge card greys out: One bridge per wave.')
    a0 = S(page, 'S.aFree')
    other = next(c for c in ((7, 7), (7, 6), (7, 2)) if idx(*c) != bw)
    click_cell(page, *other)
    check(not S(page, f'S.charges.has({idx(*other)})') and S(page, 'S.aFree') == a0 and toast(page) == 'One bridge per wave.', f'one bridge per wave ({toast(page)})')
    page.click(f'[data-rm="{T95}"]')
    check(not S(page, f'S.charges.has({T95})') and S(page, f'S.charges.get({bw}).cost') == 25 and S(page, 'S.aFree') == 500 - 25, 'calling off the knock-out refunds it; the bridge stays 25')
    click_cell(page, T95 % COLS, T95 // COLS); page.click('#atk-ctx [data-act=plant]'); page.click('#atk-ctx [data-act=close]')
    check(S(page, f'S.charges.get({T95}).cost') == p95 and S(page, 'S.aFree') == 500 - 25 - p95, f'planned again after the bridge, the knock-out still costs {p95}: plan order doesn’t matter')
    page.screenshot(path=f'{OUT}/a2_bridge_planned.png')
    # step 3: each sapper is a row of its own with a single ◆, named by its job (v22)
    page.click('#atk-next'); page.wait_for_timeout(300)
    names = page.evaluate("() => [...document.querySelectorAll('#wv-rows .wv-grp.sap .nm')].map(e => e.textContent)")
    check(S(page, 'S.step') == 2 and page.locator('#wv-rows .wv-grp.sap').count() == 2 and page.locator('#wv-rows .wv-grp.sap .dot').count() == 2
          and any(n.startswith('Bridge → wall ') for n in names) and any(n.startswith('Knock-out → Tower ') for n in names), f'Wave step: a row per sapper with one ◆, named by its job ({names})')
    t0 = S(page, f'S.charges.get({bw}).t')
    sr = f'#wv-rows .wv-grp[data-id="s{bw}"]'
    page.locator(sr).scroll_into_view_if_needed()
    db = page.locator(f'{sr} .dot').bounding_box(); lb = page.locator(f'{sr} .track').bounding_box()
    drag(page, db['x'] + db['width'] / 2, db['y'] + db['height'] / 2, lb['x'] + lb['width'] * 0.25, db['y'] + db['height'] / 2)
    t1 = S(page, f'S.charges.get({bw}).t')
    check(abs(t1 - 0.75) < 0.03 and t1 != t0, f'dragging a sapper’s ◆ sets when it leaves: a quarter of the way from the 20 s end is 15 s ({t0:.3f} → {t1:.3f})')
    page.evaluate(f'() => {{ const S = window.siegeline.state; S.charges.get({bw}).t = 0.02; S.charges.get({T95}).t = 0.02; window.siegeline.refresh(); }}')
    page.screenshot(path=f'{OUT}/a3_sapper_tracks.png')
    check(page.is_hidden('#atk-test'), 'v22: the attacker has no separate test run')
    page.click('#atk-lock'); hand(page)
    check(page.get_attribute('#pane-wave .speed [data-speed="1"]', 'aria-pressed') == 'true' and page.evaluate('() => window.siegeline.speed') == 1, 'the real wave keeps its own speed (1×), whatever the test ran at')
    d0 = S(page, 'S.dFree')
    check(S(page, 'S.units.some(u => u.sap)') or S(page, 'S.spawnList.some(e => e.sk != null)'), 'sappers march with the army')
    check(advance_until(page, f'S.grid[{T95}].off > 0'), 'the knock-out sapper takes its tower offline on walking into range')
    sap_gone = S(page, f'!S.units.some(u => u.sap && u.sap.cell === {T95})') and S(page, f'S.sapList.find(sp => sp.cell === {T95}).state') == 'done'
    check(sap_gone and S(page, 'S.wave.jammed') == 1, 'that sapper is used up')
    check(all(S(page, f'S.grid[{i}].off') == 0 for i, _ in towers if i != T95), 'the other towers keep shooting')
    check(advance_until(page, f'S.bridges.has({bw})'), 'the bridge goes down when its sapper reaches its tile')
    check(S(page, f'S.grid[{bw}]') is None and S(page, 'S.dFree') == d0 + 5 and S(page, 'S.wave.bridgeRefund') == 5, 'the bridge replaced the wall and the wall is refunded to the defender')
    check(S(page, f'[{bw - COLS}, {bw + COLS}].every(j => !S.seenGrid[j] || S.seenGrid[j].t !== "wall" || (S.grid[j] && S.grid[j].t === "wall"))') and S(page, f'!!S.grid[{bw - COLS}]'),
          f'a bridge leaves the walls next to it standing (bridge on {BW})')
    page.wait_for_timeout(300)
    page.screenshot(path=f'{OUT}/w2_bridge.png')
    page.evaluate('() => window.siegeline.advance(200)')
    L2, before = S(page, 'S.last'), S(page, match)
    sapline = page.inner_text('#ov-sum .sum-sap') if page.is_visible('#ov-sum .sum-sap') else ''
    details(page)
    check(L2['bridges'] == 1 and L2['sapOk'] == 2 and L2['sappers'] == 2 and 'bridged' in page.inner_text('#ov-sum').lower() and sapline == 'Sappers landed 2 / 2',
          f'summary: “Sappers landed 2 / 2” up top, the bridge in its Details ({sapline})')
    check(S(page, f'S.grid[{T95}].off') == 0 and S(page, 'S.charges.size') == 0, 'a knock-out lasts the wave; the plan is spent')
    page.click('#sum-replay'); page.evaluate('() => window.siegeline.advance(200)')
    R = S(page, 'S.wave')
    check([R[k] for k in ['x', 'y', 'kills', 'bridges', 'jammed', 'sapOk']] == [L2[k] for k in ['X', 'Y', 'kills', 'bridges', 'jammed', 'sapOk']], 'replay with sappers matches the real wave')
    page.click('#rp-close')
    check(S(page, match) == before and S(page, 'S.bridges.size') == 1, 'replaying changes nothing in the match')
    page.click('#sum-next'); hand(page)
    # round 3, defender: the bridge stays, nothing goes on it, and its ends can be walled
    check(S(page, f'S.bridges.has({bw}) && !S.grid[{bw}]'), 'the bridge is still there next round')
    click_cell(page, *BW)
    check(S(page, f'S.grid[{bw}]') is None and 'bridge' in toast(page).lower(), f'nothing can be built on a bridge ({toast(page)})')
    page.screenshot(path=f'{OUT}/d3_bridge.png')
    W2 = spot(page, 7); w2 = idx(*W2)  # a wall beside the route the attacker saw
    page.click('.tool[data-tool=remove]'); click_cell(page, *W2)
    check(S(page, f'S.grid[{w2}]') is None, 'defender takes down a wall the attacker saw')
    page.click('.tool[data-tool=tower]'); click_cell(page, T95 % COLS, T95 // COLS)
    check(page.is_visible('#te-price'), 'the knocked-out tower is back: it can be retuned')
    fm = S(page, 'S.freeMv'); n95 = S(page, f'S.grid[{T95}].n')
    check(fm and fm['all'] and n95 in fm['n'] and page.inner_text('#te-move').startswith('Moves free this round: a bridge went down') and int(page.inner_text('#te-refund')) == S(page, f'window.siegeline.towerCost(S.grid[{T95}].cfg)') + S(page, 'Math.max(...S.grid.filter(g => g && g.t === "tower").map(g => g.fee || 0))'),
          f'v23: a bridge landed last wave, so every move is free this round (and the knocked-out tower is listed): {fm} · {page.inner_text("#te-move")}')
    page.click('#def-ctx [data-act=close]')
    check('×' in page.inner_text('#d-intel') and page.is_visible('#d-intel [data-act=replay]'), f'v21: the intel strip shows the army seen last wave, with Replay ({page.inner_text("#d-intel")})')
    page.click('#def-body [data-act=replay]')
    check(page.evaluate('() => window.siegeline.replaying') and S(page, 'S.round') == 2, 'the build screen replays the last wave while planning')
    page.keyboard.press('Escape')
    check(S(page, 'S.phase') == 'defend' and S(page, 'S.step') == 0 and S(page, 'S.round') == 3, 'Escape closes the replay back to planning')
    page.click('#def-lock'); hand(page)
    page.click('#atk-next'); page.wait_for_timeout(300)
    a0 = S(page, 'S.aFree'); click_cell(page, *W2)
    check(S(page, 'S.totals.bridgeTries') == 1 and S(page, 'S.totals.koTries') == 1 and S(page, f'S.charges.get({w2}).cost') == 31 and S(page, 'S.aFree') == a0 - 31,
          'one bridge and one knock-out sent so far: this bridge costs 25 × (1 + 0.25) = 31')
    at2 = S(page, f'S.charges.get({w2}).at')
    on_route = S(page, f'S.path.includes({at2})')  # the defender's real route, after taking the wall down
    page.click('#atk-lock')
    hand(page)
    page.evaluate('() => window.siegeline.advance(200)')
    if on_route: check(S(page, f'S.bridges.has({w2}) && S.bridges.has({bw})') and S(page, 'S.last.bridgeRefund') == 0, 'taking the wall down first does not stop a bridge whose sapper still reaches its tile (and refunds nothing more)')
    else: check(not S(page, f'S.bridges.has({w2})') and S(page, 'S.last.sapMissed') == 1, 'with the wall gone the route skips the sapper’s tile: the bridge misses')
    page.click('#sum-next')
    # attacker win + rematch
    page.evaluate('() => { window.siegeline.state.keep = 3; }')
    hand(page)
    # round 4: the defender turns a seen wall into a tower, so a bridge planned there misses
    W3 = spot(page, 7); w3 = idx(*W3)
    page.click('.tool[data-tool=remove]'); click_cell(page, *W3)
    page.click('.tool[data-tool=tower]'); click_cell(page, *W3); page.click('[data-act=close]')
    check(S(page, f'S.grid[{w3}].t') == 'tower', 'a tower replaces a seen wall')
    page.click('#def-lock'); hand(page)
    page.evaluate('() => { const S = window.siegeline.state; S.aFree = 3000; }')
    for _ in range(15): page.click('.step.plus[data-i="0"]')
    page.click('#atk-next'); page.wait_for_timeout(300)
    a0 = S(page, 'S.aFree'); click_cell(page, *W3)
    check(S(page, f'S.charges.get({w3}).cost') == 38 and S(page, 'S.aFree') == a0 - 38, 'the third bridge costs 25 × (1 + 2 × 0.25) = 38')
    page.click('#atk-next'); page.click('[data-wv=rush]'); page.click('#atk-lock'); hand(page)
    check(advance_until(page, f'S.sapList[0].state !== "go" && S.sapList[0].state !== "wait"'), 'the sapper gets to the end of its job')
    check(S(page, f'S.grid[{w3}].t') == 'tower' and not S(page, f'S.bridges.has({w3})') and S(page, 'S.wave.missed + S.wave.sapMissed') >= 1, 'a bridge on a wall that became a tower misses')
    page.evaluate('() => window.siegeline.advance(120)'); page.wait_for_timeout(2000)
    check(S(page, 'S.winner') == 'attacker' and page.is_visible('#ov-end'), 'attacker wins when the keep falls')
    page.click('#end-again')
    check(S(page, 'S.round') == 1 and S(page, 'S.keep') == 1000 and S(page, 'S.grid.every(g=>!g)') and S(page, 'S.charges.size') == 0 and S(page, 'S.bridges.size') == 0, 'rematch resets, bridges too')
    # defender win
    for rnd in range(1, 9):
        hand(page); page.click('#def-lock'); hand(page)
        page.click('#atk-next')
        if rnd == 8:
            page.wait_for_timeout(150)
            check(page.inner_text('#a-chg-note') == 'No sabotage this wave.', 'no sabotage in the final wave')
        page.click('#atk-lock')
        if rnd == 1: check('nothing' in page.inner_text('#atk-lock').lower(), 'empty army needs confirm')
        page.click('#atk-lock'); hand(page)
        page.evaluate('() => window.siegeline.advance(5)'); page.wait_for_timeout(60)
        if rnd < 8: page.click('#sum-next')
    check(S(page, 'S.winner') == 'defender' and page.is_visible('#ov-end'), 'defender wins after 8 rounds')
    check(not errors, f'no errors on desktop {errors[:3]}')
    ctx.close()

    # ---------- phone portrait
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); no_terrain(page)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    page.tap('#def-steps [data-act=hints]')  # known cells below
    def tap_cell(c, r):
        x, y = page.evaluate(f'() => window.siegeline.cellToClient({idx(c,r)})'); page.touchscreen.tap(x, y)
    tap_cell(4, 4)
    check(S(page, f'S.grid[{idx(4,4)}] && S.grid[{idx(4,4)}].t') == 'wall', 'phone: tap places a wall')
    page.screenshot(path=f'{OUT}/m0_maze.png')
    page.tap('.tool[data-tool=tower]'); page.wait_for_timeout(150)
    tap_cell(9, 5); tap_cell(9, 5)
    check(page.is_visible('#te-price'), 'phone: two taps place a tower and open the editor sheet')
    bx = page.locator('#def-ctx').bounding_box()
    check(bx and bx['x'] >= 0 and bx['x'] + bx['width'] <= 390 and bx['y'] + bx['height'] <= 844, f'phone: editor sheet fits {bx}')
    page.screenshot(path=f'{OUT}/m1_editor.png')
    page.tap('#def-ctx [data-act=close]'); page.wait_for_timeout(400)  # the board slides back from under the sheet
    # touch: drag a tower with a finger; a tap still opens its sheet
    cdp0 = ctx.new_cdp_session(page)
    def touch_drag(a, z):
        (x0, y0), (x1, y1) = [page.evaluate(f'() => window.siegeline.cellToClient({idx(*c)})') for c in (a, z)]
        cdp0.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
        for k in range(1, 9): cdp0.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * k / 8, 'y': y0 + (y1 - y0) * k / 8}]}); page.wait_for_timeout(20)
        cdp0.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); page.wait_for_timeout(80)
    n9, free9 = S(page, f'S.grid[{idx(9,5)}].n'), S(page, 'S.dFree')
    touch_drag((9, 5), (9, 2))
    check(S(page, f'S.grid[{idx(9,2)}] && S.grid[{idx(9,2)}].n') == n9 and S(page, f'S.grid[{idx(9,5)}]') is None and S(page, 'S.dFree') == free9, 'phone: drag a tower with a finger to move it')
    touch_drag((9, 2), (9, 5))
    tap_cell(9, 5); page.wait_for_timeout(100)
    check(S(page, f'S.grid[{idx(9,5)}].n') == n9 and page.is_visible('#te-price'), 'phone: dragged back, and a tap opens its sheet')
    page.tap('#def-ctx [data-act=close]'); page.wait_for_timeout(400)
    # a wobbly tap near the cell's edge that slips a little into the next cell is still a tap, not a move
    (cx, cy), (nx, ny) = [page.evaluate(f'() => window.siegeline.cellToClient({idx(*c)})') for c in ((9, 5), (10, 5))]
    at = lambda f: {'x': cx + (nx - cx) * f, 'y': cy + (ny - cy) * f}
    cdp0.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [at(0.42)]})
    for f in (0.48, 0.55, 0.62): cdp0.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [at(f)]}); page.wait_for_timeout(20)
    cdp0.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); page.wait_for_timeout(100)
    check(S(page, f'S.grid[{idx(9,5)}] && S.grid[{idx(9,5)}].n') == n9 and S(page, f'S.grid[{idx(10,5)}]') is None and page.is_visible('#te-price'),
          'phone: a tap that wobbles over a cell edge opens the sheet and moves nothing')
    page.tap('#def-ctx [data-act=close]')
    page.tap('#def-lock'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    for _ in range(4): page.tap('.step.plus[data-i="0"]')
    for _ in range(6): page.tap('.step.plus[data-i="2"]')
    page.screenshot(path=f'{OUT}/m2_army.png')
    page.tap('#atk-next'); page.wait_for_timeout(100); page.tap('#atk-next'); page.wait_for_timeout(200)
    row0 = '#wv-rows .wv-grp[data-id] >> nth=0'
    page.locator(row0).scroll_into_view_if_needed(); page.wait_for_timeout(100)
    hb = page.locator(f'{row0} >> .bar .h.l').bounding_box(); lb = page.locator(f'{row0} >> .track').bounding_box()
    cdp = ctx.new_cdp_session(page)
    x0, y0 = hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
    for k in range(1, 9):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (lb['x'] + lb['width'] * 0.1 - x0) * k / 8, 'y': y0}]}); page.wait_for_timeout(20)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    e0 = S(page, 'S.designs[0].tl.e')
    check(e0 > 0.8, f'phone: touch-drag the bar’s left end (the last release) out toward 20 s ({e0:.2f})')
    page.screenshot(path=f'{OUT}/m3_wave.png')
    ov = page.evaluate('() => document.documentElement.scrollWidth > innerWidth')
    check(not ov, 'phone: no horizontal overflow')
    page.tap('#atk-lock'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(2500)
    page.screenshot(path=f'{OUT}/m5_live.png')
    page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(200)
    page.tap('#sum-replay'); page.wait_for_timeout(300)
    rb = page.locator('#rp-close').bounding_box()
    check(rb and rb['y'] + rb['height'] <= 844 and rb['x'] + rb['width'] <= 390, f'phone: replay controls visible {rb}')
    page.screenshot(path=f'{OUT}/m6_replay.png')
    page.tap('#rp-close'); page.wait_for_timeout(100)
    check(page.is_visible('#ov-sum'), 'phone: closing the replay returns to the summary')
    # round 2 on the phone: the attacker taps a seen wall to plan a bridge, and it shows on the transposed board
    page.tap('#sum-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    page.tap('#def-lock'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    sure_sappers(page)
    page.tap('#atk-next'); page.wait_for_timeout(300)
    check(page.evaluate(f'() => window.siegeline.canBridgeAt({idx(4,4)})'), 'phone: the wall at (4,4) sits beside the route')
    tap_cell(4, 4)
    check(S(page, f'S.charges.has({idx(4,4)}) && S.charges.get({idx(4,4)}).kind') == 'bridge', 'phone: tapping a seen wall plans a bridge')
    page.screenshot(path=f'{OUT}/m7_bridge_planned.png')
    page.tap('#atk-next'); page.wait_for_timeout(300)
    check(page.locator('#wv-rows .wv-grp.sap').count() == 1 and not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: the sapper’s row fits the Wave step')
    page.screenshot(path=f'{OUT}/m7b_sapper_track.png')
    page.tap('#atk-lock'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(1200)
    check(advance_until(page, f'S.bridges.has({idx(4,4)})'), 'phone: the bridge goes down when its sapper gets there')
    page.screenshot(path=f'{OUT}/m8_bridge_wave.png')
    page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(200)
    page.tap('#sum-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    page.screenshot(path=f'{OUT}/m9_bridge_defender.png')
    check(not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: no horizontal overflow with a bridge on the map')
    check(not errors, f'phone: no errors {errors[:3]}')
    ctx.close()

    # ---------- build helpers: hints (hot tiles, time under fire), shapes, and the test run
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page)
    hints_off(page)  # known cells first; hints back on once the maze stands
    for r in range(0, 9): click_cell(page, 5, r)
    for r in range(2, 11): click_cell(page, 10, r)
    page.click('.tool[data-tool=tower]'); click_cell(page, 7, 4); page.click('[data-act=close]')
    page.click('.tool[data-tool=wall]'); page.click('#def-steps [data-act=hints]')
    check(page.get_attribute('#def-steps [data-act=hints]', 'aria-pressed') == 'true', 'the Hints switch turns hints back on')
    page.wait_for_function('() => Array.isArray(window.siegeline.hot)', timeout=5000)
    hot = page.evaluate('() => window.siegeline.hot')
    check(0 < len(hot) <= 3 and all(S(page, f'!S.grid[{i}]') for i in hot), f'hot tiles: up to 3 empty cells suggested ({[(i % COLS, i // COLS) for i in hot]})')
    mean = page.evaluate('() => window.siegeline.avgSpeed()')
    check(abs(mean - sum([0.7, 0.9, 1.1, 1.3, 1.6, 1.9, 2.3, 2.8]) / 8) < 1e-9, f'average speed is the mean of the speed slider ({mean})')
    uf = page.evaluate('() => window.siegeline.underFire()')
    check(f'{uf:.1f}s' in page.inner_text('#d-route').lower() and uf > 0, f'readout: Path · Under fire ({page.inner_text("#d-route")})')
    len0 = route_len(page)
    page.mouse.move(*page.evaluate(f'() => window.siegeline.cellToClient({hot[0]})')); page.wait_for_timeout(120)
    bar = page.inner_text('#d-route')
    check('→' in bar, f'hovering a glowing tile previews the whole set ({bar})')
    # the route the set forces is the one units really walk: one tanky unit, before and after, in a played wave
    unit = '{ ...window.siegeline.state.designs[0], hp: 9, speed: 4, armor: 3, count: 1, tl: { s: 0, e: 0, pos: null } }'
    walk = f'() => {{ const sl = window.siegeline, S = sl.state; return sl.trial(S.grid, [{unit}], [], 99, [...S.bridges]).t; }}'
    t0 = page.evaluate(walk); f0 = S(page, 'S.dFree')
    page.mouse.click(*page.evaluate(f'() => window.siegeline.cellToClient({hot[0]})')); page.wait_for_timeout(80)
    len1 = route_len(page); t1 = page.evaluate(walk)
    check(all(S(page, f'S.grid[{i}] && S.grid[{i}].t') == 'wall' for i in hot) and S(page, 'S.dFree') == f0 - 5 * len(hot), f'one click on a glowing tile places the whole set as walls ({len(hot)} for {5 * len(hot)} coins)')
    check(len1 > len0 and abs((t1 - t0) * 1.6 - (len1 - len0)) < 0.05, f'the set lengthens the route units walk in a played wave: {len0} → {len1} steps, the unit took {t1 - t0:.2f}s longer at 1.6 cells/s')
    page.click('#def-steps [data-act=hints]'); page.wait_for_timeout(60)
    check(page.evaluate('() => window.siegeline.hot') is None and 'under fire' not in page.inner_text('#d-route').lower(), 'Hints off: no glow, no time under fire (the path length stays)')
    page.wait_for_timeout(400)  # let the switch's storage write settle before the page goes
    page.reload(); page.wait_for_timeout(300); no_terrain(page); page.click('#info-go'); page.click('#mode-local'); hand(page)
    check(page.get_attribute('#def-steps [data-act=hints]', 'aria-pressed') == 'false', 'the Hints choice is remembered on this device')
    # shapes
    page.click('.tool[data-tool=shape]')
    check(page.is_visible('#d-shapes') and page.locator('#d-shapes [data-shape]').count() == 4, 'Shapes: four pieces to pick from')
    page.mouse.move(*page.evaluate(f'() => window.siegeline.cellToClient({idx(2,2)})')); page.wait_for_timeout(80)
    f0 = S(page, 'S.dFree'); click_cell(page, 2, 2)
    uturn = [idx(c, r) for r, row in enumerate(['#####', '....#', '###.#', '....#', '#####']) for c, ch in enumerate(row) if ch == '#']
    check(all(S(page, f'S.grid[{i}] && S.grid[{i}].t') == 'wall' for i in uturn) and S(page, 'S.dFree') == f0 - 5 * len(uturn), f'a U-turn drops in as {len(uturn)} ordinary walls at 5 each')
    page.keyboard.press('r'); page.keyboard.press('f')
    check(S(page, 'window.siegeline.shapeSel.rot') == 1 and S(page, 'window.siegeline.shapeSel.flip') is True, 'R turns the piece a quarter, F flips it')
    page.keyboard.press('r'); page.keyboard.press('r'); page.keyboard.press('r'); page.keyboard.press('f')
    page.click('[data-shape=corridor]'); f0 = S(page, 'S.dFree'); n0 = S(page, 'S.grid.filter(Boolean).length')
    click_cell(page, 2, 2)  # right over the U-turn: walls already there stay, only the rest is built
    corridor = [idx(c, r) for r, row in enumerate(['.#.#.', '.#.#.', '.#.#.', '.#.#.', '.#.T.']) for c, ch in enumerate(row) if ch in '#T']
    new = [i for i in corridor if i not in uturn]
    tower = idx(3, 4) not in uturn
    check(S(page, 'S.grid.filter(Boolean).length') == n0 + len(new) and S(page, 'S.dFree') == f0 - 5 * sum(1 for i in new if i != idx(3, 4)) - (40 if tower else 0),
          f'cells already built are kept and not charged ({len(new)} new)')
    page.click('[data-shape=uturn]'); page.keyboard.press('f'); g0 = S(page, 'S.grid.filter(Boolean).length')
    click_cell(page, 13, 5)  # a U-turn opening right, round the exit, would wall the route in (its gap cell on the exit stays a hole)
    check(S(page, 'S.grid.filter(Boolean).length') == g0 and toast(page) == 'Path must stay open', f'a shape that would close the route is refused whole ({toast(page)})')
    page.keyboard.press('f')
    page.evaluate('() => { window.siegeline.state.dFree = 12; }'); click_cell(page, 12, 7)
    check(S(page, 'S.grid.filter(Boolean).length') == g0 and 'coins short' in toast(page), f'a shape you can’t afford says how many coins are short ({toast(page)})')
    page.evaluate('() => { window.siegeline.state.dFree = 300; }')
    page.screenshot(path=f'{OUT}/h0_shapes.png')
    # test run, from round 2
    check(page.is_hidden('#def-test'), 'no Test before a wave has been played')
    page.click('#def-lock'); hand(page)
    for _ in range(8): page.click('.step.plus[data-i="0"]')
    page.click('#atk-lock')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    L = S(page, 'S.last'); page.click('#sum-next'); hand(page)
    keep, free, grid = S(page, 'S.keep'), S(page, 'S.dFree'), S(page, 'JSON.stringify(S.grid.map(g => g && g.t))')
    check(page.is_visible('#def-test'), 'round 2: the build step offers Test')
    page.click('#def-test')
    check(page.evaluate('() => window.siegeline.testing') and S(page, 'S.phase') == 'wave' and page.is_visible('#test-skip') and page.is_visible('#pane-wave .speed'),
          'Test plays last wave’s army on the board, input locked, with speed controls and a Skip button')
    page.wait_for_timeout(500)
    check(page.inner_text('#v-keep') == str(int(-(-keep // 1))), 'the HUD keeps showing the real keep during a test')
    page.screenshot(path=f'{OUT}/h1_testing.png')
    page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    R = page.evaluate('() => window.siegeline.testResult')
    check(not page.evaluate('() => window.siegeline.testing') and S(page, 'S.phase') == 'defend' and S(page, 'S.keep') == keep and S(page, 'S.dFree') == free
          and S(page, 'JSON.stringify(S.grid.map(g => g && g.t))') == grid, 'after the test nothing in the match has changed')
    check(R and R['leaks'] == L['leaks'] and abs(R['y'] - L['Y']) < 1e-6 and page.is_visible('#d-test')
          and f"{L['leaks']}/{R['sent']} leaked" in page.inner_text('#d-test') and f"Keep −{round(L['Y'])}" in page.inner_text('#d-test'),
          f'the same build tested against the same army gives last wave’s result ({page.inner_text("#d-test")})')
    page.click('#def-test'); page.click('#test-skip')
    check(not page.evaluate('() => window.siegeline.testing') and page.is_visible('#d-test'), 'Skip jumps to the result')
    page.screenshot(path=f'{OUT}/h2_tested.png')
    page.click('#d-test [data-act=test-x]')
    check(page.is_hidden('#d-test'), 'the result card can be dismissed')
    page.click('#def-test'); page.click('#test-skip'); click_cell(page, 12, 0)
    check(page.is_hidden('#d-test'), 'the result card goes once the build changes')
    check(not errors, f'build helpers: no errors {errors[:3]}')
    ctx.close()

    # the same on a phone in portrait: one toolbar row, the board keeps its turn when Shapes opens, the card stays off the board
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); page.evaluate('() => { window.siegeline.rules.starterPresses = 0; }')  # terrain on, but an empty board for the shape
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    tops = page.evaluate("() => [...document.querySelectorAll('#def-body .toolrow > *')].map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.right)]; })")
    check(len({t for t, _ in tops}) == 1 and max(r for _, r in tops) <= 390 - 16, f'phone: the tool row (four tools) fits one row {tops}')
    v0 = page.evaluate('() => [window.siegeline.view.rot, window.siegeline.view.cs]')
    page.tap('.tool[data-tool=shape]'); page.wait_for_timeout(200)
    v1 = page.evaluate('() => [window.siegeline.view.rot, window.siegeline.view.cs]')
    check(v0[0] and v1[0] and v1[1] >= 20, f'phone: the board stays turned with Shapes open, cells {v0[1]} → {v1[1]} px (a 5×5 ghost is {5 * v1[1]} px)')
    x, y = page.evaluate(f'() => window.siegeline.cellToClient({idx(12, 2)})'); page.touchscreen.tap(x, y); page.wait_for_timeout(100)
    g0 = S(page, 'S.grid.filter(Boolean).length'); page.touchscreen.tap(x, y); page.wait_for_timeout(100)
    check(S(page, 'S.grid.filter(Boolean).length') > g0, 'phone: tap shows the ghost, a second tap on it places the shape')
    page.screenshot(path=f'{OUT}/m11_shapes.png')
    page.tap('#def-lock'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    for _ in range(6): page.tap('.step.plus[data-i="0"]')
    page.tap('#atk-lock'); page.wait_for_timeout(60)
    page.wait_for_timeout(450); page.tap('#ov-hand'); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(300)
    page.tap('#sum-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    page.tap('#def-test'); page.wait_for_timeout(200); page.tap('#test-skip'); page.wait_for_timeout(300)
    card = page.locator('#d-test').bounding_box()
    board = page.evaluate("""() => { const v = window.siegeline.view, r = document.querySelector('#board').getBoundingClientRect();
      const w = (v.rot ? 11 : 16) * v.cs, h = (v.rot ? 16 : 11) * v.cs; return { x: r.left + v.ox, y: r.top + v.oy, width: w, height: h }; }""")
    apart = card and (card['y'] >= board['y'] + board['height'] or card['y'] + card['height'] <= board['y'] or card['x'] >= board['x'] + board['width'] or card['x'] + card['width'] <= board['x'])
    check(page.is_visible('#d-test') and apart, f'phone: the test result card sits clear of the board {card} vs {board}')
    check(not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: no horizontal overflow on the build step')
    page.screenshot(path=f'{OUT}/m12_tested.png')
    check(not errors, f'phone build helpers: no errors {errors[:3]}')
    ctx.close()

    # ---------- ties between equal routes go over the bridge (the default heading rule would go up instead)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page()
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    page.evaluate(f'() => {{ window.siegeline.state.bridges.add({idx(8,7)}); window.siegeline.state.dFree = 999; }}')
    for r in range(11):
        if r not in (3, 7): click_cell(page, 8, r)
    path = S(page, 'S.path')
    check(idx(8, 7) in path and idx(8, 3) not in path, 'of two equally long routes, units take the one over the bridge')
    page.evaluate(f'() => {{ window.siegeline.state.bridges.clear(); }}')
    click_cell(page, 8, 3); page.click('.tool[data-tool=remove]'); click_cell(page, 8, 3)  # rebuild the route without the bridge
    path = S(page, 'S.path')
    check(idx(8, 3) in path, 'without the bridge the same tie goes the other way')
    ctx.close()

    # ---------- sapper rules on hand-built defenses, played in hidden test waves (the same simulation as a real wave)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page)
    # a wall three thick (columns 7-9, gap at the bottom) with a bridge laid in its first layer: (7,5) leads nowhere
    thick = [idx(c, r) for c in (7, 8, 9) for r in range(10)]
    setup = f'''() => {{ const S = window.siegeline.state; S.seenGrid = S.seenGrid.map(() => null); for (const i of {thick}) S.seenGrid[i] = {{ t: 'wall', fresh: false }};
      S.seenGrid[{idx(7,5)}] = null; S.bridges = new Set([{idx(7,5)}]); S.grid = S.seenGrid.map(g => g && {{ ...g }}); S.seenVer++; S.seenRound = 1; S.gridVer++; }}'''
    page.evaluate(setup)
    check(page.evaluate(f'() => window.siegeline.canBridgeAt({idx(8,5)})') and not page.evaluate(f'() => window.siegeline.canBridgeAt({idx(8,4)})'),
          'chaining: a wall behind a bridge can be bridged though it doesn’t touch the route; one beside neither can’t')
    sap = lambda body: page.evaluate(f'''() => {{ const sl = window.siegeline, S = sl.state; return (() => {{ {body} }})(); }}''')
    r = sap(f'''const at = sl.seenRoute().find(p => p === {idx(6,5)});
      return sl.trial(S.seenGrid, [], new Map([[{idx(8,5)}, {{ kind: 'bridge', t: 0, cost: 0, at }}]]), 5, [...S.bridges]);''')
    check(r['bridges'] == 1 and r['sapOk'] == 1, f'the sapper stands on the route beside the old bridge and bridges the wall behind it ({r})')
    # the same sapper whose tile is off the route: the sabotage fails at once, the sapper walks on and does nothing at the keep
    r = sap(f'''const route = sl.seenRoute(), off = [...Array(176).keys()].find(i => !S.seenGrid[i] && !S.bridges.has(i) && !route.includes(i) && i % 16 === 12);
      return sl.trial(S.seenGrid, [], new Map([[{idx(8,5)}, {{ kind: 'bridge', t: 0, cost: 0, at: off }}]]), 5, [...S.bridges]);''')
    check(r['bridges'] == 0 and r['sapMissed'] == 1 and r['Y'] == 0 and r['leaks'] == 0, f'path changed: a bridge sapper whose tile is off the route misses and deals no damage at the keep ({r})')
    # knock-outs: a tower whose range covers the entry goes down; one whose range the route never enters can't
    page.evaluate(f'''() => {{ const S = window.siegeline.state, T = (i, range) => ({{ t: 'tower', cfg: {{ range, dps: 2, rate: 3, splash: 0 }}, fee: 0, off: 0, n: i, fresh: false, cd: 0, ang: 0, kick: 0, dealt: 0 }});
      S.seenGrid[{idx(2,6)}] = T({idx(2,6)}, 2); S.seenGrid[{idx(12,0)}] = T({idx(12,0)}, 0); S.seenVer++; }}''')
    r = sap(f'''return sl.trial(S.seenGrid, [], new Map([[{idx(2,6)}, {{ kind: 'tower', t: 0, cost: 0 }}]]), 5, [...S.bridges]);''')
    check(r['jammed'] == 1 and r['sapOk'] == 1, f'a knock-out sapper walking into a tower’s range takes it offline ({r})')
    r = sap(f'''return sl.trial(S.seenGrid, [], new Map([[{idx(12,0)}, {{ kind: 'tower', t: 0, cost: 0 }}]]), 5, [...S.bridges]);''')
    check(r['jammed'] == 0 and r['sapMissed'] == 1, f'a tower whose range the route never enters can’t be knocked out ({r})')
    # a sapper on its own in front of strong towers is shot down, and its sabotage with it
    page.evaluate('() => { window.siegeline.rules.sapper.hp = 0; }')
    r = sap(f'''const G = S.seenGrid.map(g => g && (g.t === 'tower' ? {{ ...g, cfg: {{ ...g.cfg, range: 7, dps: 8 }} }} : g));
      return sl.trial(G, [], new Map([[{idx(8,5)}, {{ kind: 'bridge', t: 0, cost: 0, at: {idx(6,5)} }}]]), 5, [...S.bridges]);''')
    check(r['sapLost'] == 1 and r['bridges'] == 0 and r['kills'] == 0, f'a sapper shot down is lost with its sabotage (not counted as an army kill) ({r})')
    page.evaluate('() => { window.siegeline.rules.sapper.hp = 2; }')
    check(not errors, f'sapper rules: no errors {errors[:3]}')
    ctx.close()

    # ---------- v18: sabotage prices per kind, on slider price; the cap bar; auto-tune
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    # the v18 spec's worked table was priced on v18-v22.2's tower prices (range by its square, damage ^1.15): v23 changed
    # those, not the sabotage formula, so this block checks the formula on the old prices (v23's are checked further on)
    page.evaluate('() => { const R = window.siegeline.rules; R.rangePow = 2; R.dpsPow = 1.15; }')
    PRESETS = {'basic': {}, 'cannon': {'rate': 4, 'splash': 2}, 'sniper': {'range': 5, 'rate': 5}, 'mid': {'range': 4, 'dps': 4, 'splash': 1}, 'big': {'range': 7, 'dps': 6, 'splash': 3, 'slow': True}}
    cost = lambda k: page.evaluate(f'() => {{ const sl = window.siegeline; return sl.towerCost({{ range: 2, dps: 2, rate: 3, splash: 0, slow: false, poison: false, chain: false, ...{json.dumps(PRESETS[k])} }}); }}')
    C = {k: cost(k) for k in PRESETS}
    check([C[k] for k in ('basic', 'cannon', 'sniper', 'mid')] == [40, 76, 102, 212], f'slider prices of the spec’s towers: {C}')
    table = {k: page.evaluate(f'() => [0, 1, 2, 3, 4].map(t => window.siegeline.knockPrice({C[k]}, t))') for k in C}
    want = {'basic': [23, 29, 35, 40, 46], 'cannon': [30, 38, 45, 53, 60], 'sniper': [35, 44, 53, 62, 71], 'mid': [57, 72, 86, 100, 115]}
    check(all(table[k] == want[k] for k in want), f'knock-out prices by earlier knock-outs match the spec’s table {table}')
    check(page.evaluate('() => [0, 1, 2, 3, 4].map(b => window.siegeline.bridgePrice(b))') == [25, 31, 38, 44, 50], 'bridge prices by earlier bridges: 25, 31, 38, 44, 50')
    print(f'   (the spec’s “Big” tower, range 5, 48 dps, splash 1.3, frost, has slider price {C["big"]} here: knock-out {table["big"]})')
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    page.click('#def-lock'); hand(page)
    for _ in range(3): page.click('.step.plus[data-i="0"]')
    for _ in range(3): page.click('.step.plus[data-i="1"]')
    # a hand-made defense as if seen last wave: a Sniper, a Mid and a Big tower (with fees, which sabotage ignores) beside a wall
    seen = f'''([towers, tries]) => {{ const S = window.siegeline.state, T = (cfg, fee) => ({{ t: 'tower', cfg: {{ range: 2, dps: 2, rate: 3, splash: 0, slow: false, poison: false, chain: false, ...cfg }}, fee, off: 0, n: 1, fresh: false, cd: 0, ang: 0, kick: 0, dealt: 0 }});
      S.seenGrid = S.seenGrid.map(() => null); for (const [i, cfg, fee] of towers) S.seenGrid[i] = T(cfg, fee);
      for (let r = 0; r < 10; r++) S.seenGrid[r * 16 + 7] = {{ t: 'wall', fresh: false }};
      S.seenVer++; S.seenRound = 1; S.round = 2; Object.assign(S.totals, tries); S.aFree = 2000; }}'''  # round 2: no sabotage in the first wave
    SN, MI, BG = idx(4, 3), idx(4, 7), idx(11, 2)
    page.evaluate(seen, [[[SN, PRESETS['sniper'], 30], [MI, PRESETS['mid'], 20], [BG, PRESETS['big'], 10]], {'bridgeTries': 0, 'koTries': 2}])
    page.click('#atk-next'); page.wait_for_timeout(250)
    def plant(i):
        click_cell(page, i % COLS, i // COLS); page.wait_for_timeout(60)
        if page.is_visible('#atk-ctx [data-act=plant]'): page.click('#atk-ctx [data-act=plant]')
        page.click('#atk-ctx [data-act=close]')
    plant(SN); plant(MI); one = [S(page, f'S.charges.get({SN}).cost'), S(page, f'S.charges.get({MI}).cost')]
    page.click(f'[data-rm="{SN}"]'); page.click(f'[data-rm="{MI}"]')
    plant(MI); plant(SN); two = [S(page, f'S.charges.get({SN}).cost'), S(page, f'S.charges.get({MI}).cost')]
    check(one == [53, 86] and two == [53, 86] and S(page, 'S.aFree') == 2000 - 139, f'two knock-outs already sent: a Sniper and a Mid this round cost 53 + 86 = 139, in either order ({one}, {two})')
    over = C["sniper"] + C["mid"] + C["big"] - (C["sniper"] + C["mid"] + C["big"]) / 2
    click_cell(page, SN % COLS, SN // COLS); page.wait_for_timeout(60)
    capt = page.inner_text('#a-cap-card').lower()
    check('139 coins' in capt and 'cap reached' in capt, f'with the Big tower too dear to fit, the cap is reached; the bar shows this round’s knock-out coins ({capt})')
    page.click('#atk-ctx [data-act=close]')
    click_cell(page, BG % COLS, BG // COLS); page.wait_for_timeout(60)
    check(f'over the cap by {int(over + 0.999)}' in page.inner_text('#a-cap-card').lower(), f'the cap counts slider prices, not fees: the Big tower is over by {over:.0f} ({page.inner_text("#a-cap-card")})')
    page.click('#atk-ctx [data-act=close]')
    check(page.inner_text('#a-sabo-bridge') == '25', f'knock-outs don’t raise the bridge price: separate counters ({page.inner_text("#a-sabo-bridge")})')
    page.screenshot(path=f'{OUT}/v18_cap.png')
    # three knock-outs sent before: the next bridge still costs 25, the next knock-out on a Basic tower 23 × 1.75
    page.click(f'[data-rm="{SN}"]'); page.click(f'[data-rm="{MI}"]')
    page.evaluate(seen, [[[idx(4, 3), {}, 0], [idx(4, 7), {}, 10]], {'bridgeTries': 0, 'koTries': 3}])
    atk_back(page); page.click('#atk-next'); page.wait_for_timeout(200)
    check(page.inner_text('#a-sabo-bridge') == '25' and page.inner_text('#a-sabo-tower') == '40',
          f'three knock-outs sent: the next bridge still costs 25, a Basic knock-out 40 ({page.inner_text("#a-sabo-bridge")} / {page.inner_text("#a-sabo-tower")})')
    # one tower always fits, even past the cap; after it nothing else can be added
    page.evaluate(seen, [[[BG, PRESETS['big'], 0], [SN, {}, 0]], {'bridgeTries': 0, 'koTries': 0}])
    atk_back(page); page.click('#atk-next'); page.wait_for_timeout(200)
    plant(BG)
    click_cell(page, BG % COLS, BG // COLS); page.wait_for_timeout(60)
    capt = page.inner_text('#a-cap-card').lower()
    check(S(page, f'S.charges.has({BG})') and 'one tower always fits' in capt and S(page, 'document.querySelector("#a-cap-card .fill").style.width') == '100%',
          f'a first target worth more than the cap still fits, and the bar says so ({capt})')
    page.click('#atk-ctx [data-act=close]')
    plant(SN)
    check(not S(page, f'S.charges.has({SN})'), 'with the one-tower exception used, nothing else can be added')
    page.click(f'[data-rm="{BG}"]')
    check(not errors, f'v18 attacker: no errors {errors[:3]}')
    ctx.close()
    # auto-tune: spends free coins on the towers placed, never lowers a slider or touches fire rate; Undo refunds it
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    for r in range(0, 10): click_cell(page, 7, r)
    page.click('.tool[data-tool=tower]'); click_cell(page, 6, 9); set_slider(page, '#te-range', 6); set_slider(page, '#te-rate', 0); page.click('[data-act=close]')
    click_cell(page, 8, 8); page.click('[data-act=close]')
    page.evaluate('() => { window.siegeline.state.dFree += 300; }'); page.click('.tool[data-tool=wall]')
    cfg0, f0, n0 = S(page, 'S.grid.map(g => g && g.t === "tower" ? { ...g.cfg } : null)'), S(page, 'S.dFree'), S(page, 'S.grid.filter(Boolean).length')
    page.click('#def-body [data-act=tune]')
    cfg1, f1 = S(page, 'S.grid.map(g => g && g.t === "tower" ? { ...g.cfg } : null)'), S(page, 'S.dFree')
    nolower = all(c0 is None or all(c1[k] >= c0[k] for k in ('range', 'dps', 'accuracy', 'splash')) and c1['rate'] == c0['rate'] and all(c1[k] or not c0[k] for k in ('slow', 'poison', 'chain')) for c0, c1 in zip(cfg0, cfg1))
    check(nolower and cfg1 != cfg0 and f1 < f0 and S(page, 'S.grid.filter(Boolean).length') == n0, f'auto-tune spends coins on upgrades, never lowers a slider or changes fire rate, adds nothing ({f0} → {f1})')
    check(f'spent {f0 - f1} coins' in page.inner_text('#d-help').lower() and f'{f1} left' in page.inner_text('#d-help').lower(), f'auto-tune says what it spent ({page.inner_text("#d-help")})')
    page.screenshot(path=f'{OUT}/v18_tune.png')
    page.click('#def-body [data-act=undo]')
    check(S(page, 'S.grid.map(g => g && g.t === "tower" ? { ...g.cfg } : null)') == cfg0 and S(page, 'S.dFree') == f0, 'auto-tune: one Undo restores every tower and the coins')
    check(not errors, f'v18 auto-tune: no errors {errors[:3]}')
    ctx.close()

    # ---------- v20.4: the user's Defender QoL spec: Auto-maze, Remove & Inspect, Undo
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    grid = lambda: S(page, 'S.grid.map(g => g ? (g.t === "tower" ? ["tower", g.n, g.fee, !!g.fresh, JSON.stringify(g.cfg)] : [g.t, !!g.fresh]) : null)')
    xy = lambda c, r: page.evaluate(f'() => window.siegeline.cellToClient({idx(c, r)})')
    depth = lambda: page.evaluate('() => window.siegeline.undoDepth()')
    def maze():
        page.click('#def-body [data-act=maze]')
        page.wait_for_function('() => !window.siegeline.mazing'); page.wait_for_timeout(30)
    check(page.is_visible('#def-body [data-act=maze]') and page.is_disabled('#def-body [data-act=tune]') and page.is_disabled('#def-body [data-act=undo]'),
          'Build screen: Auto-maze, Auto-tune (greyed until a tower stands) and Undo (greyed with nothing to undo) in the tool row')
    # round 1: a fixed 60 coins, walls only, the route longer, room left for four towers
    g0, f0, len0 = grid(), S(page, 'S.dFree'), route_len(page)
    check(page.evaluate('() => window.siegeline.mazeBudget()') == 60, 'auto-maze budget in the first wave: 60 coins')
    maze()
    g1, f1, len1 = grid(), S(page, 'S.dFree'), route_len(page)
    added = [i for i in range(len(g0)) if g0[i] != g1[i]]
    check(added and all(g0[i] is None and g1[i] == ['wall', True] for i in added) and f0 - f1 == 5 * len(added) <= 60 and len1 > len0,
          f'auto-maze: {len(added)} new walls for {f0 - f1} coins (at most 60), nothing else; route {len0} → {len1}')
    check(f1 >= 40 + 50 + 60 + 70, f'after auto-maze four plain towers still fit ({f1} free)')
    check(f'{len0} → {len1}' in page.inner_text('#d-help') and f'{f0 - f1} coins' in page.inner_text('#d-help'), f'the helper row says what it built ({page.inner_text("#d-help")})')
    page.screenshot(path=f'{OUT}/q0_automaze.png')
    page.click('#def-body [data-act=undo]')
    check(grid() == g0 and S(page, 'S.dFree') == f0 and route_len(page) == len0 and 'auto-maze' in toast(page).lower(), f'one Undo takes the whole auto-maze back and refunds it ({toast(page)})')
    maze(); page.keyboard.press('Control+z')
    check(grid() == g0 and S(page, 'S.dFree') == f0, 'Ctrl+Z does the same')
    # add-only: it builds around what's there (walls, a tuned tower) and never moves, removes or retunes anything
    for r in range(3, 8): click_cell(page, 4, r)
    page.click('.tool[data-tool=tower]'); click_cell(page, 10, 5); set_slider(page, '#te-dps', 3); set_slider(page, '#te-range', 3); page.click('[data-act=close]')
    page.click('.tool[data-tool=wall]')
    g2, f2 = grid(), S(page, 'S.dFree')
    maze()
    g3, f3 = grid(), S(page, 'S.dFree')
    new_cells = [i for i in range(len(g2)) if g2[i] is None and g3[i]]
    check(new_cells and all(g2[i] is None or g3[i] == g2[i] for i in range(len(g2))) and all(g3[i] == ['wall', True] for i in new_cells) and f2 - f3 == 5 * len(new_cells),
          f'auto-maze only adds walls: everything already built stays as it was ({len(new_cells)} walls added)')
    check(S(page, 'S.path && S.path[S.path.length - 1]') == idx(15, 5), 'the route stays open')
    # multi-step: each change comes back off in turn, newest first, until the board is as the round began
    n = depth()
    check(n == 8, f'eight changes to undo: five walls, a tower, its tuning (one change), auto-maze ({n})')
    said = []
    for _ in range(n): page.keyboard.press('Control+z'); said.append(toast(page).lower())
    check(grid() == g0 and S(page, 'S.dFree') == f0 and depth() == 0, 'undoing all of them leaves the board and the coins as the round began')
    check(said[:3] == ['undone: auto-maze.', 'undone: tower 1 tuning.', 'undone: tower placed.'] and said[3] == 'undone: wall placed.', f'each undo says what it took back ({said[:4]})')
    page.keyboard.press('Control+z')
    check(toast(page) == 'Nothing to undo this round.', 'nothing left to undo')
    # Remove & Inspect: hovering a wall previews the route as if it were bridged; the click removes it
    drag(page, *xy(7, 0), *xy(7, 9))
    check(depth() == 1 and S(page, 'S.grid.filter(g => g && g.t === "wall").length') == 10, 'a drawn line of walls is one change')
    base = route_len(page)
    page.click('.tool[data-tool=remove]')
    check(page.get_attribute('.tool[data-tool=remove]', 'aria-label') == 'Remove & Inspect (R)' and ''.join(page.inner_text('.tool[data-tool=remove]').split()).lower() == 'remove&inspect', 'the Remove card is now Remove & Inspect')
    check(page.is_visible('#tip') and page.inner_text('#tip') == 'Hover walls to preview bridge risk.', 'the first time it is picked, one line says what the inspect part does')
    x, y = xy(7, 5); page.mouse.move(x, y); page.wait_for_timeout(120)
    bar = page.inner_text('#d-route')
    check(S(page, f'S.grid[{idx(7, 5)}].t') == 'wall' and re.search(rf'path\s+{base}\s*→\s*15\s*\(−{base - 15}\)', bar, re.I), f'hovering a wall previews the route without it ({bar})')
    page.screenshot(path=f'{OUT}/q1_inspect.png')
    page.mouse.click(x, y); page.wait_for_timeout(50)
    check(S(page, f'S.grid[{idx(7, 5)}]') is None and route_len(page) == 15, 'a click removes it, and the route is the one previewed')
    page.keyboard.press('Control+z')
    page.click('.tool[data-tool=wall]'); page.click('.tool[data-tool=remove]')
    check(page.is_hidden('#tip'), 'the inspect line shows only the first time')
    # a swipe takes walls back and passes over towers; one Undo puts the swipe back
    page.click('.tool[data-tool=tower]'); click_cell(page, 4, 2); set_slider(page, '#te-dps', 3); set_slider(page, '#te-accuracy', 2); page.click('[data-act=close]')
    page.click('.tool[data-tool=wall]'); drag(page, *xy(2, 2), *xy(6, 2))
    sw, fs, tn = grid(), S(page, 'S.dFree'), S(page, f'S.grid[{idx(4, 2)}].n')
    page.click('.tool[data-tool=remove]'); drag(page, *xy(1, 2), *xy(6, 2))
    check(all(S(page, f'S.grid[{idx(c, 2)}]') is None for c in (2, 3, 5, 6)) and S(page, f'S.grid[{idx(4, 2)}].t') == 'tower' and S(page, 'S.dFree') == fs + 20,
          'with Remove & Inspect a swipe takes the walls back and passes over the tower')
    page.keyboard.press('Control+z')
    check(grid() == sw and S(page, 'S.dFree') == fs, 'one Undo puts the whole swipe back')
    # a click on a tower removes it, with Undo right there; the Undo restores it exactly
    page.mouse.move(*xy(4, 2)); page.mouse.down(); page.mouse.move(xy(4, 2)[0] + 3, xy(4, 2)[1] + 2); page.mouse.up(); page.wait_for_timeout(50)
    msg = page.inner_text('#undo-msg') if page.is_visible('#undo-pop') else ''
    check(S(page, f'S.grid[{idx(4, 2)}]') is None and re.fullmatch(rf'Tower {tn} removed · \+\d+', msg) and S(page, 'S.dFree') == fs + int(msg.split('+')[1]),
          f'a click on a tower (a few pixels of wobble included) removes it, and says so with an Undo ({msg})')
    page.screenshot(path=f'{OUT}/q2_removed.png')
    page.click('#undo-btn')
    check(grid() == sw and S(page, 'S.dFree') == fs and page.is_hidden('#undo-pop'), 'its Undo puts the tower back with its tuning, fee and number, and takes the refund back')
    # a drag moves it instead
    drag(page, *xy(4, 2), *xy(4, 5))
    check(S(page, f'S.grid[{idx(4, 2)}]') is None and S(page, f'S.grid[{idx(4, 5)}] && S.grid[{idx(4, 5)}].n') == tn and S(page, 'S.dFree') == fs and page.is_hidden('#undo-pop'),
          'with Remove & Inspect a drag moves a tower, free, and removes nothing')
    page.keyboard.press('Control+z')
    check(grid() == sw, 'Undo moves it back')
    # a tower's tuning is one change: Undo puts every slider and the coins back
    page.click('.tool[data-tool=tower]'); click_cell(page, 4, 2)
    cfg0, fq, d0 = S(page, f'JSON.stringify(S.grid[{idx(4, 2)}].cfg)'), S(page, 'S.dFree'), depth()
    set_slider(page, '#te-range', 3); set_slider(page, '#te-dps', 4); set_slider(page, '#te-rate', 4); page.click('#def-ctx [data-fx=slow]')
    check(depth() == d0 + 1 and S(page, 'S.dFree') < fq, 'tuning a tower (sliders and an effect) is one change')
    page.keyboard.press('Control+z')
    check(S(page, f'JSON.stringify(S.grid[{idx(4, 2)}].cfg)') == cfg0 and S(page, 'S.dFree') == fq and page.is_visible('#te-price'), 'Undo takes the tuning back, coins included, and the card stays open')
    page.click('[data-act=close]')
    # once the defender is done, nothing more to undo: the attacker can't, and next round starts afresh
    page.click('.tool[data-tool=wall]'); click_cell(page, 12, 8)
    page.click('#def-lock'); hand(page)
    gd = grid(); page.keyboard.press('Control+z')
    check(S(page, 'S.phase') == 'attack' and grid() == gd, 'Ctrl+Z does nothing on the attacker’s turn')
    page.click('.step.plus[data-i="0"]')
    page.click('#atk-lock')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    page.click('#sum-next'); hand(page)
    check(S(page, '[S.phase, S.round]') == ['defend', 2] and depth() == 0 and page.is_disabled('#def-body [data-act=undo]'), 'after the wave the defender’s history is gone: last round can’t be undone')
    page.keyboard.press('Control+z')
    check(S(page, f'S.grid[{idx(12, 8)}].t') == 'wall' and toast(page) == 'Nothing to undo this round.', 'Ctrl+Z leaves last round’s build alone')
    fr = S(page, 'S.dFree')
    check(page.evaluate('() => window.siegeline.mazeBudget()') == min(fr, int(fr * 0.4)), f'auto-maze budget after the first wave: 40% of the free coins ({fr} free)')
    # the history survives a test run
    click_cell(page, 12, 9)
    page.click('#def-test'); page.wait_for_timeout(100); page.click('#test-skip'); page.wait_for_timeout(200)
    check(S(page, 'S.phase') == 'defend' and not page.evaluate('() => window.siegeline.testing') and depth() == 1, 'a test run leaves the history as it was')
    page.keyboard.press('Control+z')
    check(S(page, f'S.grid[{idx(12, 9)}]') is None, 'and Undo still takes back the change made before it')
    check(not errors, f'v20.4 desktop: no errors {errors[:3]}')
    ctx.close()

    # the same on a 390 px phone: the hold previews, a tap removes, the pop-up and the helper row fit
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); no_terrain(page)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    page.tap('#def-steps [data-act=hints]')
    xy = lambda c, r: page.evaluate(f'() => window.siegeline.cellToClient({idx(c, r)})')
    cdp = ctx.new_cdp_session(page)
    tools = page.evaluate("() => [...document.querySelectorAll('#def-body .toolrow .tool')].map(b => [Math.round(b.getBoundingClientRect().top), b.querySelector('.tcost').scrollWidth <= b.querySelector('.tcost').clientWidth])")
    check(len({t for t, _ in tools}) == 1 and all(fit for _, fit in tools), f'phone: the four tools in one row, "& inspect" not cut off ({tools})')
    page.tap('#def-body [data-act=maze]'); page.wait_for_function('() => !window.siegeline.mazing'); page.wait_for_timeout(50)
    row = page.evaluate("() => [...document.querySelectorAll('#def-body .helprow > button')].map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.right)]; })")
    check(S(page, 'S.grid.filter(g => g && g.t === "wall").length') > 0 and len({t for t, _ in row}) == 1 and max(r for _, r in row) <= 390 and not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'),
          f'phone: Auto-maze builds, and its row fits 390 px ({row})')
    page.tap('.tool[data-tool=tower]'); x, y = xy(1, 1); page.touchscreen.tap(x, y); page.wait_for_timeout(100); page.touchscreen.tap(x, y); page.wait_for_timeout(150)
    if page.is_visible('#def-ctx [data-act=close]'): page.tap('#def-ctx [data-act=close]')
    page.tap('.tool[data-tool=remove]'); page.wait_for_timeout(100)
    check(page.is_visible('#tip') and page.inner_text('#tip') == 'Hold a wall to preview bridge risk.', 'phone: the first time, the line says to hold a wall')
    walls = S(page, 'S.grid.map((g, i) => g && g.t === "wall" ? i : -1).filter(i => i >= 0)')
    w = walls[len(walls) // 2]; x, y = page.evaluate(f'() => window.siegeline.cellToClient({w})')
    base = route_len(page)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y}]}); page.wait_for_timeout(650)
    bar = page.inner_text('#d-route')
    check(S(page, f'!!S.grid[{w}]') and re.search(rf'path\s+{base}\s*→\s*\d+', bar, re.I), f'phone: a finger held on a wall previews the route without it ({bar})')
    page.screenshot(path=f'{OUT}/q3_phone_hold.png')
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); page.wait_for_timeout(100)
    check(S(page, f'!!S.grid[{w}]') and route_len(page) == base, 'phone: letting go removes nothing')
    page.touchscreen.tap(x, y); page.wait_for_timeout(100)
    check(not S(page, f'!!S.grid[{w}]'), 'phone: a quick tap removes the wall')
    page.tap('#def-body [data-act=undo]'); page.wait_for_timeout(50)
    check(S(page, f'!!S.grid[{w}]') and route_len(page) == base, 'phone: the Undo button puts it back')
    # a finger that sets off from a wall at once swipes walls away
    col = [i for i in walls if i % COLS == w % COLS] or walls
    run = sorted(col)[:3]
    (x0, y0), (x1, y1) = [page.evaluate(f'() => window.siegeline.cellToClient({i})') for i in (run[0], run[-1])]
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
    for k in range(1, 7): cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * k / 6, 'y': y0 + (y1 - y0) * k / 6}]}); page.wait_for_timeout(15)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); page.wait_for_timeout(80)
    check(all(not S(page, f'!!S.grid[{i}]') for i in run), f'phone: a swipe that starts on a wall takes the walls it crosses ({run})')
    page.tap('#def-body [data-act=undo]')
    f1 = S(page, 'S.dFree'); x, y = xy(1, 1); page.touchscreen.tap(x, y); page.wait_for_timeout(150)
    pb = page.locator('#undo-pop').bounding_box() if page.is_visible('#undo-pop') else None
    check(not S(page, f'!!S.grid[{idx(1, 1)}]') and pb and pb['x'] >= 0 and pb['x'] + pb['width'] <= 390, f'phone: one tap removes a tower, and the Undo pop-up fits ({pb})')
    page.screenshot(path=f'{OUT}/q4_phone_pop.png')
    page.tap('#undo-btn'); page.wait_for_timeout(50)
    check(S(page, f'S.grid[{idx(1, 1)}] && S.grid[{idx(1, 1)}].t') == 'tower' and S(page, 'S.dFree') == f1, 'phone: its Undo puts the tower back')
    check(not errors, f'v20.4 phone: no errors {errors[:3]}')
    ctx.close()

    # ---------- v19: tower accuracy (each shot rolls once) and the wave scrubber
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    # spec test 2: per-shot accuracy for all 24 slider × fire-rate pairs
    want = [[72, 75, 78, 80, 83, 86], [79, 82, 85, 87, 90, 93], [86, 89, 92, 94, 97, 100], [92, 95, 98, 100, 100, 100]]
    got = page.evaluate('() => [0, 1, 2, 3].map(a => [0, 1, 2, 3, 4, 5].map(r => window.siegeline.shotAcc({ range: 2, dps: 2, accuracy: a, rate: r, splash: 0 })))')
    check(got == want, f'per-shot accuracy matches the spec’s table for all 24 pairs {got}')
    # hidden test waves on a fixed maze: towers beside the route, an army in one bunch
    maze = [idx(5, r) for r in range(0, 10)] + [idx(10, r) for r in range(1, 11)]
    run = """([maze, towers, army, seed]) => { const sl = window.siegeline, G = new Array(176).fill(null);
      for (const i of maze) G[i] = { t: 'wall', fresh: false };
      for (const [i, cfg] of towers) G[i] = { t: 'tower', cfg: { range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: false, ...cfg }, fee: 0, off: 0, n: 1, fresh: false, cd: 0, ang: 0, kick: 0, dealt: 0 };
      const ds = army.map(([hp, speed, count, e], k) => ({ name: 'U' + k, color: '#ffb547', hp, speed, armor: 0, regen: 0, resist: 'none', count, tl: { s: 0, e, pos: null } }));
      return sl.trial(G, ds, [], seed, []); }"""
    T1 = idx(7, 5)
    page.evaluate('() => { window.siegeline.rules.rateAcc = [-100, -100, -100, -100, -100, -100]; }')  # every shot at 0%
    fz = page.evaluate(run, [maze, [[T1, {'slow': True, 'poison': True}]], [[5, 3, 4, 0.1]], 3])
    fz0 = page.evaluate(run, [maze, [[T1, {}]], [[5, 3, 4, 0.1]], 3])
    check(fz['misses'] > 0 and fz['dealt'] == 0 and abs(fz['Y'] - fz['X']) < 1e-9 and abs(fz['t'] - fz0['t']) < 1e-9,
          f'spec test 3: at 0% a single-target tower deals nothing and applies no frost or poison (missed {fz["misses"]}, dealt {fz["dealt"]}, wave {fz["t"]:.2f}s = {fz0["t"]:.2f}s without effects)')
    one = page.evaluate(run, [maze, [[T1, {'rate': 4, 'splash': 2}]], [[5, 3, 1, 0]], 3])
    many = page.evaluate(run, [maze, [[T1, {'rate': 4, 'splash': 2}]], [[5, 3, 8, 0.02]], 3])
    check(one['misses'] > 0 and one['dealt'] == 0 and many['dealt'] > 0 and many['Y'] < many['X'],
          f'spec test 3: at 0% a splash shot spares its target but hits the rest of the blast (alone: dealt {one["dealt"]}; in a bunch of 8: dealt {round(many["dealt"])})')
    page.evaluate('() => { window.siegeline.rules.rateAcc = [-8, -5, -2, 0, 3, 6]; }')
    # spec test 4: at 100% (the top slider at 1/s or slower) a wave plays exactly as it did in v18, for the same seed
    sure = [[T1, {'accuracy': 3, 'rate': 3, 'dps': 4}], [idx(12, 4), {'accuracy': 3, 'rate': 4, 'splash': 2, 'poison': True}], [idx(3, 6), {'accuracy': 3, 'rate': 5, 'chain': True, 'slow': True}]]
    army = [[5, 3, 6, 0.2], [2, 6, 10, 0.1]]
    now = page.evaluate(run, [maze, sure, army, 11])
    try: v18 = subprocess.run(['git', 'show', '52d977a:index.html'], cwd=ROOT, capture_output=True, text=True).stdout
    except Exception: v18 = ''
    if 'const PROTO = 8' in v18:
        old = ctx.new_page(); old.goto('file://' + write_build('v18.html', v18)); old.wait_for_timeout(300)
        then = old.evaluate(run, [maze, sure, army, 11]); old.close()
        keys = ['X', 'Y', 'kills', 'leaks', 't']
        check(now['misses'] == 0 and now['Y'] < now['X'] and [now[k] for k in keys] == [then[k] for k in keys],
              f'spec test 4: at 100% accuracy the wave matches v18 exactly ({ {k: now[k] for k in keys} } vs { {k: then[k] for k in keys} })')
    else: print('SKIP spec test 4: the v18 build (52d977a) is not in this checkout')
    # a played wave: misses happen at the default 80%
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    for r in range(0, 10): click_cell(page, 7, r)
    page.click('.tool[data-tool=tower]'); click_cell(page, 8, 9); set_slider(page, '#te-rate', 0); page.click('[data-act=close]')  # rapid fire beside the gap the route must take
    page.click('#def-lock'); hand(page)
    for _ in range(3): page.click('.step.plus[data-i="0"]')
    page.click('#atk-lock')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    check(S(page, 'S.last.misses') > 0 and S(page, 'S.phase') == 'summary', f'towers at 80% miss some shots in a real wave ({S(page, "S.last.misses")} missed)')
    page.click('#sum-next'); hand(page); page.click('#def-lock'); hand(page)
    for _ in range(2): page.click('.step.plus[data-i="1"]')  # two Brutes beside the Runners, for the path sliders
    # the attacker's card for a seen tower: Accuracy and Expected damage rows
    page.click('#atk-next'); page.wait_for_timeout(200)
    click_cell(page, 8, 9); page.wait_for_timeout(80)
    card = page.inner_text('#atk-ctx')
    check('72% per shot' in card and 'expected 13/s' in card, f'a tower card shows its accuracy at 4 shots/s and expected damage after misses ({card[:200]!r})')
    page.click('#atk-ctx [data-act=close]')
    # v22: the tower card still shows accuracy; on to the Wave step, whose forecast plays this round's plan
    page.click('#atk-next'); page.wait_for_timeout(250)
    check(page.is_visible('#wv-play') and page.locator('#wv-rows .wv-grp').count() == 2, 'v22: the Wave step opens with ▶ PLAY WAVE and a row per group')
    check(not errors, f'v19 accuracy: no errors {errors[:3]}')
    ctx.close()

    # ---------- v22: the Wave step (the user's "Attacker wave screen" spec, Part E) on a 1440×900 screen
    def v22_round2(page, bridge=True, ko=True):
        """Round 1: an Auto-maze and four towers beside the route; the attacker sends Runners, Brutes and Swarm. Round 2:
        the same defense; the attacker plans a bridge and a knock-out and opens the Wave step."""
        page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
        page.click('#def-body [data-act=maze]'); page.wait_for_function('() => !window.siegeline.mazing'); page.wait_for_timeout(50)
        page.click('.tool[data-tool=tower]')
        cells = page.evaluate("""() => { const S = window.siegeline.state, p = S.path, out = [];
          for (let k = 4; k < p.length - 3 && out.length < 4; k += 6) for (const d of [16, -16, 1, -1]) { const j = p[k] + d; if (j >= 0 && j < 176 && !S.grid[j] && !p.includes(j) && j !== 80 && j !== 95) { out.push(j); break; } }
          return out; }""")
        for j in cells: click_cell(page, j % COLS, j // COLS); page.keyboard.press('Escape')
        page.click('#def-lock'); hand(page)
        for i, n in ((0, 3), (1, 2), (2, 8)):
            for _ in range(n): page.click(f'.step.plus[data-i="{i}"]')
        page.click('#atk-lock'); hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(80)
        page.click('#sum-next'); hand(page); page.click('#def-lock'); hand(page)
        page.click('#atk-next'); page.wait_for_timeout(150)
        if bridge:
            sp = spot(page)
            if sp: click_cell(page, *sp)
        if ko:
            tw = page.evaluate('() => window.siegeline.state.seenGrid.map((g, i) => g && g.t === "tower" ? i : -1).filter(i => i >= 0)')
            if tw: click_cell(page, tw[0] % COLS, tw[0] // COLS); page.click('#atk-ctx [data-act=plant]'); page.click('#atk-ctx [data-act=close]')
        page.click('#atk-next'); page.wait_for_timeout(300)
        return cells
    ctx = b.new_context(viewport={'width': 1440, 'height': 900})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page); sure_sappers(page)
    v22_round2(page)
    W = 'window.siegeline.wave'
    ev = lambda e: page.evaluate('() => ' + e)
    ztags = ev(W + '.zones().map(z => z.id + " " + z.tags.join("+"))')
    check(S(page, 'S.round') == 2 and S(page, 'S.step') == 2 and S(page, 'S.charges.size') == 2 and len(ztags) >= 1,
          f'v22: round 2 with a bridge and a knock-out planned, and zones on the route ({ztags})')
    # test 1: the layout fits 1440×900 and 1920×1080 with no page scroll; at 1280×800 the overflow is at most 30 px
    def overflow():
        return page.evaluate("""() => { const d = document.documentElement, sc = document.querySelector('#pane-atk .scroll'), u = document.querySelector('#wvx').getBoundingClientRect();
          return { page: Math.max(0, d.scrollHeight - innerHeight), wide: Math.max(0, d.scrollWidth - innerWidth), panel: Math.max(0, sc.scrollHeight - sc.clientHeight), under: Math.max(0, Math.ceil(u.bottom - innerHeight)) }; }""")
    for (w, h, most) in ((1440, 900, 0), (1920, 1080, 0), (1280, 800, 30)):
        page.set_viewport_size({'width': w, 'height': h}); page.wait_for_timeout(250)
        o = overflow()
        check(o['wide'] == 0 and o['page'] == 0 and max(o['panel'], o['under']) <= most, f'v22 test 1: at {w}×{h} the Wave step fits (overflow {o}, allowed {most})')
        page.screenshot(path=f'{OUT}/v22_wave_{w}x{h}.png')
    page.set_viewport_size({'width': 1440, 'height': 900}); page.wait_for_timeout(200)
    # test 15: the forecast never changes S, the match's random stream or the encoded plan
    snap = lambda: page.evaluate("""() => { const sl = window.siegeline, S = sl.state; return JSON.stringify([S.round, S.phase, S.aFree, S.dFree, S.keep, S.path, [...S.bridges], S.grid.map(g => g && [g.t, g.off || 0, g.dealt || 0]),
      S.seenGrid.map(g => g && g.t), S.totals, S.units.length, sl.wave.plan(), sl.streamId()]); }""")
    s0 = snap()
    for k in range(3): page.evaluate(f'() => {{ window.siegeline.state.designs[0].tl.pos[0] += 0; return window.siegeline.wave.forecast(); }}')
    page.click('#wv-play'); page.wait_for_timeout(500); page.click('#wv-play')
    check(snap() == s0, 'v22 test 15: running and playing the forecast changes nothing in the match, its random stream or the plan')
    # selection: exactly one group, highlighted in the timeline and named in the tools panel
    def sel_ok():
        return page.evaluate("""() => { const rows = [...document.querySelectorAll('#wv-rows .wv-grp.sel')], ed = document.querySelector('#wv-tools .tools-h b');
          if (rows.length !== 1 || !ed) return false; const id = rows[0].dataset.id, g = window.siegeline.wave.groups().find(x => x.id === id);
          return id === window.siegeline.wave.sel && !!g && ed.textContent.replace(/\\s+/g, ' ').includes(rows[0].querySelector('.nm').textContent.replace(/^◆ /, '')); }""")
    check(sel_ok(), 'v22: exactly one group is selected, its row highlighted and named in the tools panel’s EDITING line')
    page.click('#wv-rows .wv-grp >> nth=2 >> .rh'); page.wait_for_timeout(60)
    check(sel_ok() and ev(f'{W}.sel') == page.get_attribute('#wv-rows .wv-grp >> nth=2', 'data-id'), 'v22 test 9: clicking a row selects its group')
    # test 5: Split then Merge restores the original release times; test 16: the plan for a split design is the plan
    p0 = S(page, 'JSON.stringify(S.designs[2].tl)'); plan0 = ev(f'{W}.plan()')
    page.click('[data-wv=split]'); page.wait_for_timeout(60)
    gs = ev(f'{W}.groups().filter(g => g.di === 2)')
    check(len(gs) == 2 and sel_ok() and ev(f'{W}.sel') == gs[0]['id'] and [len(g['idx']) for g in gs] == [4, 4] and page.inner_text('#wv-tools .tools-h .glt') == 'A'
          and [g['name'] for g in gs] == ['Swarm A', 'Swarm B'], f'v22: Split makes two groups of the design, Swarm A (the first half to leave, selected) and Swarm B ({[(g["name"], len(g["idx"])) for g in gs]})')
    check(ev(f'{W}.plan()') == plan0, 'v22 test 16: splitting alone leaves the plan sent online exactly as it was')
    page.click('[data-wv=place][data-w=last]'); page.wait_for_timeout(60)
    split_plan = ev(f'{W}.plan()'); split_pos = S(page, 'S.designs[2].tl.pos.slice()')
    page.click(f'[data-wv=merge][data-o="{gs[1]["id"]}"]'); page.wait_for_timeout(60)
    check(len(ev(f'{W}.groups().filter(g => g.di === 2)')) == 1 and sel_ok(), 'v22: Merge joins them again, the merged group selected')
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z'); page.keyboard.press('Control+z'); page.wait_for_timeout(60)
    check(S(page, 'JSON.stringify(S.designs[2].tl)') == p0 and len(ev(f'{W}.groups().filter(g => g.di === 2)')) == 1 and sel_ok(),
          'v22 Undo: three presses take back Merge, Last and Split, one each, to the times and the group it started with')
    page.click('[data-wv=split]'); page.locator('[data-wv=merge]').first.click() if page.locator('[data-wv=merge]').count() else None
    page.wait_for_timeout(60)
    check(S(page, 'JSON.stringify(S.designs[2].tl)') == p0, 'v22 test 5: Split then Merge restores the original release times')
    page.evaluate(f"() => {{ const S = window.siegeline.state; S.designs[2].tl = {{ s: Math.min(...{split_pos}), e: Math.max(...{split_pos}), pos: {split_pos} }}; window.siegeline.refresh(); }}")
    check(ev(f'{W}.plan()') == split_plan, 'v22 test 16: the plan sent for a split design equals the same release times entered without splitting')
    # test 6: Merge never across designs; Link only for equal speeds
    page.click('#wv-rows .wv-grp >> nth=0 >> .rh'); page.wait_for_timeout(60)
    check(page.locator('[data-wv=merge]').count() == 0 and page.locator('[data-wv=link]').count() == 0, 'v22 test 6: Runners (2.3 c/s) get no Merge with other designs, and no Link: no other design has their speed')
    page.evaluate("() => { const S = window.siegeline.state; S.designs[1].speed = S.designs[2].speed; window.siegeline.refresh(); }")
    page.click('#wv-rows .wv-grp >> nth=1 >> .rh'); page.wait_for_timeout(60)
    opts = page.evaluate("() => [...document.querySelectorAll('[data-wv=link]')].map(o => o.textContent)")
    check(page.locator('[data-wv=merge]').count() == 0 and opts and all('Swarm' in o for o in opts), f'v22 test 6: Brutes at the Swarm’s speed are offered Link with it, never Merge ({opts})')
    page.click('[data-wv=link]'); page.wait_for_timeout(60)
    lk = ev(f'{W}.groups().filter(g => g.cell == null).map(g => g.link)')
    page.click('[data-wv=place][data-w=lead]'); page.wait_for_timeout(60)
    check(lk[1] and lk[1] == lk[2] and S(page, 'Math.min(...S.designs[1].tl.pos, ...S.designs[2].tl.pos)') < 1e-9 and page.locator('#wv-rows .chain').count() == 2,
          'v22: linked groups move together (Lead puts the earliest of both at 0 s) and show a chain icon')
    page.click('[data-wv=unlink]'); page.keyboard.press('Control+z'); page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    page.evaluate("() => { const S = window.siegeline.state; S.designs[1].speed = 1; window.siegeline.refresh(); }")
    # test 8: every planned sapper is in the Meet list by its job name; test 7: Meet with a sapper
    page.click('#wv-rows .wv-grp >> nth=2 >> .rh'); page.wait_for_timeout(60)
    mo = page.evaluate("() => [...document.querySelectorAll('#wv-mo option')].map(o => o.textContent)")
    check(any(o.startswith('◆ Bridge ') for o in mo) and any(o.startswith('◆ Knock-out T') for o in mo), f'v22 test 8: every planned sapper is in the Meet list, named by its job ({mo})')
    ko = S(page, '[...S.charges].find(([, c]) => c.kind === "tower")[0]')
    zones = ev(f'{W}.zones()'); zk = next((z['id'] for z in zones if ko in z['towers']), zones[0]['id'])
    page.select_option('#wv-mo', f's{ko}'); page.select_option('#wv-mz', zk); page.click('[data-wv=meet]'); page.wait_for_timeout(150)
    note = page.inner_text('#wv-note')
    mid = page.evaluate(f"""() => {{ const sl = window.siegeline, f = sl.wave.forecast(), z = sl.wave.zones().find(q => q.id === '{zk}'), cells = new Set(z.cells);
      return null; }}""")
    check(('now pass' in note and 'Knock-out sapper' in note and zk in note) or note.startswith('Closest possible') or 'never reach' in note,
          f'v22 test 7: Meet lines the Swarm up with the knock-out sapper in {zk}, or says why it can’t ({note})')
    check(sel_ok() and ev(f'{W}.selZ') == zk and 'Met in' in page.inner_text('#wv-log'), 'v22 test 9: after Meet the Swarm stays selected, the zone is picked and the log says what changed')
    page.keyboard.press('Control+z'); page.wait_for_timeout(60)
    check(sel_ok(), 'v22 test 9: and after Undo the highlighted row is still the group in the EDITING line')
    def pick_zone(zid):
        if ev(f'{W}.selZ') != zid: page.click(f'.wv-zc[data-z="{zid}"]'); page.wait_for_timeout(60)
    # test 10: zone stars, ✕ counts and the LAST RUN rows match the forecast's deaths and each tower's damage
    f = ev(f'{W}.forecast()'); zones = ev(f'{W}.zones()')
    ok = True
    for z in zones:
        ts = set(z['towers']); lost = sum(1 for d in f['deaths'] if not d['sap'] and d['by'] in ts); dmg = sum(f['dealt'].get(str(i), 0) for i in z['towers'])
        q = lost / z['entered'] if z['entered'] else 0; st = 3 if not z['entered'] else 3 if q <= 0.05 else 2 if q <= 0.2 else 1 if q <= 0.4 else 0
        ok = ok and z['lost'] == lost and abs(z['dmg'] - dmg) < 1e-6 and z['stars'] == st
    pick_zone(zones[0]['id'])
    page.evaluate(f'() => {{ {W}.T = 0; }}'); page.wait_for_timeout(60)
    chips = page.evaluate("() => [...document.querySelectorAll('.wv-zc')].map(c => [c.dataset.z, c.querySelector('.k').textContent, c.querySelectorAll('.stars').length ? c.querySelector('.stars').textContent.split('').filter(x => x === '★').length : -1])")
    rows = page.evaluate("() => [...document.querySelectorAll('#wv-zcard .lr tr')].map(r => r.textContent)")
    ok2 = all(c[1] == f'✕{z["lost"]}' and c[2] == z['stars'] for c, z in zip(chips, zones)) and len(rows) == len(zones) and all(f'{round(z["dmg"]):,} dmg' in r and (('0 died' in r) == (z['lost'] == 0)) for r, z in zip(rows, zones))
    check(ok and ok2, f'v22 test 10: zone stars, ✕ counts and the LAST RUN rows match the forecast’s deaths and its towers’ damage ({chips}, {rows})')
    card = page.inner_text('#wv-zcard').upper()
    check('THREAT' in card and 'BEAT IT' in card and 'LAST RUN' in card and f'OPTIMIZE {zones[0]["id"]}' in card and f'LOCK {zones[0]["id"]}' in card, f'v22: the zone card has its threats, how to beat it, LAST RUN, Optimize and Lock ({card[:120]!r})')
    # test 13: each Play press saves a run, unless nothing changed; test 14: Restore brings that plan back exactly
    n0 = len(ev(f'{W}.runs'))
    page.click('#wv-play'); page.wait_for_timeout(200); page.click('#wv-play'); page.wait_for_timeout(50)
    n1 = len(ev(f'{W}.runs'))
    page.click('#wv-play'); page.wait_for_timeout(200); page.click('#wv-play'); page.wait_for_timeout(50)
    n2 = len(ev(f'{W}.runs'))
    check(n1 == n0 + 1 and n2 == n1, f'v22 test 13: Play saves a run; Play again with no change doesn’t ({n0} → {n1} → {n2})')
    saved = ev(f'{W}.plan()')
    page.click('[data-wv=rush]'); page.wait_for_timeout(60)
    page.click('#wv-play'); page.wait_for_timeout(100); page.click('#wv-play')
    check(len(ev(f'{W}.runs')) == n1 + 1 and ev(f'{W}.plan()') != saved, 'v22: a changed plan saves a new run')
    page.click(f'.run[data-run="{n1 - 1}"]'); page.wait_for_timeout(60)
    check(page.is_visible('[data-wv=restore]'), 'v22: tapping a run offers Restore this run (its losses show as grey ✕s on the map)')
    page.screenshot(path=f'{OUT}/v22_run_cmp.png')
    page.click('[data-wv=restore]'); page.wait_for_timeout(80)
    check(ev(f'{W}.plan()') == saved, 'v22 test 14: Restore brings back that run’s plan exactly')
    # test 11: lock a zone, optimize another: the locked zone's losses never go up; test 12: the log lists every zone that changed
    zones = ev(f'{W}.zones()')
    if len(zones) >= 2:
        za, zb = zones[0], zones[1]
        pick_zone(za['id'])
        page.click(f'[data-wv=lock][data-z="{za["id"]}"]'); page.wait_for_timeout(40); cap = ev(f'{W}.locks')[za['id']]
        check(cap == za['lost'] and 'LOCKED' in page.inner_text(f'.wv-zc[data-z="{za["id"]}"]').upper(), f'v22: Lock records {za["id"]}’s losses ({cap}) as its cap')
        pick_zone(zb['id'])
        k0 = {z['id']: z['lost'] for z in ev(f'{W}.zones()')}
        page.click(f'[data-wv=opt][data-z="{zb["id"]}"]')
        page.wait_for_function(f'() => !{W}.busy', timeout=60000); page.wait_for_timeout(100)
        k1 = {z['id']: z['lost'] for z in ev(f'{W}.zones()')}
        log = page.inner_text('#wv-log')
        check(k1[za['id']] <= cap, f'v22 test 11: optimizing {zb["id"]} never raises locked {za["id"]}’s losses ({k0} → {k1}, cap {cap})')
        check(all(z in log for z in k0 if k0[z] != k1[z]) and (f'Optimized {zb["id"]}' in log or 'No better plan' in log),
              f'v22 test 12: the change log lists every zone whose losses changed ({log[:160]!r})')
        pick_zone(za['id']); page.click(f'[data-wv=lock][data-z="{za["id"]}"]')
    else: print('SKIP v22 tests 11-12: only one zone on this map')
    # Auto-sequence: in chunks, "Working it out…", up to 4 changes, ghosts of where groups were, BEATS AUTO when it should
    b0 = ev(f'{W}.forecast().breach')
    page.click('[data-wv=auto]')
    check(page.text_content('[data-wv=auto]') == 'Working it out…' and page.is_disabled('[data-wv=auto]') and ev(f'{W}.busy'), 'v22: Auto-sequence works in chunks: “Working it out…”, its button disabled')
    page.wait_for_function(f'() => !{W}.busy', timeout=60000); page.wait_for_timeout(100)
    b1 = ev(f'{W}.forecast().breach'); log = page.inner_text('#wv-log')
    check(b1 >= b0 - 1e-9 and (('Auto-sequenced' in log and f'through {b0 * 100:.1f}%' in log) or 'No better sequence' in log) and len(page.locator('#wv-log ol li').all()) <= 4,
          f'v22: Auto-sequence never makes the plan worse, and says what it did ({b0:.3f} → {b1:.3f}; {log[:120]!r})')
    if 'Auto-sequenced' in log:
        check(page.locator('#wv-rows .ghost:not([hidden])').count() >= 1 and 'BEFORE THE LAST CHANGE' in page.inner_text('#wv-key').upper(), 'v22: moved groups show a dashed ghost of where they were, and the header says so')
    a = ev(f'{W}.auto')
    check(a is None or page.is_visible('#wv-beat') == (b1 > a + 1e-9), f'v22: BEATS AUTO shows exactly when the plan beats Auto-sequence’s best from the step’s opening ({b1:.3f} vs {a})')
    # any edit while Auto-sequence works cancels it
    page.click('[data-wv=auto]'); page.wait_for_timeout(20)
    if ev(f'{W}.busy'):
        page.click('[data-wv=even]'); page.wait_for_timeout(80)
        check(not ev(f'{W}.busy') and page.inner_text('#wv-log') == '', 'v22: an edit while Auto-sequence works cancels it')
        page.keyboard.press('Control+z'); page.wait_for_timeout(40)
    else: page.wait_for_function(f'() => !{W}.busy', timeout=60000)
    # a manual edit clears the log and the ghosts
    row0 = '#wv-rows .wv-grp >> nth=0'
    bb = page.locator(f'{row0} >> .bar').bounding_box()
    if bb and bb['width'] > 4:
        drag(page, bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2, bb['x'] + bb['width'] / 2 + 6, bb['y'] + bb['height'] / 2)
        check(page.inner_text('#wv-log') == '' and page.locator('#wv-rows .ghost:not([hidden])').count() == 0, 'v22: the next manual edit clears the change log and the ghosts')
    # the clock: 3× normal speed; the space bar toggles; the result shows at the end
    page.evaluate(f'() => {{ {W}.T = 0; }}'); page.mouse.click(5, 450)
    page.keyboard.press(' '); t0 = ev(f'{W}.T'); page.wait_for_timeout(1000); t1 = ev(f'{W}.T')
    check(ev(f'{W}.playing') and 2.0 < t1 - t0 < 4.2, f'v22: the space bar plays the forecast at 3× ({t1 - t0:.2f} s of clock in a second)')
    page.keyboard.press(' ')
    check(not ev(f'{W}.playing'), 'v22: and pauses it')
    page.evaluate(f'() => {{ {W}.T = 999; }}'); page.wait_for_timeout(120)
    page.screenshot(path=f'{OUT}/v22_end.png')
    # the lens: hovering a dot lights up its unit
    d = page.locator('#wv-rows .dot >> nth=1').bounding_box(); page.mouse.move(d['x'] + 4, d['y'] + 4); page.wait_for_timeout(60)
    check(page.locator('#wv-rows .dot.lens').count() == 1, 'v22: hovering a dot enlarges it and lights up its unit on the map')
    page.mouse.move(5, 5)
    # test 17: every control once, no console errors
    for sel in ['[data-wv=how]', '[data-wv=how]', '[data-wv=even]', '[data-wv=seq]', '[data-wv=rush]', '#wv-rows .wv-grp >> nth=1 >> .rh', '[data-wv=place][data-w=middle]',
                '[data-wv=shape][data-f=pulses]', '[data-wv=shape][data-f=front]', '[data-wv=shape][data-f=trickle]', '[data-wv=shape][data-f=even]', '[data-wv=split]',
                '[data-wv=undo]', '.wv-zc >> nth=0', '[data-wv=lock]', '[data-wv=lock]', '.wv-zc >> nth=0']:
        if page.locator(sel).count(): page.locator(sel).first.click(); page.wait_for_timeout(40)
    sap = page.locator('#wv-rows .wv-grp.sap >> nth=0 >> .rh'); sap.click(); page.wait_for_timeout(40)
    if page.locator('[data-wv=inside]').count(): page.locator('[data-wv=inside]').first.click()
    dens = page.locator('#wv-rows .wv-grp >> nth=0 >> .rh'); dens.click(); page.wait_for_timeout(40)
    db = page.locator('#wv-dens').bounding_box()
    if db: drag(page, db['x'] + 4, db['y'] + db['height'] / 2, db['x'] + db['width'] * 0.3, db['y'] + db['height'] / 2)
    hd = page.locator('#wv-rows .wv-grp >> nth=0 >> .hdl').bounding_box()
    order0 = page.evaluate("() => [...document.querySelectorAll('#wv-rows .wv-grp')].map(e => e.dataset.id)")
    drag(page, hd['x'] + 6, hd['y'] + 6, hd['x'] + 6, hd['y'] + 130)
    order1 = page.evaluate("() => [...document.querySelectorAll('#wv-rows .wv-grp')].map(e => e.dataset.id)")
    check(order1 != order0 and sorted(order1) == sorted(order0), f'v22: dragging ⋮⋮ reorders the rows ({order0} → {order1})')
    tr = page.locator('#wv-rows .wv-grp >> nth=0 >> .track').bounding_box(); page.mouse.click(tr['x'] + tr['width'] * 0.5, tr['y'] + 3)
    page.click('#wv-play'); page.wait_for_timeout(300); page.click('#wv-play')
    page.click('#atk-steps [data-step="0"]'); page.click('#atk-steps [data-step="2"]'); page.wait_for_timeout(100)
    check(not errors, f'v22 test 17: every control on the Wave step, and no console errors {errors[:3]}')
    page.screenshot(path=f'{OUT}/v22_after_clicks.png')
    # Part A test 3: a planned bridge that changes the route carries no warning on the Sabotage step
    page.click('#atk-steps [data-step="1"]'); page.wait_for_timeout(150)
    bridges = ev(f'{W}.forecast().bridges')
    check(bridges and not bridges[0]['same'] and page.is_hidden('#a-sabo-warn') and 'won’t take this bridge' not in page.inner_text('#a-charges'),
          f'v22 Part A test 3: a bridge that changes the route shows no warning ({bridges})')
    ctx.close()

    # ---------- v22.1: the user's fixes to the Wave step (split groups on their own, Split/Merge, Meet at any cells, the
    # map keeping its size, quick buy and sell on the Army step, timing kept when a count changes, buttons vs labels)
    ctx = b.new_context(viewport={'width': 1440, 'height': 900})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page); sure_sappers(page)
    v22_round2(page)
    W = 'window.siegeline.wave'
    ev = lambda e: page.evaluate('() => ' + e)
    grp = lambda gid: ev(f'{W}.groups().find(g => g.id === "{gid}")')
    sw = ev(f'{W}.groups().find(g => g.di === 2).id')
    page.evaluate(f'() => {W}.select("{sw}")'); page.wait_for_timeout(60)
    # Split with a chosen size: the stepper moves the cut, hovering Split marks it on the track
    page.click('[data-wv=cut][data-d="-1"]'); page.wait_for_timeout(40)
    page.hover('#wv-split'); page.wait_for_timeout(80)
    cutv = page.inner_text('#wv-cutv').replace('\n', ' ')
    marks = page.evaluate("() => [document.querySelectorAll('#wv-rows .wv-grp.sel .cutm:not([hidden])').length, document.querySelectorAll('#wv-rows .wv-grp.sel .dot.cutoff').length]")
    check(cutv.split() == ['3', '✂', '5'] and marks == [1, 5], f'v22.1: Split’s stepper sets the cut (3 ✂ 5), and hovering it marks the cut and the 5 that would go on the track ({cutv!r}, {marks})')
    page.click('[data-wv=split]'); page.wait_for_timeout(80)
    gs = ev(f'{W}.groups().filter(g => g.di === 2)')
    A, B = gs[0]['id'], gs[1]['id']
    check([len(g['idx']) for g in gs] == [3, 5] and [g['name'] for g in gs] == ['Swarm A', 'Swarm B'] and max(gs[0]['secs']) <= min(gs[1]['secs']) + 1e-9,
          f'v22.1: Split keeps the first 3 to leave as Swarm A and makes the last 5 Swarm B ({[(g["name"], len(g["idx"])) for g in gs]})')
    rowA, rowB = f'#wv-rows .wv-grp[data-id="{A}"]', f'#wv-rows .wv-grp[data-id="{B}"]'
    check('A' in page.inner_text(f'{rowA} .glt') and 'B' in page.inner_text(f'{rowB} .glt'), 'v22.1: the rows say which group is which (A, B)')
    # split groups are independent: drag B past A toward the gate and back; A never moves, each row's dots stay its own
    def dots_ok(gid):
        g = grp(gid); left = page.evaluate(f"() => [...document.querySelectorAll('#wv-rows .wv-grp[data-id=\"{gid}\"] .dot')].map(d => parseFloat(d.style.left)).sort((a, b) => a - b)")
        want = sorted((1 - t / 20) * 100 for t in g['secs'])
        return len(left) == len(want) and all(abs(a - b) < 0.05 for a, b in zip(left, want))
    secsA = grp(A)['secs']
    tb = page.locator(f'{rowB} .track').bounding_box(); bb = page.locator(f'{rowB} .bar').bounding_box()
    drag(page, bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2, tb['x'] + tb['width'] - 4, bb['y'] + bb['height'] / 2, steps=14); page.wait_for_timeout(120)
    g1 = grp(B)
    check(grp(A)['secs'] == secsA and min(g1['secs']) < max(secsA) and dots_ok(A) and dots_ok(B),
          f'v22.1: dragging Swarm B past Swarm A toward the gate moves only B; A keeps its times and each row shows its own units ({secsA} / {g1["secs"]})')
    bb = page.locator(f'{rowB} .bar').bounding_box()
    drag(page, bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2, tb['x'] + 30, bb['y'] + bb['height'] / 2, steps=14); page.wait_for_timeout(120)
    check(grp(A)['secs'] == secsA and min(grp(B)['secs']) > max(secsA) and dots_ok(A) and dots_ok(B) and [len(g['idx']) for g in ev(f'{W}.groups().filter(g => g.di === 2)')] == [3, 5],
          'v22.1: and dragging it back past A again moves only B')
    # each group's own tools: Lead on A moves A only
    page.evaluate(f'() => {W}.select("{A}")'); secsB = grp(B)['secs']
    page.click('[data-wv=place][data-w=middle]'); page.wait_for_timeout(60)
    check(grp(B)['secs'] == secsB and grp(A)['secs'] != secsA and dots_ok(A) and dots_ok(B), 'v22.1: Position on Swarm A moves A only')
    # Merge is a button per group of the same design
    mg = page.evaluate("() => [...document.querySelectorAll('[data-wv=merge]')].map(b => [b.dataset.o, b.textContent])")
    check(len(mg) == 1 and mg[0][0] == B and 'Swarm B' in mg[0][1] and '×5' in mg[0][1], f'v22.1: Merge offers Swarm B ×5 as a button ({mg})')
    page.click(f'[data-wv=merge][data-o="{B}"]'); page.wait_for_timeout(60)
    gs = ev(f'{W}.groups().filter(g => g.di === 2)')
    check(len(gs) == 1 and len(gs[0]['idx']) == 8 and gs[0]['name'] == 'Swarm' and dots_ok(gs[0]['id']), 'v22.1: Merge makes one group of 8 again, named plainly Swarm')
    page.keyboard.press('Control+z'); page.wait_for_timeout(60)
    check(len(ev(f'{W}.groups().filter(g => g.di === 2)')) == 2, 'v22.1: Undo splits them again')
    # a group linked to another design splits its own units only
    page.evaluate("() => { const S = window.siegeline.state; S.designs[1].speed = S.designs[2].speed; window.siegeline.refresh(); }")
    page.evaluate(f'() => {W}.select("{A}")'); page.wait_for_timeout(60)
    page.locator('[data-wv=link]').first.click(); page.wait_for_timeout(60)
    page.click('[data-wv=split]'); page.wait_for_timeout(60)
    lg = ev(f'{W}.groups().filter(g => g.cell == null).map(g => [g.di, g.idx.length, g.link])')
    check(sorted(x[1] for x in lg if x[0] == 2) == [1, 2, 5] and [x[1] for x in lg if x[0] == 1] == [2] and sum(x[1] for x in lg if x[0] == 2) == 8,
          f'v22.1: splitting Swarm A while it’s linked to the Brutes cuts only its own units ({lg})')
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z'); page.wait_for_timeout(60)
    page.evaluate("() => { const S = window.siegeline.state; S.designs[1].speed = 1; window.siegeline.refresh(); }")
    check(not any(g['link'] for g in ev(f'{W}.groups()')) and len(ev(f'{W}.groups().filter(g => g.di === 2)')) == 2, 'v22.1: two Undos take back that Split and the Link')
    # the map keeps its size whatever zone is picked
    box = lambda: page.evaluate("() => { const r = document.querySelector('#board').getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }")
    b0 = box(); sizes = []
    for z in ev(f'{W}.zones()'):
        page.click(f'.wv-zc[data-z="{z["id"]}"]'); page.wait_for_timeout(120); sizes.append(box())
    page.click('.wv-zc >> nth=0'); page.wait_for_timeout(60)
    if ev(f'{W}.selZ'): page.click('.wv-zc >> nth=0'); page.wait_for_timeout(120)
    sizes.append(box())
    check(all(x == b0 for x in sizes), f'v22.1: picking a zone (and clearing it) never changes the map’s size ({b0}, {sizes})')
    for k in range(3): page.click('#wv-play'); page.wait_for_timeout(120); page.click('[data-wv=rush]' if k % 2 else '[data-wv=even]'); page.wait_for_timeout(60)
    check(box() == b0, f'v22.1: neither do saved runs ({box()})')
    # Meet at cells picked on the map: a drag along the route takes that stretch of it
    page.evaluate(f'() => {W}.select("{A}")'); page.wait_for_timeout(60)
    route = ev(f'{W}.forecast().routes[0].path')
    page.click('[data-wv=pick]'); page.wait_for_timeout(40)
    check(ev(f'{W}.pick') and page.get_attribute('[data-wv=pick]', 'aria-pressed') == 'true', 'v22.1: the crosshair starts picking cells on the map')
    page.keyboard.press('Escape'); page.wait_for_timeout(40)
    check(not ev(f'{W}.pick'), 'v22.1: Escape stops picking')
    page.click('[data-wv=pick]'); page.wait_for_timeout(40)
    selz = ev(f'{W}.selZ')
    xy = lambda i: page.evaluate(f'() => window.siegeline.cellToClient({i})')
    (x0, y0), (x1, y1) = xy(route[6]), xy(route[10])
    drag(page, x0, y0, x1, y1, steps=12); page.wait_for_timeout(120)
    pl = ev(f'{W}.place')
    check(pl and sorted(pl['cells']) == sorted(route[6:11]) and not ev(f'{W}.pick') and page.input_value('#wv-mz') == 'cells' and ev(f'{W}.selZ') == selz,
          f'v22.1: a drag from one route cell to another picks that stretch of route (5 cells), shown as {pl and pl["label"]!r} in the Meet line; no zone gets picked')
    brute = ev(f'{W}.groups().find(g => g.di === 1).id')
    page.select_option('#wv-mo', brute); page.click('[data-wv=meet]'); page.wait_for_timeout(200)
    note = page.inner_text('#wv-note'); pa, pb = ev(f'{W}.presence("{A}", "cells")'), ev(f'{W}.presence("{brute}", "cells")')
    met = pa and pb and abs((pa[0] + pa[1]) / 2 - (pb[0] + pb[1]) / 2) < 1.5
    check((met and 'now pass through cells ' in note) or note.startswith('Closest possible') or 'never reach' in note,
          f'v22.1: Meet at those cells lines Swarm A up with the Brutes there, or says why it can’t ({note!r}, {pa}, {pb})')
    check('Met at cells' in page.inner_text('#wv-log'), 'v22.1: the change log says where they met')
    page.keyboard.press('Control+z'); page.wait_for_timeout(60)
    # a tap picks one cell
    page.click('[data-wv=pick]'); page.mouse.click(*xy(route[3])); page.wait_for_timeout(100)
    check(ev(f'{W}.place')['cells'] == [route[3]] and ev(f'{W}.place')['label'].startswith('Cell '), f'v22.1: a tap picks a single cell ({ev(W + ".place")})')
    # buttons and labels read apart; no "none lost"
    st = page.evaluate("""() => { const b = document.querySelector('[data-wv=even]'), l = document.querySelector('.wv-tools .wvt > span'), cs = e => getComputedStyle(e);
      return [cs(b).textTransform, cs(b).fontFamily, cs(l).textTransform, cs(l).fontFamily, cs(b).backgroundColor]; }""")
    check(st[0] == 'none' and 'Mono' not in st[1] and st[2] == 'uppercase' and 'Mono' in st[3] and st[4] not in ('rgba(0, 0, 0, 0)', 'transparent'),
          f'v22.1: buttons are filled, in sentence case and a sans font; labels small mono capitals ({st})')
    check('none lost' not in page.inner_text('#wv-rows') and 'closer to the gate' not in page.inner_text('#wv').lower() and 'group 1 of' not in page.inner_text('#wv').lower(),
          'v22.1: the explanatory lines are gone (none lost, closer to the gate, group n of m)')
    page.screenshot(path=f'{OUT}/v221_wave.png')
    # the Army step: Max buys as many as the coins allow, 0 sells them all
    page.click('#atk-steps [data-step="0"]'); page.wait_for_timeout(150)
    c0 = S(page, '[S.aFree, S.designs[0].count, window.siegeline.unitCost(S.designs[0])]')
    page.click('.step.max[data-i="0"]'); page.wait_for_timeout(60)
    c1 = S(page, '[S.aFree, S.designs[0].count]')
    check(c1[1] == c0[1] + c0[0] // c0[2] and c1[0] == c0[0] % c0[2] and page.is_disabled('.step.max[data-i="0"]'), f'v22.1: Max buys as many as the coins allow ({c0} → {c1})')
    page.click('.step.zero[data-i="0"]'); page.wait_for_timeout(60)
    c2 = S(page, '[S.aFree, S.designs[0].count]')
    check(c2 == [c0[0] + c0[1] * c0[2], 0] and page.is_disabled('.step.zero[data-i="0"]') and page.is_disabled('.step.minus[data-i="0"]'), f'v22.1: 0 sells them all ({c2})')
    page.click('.step.plus[data-i="0"]'); page.click('.step.plus[data-i="0"]'); page.click('.step.plus[data-i="0"]')
    # a count change keeps the Wave step's timing: one more Swarm joins the group that leaves last, two fewer drop the last ones
    before = {g['id']: g['secs'] for g in ev(f'{W}.groups()') if g['di'] == 2}
    page.click('.step.plus[data-i="2"]'); page.wait_for_timeout(60)
    page.click('#atk-steps [data-step="2"]'); page.wait_for_timeout(200)
    after = {g['id']: g['secs'] for g in ev(f'{W}.groups()') if g['di'] == 2}
    rest = list(after[B])
    for t in before[B]: rest.remove(t) if t in rest else None
    check(list(after) == [A, B] and after[A] == before[A] and len(after[B]) == 6 and len(rest) == 1 and min(before[B]) <= rest[0] <= 20 and len({round(t, 6) for t in after[B]}) == 6,
          f'v22.1: one more Swarm keeps both groups and their times; the new one joins Swarm B (which ends at 20 s, so into its widest gap, never on top of another) ({after})')
    before = {g['id']: g['secs'] for g in ev(f'{W}.groups()') if g['di'] == 2}
    page.click('#atk-steps [data-step="0"]'); page.wait_for_timeout(100)
    for _ in range(4): page.click('.step.minus[data-i="2"]')
    page.click('#atk-steps [data-step="2"]'); page.wait_for_timeout(200)
    after = {g['id']: g['secs'] for g in ev(f'{W}.groups()') if g['di'] == 2}
    check(after.get(A) == before[A] and after.get(B) == before[B][:2], f'v22.1: four fewer drop the last ones to leave, from Swarm B ({after})')
    for _ in range(3): page.click('#atk-steps [data-step="0"]'); page.click('.step.minus[data-i="2"]'); page.click('#atk-steps [data-step="2"]')
    page.wait_for_timeout(150)
    gs = ev(f'{W}.groups().filter(g => g.di === 2)')
    check(len(gs) == 1 and gs[0]['id'] == A and gs[0]['secs'] == before[A][:2] and gs[0]['name'] == 'Swarm', f'v22.1: a group whose units are all gone goes, and the last one loses its letter ({gs})')
    # on a phone: one column, nothing wider than the screen, the zone chips in a row
    page.set_viewport_size({'width': 390, 'height': 844}); page.wait_for_timeout(300)
    wide = page.evaluate('() => document.documentElement.scrollWidth - innerWidth')
    dirn = page.evaluate("() => getComputedStyle(document.querySelector('#wv-strip')).flexDirection")
    check(wide == 0 and dirn == 'row', f'v22.1 on a phone: nothing wider than 390 px, the zone chips in a row ({wide}, {dirn})')
    page.screenshot(path=f'{OUT}/v221_wave_390.png', full_page=True)
    page.click('#atk-steps [data-step="0"]'); page.wait_for_timeout(200)
    rw = page.evaluate("() => [...document.querySelectorAll('#roster .uhead')].map(h => [Math.round(h.scrollWidth - h.clientWidth), Math.round(h.querySelector('.stepper').getBoundingClientRect().right)])")
    check(all(o <= 0 and r <= 390 for o, r in rw), f'v22.1 on a phone: each design row fits with 0, −, +, Max ({rw})')
    page.screenshot(path=f'{OUT}/v221_army_390.png')
    check(not errors, f'v22.1: no errors {errors[:3]}')
    ctx.close()

    # ---------- v22.2: the defender's tower card opens under the tools, which stay in reach (no Done to pick Wall or Remove)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    page.click('#def-body [data-act=maze]'); page.wait_for_function('() => !window.siegeline.mazing'); page.wait_for_timeout(50)
    page.click('.tool[data-tool=tower]')
    tcells = page.evaluate("""() => { const S = window.siegeline.state, p = S.path, out = [];
      for (let k = 4; k < p.length - 3 && out.length < 4; k += 6) for (const d of [16, -16, 1, -1]) { const j = p[k] + d; if (j >= 0 && j < 176 && !S.grid[j] && !p.includes(j) && j !== 80 && j !== 95) { out.push(j); break; } }
      return out; }""")
    for j in tcells: click_cell(page, j % COLS, j // COLS); page.keyboard.press('Escape')
    page.click('#def-lock'); hand(page)
    page.click('.step.plus[data-i="0"]'); page.click('#atk-lock'); hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    page.click('#sum-next'); hand(page); page.wait_for_timeout(80)
    fit = """() => { const sc = document.querySelector('#pane-def .scroll'), r = e => e.getBoundingClientRect(), s = r(sc), tr = r(document.querySelector('#def-body .toolrow')), hr = r(document.querySelector('#def-body .helprow')), cf = r(document.querySelector('#def-ctx [data-act=close]'));
      const inside = q => q.top >= s.top - 1 && q.bottom <= s.bottom + 1;
      return [sc.scrollHeight - sc.clientHeight, inside(tr), inside(hr), inside(cf), tr.bottom <= r(document.querySelector('#def-ctx')).top]; }"""
    for (w, h) in ((1366, 860), (1440, 900), (1280, 800)):
        page.set_viewport_size({'width': w, 'height': h}); page.wait_for_timeout(200)
        page.keyboard.press('Escape'); click_cell(page, tcells[0] % COLS, tcells[0] // COLS); page.wait_for_timeout(150)
        m = page.evaluate(fit)
        check(S(page, 'S.sel && S.sel.k') == 'tower' and m == [0, True, True, True, True], f'v22.2 at {w}×{h}: the tower card opens under the tools; the tools, the helpers and the card’s Done all in view, nothing to scroll ({m})')
    page.screenshot(path=f'{OUT}/v222_card.png')
    # one click on a tool, no Done: Wall picks the tool (the card stays until you build), a wall on the board closes the card
    page.click('.tool[data-tool=wall]'); page.wait_for_timeout(60)
    check(S(page, 'S.tool') == 'wall' and S(page, 'S.sel && S.sel.k') == 'tower', 'v22.2: with the card open, one click on Wall picks the Wall tool')
    free = page.evaluate("() => { const S = window.siegeline.state; for (let i = 0; i < 176; i++) if (!S.grid[i] && i !== 80 && i !== 95 && !S.path.includes(i) && S.terrain[i] === 0) return i; return -1; }")
    n0 = S(page, 'S.grid.filter(g => g && g.t === "wall").length')
    click_cell(page, free % COLS, free // COLS); page.wait_for_timeout(80)
    check(S(page, 'S.grid.filter(g => g && g.t === "wall").length') == n0 + 1 and not S(page, 'S.sel'), 'v22.2: and the next click on the board builds a wall, closing the card')
    click_cell(page, tcells[1] % COLS, tcells[1] // COLS); page.wait_for_timeout(80)
    page.click('.tool[data-tool=remove]'); page.wait_for_timeout(60)
    check(S(page, 'S.tool') == 'remove' and not S(page, 'S.sel') and page.inner_text('#def-ctx').strip() == '', 'v22.2: with the card open, one click on Remove picks Remove and closes the card')
    page.click('.tool[data-tool=tower]'); click_cell(page, tcells[1] % COLS, tcells[1] // COLS); page.wait_for_timeout(60)
    page.click('#def-body [data-act=tune]'); page.wait_for_timeout(80)
    check(not errors and page.is_visible('#def-ctx .card'), f'v22.2: the helpers work with the card open too, and no errors {errors[:3]}')
    # on a phone the card is still the bottom sheet over the board
    page.set_viewport_size({'width': 390, 'height': 844}); page.wait_for_timeout(250)
    check(page.evaluate("() => getComputedStyle(document.querySelector('#def-ctx')).position") == 'fixed', 'v22.2 on a phone: the card is still a bottom sheet')
    ctx.close()

    # ---------- v22 Part A: a bridge landing re-routes on the towers firing then (internals, a fixed layout)
    # Column 8 is walled but for row 1, so the route goes round over row 1. Six towers in row 8 (range 4) fire on row 5,
    # the straight line a bridge at (8,5) would open: with every tower counted it's dearer than the detour, so nobody
    # takes the bridge. Knock out the one at (6,8) first, and counting only the towers firing when the bridge lands, the
    # bridge route is the cheaper one.
    API = write_build('local_a.html', game_html().replace('window.siegeline = {', 'window.siegeline = { _i: { recompute, layBridge, get S() { return S; } },', 1))
    ctx = b.new_context(viewport={'width': 1366, 'height': 860}); page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    LAY = """(skip) => { const sl = window.siegeline, I = sl._i, S = I.S, at = (c, r) => r * 16 + c;
      const T = () => ({ t: 'tower', cfg: { range: 5, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: false }, fee: 0, off: 0, n: 1, fresh: false, cd: 0, ang: 0, kick: 0, dealt: 0 });
      S.grid = S.grid.map(() => null); S.bridges = new Set(); S.routeSkip = null;
      for (let r = 0; r < 11; r++) if (r !== 1) S.grid[at(8, r)] = { t: 'wall', fresh: false };
      for (const c of [2, 4, 6, 10, 12, 14]) S.grid[at(c, 8)] = T();
      I.recompute(); const before = S.path.slice();
      if (skip !== null) S.grid[at(6, 8)].off = 1; // the knock-out has landed
      if (skip === 'v21') { S.grid[at(8, 5)] = null; S.bridges.add(at(8, 5)); I.recompute(); } // v21.1: recompute counts every tower
      else if (skip !== null) I.layBridge(at(8, 5));
      return { before, after: S.path.slice(), br: at(8, 5) }; }"""
    for build, tag in ((API, 'v22'),):
        page.goto('file://' + build); page.wait_for_timeout(300); no_terrain(page)
        page.click('#info-go'); page.click('#mode-local'); hand(page)
        r0 = page.evaluate(LAY, None)
        r1 = page.evaluate(LAY, 'ko')
        r2 = page.evaluate(LAY, 'v21')
        check(r0['br'] not in r0['before'] and idx(8, 1) in r0['before'], 'Part A: with every tower firing the route goes round over row 1')
        check(r1['br'] in r1['after'] and r1['after'] != r1['before'], f'v22 Part A test 1: the knock-out lands first; when the bridge lands units take it, counting only the towers firing ({len(r1["before"])} → {len(r1["after"])} cells)')
        check(r2['br'] not in r2['after'], 'Part A test 1: under v21.1’s rule (the knocked-out tower still counted) the same plan keeps the old route')
        page.evaluate(LAY, 'ko')
        g = page.evaluate("() => { const S = window.siegeline._i.S; S.grid[10 + 8 * 16].off = 1; window.siegeline._i.recompute(); return S.path.slice(); }")
        check(g == r1['after'], 'v22 Part A: a knock-out after the bridge never moves the route again')
    try: v21 = subprocess.run(['git', 'show', 'c601237:index.html'], cwd=ROOT, capture_output=True, text=True).stdout
    except Exception: v21 = ''
    if 'const PROTO = 12' in v21:
        old = write_build('v21_a.html', v21.replace('window.siegeline = {', 'window.siegeline = { _i: { recompute, layBridge, get S() { return S; } },', 1))
        page.goto('file://' + old); page.wait_for_timeout(300); no_terrain(page)
        page.click('#info-go'); page.click('#mode-local'); hand(page)
        r = page.evaluate(LAY, 'ko')
        check(r['br'] not in r['after'], 'v22 Part A test 1: on the v21.1 build (c601237) the same knock-out then bridge keeps the old route')
    else: print('SKIP Part A on v21.1: the v21.1 build (c601237) is not in this checkout')
    check(not errors, f'Part A: no errors {errors[:3]}')
    ctx.close()

    # ---------- v22 Part A test 3: a bridge nobody will take is flagged on the Sabotage step (a warning, not a block)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860}); page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page); sure_sappers(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); page.click('#def-lock'); hand(page)
    page.evaluate("""() => { const sl = window.siegeline, S = sl.state, at = (c, r) => r * 16 + c;
      const T = () => ({ t: 'tower', cfg: { range: 5, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: false }, fee: 0, off: 0, n: 1, fresh: false, cd: 0, ang: 0, kick: 0, dealt: 0 });
      const G = S.seenGrid.map(() => null); for (let r = 0; r < 11; r++) if (r !== 1) G[at(8, r)] = { t: 'wall', fresh: false };
      for (const c of [2, 4, 6, 10, 12, 14]) G[at(c, 8)] = T();
      S.seenGrid = G; S.grid = G.map(g => g && { ...g, cfg: g.cfg && { ...g.cfg } }); S.seenVer++; S.gridVer++; S.seenRound = 1; S.round = 2; S.aFree = 500;
      S.designs.forEach(d => { d.count = 0; }); S.designs[0].count = 3;
      const route = sl.seenRoute(); S.charges = new Map([[at(8, 5), { kind: 'bridge', cost: 25, t: 0.02, at: route[2] }]]); S.chargeVer++; sl.refresh(); }""")
    page.click('#atk-next'); page.wait_for_timeout(200)
    br = page.evaluate(f'() => {W}.forecast().bridges')
    check(br and br[0]['same'] and page.is_visible('#a-sabo-warn') and 'Units won’t take this bridge: the route over it is under more fire.' in page.inner_text('#a-charges')
          and 'Units won’t take this bridge' in page.inner_text('#a-sabo-warn'), f'v22 Part A test 3: a bridge that leaves the route as it was is flagged on its row and its card ({br})')
    check(S(page, 'S.charges.size') == 1, 'Part A: the warning doesn’t block the bridge')
    check(not errors, f'Part A warning: no errors {errors[:3]}')
    ctx.close()

    # ---------- v22 Part B: toughness surcharge (every row of the spec's table, presets unchanged)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860}); page = ctx.new_page()
    page.goto('file://' + HARNESS); page.wait_for_timeout(300)
    table = [((0, 4, 0, 0), 6), ((2, 6, 0, 0), 20), ((2, 5, 0, 0), 16), ((6, 1, 1, 0), 35), ((5, 5, 2, 0), 74), ((6, 4, 0, 3), 98), ((7, 5, 0, 0), 160),
             ((8, 4, 0, 0), 209), ((9, 3, 0, 0), 248), ((9, 0, 0, 3), 109), ((9, 7, 0, 0), 1204), ((9, 7, 3, 0), 2529)]
    price_all = '(rows) => rows.map(([h, s, a, r]) => window.siegeline.unitCost({ hp: h, speed: s, armor: a, regen: r, resist: "none" }))'
    page.evaluate('() => { const R = window.siegeline.rules; R.__k = R.toughK; R.__b = R.bigUnit; R.toughK = 0.5; R.bigUnit = 0; }')  # the spec's rule
    got = page.evaluate(price_all, [list(r[0]) for r in table])
    page.evaluate('() => { const R = window.siegeline.rules; R.toughK = R.__k; R.bigUnit = R.__b; }')
    check(got == [r[1] for r in table], f'v22 Part B test 1: the spec’s rule (toughK 0.5, no big-unit surcharge) prices every row of its table ({got})')
    # what ships is the spec's fallback (its armor-and-regen check found designs over 50%): v6's surcharge back, toughK 0.25
    shipped = [6, 20, 16, 35, 76, 98, 128, 172, 207, 109, 1256, 3823]
    got = page.evaluate(price_all, [list(r[0]) for r in table])
    check(page.evaluate('() => [window.siegeline.rules.toughK, window.siegeline.rules.bigUnit]') == [0.25, 60] and got == shipped,
          f'v22 Part B: the shipped fallback (big-unit surcharge above 60, then +25% a point of toughness above 2.5) prices the table {got}')
    slow = page.evaluate('() => window.siegeline.unitCost({ hp: 6, speed: 1, armor: 3, regen: 3, resist: "none" })')
    check(slow == 110, f'v22 Part B: armor-and-regen slow units keep v21.1’s price under the fallback (375 HP, 0.9, armor 3, regen 3: {slow})')
    pre = page.evaluate("() => ['Runner', 'Brute', 'Swarm', 'Ghost'].map(n => window.siegeline.unitCost({ ...{ Runner: { hp: 2, speed: 6, armor: 0 }, Brute: { hp: 6, speed: 1, armor: 1 }, Swarm: { hp: 0, speed: 4, armor: 0 }, Ghost: { hp: 2, speed: 5, armor: 0 } }[n], regen: 0, resist: 'none' }))")
    check(pre == [20, 35, 6, 16], f'v22 Part B test 2: the four presets cost what they did (Runner 20, Brute 35, Swarm 6, Ghost 16: {pre})')
    ctx.close()

    # ---------- v22 Part C: moving or removing a tower the attacker saw costs a fee (on v22-v24's rise, 5 points a
    # relocation; v25's half point is checked after)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860}); page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.evaluate('() => { window.siegeline.rules.moveFeeRise = 0.05; }')
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    for r in range(0, 10): click_cell(page, 7, r)
    page.click('.tool[data-tool=tower]')
    for c, r in ((4, 5), (10, 3), (12, 8), (12, 2)): click_cell(page, c, r); page.keyboard.press('Escape')
    xy = lambda c, r: page.evaluate(f'() => window.siegeline.cellToClient({idx(c, r)})')
    def drag_cells(a, z):
        (x0, y0), (x1, y1) = xy(*a), xy(*z)
        page.mouse.move(x0, y0); page.mouse.down()
        for k in range(1, 9): page.mouse.move(x0 + (x1 - x0) * k / 8, y0 + (y1 - y0) * k / 8)
        page.mouse.up(); page.wait_for_timeout(60)
    drag_cells((4, 5), (4, 7)); drag_cells((4, 7), (4, 5))
    check(S(page, 'S.totals.moveTries') == 0, 'v22 Part C: round 1 moves are free (nothing seen yet)')
    page.click('#def-lock'); hand(page); page.click('#atk-lock')
    if not page.is_visible('#ov-hand'): page.click('#atk-lock')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    page.click('#sum-next'); hand(page)
    page.click('.tool[data-tool=wall]')
    mt = lambda: S(page, 'S.totals.moveTries')
    click_cell(page, 4, 5)
    check(page.inner_text('#te-move').startswith('Next move: 10% · 4 coins'), f'v22 Part C: the tower card shows “Next move: 10%” ({page.inner_text("#te-move")})')
    page.keyboard.press('Escape')
    f0 = S(page, 'S.dFree'); drag_cells((4, 5), (4, 8))
    check(S(page, 'S.dFree') == f0 - 4 and mt() == 1 and S(page, f'S.grid[{idx(4, 8)}].mfee') == 4, f'v22 Part C test 1: a seen tower moved in round 2 pays 10% of its tuning (40 → 4; {f0} → {S(page, "S.dFree")})')
    f1 = S(page, 'S.dFree'); drag_cells((10, 3), (10, 6))
    check(S(page, 'S.dFree') == f1 - 6 and mt() == 2, 'v22 Part C test 1: the next relocation pays 15% (6)')
    # test 2: removing a seen tower refunds its value minus the fee (now 20%: 8)
    click_cell(page, 12, 8); val = int(page.inner_text('#te-refund')); sv = page.evaluate(f'() => {{ const S = window.siegeline.state, g = S.grid[{idx(12, 8)}]; return window.siegeline.towerCost(g.cfg) + Math.max(...S.grid.filter(h => h && h.t === "tower").map(h => h.fee || 0)); }}')
    f2 = S(page, 'S.dFree'); page.click('#def-ctx [data-act=remove]'); page.wait_for_timeout(60)
    check(val == sv - 8 and S(page, 'S.dFree') == f2 + sv - 8 and mt() == 3, f'v22 Part C test 2: removing a seen tower refunds its value minus the fee ({sv} − 8 = {val}; the card said so)')
    # test 5: back onto its seen cell refunds its fee (and takes the relocation back)
    f3 = S(page, 'S.dFree'); drag_cells((4, 8), (4, 5))
    check(S(page, 'S.dFree') == f3 + 4 and mt() == 2 and S(page, f'S.grid[{idx(4, 5)}].mfee') == 0, 'v22 Part C test 5: dragged back onto its seen cell, the tower gets its fee back')
    # test 3: a tower placed this round moves and sells free
    page.click('.tool[data-tool=tower]'); click_cell(page, 2, 2); page.keyboard.press('Escape'); page.click('.tool[data-tool=wall]')
    f4 = S(page, 'S.dFree'); drag_cells((2, 2), (2, 8))
    check(S(page, 'S.dFree') == f4 and mt() == 2, 'v22 Part C test 3: a tower placed this round moves free')
    click_cell(page, 2, 8); full = int(page.inner_text('#te-refund')); page.click('#def-ctx [data-act=remove]'); page.wait_for_timeout(60)
    check(S(page, 'S.dFree') == f4 + full and mt() == 2 and page.evaluate('() => window.siegeline.towerCost({ range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0 })') + 0 <= full,
          f'v22 Part C test 3: and sells for its full value ({full})')
    # test 4: swapping two seen towers charges two fees (20% and 25%: 8 and 10); test 6: Undo puts coins and the count back
    f5, m5 = S(page, 'S.dFree'), mt()
    drag_cells((4, 5), (12, 2))
    check(S(page, 'S.dFree') == f5 - 8 - 10 and mt() == m5 + 2, f'v22 Part C test 4: swapping two seen towers charges two fees ({f5} → {S(page, "S.dFree")})')
    page.keyboard.press('Control+z'); page.wait_for_timeout(60)
    check(S(page, 'S.dFree') == f5 and mt() == m5 and S(page, f'S.grid[{idx(4, 5)}].t') == 'tower', 'v22 Part C test 6: Undo restores the coins and the relocation count exactly')
    for _ in range(4): page.keyboard.press('Control+z')
    page.wait_for_timeout(60)
    check(mt() == 3 and S(page, f'!!S.grid[{idx(4, 8)}]') and not S(page, f'!!S.grid[{idx(4, 5)}]'), 'v22 Part C test 6: Undo walks back through the removal and the move back, count and all')
    page.evaluate('() => { window.siegeline.state.totals.moveTries = 12; window.siegeline.refresh(); }')
    click_cell(page, 12, 2)
    check(page.inner_text('#te-move').startswith('Next move: 40% · 16 coins'), f'v22 Part C test 1: never above 40% ({page.inner_text("#te-move")})')
    check('go to the attacker' in (page.get_attribute('#te-move', 'data-tip') or ''), 'v23: the move fee’s tooltip says the fees go to the attacker')
    page.keyboard.press('Escape')
    # v23: what the defender paid this round, net of the fee that came back (4 + 6 + 8), goes to the attacker when the wave ends
    check(S(page, 'S.mvFee') == 18, f'v23: the round’s net move fees are kept for the attacker (4 + 6 + 8 = {S(page, "S.mvFee")})')
    a0 = S(page, 'S.aFree')
    page.click('#def-lock'); hand(page)
    check(S(page, 'S.aFree') == a0, 'v23: nothing reaches the attacker while it plans')
    page.click('#atk-lock')
    if not page.is_visible('#ov-hand'): page.click('#atk-lock')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    L = S(page, 'S.last')
    check(L['aMove'] == 18 and S(page, 'S.aFree') == a0 + L['aGain'] + 18 + L['aInt'] and S(page, 'S.mvFee') == 0 and S(page, 'S.totals.aMove') == 18,
          f'v23: when the wave ends the attacker gets the fees: pot {L["aGain"]} + moved towers 18 + interest {L["aInt"]}')
    ex = page.inner_text('#sum-extra') if page.is_visible('#sum-extra') else ''
    details(page)
    led = page.inner_text('#led-amove') if page.is_visible('#led-amove') else ''
    check('defender moved towers +18' in ex.lower() and 'Defender moved towers' in led and '+18' in led, f'v23: the summary shows it on its own line for the attacker ({ex} | {led})')
    # v25: the rate rises half a point a relocation, whichever tower, on the tower's tuning as it is now
    page.click('#sum-next'); hand(page)
    page.evaluate('() => { window.siegeline.rules.moveFeeRise = 0.005; }')
    seen = page.evaluate('() => { const S = window.siegeline.state; return S.grid.map((g, i) => (g && g.t === "tower" && S.seenGrid[i] && S.seenGrid[i].t === "tower" && S.seenGrid[i].n === g.n ? i : -1)).filter(i => i >= 0); }')
    cell = seen[0]; c0, r0 = cell % 16, cell // 16
    card = []
    for n in (0, 1, 2, 20, 100):
        page.evaluate(f'() => {{ window.siegeline.state.totals.moveTries = {n}; window.siegeline.state.freeMv = null; window.siegeline.refresh(); }}')
        click_cell(page, c0, r0); card.append(page.inner_text('#te-move').split(' · ')[0]); page.keyboard.press('Escape')
    check(card == ['Next move: 10%', 'Next move: 10.5%', 'Next move: 11%', 'Next move: 20%', 'Next move: 40%'], f'v25: the fee rises half a point a relocation, capped at 40% ({card})')
    page.evaluate(f'() => {{ const S = window.siegeline.state; S.totals.moveTries = 1; S.grid[{cell}].cfg.dps = 5; S.dFree = 2000; window.siegeline.refresh(); }}')
    tc = page.evaluate(f'() => window.siegeline.towerCost(window.siegeline.state.grid[{cell}].cfg)')
    dest = next(cr for cr in ((1, 1), (1, 9), (14, 1), (14, 9), (2, 1), (2, 9)) if not S(page, f'!!S.grid[{idx(*cr)}]'))
    f0 = S(page, 'S.dFree'); drag_cells((c0, r0), dest)
    check(S(page, 'S.dFree') == f0 - round(0.105 * tc) and S(page, 'S.totals.moveTries') == 2, f'v25: the second relocation pays 10.5% of the tower’s tuning as it is now ({tc} → {round(0.105 * tc)}; {f0} → {S(page, "S.dFree")})')
    check(not errors, f'Part C: no errors {errors[:3]}')
    ctx.close()

    # ---------- v22 Part D: Auto-army on the Army step
    ctx = b.new_context(viewport={'width': 1366, 'height': 860}); page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page)
    page.click('#def-body [data-act=maze]'); page.wait_for_function('() => !window.siegeline.mazing')
    page.click('#def-lock'); hand(page)
    army = lambda: S(page, 'JSON.stringify([S.aFree, S.designs.map(d => [d.name, d.hp, d.speed, d.armor, d.regen, d.resist, d.count])])')
    a0 = army(); free0 = S(page, 'S.aFree'); ds0 = S(page, 'S.designs.map(d => [d.hp, d.speed, d.armor, d.regen, d.resist])')
    check(S(page, 'S.designs.every(d => !d.count)'), 'Part D: the army starts empty')
    page.click('#atk-body [data-act=army]'); page.wait_for_function('() => !document.querySelector("#atk-body [data-act=army]").disabled', timeout=30000); page.wait_for_timeout(80)
    n_on = S(page, 'S.designs.filter(d => d.count > 0).length'); free1 = S(page, 'S.aFree')
    ds1 = S(page, 'S.designs.map(d => [d.hp, d.speed, d.armor, d.regen, d.resist])')
    up = all(all(a >= b for a, b in zip(n[:4], o[:4])) and all(r in n[4] for r in o[4].split('+') if r != 'none') for n, o in zip(ds1, ds0))
    check(n_on >= 2, f'v22 Part D test 4: from an empty army Auto-army ends with at least two designs ({n_on})')
    check(0 <= free1 <= free0 and len(ds1) >= len(ds0) and up, f'v22 Part D tests 1-2: it spends no more than the free coins ({free0} → {free1}), deletes no design and lowers no slider')
    line = page.inner_text('#a-help')
    check(line.startswith(f'Spent {free0 - free1} coins:'), f'v22 Part D: the line under the buttons says what it did ({line})')
    page.click('#atk-body [data-act=army-undo]'); page.wait_for_timeout(60)
    check(army() == a0, 'v22 Part D test 3: one Undo restores the army and the coins')
    for _ in range(2): page.click('.step.plus[data-i="1"]')
    for _ in range(3): page.click('.step.plus[data-i="2"]')
    b0 = army(); free0 = S(page, 'S.aFree'); ds0 = S(page, 'S.designs.map(d => [d.hp, d.speed, d.armor, d.regen, d.resist, d.count])')
    page.click('#atk-body [data-act=army]'); page.wait_for_function('() => !document.querySelector("#atk-body [data-act=army]").disabled', timeout=30000); page.wait_for_timeout(80)
    ds1 = S(page, 'S.designs.map(d => [d.hp, d.speed, d.armor, d.regen, d.resist, d.count])')
    check(all(all(a >= b for a, b in zip(n[:4], o[:4])) and n[5] >= o[5] for n, o in zip(ds1, ds0)) and 0 <= S(page, 'S.aFree') <= free0 and len(ds1) >= len(ds0),
          'v22 Part D tests 1-2: with an army it adds units and upgrades, never taking any away, within the free coins')
    page.click('#atk-body [data-act=army-undo]'); page.wait_for_timeout(60)
    check(army() == b0, 'v22 Part D test 3: and one Undo takes it back')
    check(not errors, f'Part D: no errors {errors[:3]}')
    ctx.close()

    ctx = b.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); no_terrain(page)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(150)
    rb = page.locator('#def-lock').bounding_box()
    check(rb and rb['y'] + rb['height'] <= 390, f'landscape phone: Lock in visible {rb}')
    page.screenshot(path=f'{OUT}/l0.png')
    ctx.close()

    # ---------- v19: the match length picked at the start (the keep follows), the planning clock, knock-outs keep the route
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go')
    picks = page.evaluate("() => [...document.querySelectorAll('#mode-waves button')].map(b => b.textContent + (b.getAttribute('aria-pressed') === 'true' ? '*' : ''))")
    check(picks == ['4', '6', '8*', '10', '12'] and page.inner_text('#mode-keep') == 'KEEP 1,000', f'the mode screen offers 4-12 waves, 8 picked, keep 1,000 ({picks}, {page.inner_text("#mode-keep")})')
    page.click('#mode-waves [data-rounds="4"]')
    check(page.inner_text('#mode-keep') == 'KEEP 600', 'picking 4 waves shows a keep of 600 (125 a wave, plus 25 for each of the 4 short of 8)')
    page.click('#mode-local'); hand(page)
    check(S(page, '[S.rounds, S.keep, S.keepMax]') == [4, 600, 600] and page.inner_text('#v-rounds') == 'of 4' and page.inner_text('#v-keepmax') == '/ 600',
          f'a 4-wave match: the HUD says of 4 and the keep has 600 ({page.inner_text("#v-rounds")}, {page.inner_text("#v-keepmax")})')
    check(page.is_hidden('#t-clock'), 'no clock with the planning time switched off')
    def quick_round(page, army=0):
        page.click('#def-lock'); hand(page)
        if army: page.evaluate(f'() => {{ const S = window.siegeline.state; S.designs[0].count = {army}; }}')
        page.click('#atk-lock')
        if not page.is_visible('#ov-hand'): page.click('#atk-lock')  # an empty army asks to confirm
        hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    for r in range(1, 4):
        quick_round(page)
        check(page.is_visible('#ov-sum') and f'round {r} of 4 complete' in page.inner_text('#ov-sum').lower(), f'round {r} of 4 complete')
        page.click('#sum-next'); hand(page)
    page.click('#def-lock'); hand(page)
    page.click('#atk-next'); page.wait_for_timeout(200)
    check(S(page, 'S.round') == 4 and page.inner_text('#a-chg-note') == 'No sabotage this wave.', f'no sabotage in wave 4 of 4, the final one ({page.inner_text("#a-chg-note")})')
    page.click('#atk-lock')
    if not page.is_visible('#ov-hand'): page.click('#atk-lock')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100); details(page, '#ov-end')
    check(S(page, 'S.winner') == 'defender' and page.is_visible('#ov-end') and 'survived all 4 rounds' in page.inner_text('#ov-end').lower() and '600 of 600 points' in page.inner_text('#ov-end'),
          'the defender wins after 4 waves, holding the keep of 600')
    page.click('#end-again'); hand(page)
    check(S(page, '[S.rounds, S.keep, S.round]') == [4, 600, 1], 'a rematch keeps the match length')
    # the keep scales with the length: 12 waves, 1,500 (no bonus above 8)
    page.reload(); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-waves [data-rounds="12"]'); page.click('#mode-local'); hand(page)
    check(S(page, '[S.rounds, S.keep]') == [12, 1500] and page.inner_text('#v-keep') == '1500', '12 waves: the keep has 1,500')
    ctx.close()

    # dragging towers: onto an open cell it moves, onto a wall or another tower they swap; tuning, fee, number and
    # coins stay as they were, and a tap still opens the card
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    for r in range(0, 10): click_cell(page, 7, r)  # a wall down column 7, the gap at the bottom
    page.click('.tool[data-tool=tower]'); click_cell(page, 4, 5); page.click('[data-act=close]')
    click_cell(page, 10, 3); set_slider(page, '#te-range', 4); page.click('[data-act=close]')
    T1, T2 = idx(4, 5), idx(10, 3)
    tw = lambda i: S(page, f'S.grid[{i}] && S.grid[{i}].t === "tower" ? [S.grid[{i}].n, S.grid[{i}].fee, S.grid[{i}].cfg.range] : (S.grid[{i}] && S.grid[{i}].t)')
    xy = lambda c, r: page.evaluate(f'() => window.siegeline.cellToClient({idx(c, r)})')
    def drag_cells(a, z, release=True):
        (x0, y0), (x1, y1) = xy(*a), xy(*z)
        page.mouse.move(x0, y0); page.mouse.down()
        for k in range(1, 9): page.mouse.move(x0 + (x1 - x0) * k / 8, y0 + (y1 - y0) * k / 8)
        if release: page.mouse.up()
        page.wait_for_timeout(60)
    one, two, free, walls = tw(T1), tw(T2), S(page, 'S.dFree'), S(page, 'S.grid.filter(g => g && g.t === "wall").length')
    drag_cells((4, 5), (4, 8), release=False)
    check(S(page, f'!!S.grid[{T1}] && !S.grid[{idx(4, 8)}]'), 'mid-drag nothing has moved yet')
    page.screenshot(path=f'{OUT}/d9_drag.png')
    page.mouse.up(); page.wait_for_timeout(60)
    check(tw(idx(4, 8)) == one and S(page, f'S.grid[{T1}]') is None and S(page, 'S.dFree') == free, f'drag a tower to an open cell: it moves with its number, fee and tuning, free ({tw(idx(4, 8))} vs {one})')
    drag_cells((4, 8), (7, 4))
    check(tw(idx(7, 4)) == one and tw(idx(4, 8)) == 'wall' and S(page, 'S.dFree') == free and S(page, 'S.grid.filter(g => g && g.t === "wall").length') == walls,
          'drag a tower onto a wall: they swap places, free')
    drag_cells((7, 4), (10, 3))
    check(tw(T2) == one and tw(idx(7, 4)) == two and S(page, 'S.dFree') == free, 'drag a tower onto another tower: they swap, each keeping its tuning')
    # the tower now on (10,3) stands in open ground, so dropping it in the wall's only gap would close the route
    path0 = S(page, 'S.path.length')
    drag_cells((10, 3), (7, 10))
    check(tw(T2) == one and S(page, f'S.grid[{idx(7, 10)}]') is None and toast(page) == 'Path must stay open' and S(page, 'S.path.length') == path0,
          f'a drop that would close the route is refused ({toast(page)})')
    drag_cells((10, 3), (15, 5))
    check(tw(T2) == one and 'gates' in toast(page).lower(), f'nothing goes on the keep’s gate ({toast(page)})')
    (x0, y0) = xy(7, 4); bb = page.locator('#board').bounding_box()
    page.mouse.move(x0, y0); page.mouse.down(); page.mouse.move(x0, y0 + 40, steps=4); page.mouse.move(bb['x'] + bb['width'] + 30, y0, steps=8); page.mouse.up(); page.wait_for_timeout(60)
    check(tw(idx(7, 4)) == two, 'dropped off the board: nothing moves')
    drag_cells((7, 4), (8, 4)); drag_cells((8, 4), (7, 4))
    check(tw(idx(7, 4)) == two and S(page, f'S.grid[{idx(8, 4)}]') is None, 'there and back again')
    click_cell(page, 7, 4)
    check(page.is_visible('#te-price') and S(page, 'S.sel && S.sel.cell') == idx(7, 4), 'a click without a drag still opens the tower’s card')
    drag_cells((7, 4), (8, 4))
    check(S(page, 'S.sel && S.sel.cell') == idx(8, 4) and page.is_visible('#te-price'), 'an open card follows its tower')
    page.click('[data-act=close]')
    # new or seen: like a rebuilt tower, it's new where the attacker didn't see a tower
    page.evaluate('() => { const S = window.siegeline.state; S.seenGrid = S.grid.map(g => g && { ...g, cfg: g.cfg && { ...g.cfg }, fresh: false }); S.seenVer++; S.grid.forEach(g => { if (g) g.fresh = false; }); }')
    drag_cells((8, 4), (8, 7))
    check(S(page, f'S.grid[{idx(8, 7)}].fresh') is True, 'moved to a cell the attacker didn’t see a tower on, it’s new')
    drag_cells((8, 7), (8, 4))
    check(S(page, f'S.grid[{idx(8, 4)}].fresh') is False, 'moved back to where it was seen, it isn’t')
    drag_cells((10, 3), (7, 2))
    check(S(page, f'S.grid[{idx(10, 3)}].t') == 'wall' and S(page, f'S.grid[{idx(10, 3)}].fresh') is True and S(page, f'S.grid[{idx(7, 2)}].fresh') is True,
          'swapped with a wall: both are new where the attacker saw the other')
    drag_cells((7, 2), (12, 8))
    check(isinstance(tw(idx(12, 8)), list), 'and dragged on again')
    check(not errors, f'dragging towers: no errors {errors[:3]}')
    ctx.close()

    # the planning clock: each side's own 3 minutes, from when its screen opens; when it runs out the plan goes as it stands
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.evaluate('() => { window.siegeline.rules.planSecs = 300; }')  # v23's default (no_terrain switches it off)
    page.click('#info-go')
    check(page.get_attribute('#mode-clock [data-timed="1"]', 'aria-pressed') == 'true' and '5:00' in page.inner_text('#mode-clockv'), f'v23: rounds are timed by default, 5:00 a round ({page.inner_text("#mode-clockv")})')
    page.click('#mode-local')
    check(page.is_hidden('#t-clock'), 'the clock waits behind the handoff screen')
    hand(page)
    check(page.is_visible('#t-clock') and page.inner_text('#t-clock') in ('5:00', '4:59'), f'v21: the defender gets 5:00 in the first round ({page.inner_text("#t-clock")})')
    page.click('#def-lock'); hand(page)
    check(page.is_visible('#t-clock') and page.inner_text('#t-clock') in ('5:00', '4:59'), f'v21: so does the attacker ({page.inner_text("#t-clock")})')
    page.click('#atk-lock'); page.click('#atk-lock'); hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    page.click('#sum-next'); hand(page)
    check(page.is_visible('#t-clock') and page.inner_text('#t-clock') in ('5:00', '4:59'), f'v23: from round 2 it is 5:00 too ({page.inner_text("#t-clock")})')
    # v23: untimed rounds, picked on the mode screen: no clock in any round, and nothing locks a plan in
    page.reload(); page.wait_for_timeout(300); no_terrain(page); page.evaluate('() => { window.siegeline.rules.planSecs = 300; }')
    page.click('#info-go'); page.click('#mode-clock [data-timed="0"]')
    check(page.get_attribute('#mode-clock [data-timed="0"]', 'aria-pressed') == 'true' and 'no clock' in page.inner_text('#mode-clockv').lower(), 'v23: Untimed can be picked on the mode screen')
    page.click('#mode-local'); hand(page); page.wait_for_timeout(300)
    check(page.is_hidden('#t-clock') and not page.evaluate('() => window.siegeline.state && document.querySelector("#clockbox").hidden === false'), 'v23: untimed: the defender plans without a clock')
    page.click('#def-lock'); hand(page)
    check(page.is_hidden('#clockbox'), 'v23: untimed: so does the attacker')
    page.click('#atk-lock'); page.click('#atk-lock'); hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    page.click('#sum-next'); hand(page); page.wait_for_timeout(1200)
    check(page.is_hidden('#clockbox') and S(page, 'S.phase') == 'defend', 'v23: untimed: round 2 has no clock either, and nothing sends the plan')
    page.reload(); page.wait_for_timeout(300); no_terrain(page); page.evaluate('() => { window.siegeline.rules.planSecs = 2; window.siegeline.rules.planSecsFirst = 2; }')
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    click_cell(page, 5, 4); click_cell(page, 5, 5)
    page.wait_for_timeout(1300)
    check('low' in page.get_attribute('#clockbox', 'class'), 'the last seconds show in red')
    page.wait_for_selector('#ov-hand', state='visible', timeout=4000)
    check(S(page, 'S.next') == 'attack' and 'defender’s time ran out' in page.inner_text('#hand-sub').lower() and S(page, f'S.grid[{idx(5,5)}].t') == 'wall',
          f'time up: the defense goes as built and the device passes to the attacker ({page.inner_text("#hand-sub")})')
    hand(page)
    check(S(page, 'S.phase') == 'attack' and page.is_visible('#t-clock'), 'the attacker gets a clock of their own')
    page.evaluate('() => { const S = window.siegeline.state; S.designs[0].count = 4; }')
    page.wait_for_selector('#ov-hand', state='visible', timeout=4000)
    check(S(page, 'S.next') == 'wave' and 'attacker’s time ran out' in page.inner_text('#hand-sub').lower() and '4 units' in page.inner_text('#hand-sub'),
          f'time up: the attacker’s army goes as planned ({page.inner_text("#hand-sub")})')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    page.click('#sum-next')
    check(page.is_hidden('#t-clock'), 'no clock on the handoff between rounds')
    page.evaluate('() => { window.siegeline.rules.planSecs = 3; }')
    hand(page)
    # a test run counts toward the time: when it runs out the test stops and the plan goes
    page.click('#def-test'); page.click('#pane-wave .speed [data-speed="1"]'); page.wait_for_timeout(100)
    check(page.evaluate('() => window.siegeline.testing') and page.is_visible('#t-clock'), 'the clock keeps running during a test run')
    page.wait_for_selector('#ov-hand', state='visible', timeout=5000)
    check(not page.evaluate('() => window.siegeline.testing') and S(page, 'S.next') == 'attack' and S(page, 'S.round') == 2, 'time up during a test run: the test stops and the plan goes')
    # an empty army goes empty when time runs out
    hand(page); page.evaluate('() => { const S = window.siegeline.state; S.designs.forEach(d => { d.count = 0; }); }')
    page.wait_for_selector('#ov-hand', state='visible', timeout=5000)
    check(S(page, 'S.next') == 'wave' and '0 units' in page.inner_text('#hand-sub'), f'time up on an attacker who planned nothing sends it empty, without asking ({page.inner_text("#hand-sub")})')
    check(not errors, f'planning clock: no errors {errors[:3]}')
    ctx.close()

    # knock-outs keep the route: a tower knocked out mid-wave still counts when units pick their way, so nobody turns
    # into the gap it guarded. Column 4 is walled with gaps in rows 3 and 6, and a tower at (2,7) covers the entry and
    # the near gap (row 6), so units take the far one (row 3). Without that tower's fire the near gap would win.
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page); sure_sappers(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page)
    page.click('#def-lock'); hand(page)
    KO = idx(2, 7)
    layout = f"""() => {{ const S = window.siegeline.state, T = range => ({{ t: 'tower', cfg: {{ range, dps: 2, rate: 3, splash: 0, slow: false, poison: false, chain: false }}, fee: 0, off: 0, n: 1, fresh: false, cd: 0, ang: 0, kick: 0, dealt: 0 }});
      const G = S.seenGrid.map(() => null); for (let r = 0; r < 11; r++) if (r !== 3 && r !== 6) G[r * 16 + 4] = {{ t: 'wall', fresh: false }};
      G[{KO}] = T(3); S.seenGrid = G; S.grid = G.map(g => g && {{ ...g, cfg: g.cfg && {{ ...g.cfg }} }}); S.seenVer++; S.gridVer++; S.seenRound = 1; S.round = 2;
      S.aFree = 500; S.designs.forEach(d => {{ d.count = 0; }}); }}"""
    page.evaluate(layout)
    far = page.evaluate('() => window.siegeline.seenRoute()')
    check(idx(4, 3) in far and idx(4, 6) not in far, 'with the tower firing, units take the far gap')
    page.evaluate(f"() => {{ const S = window.siegeline.state; S.seenGrid[{KO}] = {{ t: 'wall', fresh: false }}; S.seenVer++; }}")
    near_route = page.evaluate('() => window.siegeline.seenRoute()')
    check(idx(4, 6) in near_route, 'without its fire (its cell still blocked), the near gap would be cheaper')
    page.evaluate(layout)
    page.evaluate(f"() => {{ const S = window.siegeline.state; S.charges = new Map([[{KO}, {{ kind: 'tower', cost: 0, t: 0 }}]]); S.chargeVer++; }}")
    page.click('#atk-next'); page.click('#atk-next'); page.wait_for_timeout(100)
    check(S(page, 'S.step') == 2 and 'if your bridge lands' not in page.inner_text('#atk-body'), 'a knock-out alone doesn’t promise a different route')
    f = page.evaluate('() => window.siegeline.wave.forecast()')
    check(len(f['routes']) == 1 and any(o['cell'] == KO for o in f['offs']), f'v22: in the forecast the knock-out lands and the route never changes ({len(f["routes"])} routes, offs {f["offs"]})')
    page.click('#atk-lock')
    if not page.is_visible('#ov-hand'): page.click('#atk-lock')  # nothing but a sapper: Lock in asks twice
    hand(page)
    p0 = S(page, 'S.path')
    check(S(page, 'S.phase') == 'wave' and idx(4, 3) in p0, 'the real wave: units head for the far gap')
    landed = advance_until(page, f'S.grid[{KO}].off > 0')
    p1 = S(page, 'S.path')
    check(landed and p1 == p0 and idx(4, 6) not in p1, f'the knock-out lands mid-wave and the route stays as it was ({len(p0)} → {len(p1)} cells, landed {landed}, same {p1 == p0}, phase {S(page, "S.phase")})')
    page.evaluate('() => window.siegeline.advance(30)')
    check(S(page, 'S.path') == p0 or S(page, 'S.phase') != 'wave', 'and it stays so for the rest of the wave')
    check(not errors, f'knock-outs keep the route: no errors {errors[:3]}')
    ctx.close()

    # ---------- terrain: rough ground and rock, a new map every match
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    T = S(page, '[...S.terrain]')
    rough = [i for i, v in enumerate(T) if v == 1]; rock = [i for i, v in enumerate(T) if v == 2]
    check(len(rough) == round(176 * 0.05) and len(rock) == round(176 * 0.05), f'about 5% rough ground and 5% rock ({len(rough)}, {len(rock)})')
    gates = {r * COLS + c for c0 in (0, 15) for r in (4, 5, 6) for c in (c0 - 1, c0, c0 + 1) if 0 <= c < COLS}
    check(not (set(rough) | set(rock)) & gates, 'the gates and the cells around them stay clear')
    zones = [[sum(1 for r in range(r0, r1) for c in range(c0, c1) if T[r * COLS + c] == k) for (r0, r1) in ((0, 4), (4, 7), (7, 11)) for (c0, c1) in ((0, 5), (5, 11), (11, 16))] for k in (1, 2)]
    check(all(0 <= z <= 2 for zs in zones for z in zs), f'spread evenly: each of the 3x3 zones holds 0-2 of each kind {zones}')
    check(S(page, 'S.path !== null') and not set(S(page, 'S.path')) & set(rock), 'a route exists and goes around the rock')
    check(all(S(page, f'S.grid[{i}] && S.grid[{i}].t') == 'rock' for i in rock) and all(S(page, f'S.grid[{i}]') is None for i in rough), 'rock stands in the grid like a wall; rough ground stays open')
    i = rough[0]; click_cell(page, i % COLS, i // COLS)
    check(S(page, f'S.grid[{i}]') is None and 'rough' in toast(page).lower(), f'no wall on rough ground ({toast(page)})')
    j = rock[0]; click_cell(page, j % COLS, j // COLS)
    check(S(page, f'S.grid[{j}].t') == 'rock' and 'rock' in toast(page).lower(), f'no wall on rock ({toast(page)})')
    page.click('.tool[data-tool=remove]'); click_cell(page, j % COLS, j // COLS)
    check(S(page, f'S.grid[{j}].t') == 'rock' and 'can’t be removed' in toast(page), f'rock can’t be removed ({toast(page)})')
    page.screenshot(path=f'{OUT}/t0_terrain.png')
    page.click('.tool[data-tool=tower]'); click_cell(page, i % COLS, i // COLS)
    check(S(page, f'S.grid[{i}]') is None, 'no tower on rough ground')
    page.click('#def-lock'); hand(page)
    check(S(page, f'S.seenGrid[{j}] && S.seenGrid[{j}].t') == 'rock', 'the attacker sees the rock from round 1')
    for _ in range(5): page.click('.step.plus[data-i="0"]')
    page.click('#atk-lock')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    live = S(page, '[...S.terrain].join("")')
    page.click('#sum-replay'); page.wait_for_timeout(100)
    check(S(page, '[...S.terrain].join("")') == live and S(page, f'S.grid[{j}].t') == 'rock', 'the replay plays on the same map')
    page.click('#rp-close'); page.click('#sum-next'); hand(page)
    page.click('#def-lock'); hand(page)
    page.click('#atk-next'); page.wait_for_timeout(300)
    click_cell(page, j % COLS, j // COLS)
    check(S(page, 'S.charges.size') == 0 and 'can’t be bridged' in toast(page), f'rock can’t be bridged ({toast(page)})')
    click_cell(page, i % COLS, i // COLS)
    check(S(page, 'S.charges.size') == 0 and 'rough ground' in toast(page).lower(), f'rough ground needs no bridge ({toast(page)})')
    page.evaluate('() => { window.siegeline.state.keep = 1; }')
    page.click('#atk-lock'); hand(page)
    page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_selector('#ov-end', state='visible', timeout=5000)
    page.click('#end-again')
    check(S(page, '[...S.terrain].join("")') != live and S(page, 'S.terrain.filter(v => v).length') == len(rough) + len(rock), 'a rematch gets a new map')
    check(not errors, f'terrain: no errors {errors[:3]}')
    ctx.close()

    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    check(S(page, 'S.terrain.some(v => v)') and not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: terrain on the transposed board, no overflow')
    page.screenshot(path=f'{OUT}/m10_terrain.png')
    check(not errors, f'phone terrain: no errors {errors[:3]}')
    ctx.close()

    # ---------- v21: the user's "First Round, Scaling Payout, Frost & Chain, Simpler UI" spec
    INTERNALS = write_build('local_i.html', game_html().replace('window.siegeline = {', 'window.siegeline = { _i: { newState, makeUnit, strike, chainFrom, waveStep, recompute, get S() { return S; }, set S(v) { S = v; } },', 1))
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + INTERNALS); page.wait_for_timeout(300)
    # the scaling pot: the spec's table for 8 waves, p = 1 after wave 3 of 4, and the "off" values give v20.4's payout to the bit
    # the spec's values (the game ships them, or the "off" values if the payout fails its sims gate; see CLAUDE.md)
    SPEC_PAY = '{ potGrowth: 0.6, swingStart: 0.15, swingEnd: 0.25 }'
    pots = page.evaluate('() => { const R = window.siegeline.rules, was = [R.potGrowth, R.swingStart, R.swingEnd]; Object.assign(R, ' + SPEC_PAY + '); const out = [1, 2, 4, 7].map(r => { const P = window.siegeline.potFor(r, 8); return [P.pot, Math.round(P.lo * 1000) / 10, Math.round(P.hi * 1000) / 10, Math.round(P.pot * 2 * (P.hi - 0.5))]; }); [R.potGrowth, R.swingStart, R.swingEnd] = was; return out; }')
    check(pots == [[200, 35, 65, 60], [220, 33.3, 66.7, 73], [260, 30, 70, 104], [320, 25, 75, 160]], f'payout: an 8-wave match’s pot, split range and biggest gap after waves 1, 2, 4 and 7 match the spec ({pots})')
    check(page.evaluate('() => [1, 2, 3, 4].map(r => window.siegeline.potFor(r, 4).p)') == [0, 0.5, 1, 1], 'payout: a 4-wave match reaches p = 1 after wave 3')
    check(page.evaluate('() => window.siegeline.rules.planSecsFirst') == 300 and page.evaluate('() => window.siegeline.rules.starterPresses') == 3, 'the first round: 5:00 and a 3-press starter maze')
    off = page.evaluate('''() => { const sl = window.siegeline, R = sl.rules, was = [R.potGrowth, R.swingStart, R.swingEnd];
      Object.assign(R, { potGrowth: 0, swingStart: 0.2, swingEnd: 0.2 });
      let bad = 0, n = 0;
      for (const X of [0, 37, 100, 333, 1234]) for (let k = 0; k <= 60; k++) for (const r of [1, 4, 8]) {
        const Y = X * k / 50 * 0.7, sp = sl.splitFor(X, Y, r, 8), b = X > 0 ? Y / X : 0;
        const s0 = X > 0 ? Math.max(0.3, Math.min(0.7, 0.3 + (0.7 - 0.3) * b / 0.5)) : 0.5; n++;
        if (sp.pot !== 200 || sp.share !== s0 || Math.round(sp.pot * sp.share) !== Math.round(200 * s0)) bad++; }
      [R.potGrowth, R.swingStart, R.swingEnd] = was; return [bad, n]; }''')
    check(off[0] == 0, f'payout: potGrowth 0 and both swings 0.2 reproduce v20.4’s payout exactly ({off[1]} splits, {off[0]} differ)')
    # v23: regeneration heals from the moment a unit is hurt, even right after a direct hit (it waited 3 s before)
    rg = page.evaluate('''() => { const I = window.siegeline._i, R = window.siegeline.rules; I.S = I.newState(); const S = I.S, out = [];
      const T = { t: 'tower', cfg: { range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: false }, dealt: 0 };
      for (const delay of [R.regenDelay, 3]) {
        const was = R.regenDelay; R.regenDelay = delay;
        S.sentArmy = [{ name: 'R', color: '#ffb547', hp: 9, speed: 3, armor: 0, regen: 3, resist: 'none', count: 1, tl: { s: 0, e: 0, pos: null } }];
        const u = I.makeUnit(0, 0, 0); S.units = [u]; S.spawnList = []; S.spawnIdx = 0; S.waveT = 5; S.spawnStart = 0; I.recompute();
        I.strike(u, 100, 'direct', T); const h = u.hp; I.waveStep(1 / 60); out.push(u.hp - h); if (out.length === 1) out.cap = u.healCap;
        R.regenDelay = was;
      }
      return [R.regenDelay, out[0], out[1], out.cap]; }''')
    check(rg[0] == 0 and abs(rg[1] - 900 * 0.03 / 60) < 1e-9 and rg[2] == 0 and abs(rg[3] - 216) < 1e-9, f'v23: regen 3 heals 3% a second from the very next step after a direct hit (+{rg[1]:.3f} HP a step; with v22’s 3 s delay +{rg[2]}), at most 24% of 900 a wave ({rg[3]})')
    # Frost and Chain, hit by hit, on units the test places itself
    fx = page.evaluate('''() => { const I = window.siegeline._i; I.S = I.newState(); const S = I.S;
      const D = o => ({ name: 'T', color: '#ffb547', hp: 9, speed: 3, armor: 0, regen: 0, resist: 'none', count: 1, tl: { s: 0, e: 0, pos: null }, ...o });
      S.sentArmy = [D({}), D({ resist: 'frost' }), D({ armor: 3 }), D({ resist: 'shock' })];
      const T = cfg => ({ t: 'tower', cfg: { range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: false, ...cfg }, dealt: 0 });
      const fz = T({ slow: true }), plain = T({}), ch = T({ chain: true }), out = {};
      let u = I.makeUnit(0, 0, 0); I.strike(u, 10, 'direct', fz); out.first = 900 - u.hp; out.slow = [u.slowF, u.slowT];
      let h = u.hp; I.strike(u, 10, 'direct', plain); out.next = h - u.hp;
      const v = I.makeUnit(1, 0, 0); I.strike(v, 10, 'direct', fz); h = v.hp; I.strike(v, 10, 'direct', plain); out.resist = [v.slowF, h - v.hp];
      // a poison tick on a slowed unit: one step loses exactly poisonDps / 60
      const p = I.makeUnit(0, 0, 0); p.slowT = 1; p.slowF = 0.5; p.poisonT = 1; p.poisonDps = 6; S.units = [p]; S.spawnList = []; S.spawnIdx = 0; S.waveT = 0; S.spawnStart = 0; I.recompute();
      h = p.hp; I.waveStep(1 / 60); out.tick = h - p.hp;
      // chain: units 2 cells apart in a line, each jump from the unit struck before it
      const line = (xs, kinds) => xs.map((x, k) => { const w = I.makeUnit(kinds ? kinds[k] : 0, 0, 0); w.x = x; w.y = 5.5; return w; });
      const loss = us => us.map(w => Math.round((w.max - w.hp) * 1000) / 1000);
      let L = line([1, 3, 5, 7, 9]); S.units = L; I.chainFrom(L[0], 100, ch); out.jumps = loss(L);
      L = line([1, 3, 5.6]); S.units = L; I.chainFrom(L[0], 100, ch); out.reach = loss(L);
      L = line([1, 3]); S.units = L; I.chainFrom(L[0], 100, ch); out.twice = loss(L);
      L = line([1, 3], [0, 2]); S.units = L; I.chainFrom(L[0], 100, ch); out.armor = loss(L);
      L = line([1, 3], [0, 3]); S.units = L; I.chainFrom(L[0], 100, ch); out.shock = loss(L);
      return out; }''')
    check(fx['first'] == 10 and fx['slow'] == [0.5, 2.5] and abs(fx['next'] - 12) < 1e-9, f'frost: a hit slows by 50% for 2.5 s and isn’t amplified itself; the next hit, from any tower, lands 1.2× ({fx["first"]}, {fx["slow"]}, {fx["next"]})')
    check(abs(fx['resist'][0] - 0.2) < 1e-9 and abs(fx['resist'][1] - 10) < 1e-9, f'frost: a frost-resistant unit is slowed 20% and never brittle ({fx["resist"]})')
    check(abs(fx['tick'] - 0.1) < 1e-9, f'frost: poison ticks on a slowed unit aren’t amplified ({fx["tick"]:.4f} a step at 6/s)')
    check(fx['jumps'] == [0, 70, 50, 35, 0], f'chain: 3 jumps at 70%, 50% and 35%, each from the unit struck before it ({fx["jumps"]})')
    check(fx['reach'] == [0, 70, 0] and fx['twice'] == [0, 70], f'chain: it stops past 2.5 cells, and never strikes a unit twice ({fx["reach"]}, {fx["twice"]})')
    check(fx['armor'] == [0, 70] and fx['shock'] == [0, 28], f'chain: armor is ignored (an armored unit takes the full 70); Shock takes 60% less ({fx["armor"]}, {fx["shock"]})')
    # Chain and Splash don't combine, in the card; one Undo restores both
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    page.click('.tool[data-tool=tower]'); click_cell(page, 6, 5)
    check(page.get_attribute('#def-ctx [data-fx=slow]', 'data-tip').startswith('Slows each unit it hits by 50% for 2.5 s. Slowed units take 20% more damage from every tower.')
          and page.get_attribute('#def-ctx [data-fx=chain]', 'data-tip').startswith('Each hit jumps up to 3 times, 2.5 cells from unit to unit, ignoring armor (70%, 50%, 35% damage). Can’t be combined with Splash.'),
          'the Frost and Chain chips say what they do now')
    set_slider(page, '#te-splash', 1)
    page.click('#def-ctx [data-act=close]'); page.click('.tool[data-tool=wall]'); click_cell(page, 2, 2)  # another change, so the next tuning is an entry of its own
    click_cell(page, 6, 5); d0 = page.evaluate('() => window.siegeline.undoDepth()')
    page.click('#def-ctx [data-fx=chain]')
    cfg = S(page, f'S.grid[{idx(6, 5)}].cfg')
    check(cfg['chain'] and cfg['splash'] == 0 and toast(page) == 'Chain and Splash don’t combine: Splash set to Off.' and page.inner_text('#te-splash-v') == 'Off', f'turning Chain on sets Splash to Off, with the toast ({toast(page)})')
    page.keyboard.press('Control+z')
    cfg = S(page, f'S.grid[{idx(6, 5)}].cfg')
    check(not cfg['chain'] and cfg['splash'] == 1 and page.evaluate('() => window.siegeline.undoDepth()') == d0, 'one Undo restores both')
    page.click('#def-ctx [data-act=close]'); click_cell(page, 6, 5)
    page.click('#def-ctx [data-fx=chain]'); set_slider(page, '#te-splash', 2)
    cfg = S(page, f'S.grid[{idx(6, 5)}].cfg')
    check(not cfg['chain'] and cfg['splash'] == 2 and toast(page) == 'Chain and Splash don’t combine: Chain switched off.', f'moving Splash above Off switches Chain off ({toast(page)})')
    page.click('#def-ctx [data-act=close]')
    page.evaluate(f'() => {{ const S = window.siegeline.state; S.grid[{idx(6, 5)}].cfg.splash = 0; S.grid[{idx(6, 5)}].cfg.chain = true; S.dFree = 5000; }}')
    page.click('.tool[data-tool=tower]'); click_cell(page, 9, 5); page.click('#def-ctx [data-act=close]'); click_cell(page, 3, 5); page.click('#def-ctx [data-act=close]')
    page.evaluate(f'() => {{ window.siegeline.state.grid[{idx(9, 5)}].cfg.splash = 1; }}')
    page.click('#def-body [data-act=tune]')
    both = S(page, 'S.grid.filter(g => g && g.t === "tower" && g.cfg.chain && g.cfg.splash > 0).length')
    check(both == 0 and S(page, 'S.dFree') < 4000, f'auto-tune never combines Chain and Splash, even with coins to spare ({both} towers with both)')
    check(not errors, f'v21 rules: no errors {errors[:3]}')
    ctx.close()

    # the first round: the starter maze (on a map with terrain), the 5:00 clock, the attacker's Test and no sabotage
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); page.evaluate('() => { window.siegeline.rules.planSecs = 0; }')
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    walls = lambda G='S.grid': S(page, f'{G}.map((g, i) => g && g.t === "wall" ? i : -1).filter(i => i >= 0)')
    seed, n0 = S(page, 'S.mapSeed'), S(page, 'S.starter')
    a1, a2 = page.evaluate(f'() => window.siegeline.starterAt({seed})'), page.evaluate(f'() => window.siegeline.starterAt({seed})')
    check(20 <= n0 <= 36 and walls() == a1 == a2 and walls('S.seenGrid') == a1 and S(page, 'S.dFree') == 300 and S(page, 'S.terrain.some(v => v)'),
          f'starter maze: {n0} walls at match start, the same twice for the same map seed, seen by the attacker, and the coins still 300')
    check(route_len(page) >= 25 and route_len(page) > 15 + 10, f'starter maze: the route is clearly longer than the empty board’s ({route_len(page)} steps)')
    page.click('.tool[data-tool=remove]')
    w0 = a1[len(a1) // 2]; click_cell(page, w0 % COLS, w0 // COLS)
    check(S(page, f'S.grid[{w0}]') is None and S(page, 'S.dFree') == 305, 'starter maze: removing a starter wall refunds 5')
    page.keyboard.press('Control+z'); page.keyboard.press('Control+z')
    check(walls() == a1 and S(page, 'S.dFree') == 300 and toast(page) == 'Nothing to undo this round.', 'starter maze: Undo puts the wall back but never takes the starter maze away')
    page.click('#def-lock'); hand(page)
    check(page.evaluate('() => window.siegeline.tag') == 'STARTER MAZE' and walls('S.seenGrid') == a1, f'the attacker sees the starter maze in round 1, labelled ({page.evaluate("() => window.siegeline.tag")})')
    for _ in range(6): page.click('.step.plus[data-i="0"]')
    page.click('#atk-next'); page.wait_for_timeout(100)
    a0 = S(page, 'S.aFree'); click_cell(page, a1[0] % COLS, a1[0] // COLS)
    check(page.inner_text('#a-chg-note') == 'No sabotage this wave.' and S(page, 'S.charges.size') == 0 and S(page, 'S.aFree') == a0, f'no sabotage in round 1, starter maze or not ({toast(page)})')
    page.click('#atk-next'); page.wait_for_timeout(200)
    f = page.evaluate('() => window.siegeline.wave.forecast()')
    check(f and f['routes'][0]['path'] == S(page, '(window.siegeline.seenRoute() || [])') and f['sent'] == 6 and page.is_visible('#wv-play'),
          'v22: the Wave step’s forecast works in round 1, against the starter maze')
    page.click('#atk-lock'); hand(page)
    # the live pot meter: the no-breach split at the start, the defender's share growing as units reach the keep, the result at the end
    pm = lambda: (page.inner_text('#pm-d'), page.inner_text('#pm-a'), page.inner_text('#pm-pot'))
    page.wait_for_timeout(400)
    P1 = page.evaluate('() => { const P = window.siegeline.potFor(1, 8); return [Math.round(P.pot * P.lo), P.pot - Math.round(P.pot * P.lo), P.pot]; }')
    check(page.is_visible('#pot-meter') and pm() == (f'+{P1[0]}', f'+{P1[1]}', str(P1[2])), f'the pot meter starts at the no-breach split of round 1’s pot ({pm()}, {P1})')
    leaked = advance_until(page, 'S.wave.y > 20', 60)
    page.wait_for_timeout(500)
    live = page.evaluate('() => { const S = window.siegeline.state, sp = window.siegeline.splitFor(S.wave.x, S.wave.y); return Math.round(sp.pot * sp.share); }')
    check(leaked and int(pm()[0][1:]) == live and int(pm()[0][1:]) > P1[0], f'as units reach the keep it moves toward the defender, to the split the wave would pay now ({pm()}, {live})')
    page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(500)
    L = S(page, 'S.last')
    check(pm()[:2] == (f'+{L["dGain"]}', f'+{L["aGain"]}'), f'it settles on the summary’s numbers ({pm()} vs {L["dGain"]} / {L["aGain"]})')
    # the summary: three big numbers, the MVPs, the rest under Details
    dealt = S(page, 'S.grid.filter(g => g && g.t === "tower").map(g => [g.dealt, g.n])')
    yby = L['yBy']
    check(page.inner_text('#sb-keep') == f'−{L["Y"]:.0f}'.replace('−0', '−0') or page.inner_text('#sb-keep').startswith('−'), f'summary: Keep −Y ({page.inner_text("#sb-keep")})')
    check(page.inner_text('#sb-you') == f'+{L["dTot"]}' and page.inner_text('#sb-opp') == f'+{L["aTot"]}' and L['dTot'] == L['dGain'] + L['dKill'] + L['dInt'] and L['aTot'] == L['aGain'] + L['aMove'] + L['aInt'],
          f'summary: You (the defender, whose turn comes next) and Opponent, with all they earned: pot, interest, payouts (v23; {L["dTot"]} / {L["aTot"]})')
    check(page.is_hidden('#ov-sum .det') and page.is_visible('#ov-sum [data-act=details]'), 'summary: the details are under Details, closed')
    grp = page.inner_text('#mvp-group') if page.is_visible('#mvp-group') else ''
    check(not dealt and page.is_hidden('#mvp-tower') and 'Runner ×6' in grp and '100% of keep damage' in grp, f'summary: no tower, so no MVP tower; the MVP group is the one that did the keep damage ({grp})')
    page.click('#sum-next')
    check(page.inner_text('#hand-nums') == f'Keep −{L["Y"]:.0f} · Defender +{L["dTot"]} · Attacker +{L["aTot"]}'.replace(f'{L["Y"]:.0f}', page.evaluate(f'() => {{ const x = {L["Y"]}; return x >= 10 ? String(Math.round(x)) : String(Math.round(x * 10) / 10); }}')),
          f'the handoff shows the same three numbers in one line ({page.inner_text("#hand-nums")})')
    hand(page)
    check(page.is_visible('#d-intel') and 'Runner ×6' in page.inner_text('#d-intel'), f'round 2: the intel strip shows the army seen ({page.inner_text("#d-intel")})')
    page.click('#def-lock'); hand(page); page.click('#atk-next'); page.wait_for_timeout(100)
    check(any(page.evaluate(f'() => window.siegeline.canBridgeAt({i})') for i in a1 if S(page, f'!!S.seenGrid[{i}]')), 'starter walls can be bridged from round 2')
    check(not errors, f'v21 first round: no errors {errors[:3]}')
    # the same search, sliced between frames: three Auto-maze presses on the empty board build the starter maze exactly
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); page.evaluate('() => { const R = window.siegeline.rules; R.planSecs = 0; R.starterPresses = 0; }')
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    for _ in range(3): page.click('#def-body [data-act=maze]'); page.wait_for_function('() => !window.siegeline.mazing'); page.wait_for_timeout(30)
    seed = S(page, 'S.mapSeed')
    check(sorted(walls()) == page.evaluate(f'() => window.siegeline.starterAt({seed}, 3)'), 'the starter maze doesn’t depend on the slicing: three sliced Auto-maze presses build the same walls')
    # an empty army: the meter sits at 50/50
    page.click('#def-lock'); hand(page); page.click('#atk-lock'); page.click('#atk-lock'); hand(page); page.wait_for_timeout(400)
    check(pm()[:2] == ('+100', '+100'), f'the pot meter shows 50/50 for an empty army ({pm()})')
    page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(200)
    # the meter changes nothing: a replay with it hidden plays the wave to the same numbers
    page.click('#sum-next'); hand(page); page.click('#def-lock'); hand(page)
    for _ in range(8): page.click('.step.plus[data-i="2"]')
    page.click('#atk-lock'); hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    L = S(page, 'S.last'); page.evaluate("() => { document.querySelector('#potbox').style.display = 'none'; }")
    page.click('#sum-replay'); page.evaluate('() => window.siegeline.advance(200)')
    R = S(page, 'S.wave')
    check([R['x'], R['y'], R['kills'], R['leaks']] == [L['X'], L['Y'], L['kills'], L['leaks']], 'the pot meter is display only: the wave plays to the same numbers without it')
    page.click('#rp-close')
    check(not errors, f'v21 Auto-maze and pot meter: no errors {errors[:3]}')
    ctx.close()

    # the UI pass on a desktop: the tower card and the unit row editor without scrolling, Remove and Copy tuning on the card,
    # the tower strip, the MVP tower, shortcuts, and "?" at the right section
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    inview = lambda sels, W, H: all((lambda bb: bb and bb['x'] >= 0 and bb['y'] >= 0 and bb['x'] + bb['width'] <= W and bb['y'] + bb['height'] <= H)(page.locator(s_).bounding_box()) for s_ in sels)
    CARD = ['#def-ctx .pre[data-pre=Basic]', '#def-ctx .pre[data-pre=Frost]'] + [f'#te-{k}' for k in ('range', 'dps', 'accuracy', 'rate', 'splash')] + [f'#def-ctx [data-fx={k}]' for k in ('slow', 'poison', 'chain')] + ['#def-ctx [data-act=remove]', '#def-ctx [data-act=copy]', '#def-ctx [data-act=close]', '#te-stat']
    noscroll = lambda sel: page.evaluate(f"() => {{ const e = document.querySelector('{sel}'); return e.scrollHeight <= e.clientHeight + 1; }}")
    for r in range(0, 10): click_cell(page, 7, r)
    page.click('.tool[data-tool=tower]'); click_cell(page, 6, 5)
    check(inview(CARD, 1366, 860) and noscroll('#pane-def .scroll'), 'the tower card has every control (presets, five sliders, three effects, Remove, Copy tuning, Done) in view, without scrolling, at 1366×860')
    check(re.fullmatch(r'Expected \d+/s · covers \d+ route cells? · \d+\.\d s under fire', page.inner_text('#te-stat')) is not None, f'its stat line ({page.inner_text("#te-stat")})')
    page.screenshot(path=f'{OUT}/v21_card.png')
    set_slider(page, '#te-range', 4); cfg = S(page, f'S.grid[{idx(6, 5)}].cfg')
    page.click('#def-ctx [data-act=copy]')
    check(S(page, 'S.tool') == 'tower' and 'T1 tuning' in page.inner_text('.tool[data-tool=tower]'), f'Copy tuning: the Tower tool reads “Tower · T1 tuning ×” ({page.inner_text(".tool[data-tool=tower]")})')
    f0 = S(page, 'S.dFree'); click_cell(page, 9, 3)
    price = page.evaluate(f'() => window.siegeline.towerCost({json.dumps(cfg)})')
    check(S(page, f'S.grid[{idx(9, 3)}].cfg') == cfg and S(page, 'S.dFree') == f0 - price - 10, f'the next tower is placed with that tuning, priced as usual ({price} + 10 fee)')
    page.click('.tool[data-tool=tower] [data-act=brush-x]'); click_cell(page, 9, 7)
    check(S(page, f'S.grid[{idx(9, 7)}].cfg.range') == 2, 'its × clears the brush: the next tower is a Basic again')
    if page.is_visible('#def-ctx [data-act=close]'): page.click('#def-ctx [data-act=close]')
    page.click(f'#d-tstrip [data-cell="{idx(9, 3)}"]')
    check(S(page, 'S.sel && S.sel.cell') == idx(9, 3) and page.inner_text('#def-ctx .ed-title') == 'Tower 2', 'the tower strip opens the right card')
    f0 = S(page, 'S.dFree'); page.click('#def-ctx [data-act=remove]')
    check(S(page, f'S.grid[{idx(9, 3)}]') is None and S(page, 'S.dFree') > f0 and page.is_visible('#undo-pop'), 'Remove on the card removes the tower, with the Undo pop-up')
    page.click('#undo-btn')
    check(S(page, f'S.grid[{idx(9, 3)}] && S.grid[{idx(9, 3)}].n') == 2 and S(page, 'S.dFree') == f0, 'and Undo puts it back')
    # shortcuts: W, T, R, S pick the tools; Delete removes the selected tower; Escape is Done
    page.mouse.move(5, 5)
    for k, t in (('t', 'tower'), ('r', 'remove'), ('s', 'shape'), ('w', 'wall')):
        page.keyboard.press(k); check(S(page, 'S.tool') == t, f'shortcut {k.upper()} picks {t}')
    click_cell(page, 9, 7); page.keyboard.press('Escape')
    check(S(page, 'S.sel') is None, 'Escape is Done')
    click_cell(page, 9, 7); page.keyboard.press('Delete')
    check(S(page, f'S.grid[{idx(9, 7)}]') is None and page.is_visible('#undo-pop'), 'Delete removes the selected tower, with Undo')
    page.keyboard.press('Control+z')
    click_cell(page, 6, 5); page.click('#btn-info'); page.wait_for_timeout(100)
    top = page.evaluate("() => document.querySelector('#info-tower').getBoundingClientRect().top - document.querySelector('#info-body').getBoundingClientRect().top")
    check(page.is_visible('#ov-info') and -2 <= top <= 30, f'“?” opens the rules at the section for the screen (the tower card: Towers, {top:.0f} px from the top)')
    check('W' in page.inner_text('#info-build') and 'Delete' in page.inner_text('#info-build'), 'the shortcuts are listed under “?”')
    page.click('#info-x'); page.click('#def-ctx [data-act=close]')
    # the MVP tower: the most damage this wave (a rapid-fire tower beside the wall's only gap, which the route must take)
    page.evaluate('() => { window.siegeline.state.dFree += 200; window.siegeline.refresh(); }')
    page.click('.tool[data-tool=tower]'); click_cell(page, 8, 9); set_slider(page, '#te-rate', 0)
    if page.is_visible('#def-ctx [data-act=close]'): page.click('#def-ctx [data-act=close]')
    page.click('#def-lock'); hand(page)
    for _ in range(6): page.click('.step.plus[data-i="2"]')
    page.click('.rpick[data-i="0"]')
    UE = [f'#ue-{k}' for k in ('hp', 'speed', 'armor', 'regen')] + ['#ue-name', '#roster [data-resist=shock]', '#roster [data-act=delete]', '#roster [data-act=copy-design]', '#roster [data-act=close]']
    check(inview(UE, 1366, 860) and noscroll('#pane-atk .scroll') and page.locator('#roster [data-resist]').count() == 5, 'the unit row editor opens in place with every control in view, five resists (Shock among them), at 1366×860')
    check(page.get_attribute('#roster [data-resist=shock]', 'data-tip').startswith('Shock resist: takes 60% less chain damage'), 'Shock: takes 60% less chain damage')
    page.click('#ue-name'); page.keyboard.press('End'); page.keyboard.press('Backspace'); page.keyboard.press('w')
    check(S(page, 'S.designs.length') == 3 and S(page, 'S.designs[0].name') == 'Runnew', f'typing in the name field: Backspace deletes a letter, not the design, and W types ({S(page, "S.designs[0].name")})')
    page.click('#roster [data-act=copy-design]')
    check(S(page, 'S.designs.length') == 4 and S(page, '[S.designs[3].hp, S.designs[3].speed, S.designs[3].count]') == S(page, '[S.designs[0].hp, S.designs[0].speed, 0]'), 'Copy design adds the same stats with none in the army yet')
    page.mouse.click(5, 5); page.keyboard.press('Delete')
    check(S(page, 'S.designs.length') == 3 and S(page, 'S.sel') is None, 'Delete closes and deletes the open design')
    page.click('#atk-lock'); hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    best = S(page, 'S.grid.filter(g => g && g.t === "tower" && g.dealt > 0).sort((a, b) => b.dealt - a.dealt || a.n - b.n)[0]')
    allD = S(page, 'S.grid.reduce((v, g) => v + (g && g.t === "tower" ? g.dealt : 0), 0)')
    mt = page.inner_text('#mvp-tower') if page.is_visible('#mvp-tower') else ''
    check(best and f'Tower {best["n"]}' in mt and f'{round(best["dealt"] / allD * 100)}% of all damage' in mt and S(page, 'S.last.mvp.tower.cell') is not None, f'the MVP tower is the one that dealt the most ({mt})')
    details(page)
    check(page.is_visible('#ov-sum .det') and 'Defender share =' in page.inner_text('#ov-sum .det'), 'Details opens the pot explanation and the rest')
    check(not errors, f'v21 desktop UI: no errors {errors[:3]}')
    ctx.close()

    # and on a 390 px phone: the coins in the HUD, the card as a half-height sheet with nothing to scroll, the unit editor
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); no_terrain(page)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    clipped = page.evaluate("() => ['#potbox', '.keepbox', '.roundchip', '#btn-info'].map(s => { const e = document.querySelector(s), r = e.getBoundingClientRect(); return r.left >= 0 && r.right <= 390 && e.scrollWidth <= e.clientWidth + 1; })")
    check(all(clipped) and page.is_visible('#d-free') and page.inner_text('#d-free') == '300' and not page.query_selector('#coinbox'), f'phone: the free coins are in the panel, not the HUD, and nothing in the HUD is clipped ({clipped})')
    page.tap('.tool[data-tool=tower]'); x, y = page.evaluate(f'() => window.siegeline.cellToClient({idx(12, 8)})'); page.touchscreen.tap(x, y); page.wait_for_timeout(100); page.touchscreen.tap(x, y); page.wait_for_timeout(600)
    sheet = page.locator('#def-ctx').bounding_box()
    check(inview(CARD, 390, 844) and noscroll('#def-ctx') and sheet['height'] <= 844 * 0.55, f'phone: the tower card is a half-height sheet with every control in view and nothing to scroll ({sheet["height"]:.0f} px)')
    tower_y = page.evaluate(f'() => window.siegeline.cellToClient({idx(12, 8)})[1]')
    check(tower_y < sheet['y'], f'phone: the board slides so the tower sits above the sheet ({tower_y:.0f} < {sheet["y"]:.0f})')
    page.screenshot(path=f'{OUT}/v21_phone_card.png')
    page.tap('#def-ctx [data-act=close]'); page.tap('#def-lock'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    page.tap('.rpick[data-i="1"]'); page.wait_for_timeout(200)
    check(inview(UE, 390, 844), 'phone: the unit row editor has every control in view')
    page.screenshot(path=f'{OUT}/v21_phone_unit.png')
    check(not errors, f'v21 phone UI: no errors {errors[:3]}')
    ctx.close()

    # ---------- v21.1: the user's fixes: a tower on a wall, several resists, Next as the attacker's main button, the HUD
    # without coins, the summary's Details at a laptop's height, the slider tracks, and the clock's last 30 seconds
    ctx = b.new_context(viewport={'width': 1280, 'height': 720})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + INTERNALS); page.wait_for_timeout(400); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); page.wait_for_timeout(500); hand(page); hints_off(page)
    check(not page.query_selector('#coinbox') and page.inner_text('#d-free') == '300' and page.is_visible('#potbox') and page.is_visible('#keepbox'),
          'the HUD shows the round, the keep, the clock and the pot, no coins; the free coins are in the panel')
    page.click('.tool[data-tool=wall]'); click_cell(page, 5, 3); click_cell(page, 6, 3)
    L0, f0 = route_len(page), S(page, 'S.dFree')
    page.click('.tool[data-tool=tower]'); click_cell(page, 5, 3); page.wait_for_timeout(100)
    g = S(page, f'S.grid[{idx(5,3)}] && [S.grid[{idx(5,3)}].t, S.grid[{idx(5,3)}].fresh]')
    check(g == ['tower', True] and S(page, 'S.dFree') == f0 + 5 - 40 and route_len(page) == L0, f'the Tower tool on a wall replaces it: the wall’s 5 come back, a 40-coin tower goes up, the route is unchanged ({g}, {f0} → {S(page, "S.dFree")})')
    if page.is_visible('#def-ctx [data-act=close]'): page.click('#def-ctx [data-act=close]')
    page.keyboard.press('Control+z'); page.wait_for_timeout(100)
    check(S(page, f'S.grid[{idx(5,3)}].t') == 'wall' and S(page, 'S.dFree') == f0, 'one Undo puts the wall back and the coins with it')
    page.evaluate('() => { window.siegeline.state.dFree = 30; window.siegeline.refresh(); }')
    page.click('.tool[data-tool=tower]'); click_cell(page, 6, 3); page.wait_for_timeout(100)
    check(S(page, f'S.grid[{idx(6,3)}].t') == 'wall' and 'with the wall’s 5 back' in toast(page), f'without the coins (30 + the wall’s 5 against 50) the wall stays, and the message counts the refund ({toast(page)})')
    page.evaluate('() => { window.siegeline.state.dFree = 300; window.siegeline.refresh(); }')
    page.click('#def-lock'); hand(page)
    # the attacker's footer: Next is the main button on Army and Sabotage, Lock in the small one beside it
    cls = lambda sel: page.get_attribute(sel, 'class') or ''
    check('ready' in cls('#atk-next') and page.inner_text('#atk-next').lower() == 'next: sabotage' and 'back' in cls('#atk-lock')
          and page.locator('#atk-next').bounding_box()['width'] > page.locator('#atk-lock').bounding_box()['width'], 'Army: the main button is Next: Sabotage, Lock in the small one beside it')
    # several resists on one design, each multiplying the price
    page.click('#roster .rpick[data-i="1"]'); page.wait_for_timeout(150)
    hd = lambda: page.locator('#roster .urow[data-i="1"] .uhead').bounding_box()['height']
    h0, costs = hd(), [page.inner_text('#u1-cost')]
    for k in ('splash', 'shock', 'frost'): page.click(f'#roster [data-resist={k}]'); costs.append(page.inner_text('#u1-cost'))
    res = S(page, 'S.designs[1].resist')
    check(res == 'splash+frost+shock' and costs == ['35 each', '46 each', '59 each', '87 each'], f'a design takes several resists, each ×1.3 on the price (the big-unit surcharge past 60; a Brute’s toughness is under 2.5): {res} {costs}')
    pressed = page.evaluate("() => [...document.querySelectorAll('#roster [data-resist]')].filter(b => b.getAttribute('aria-pressed') === 'true').map(b => b.dataset.resist)")
    check(sorted(pressed) == ['frost', 'shock', 'splash'] and page.locator('#roster .urow[data-i="1"] .us.rs i').count() == 3 and abs(hd() - h0) < 1,
          f'the editor shows the three pressed; the row shows one Res pill with a dot each, and doesn’t grow ({pressed}, {h0:.0f} → {hd():.0f} px)')
    check(page.evaluate('() => window.siegeline.encodeArmy(window.siegeline.state.designs)[1][6]') == 1 + 4 + 8, 'an army encodes its resists as a bitmask (splash 1, poison 2, frost 4, shock 8)')
    page.click('#roster [data-resist=frost]')
    check(S(page, 'S.designs[1].resist') == 'splash+shock', 'a pressed resist toggles off on its own')
    page.click('#roster [data-act=copy-design]'); page.wait_for_timeout(500)
    check(S(page, 'S.designs.length') == 4 and S(page, 'S.designs[3].resist') == 'splash+shock' and page.evaluate("() => { const r = document.querySelector('#roster .urow[data-i=\"3\"]').getBoundingClientRect(), s = document.querySelector('#pane-atk .scroll').getBoundingClientRect(); return r.top >= s.top - 1 && r.top < s.bottom; }"),
          'Copy design copies the resists and brings the copy into view')
    page.click('#roster [data-act=close]'); page.click('#roster .step.plus[data-i="1"]'); page.click('#roster .step.plus[data-i="1"]')
    page.click('#atk-next'); page.click('#atk-next'); page.wait_for_timeout(200)
    check(page.is_hidden('#atk-next') and 'ready' in cls('#atk-lock'), 'Wave: Lock in is the main button')
    page.click('#atk-lock'); hand(page)
    rs = page.evaluate('() => { const I = window.siegeline._i, u = window.siegeline.state.units.find(u => u.di === 1); return u ? [!!u.rs.splash, !!u.rs.shock, !!u.rs.frost] : null; }')
    page.evaluate('() => window.siegeline.advance(4)')
    rs = rs or page.evaluate('() => { const u = window.siegeline.state.units.find(u => u.di === 1); return u ? [!!u.rs.splash, !!u.rs.shock, !!u.rs.frost] : null; }')
    check(rs == [True, True, False], f'in the wave the unit resists splash and shock, not frost ({rs})')
    advance_until(page, 'S.phase === "summary"')
    page.wait_for_timeout(400)
    hs = "() => [...document.querySelectorAll('#sum-body > *')].filter(e => e.offsetParent && !e.classList.contains('det')).map(e => Math.round(e.getBoundingClientRect().height))"
    h_closed = page.evaluate(hs); details(page); page.wait_for_timeout(300); h_open = page.evaluate(hs)
    sq = [f'{a}→{b}' for a, b in zip(h_closed, h_open) if b < a]
    nb, tog = page.locator('#sum-next').bounding_box(), page.locator('#ov-sum [data-act=details]').bounding_box()
    check(not sq and tog['height'] >= 26 and nb['y'] + nb['height'] <= 720, f'at 1280×720 the opened Details squash nothing (the toggle {tog["height"]:.0f} px) and Start round stays in view ({sq})')
    check(not errors, f'v21.1 fixes: no errors {errors[:3]}')
    ctx.close()

    # units with several resists, hit by hit: frost and shock together
    ctx = b.new_context(); page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + INTERNALS); page.wait_for_timeout(300)
    fx = page.evaluate('''() => { const I = window.siegeline._i; I.S = I.newState(); const S = I.S;
      const D = o => ({ name: 'T', color: '#ffb547', hp: 9, speed: 3, armor: 0, regen: 0, resist: 'none', count: 1, tl: { s: 0, e: 0, pos: null }, ...o });
      S.sentArmy = [D({ resist: 'frost+shock' }), D({ resist: 'splash+poison' })];
      const T = cfg => ({ t: 'tower', cfg: { range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: false, ...cfg }, dealt: 0 });
      const u = I.makeUnit(0, 0, 0); I.strike(u, 10, 'direct', T({ slow: true })); let h = u.hp; I.strike(u, 10, 'direct', T({})); const out = { slow: u.slowF, next: h - u.hp };
      h = u.hp; I.strike(u, 100, 'chain', T({ chain: true })); out.chain = h - u.hp;
      const v = I.makeUnit(1, 0, 0); h = v.hp; I.strike(v, 100, 'splash', T({ splash: 1 })); out.splash = h - v.hp; I.strike(v, 10, 'direct', T({ poison: true })); out.pois = v.poisonDps;
      return out; }''')
    check(abs(fx['slow'] - 0.2) < 1e-9 and abs(fx['next'] - 10) < 1e-9 and abs(fx['chain'] - 40) < 1e-9, f'frost + shock: slowed 20% and never brittle, and chain hits 60% weaker ({fx})')
    check(abs(fx['splash'] - 40) < 1e-9 and abs(fx['pois'] - 10 * 0.6 / 3 * 0.4) < 1e-9, f'splash + poison: both resists work on one unit ({fx})')
    check(not errors, f'v21.1 resists: no errors {errors[:3]}')
    ctx.close()

    # ---------- v23: tower prices, sapper armor, a sapper shot down pays the defender, a missed one pays no one, interest
    ctx = b.new_context(viewport={'width': 1366, 'height': 860}); page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    tc = lambda cfg: page.evaluate(f'() => window.siegeline.towerCost({{ range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: false, ...{json.dumps(cfg)} }})')
    PT = {'range': 0, 'dps': 8, 'accuracy': 3, 'rate': 3, 'chain': True}  # the playtest's tower: 1.5 cells, 75 a second, 100%, chain
    m = page.evaluate('() => { const T = window.siegeline.TS; return [T.range.mult(0), T.range.mult(7), T.dps.mult(8), T.range.mult(2), T.dps.mult(2)]; }')
    check([round(x, 2) for x in m] == [0.6, 2.0, 7.37, 1.0, 1.0], f'v23: range priced linearly (1.5 cells ×0.6, 5 cells ×2) and damage ^1.4 (75 a second ×7.4); the default is ×1 on both ({m})')
    new = [tc({}), tc(PT), tc({'rate': 4, 'splash': 2}), tc({'range': 5, 'rate': 5})]
    page.evaluate('() => { const R = window.siegeline.rules; R.rangePow = 2; R.dpsPow = 1.15; }')
    old = [tc({}), tc(PT)]
    page.evaluate('() => { const R = window.siegeline.rules; R.rangePow = 1; R.dpsPow = 1.4; }')
    check(new[0] == 40 and old[0] == 40 and new[1] == 425 and old[1] == 178, f'v23: a default tower still costs 40; the playtest’s tower {old[1]} → {new[1]} (the spec: about 178 → 425)')
    check(new[2] == 76 and new[3] == 64, f'v23: a Cannon is still 76 (range and damage at the default); a Sniper (4 cells) 102 → {new[3]}')
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    page.click('#def-lock'); hand(page); page.click('#atk-lock')
    if not page.is_visible('#ov-hand'): page.click('#atk-lock')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    L1 = S(page, 'S.last')
    check(L1['dInt'] == min(150, L1['dLeft']) * 15 // 100 and L1['aInt'] == 22 and L1['dTot'] == L1['dGain'] + L1['dInt'],
          f'v23: interest after wave 1: 15% of what each side left unspent, up to 150 (defender {L1["dLeft"]} → +{L1["dInt"]}, attacker 300 → +22)')
    page.click('#sum-next'); hand(page)
    # round 2: a strong tower by the entry (1), two Basic towers further on (2 and 3); tower 3 has moved since the attacker saw it
    T1, T2, T3, T3now = idx(2, 4), idx(13, 3), idx(9, 2), idx(9, 8)
    page.evaluate(f'''() => {{ const S = window.siegeline.state, T = (cfg, n) => ({{ t: 'tower', cfg: {{ range: 2, dps: 2, accuracy: 0, rate: 3, splash: 0, slow: false, poison: false, chain: false, ...cfg }}, fee: 0, off: 0, n, fresh: false, cd: 0, ang: 0, kick: 0, dealt: 0 }});
      S.seenGrid = S.seenGrid.map(() => null); S.seenGrid[{T1}] = T({{ dps: 8, accuracy: 3 }}, 1); S.seenGrid[{T2}] = T({{}}, 2); S.seenGrid[{T3}] = T({{}}, 3);
      S.grid = S.grid.map(() => null); S.grid[{T1}] = T({{ dps: 8, accuracy: 3 }}, 1); S.grid[{T2}] = T({{}}, 2); S.grid[{T3now}] = {{ ...T({{}}, 3), fresh: true }};
      S.towerSeq = 3; S.seenVer++; S.gridVer++; S.dFree = 100; window.siegeline.refresh(); }}''')
    page.click('#def-lock'); hand(page)
    page.click('#atk-next'); page.wait_for_timeout(250)
    def plant(i):
        click_cell(page, i % COLS, i // COLS); page.wait_for_timeout(60)
        if page.is_visible('#atk-ctx [data-act=plant]'): page.click('#atk-ctx [data-act=plant]')
        page.click('#atk-ctx [data-act=close]')
    plant(T2); plant(T3)
    cost2 = S(page, f'S.charges.get({T2}).cost')
    tip = page.get_attribute('[data-sabo=tower]', 'data-tip') or ''
    check(S(page, 'S.charges.size') == 2 and 'armor that blocks 3' in tip and 'its whole price goes to the defender' in tip and 'the knock-out misses and its coins are spent' in tip,
          f'v23: the knock-out card says sappers are armored, a shot-down one pays the defender (its whole price since v24), and a moved target means a miss ({tip})')
    page.evaluate(f'() => {{ const S = window.siegeline.state; S.charges.get({T2}).t = 0; S.charges.get({T3}).t = 0.5; }}')  # the first alone into tower 1's fire
    a2 = S(page, 'S.aFree')
    page.click('#atk-lock')
    if not page.is_visible('#ov-hand'): page.click('#atk-lock')
    hand(page)
    advance_until(page, 'S.units.some(u => u.sap)', 40)
    arm = S(page, '(S.units.find(u => u.sap) || {}).armor')
    page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    L = S(page, 'S.last'); saps = S(page, 'S.sapList.map(s => s.state)')
    check(arm == 3, f'v23: sappers march with armor 1 (each hit loses 3; {arm})')
    check(saps == ['lost', 'miss'] and L['sapLost'] == 1 and L['dKill'] == cost2,
          f'v24: the sapper shot down pays the defender its sabotage’s whole price ({cost2} → +{L["dKill"]}); the one whose tower moved missed and pays no one ({saps})')
    check(L['dInt'] == 15 and L['aInt'] == 22 and L['aLeft'] == a2 and L['dTot'] == L['dGain'] + L['dKill'] + 15 + L['bridgeRefund'] * 0,
          f'v23: interest on what was left when the wave started (defender 100 → +15, attacker {a2} → +22, at most 150 counted)')
    ex = page.inner_text('#sum-extra') if page.is_visible('#sum-extra') else ''
    details(page)
    led = page.inner_text('#led-dkill') if page.is_visible('#led-dkill') else ''
    check(f'sappers shot down +{L["dKill"]}' in ex.lower() and 'interest +15' in ex.lower() and f'+{L["dKill"]}' in led and page.is_visible('#led-dint') and page.is_visible('#led-aint'),
          f'v23: the summary shows the payout and the interest on their own lines ({ex} | {led})')
    check(S(page, 'S.freeMv') is None, 'v23: nothing landed (one sapper shot down, one missed), so no free moves next round')
    page.click('#sum-next'); hand(page)
    # pretend tower 2 was knocked out last wave: it moves free this round; tower 1 still pays
    page.evaluate('() => { window.siegeline.state.freeMv = { all: false, n: [2] }; window.siegeline.refresh(); }')
    xy = lambda c, r: page.evaluate(f'() => window.siegeline.cellToClient({idx(c, r)})')
    def drag_to(a, z):
        (x0, y0), (x1, y1) = xy(*a), xy(*z)
        page.mouse.move(x0, y0); page.mouse.down()
        for k in range(1, 9): page.mouse.move(x0 + (x1 - x0) * k / 8, y0 + (y1 - y0) * k / 8)
        page.mouse.up(); page.wait_for_timeout(60)
    click_cell(page, 13, 3); why = page.inner_text('#te-move'); page.keyboard.press('Escape')
    f0, m0 = S(page, 'S.dFree'), S(page, 'S.totals.moveTries')
    drag_to((13, 3), (13, 1))
    check(S(page, f'S.grid[{idx(13, 1)}] && S.grid[{idx(13, 1)}].n') == 2 and S(page, 'S.dFree') == f0 and S(page, 'S.totals.moveTries') == m0 and S(page, 'S.mvFee') == 0 and why.startswith('Moves free this round: knocked out last wave'),
          f'v23: a tower knocked out last wave moves free, and doesn’t count as a relocation ({why})')
    fee1 = round(0.1 * S(page, f'window.siegeline.towerCost(S.grid[{T1}].cfg)') + 1e-9)
    drag_to((2, 4), (2, 1))
    check(S(page, 'S.dFree') == f0 - fee1 and S(page, 'S.mvFee') == fee1 and S(page, 'S.totals.moveTries') == m0 + 1, f'v23: a tower that wasn’t knocked out still pays its fee ({fee1})')
    info = page.evaluate("() => document.querySelector('#info-sabotage').innerText + document.querySelector('#info-tower').innerText")
    check('light armor' in info and '100% of its price goes to the defender' in info and 'it misses and its coins are spent' in info and '^1.4' in info and 'in proportion to its reach' in info,
          'v23: the rules sheet explains sapper armor, the payout, the missed-on-moved rule and the new tower prices')
    check(not errors, f'v23: no errors {errors[:3]}')
    ctx.close()

    # ---------- v24: sabotage on or off, picked on the mode screen
    ctx = b.new_context(viewport={'width': 1366, 'height': 860}); page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go')
    check(page.get_attribute('#mode-sabo [data-sabo="1"]', 'aria-pressed') == 'true', 'v24: sabotage is on by default')
    page.click('#mode-sabo [data-sabo="0"]')
    up = page.evaluate('() => Math.round((window.siegeline.rules.noSabHp - 1) * 100)')
    check(page.get_attribute('#mode-sabo [data-sabo="0"]', 'aria-pressed') == 'true' and (f'+{up}%' in page.inner_text('#mode-sabov') if up > 0 else True),
          f'v24: Off can be picked, and the row says what units get then ({page.inner_text("#mode-sabov")})')
    page.click('#mode-local'); hand(page); hints_off(page)
    check(S(page, 'S.sabo') is False, 'v24: the match has sabotage off')
    same = page.evaluate('''() => { const sl = window.siegeline, S = sl.state, d = S.designs[1], off = sl.unitCost(d); S.sabo = true; const on = sl.unitCost(d); S.sabo = false; return on === off; }''')
    check(same, 'v24: with sabotage off units cost what they always do')
    page.click('.tool[data-tool=tower]'); click_cell(page, 9, 5); page.keyboard.press('Escape')
    page.click('#def-lock'); hand(page)
    tabs = page.evaluate("() => [...document.querySelectorAll('#atk-steps [data-step]')].map(b => b.textContent)")
    check(tabs == ['1Army', '2Wave'] and 'wave' in page.inner_text('#atk-next').lower(), f'v24: the attacker has two steps, Army and Wave ({tabs}, {page.inner_text("#atk-next")})')
    page.click('.step.plus[data-i="0"]'); page.click('#atk-next'); page.wait_for_timeout(150)
    check(S(page, 'S.step') == 2, 'v24: Next goes from Army straight to Wave')
    hp0 = S(page, 'window.siegeline.US.hp.steps[S.designs[0].hp]'); want = S(page, f'{hp0} * window.siegeline.rules.noSabHp')
    page.click('#atk-lock'); hand(page); advance_until(page, 'S.units.some(u => !u.sap)', 20)
    got = S(page, '(S.units.find(u => !u.sap) || {}).max')
    check(abs(got - want) < 1e-9 and (got > hp0 if up > 0 else got == hp0), f'v24: with sabotage off units march with noSabHp of their health ({hp0} → {got})')
    page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    page.click('#sum-next'); hand(page); page.click('#def-lock'); hand(page)
    click_cell(page, 9, 5); page.wait_for_timeout(80)  # a seen tower, tapped on the Army step
    card = page.inner_text('#atk-ctx').lower() if page.is_visible('#atk-ctx') else ''
    check('send a sapper' not in card and S(page, 'S.charges.size') == 0, f'v24: round 2 with sabotage off: a seen tower offers no sapper ({card[:80]})')
    check(not errors, f'v24: no errors {errors[:3]}')
    ctx.close()

    # ---------- v25: the short How to play and the start screen
    for vw, vh in ((1366, 860), (1280, 720), (390, 844)):
        phone = vw < 600
        ctx = b.new_context(viewport={'width': vw, 'height': vh}, **({'device_scale_factor': 2, 'is_mobile': True, 'has_touch': True} if phone else {}))
        page = ctx.new_page(); errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('file://' + HARNESS); page.wait_for_timeout(400)
        tap = page.tap if phone else page.click
        shown = page.evaluate('() => [...document.querySelectorAll("#info-body > section")].filter(x => x.offsetParent).map(x => x.id)')
        body = page.evaluate('() => { const b = document.querySelector("#info-body"); return [b.scrollHeight, b.clientHeight]; }')
        words = len(page.inner_text('#info-play').split())
        check(shown == ['info-play'] and words < 120, f'v25 {vw}: the opening shows only a short How to play ({shown}, {words} words)')
        check(body[0] <= body[1] + 2, f'v25 {vw}: How to play fits without scrolling ({body})')
        tap('#info-more'); page.wait_for_timeout(150)
        check(page.is_visible('#info-round') and page.is_visible('#info-build'), f'v25 {vw}: All the rules opens the rest of the sheet')
        tap('#info-go'); page.wait_for_timeout(250)
        check(page.is_visible('#ov-mode') and page.is_hidden('#ov-info'), f'v25 {vw}: Start playing leads to the start screen')
        names = page.evaluate('() => [...document.querySelectorAll("#mode-cards .mcard")].map(c => c.querySelector("h2").textContent + " / " + c.querySelector(".msub").textContent)')
        check(names == ['Single player / Versus computer', 'Multiplayer / On this device', 'Online / Against friends'], f'v25 {vw}: the three ways to play, in order ({names})')
        lbls = page.evaluate('() => [...document.querySelectorAll(".st-set .mlbl")].map(x => x.textContent)')
        check(lbls == ['Waves', 'Clock', 'Sabotage'], f'v25 {vw}: the settings above them ({lbls})')
        over = page.evaluate('() => document.documentElement.scrollWidth > innerWidth || document.querySelector("#ov-mode").scrollWidth > innerWidth')
        scrolls = page.evaluate('() => document.querySelector("#mode-cards").classList.contains("scrolls")')
        check(not over, f'v25 {vw}: no sideways page scroll')
        if phone:
            check(scrolls and page.is_visible('#mode-dots'), 'v25 phone: the cards side-scroll with a dot each')
            page.tap('#mode-dots button:nth-child(3)'); page.wait_for_timeout(700)
            r = page.evaluate('() => document.querySelector("#mode-online").getBoundingClientRect().toJSON()')
            check(r['left'] >= 0 and r['right'] <= vw and page.get_attribute('#mode-dots button:nth-child(3)', 'aria-selected') == 'true', f'v25 phone: the third dot brings Online into view ({r["left"]:.0f}–{r["right"]:.0f})')
        else:
            boxes = page.evaluate('() => ["#mode-solo", "#mode-local", "#mode-online"].map(id => document.querySelector(id).getBoundingClientRect().toJSON())')
            check(not scrolls and page.is_hidden('#mode-dots') and all(x['right'] <= vw and x['bottom'] <= vh for x in boxes), f'v25 {vw}: all three side by side, every Play button in view')
        check(page.is_hidden('#mode-fine'), f'v25 {vw}: the Claude-only fine print stays hidden here')
        tap('#mode-help'); page.wait_for_timeout(200)
        check(page.is_visible('#ov-info') and page.inner_text('#info-go').lower() == 'back' and page.evaluate('() => document.querySelector("#ov-info").classList.contains("intro")'), f'v25 {vw}: How to play from the start screen, with Back')
        tap('#info-go'); page.wait_for_timeout(200)
        check(page.is_visible('#ov-mode'), f'v25 {vw}: Back returns to the start screen')
        if not phone:
            page.click('#mode-local'); hand(page); page.click('#btn-info'); page.wait_for_timeout(150)
            check(not page.evaluate('() => document.querySelector("#ov-info").classList.contains("intro")') and page.is_visible('#info-build'), 'v25: “?” in a match opens the whole sheet, at the screen’s section')
        check(not errors, f'v25 {vw}: no errors {errors[:3]}')
        ctx.close()

    # the clock's last 30 seconds: it grows and turns red, and the last 10 count down over the board too
    ctx = b.new_context(viewport={'width': 1366, 'height': 860}); page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); page.evaluate('() => { const r = window.siegeline.rules; r.roughShare = 0; r.rockShare = 0; r.starterPresses = 0; r.planSecsFirst = 33; }')
    page.click('#info-go'); page.click('#mode-local'); page.wait_for_timeout(500); hand(page)
    fs0 = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('#t-clock')).fontSize)")
    check('low' not in (page.get_attribute('#clockbox', 'class') or '') and page.is_hidden('#clockbig'), 'with 33 s left the clock is its usual size')
    page.wait_for_function("() => document.querySelector('#clockbox').classList.contains('low')", timeout=20000); page.wait_for_timeout(500)
    fs1 = page.evaluate("() => parseFloat(getComputedStyle(document.querySelector('#t-clock')).fontSize)")
    check(fs1 >= fs0 * 1.5 and page.is_hidden('#clockbig'), f'at 30 s it grows ({fs0:.0f} → {fs1:.0f} px) and turns red')
    page.wait_for_function("() => !document.querySelector('#clockbig').hidden", timeout=30000)
    check('last' in page.get_attribute('#clockbox', 'class') and page.inner_text('#clockbig-v').startswith('0:'), f'the last 10 seconds also count down over the board ({page.inner_text("#clockbig-v")})')
    check(not errors, f'v21.1 clock: no errors {errors[:3]}')
    ctx.close()
    b.close()

print('\nFAILURES:', len(fails))
for f in fails: print(' -', f)
