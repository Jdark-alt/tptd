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
    check(page.locator('[data-act=tips]').count() == 0 and 'priced by its square' in tt('range').lower(), 'v21: no Tips button; a slider’s hint is in its tooltip (and under “?”)')
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
    check(S(page, 'S.step') == 2 and page.is_visible('#tl .lane'), 'Wave step (3) shows the timeline')
    check(S(page, 'S.designs[0].tl.e') == 0.3, 'default timeline window is 6 seconds')
    # drag the end handle of track 0 to the far right
    hb = page.locator('.lane[data-i="0"] .hdl.e').bounding_box()
    lb = page.locator('.lane[data-i="0"]').bounding_box()
    drag(page, hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2, lb['x'] + lb['width'] - 2, hb['y'] + hb['height'] / 2)
    e0 = S(page, 'S.designs[0].tl.e')
    check(e0 > 0.95, f'dragging the end handle stretches the group ({e0:.2f})')
    # drag one clip of the swarm track to the middle
    page.locator('.lane[data-i="2"]').scroll_into_view_if_needed()  # the wave plan scrolls; a lower track may sit under the nav
    cb = page.locator('.lane[data-i="2"] .clip').nth(0).bounding_box()
    lb2 = page.locator('.lane[data-i="2"]').bounding_box()
    drag(page, cb['x'] + cb['width'] / 2, cb['y'] + cb['height'] / 2, lb2['x'] + lb2['width'] * 0.5, cb['y'] + cb['height'] / 2)  # the spread tracks span 20 s
    pos = S(page, 'S.designs[2].tl.pos')
    check(pos is not None and abs(pos[0] - 0.5) < 0.05, f'dragging a single dot places it ({pos[0] if pos else None})')
    # the whole group: drag the swarm's track (away from its tab and dots) 5 s later; its spread stays
    s0, e0 = S(page, 'S.designs[2].tl.s'), S(page, 'S.designs[2].tl.e')
    y = lb2['y'] + 16  # above the dots, between the knobs
    drag(page, lb2['x'] + lb2['width'] * 0.6, y, lb2['x'] + lb2['width'] * 0.85, y)
    s1, e1 = S(page, 'S.designs[2].tl.s'), S(page, 'S.designs[2].tl.e')
    check(abs((s1 - s0) * 20 - 5) < 0.3 and abs((e1 - s1) - (e0 - s0)) < 1e-9, f'sliding a track moves the whole group, keeping its spread ({s0 * 20:.1f}s → {s1 * 20:.1f}s)')
    drag(page, lb2['x'] + lb2['width'] * 0.6, y, lb2['x'] + lb2['width'] * 0.99, y)
    check(abs(S(page, 'Math.max(...window.siegeline.tlPositions(window.siegeline.state.designs[2]))') - 1) < 1e-9 and toast(page) == 'Must be released by 20 s',
          f'a wave dragged past 20 s stops there ({toast(page)})')
    peak = page.inner_text('#tl-peak')
    page.screenshot(path=f'{OUT}/a1_wave.png')
    page.click('.mini[data-act=rush]')
    check(S(page, 'S.designs.every(d=>d.tl.e<=0.12 && !d.tl.pos)'), 'All at once bunches every track')
    page.click('.mini[data-act=even]')
    check(S(page, 'S.designs.every(d=>d.tl.s===0 && d.tl.e===1)'), 'Even spreads every track')
    page.click('.mini[data-act=rush]')
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
    # step 3: each sapper is a track with one dot
    page.click('#atk-next'); page.wait_for_timeout(300)
    check(S(page, 'S.step') == 2 and page.locator('.lane.sap').count() == 2 and 'reaches target' in page.inner_text('#tl'), 'Wave step: a block for each sapper, with when it reaches its target')
    t0 = S(page, f'S.charges.get({bw}).t')
    page.locator(f'.lane.sap[data-sap="{bw}"]').scroll_into_view_if_needed()
    db = page.locator(f'.lane.sap[data-sap="{bw}"] .clip').bounding_box(); lb = page.locator(f'.lane.sap[data-sap="{bw}"]').bounding_box()
    drag(page, db['x'] + db['width'] / 2, db['y'] + db['height'] / 2, lb['x'] + lb['width'] * 0.25, db['y'] + db['height'] / 2)
    t1 = S(page, f'S.charges.get({bw}).t')
    check(abs(t1 - 0.25) < 0.03 and t1 != t0, f'dragging a sapper’s dot sets when it leaves ({t0:.3f} → {t1:.3f})')
    page.evaluate(f'() => {{ const S = window.siegeline.state; S.charges.get({bw}).t = 0.02; S.charges.get({T95}).t = 0.02; }}')
    page.screenshot(path=f'{OUT}/a3_sapper_tracks.png')
    # the attacker's test run: the planned wave against the defense as seen
    plan = S(page, 'JSON.stringify([S.aFree, [...S.charges], S.designs.map(d => d.count), S.round])')
    check(page.is_visible('#atk-test'), 'the Wave step offers Test from round 2')
    page.click('#atk-test')
    check(page.evaluate('() => window.siegeline.testing') and S(page, 'S.phase') == 'wave' and S(page, 'JSON.stringify(S.grid.map(g => g && g.t))') == S(page, 'JSON.stringify(S.seenGrid.map(g => g && g.t))')
          and S(page, 'S.units.length + S.spawnList.length') > 0, 'Test plays the planned wave, sappers included, against the defense as last seen')
    check(page.is_visible('#pane-wave .speed') and page.get_attribute('#pane-wave .speed [data-speed="5"]', 'aria-pressed') == 'true', 'a test run has 1×, 5×, 10× and starts at 5×')
    page.click('#pane-wave .speed [data-speed="10"]')
    check(page.get_attribute('#pane-wave .speed [data-speed="10"]', 'aria-pressed') == 'true', 'the test speed can be changed')
    page.wait_for_timeout(1200); page.screenshot(path=f'{OUT}/a4_atk_test.png')
    page.click('#test-skip')
    r = page.evaluate('() => window.siegeline.testResult')
    check(not page.evaluate('() => window.siegeline.testing') and S(page, 'S.phase') == 'attack' and S(page, 'S.step') == 2
          and S(page, 'JSON.stringify([S.aFree, [...S.charges], S.designs.map(d => d.count), S.round])') == plan, 'after the test the plan is exactly as it was')
    check(r and r['side'] == 'atk' and r['sappers'] == 2 and page.is_visible('#a-test') and f"Sappers {r['sapOk']}/2 landed" in page.inner_text('#a-test'),
          f'the result card says how many sappers landed ({page.inner_text("#a-test")})')
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
    page.click('#atk-next'); page.click('.mini[data-act=rush]'); page.click('#atk-lock'); hand(page)
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
    page.locator('.lane[data-i="0"]').scroll_into_view_if_needed()
    hb = page.locator('.lane[data-i="0"] .hdl.e').bounding_box(); lb = page.locator('.lane[data-i="0"]').bounding_box()
    cdp = ctx.new_cdp_session(page)
    x0, y0 = hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
    for k in range(1, 9):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (lb['x'] + lb['width'] * 0.9 - x0) * k / 8, 'y': y0}]}); page.wait_for_timeout(20)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    e0 = S(page, 'S.designs[0].tl.e')
    check(e0 > 0.8, f'phone: touch-drag a timeline handle ({e0:.2f})')
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
    check(page.is_visible('.lane.sap') and not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: the sapper’s track fits the Wave step')
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
    # the scrubber and the v20.1 "Spread + Path planner" spec on the Wave step: Runners ×3 and Brutes ×2, no bridge yet
    page.click('#atk-next'); page.wait_for_timeout(250)
    check(page.is_visible('#a-scrub') and page.inner_text('#scrub-lbl') == 'T = 0.0 s' and page.is_hidden('#scrub-br') and page.locator('#tl [data-al]').count() == 0,
          'the Wave step opens the scrubber at T = 0 s, no bridge toggle without a bridge, and auto-align is gone')
    check(page.get_attribute('#scrub-t', 'max') == '60' and all(page.locator(f'.lane[data-i="{i}"]').count() == 1 and page.locator(f'.pth[data-g="d{i}"]').count() == 1 for i in (0, 1)),
          'one master time slider (0–60 s), then a row per design with a spread track and a path slider')
    check(S(page, 'window.siegeline.scrub.view().dots.length') == 0 and page.inner_text('.pth[data-g="d0"]').strip() == '+3' and page.inner_text('.pth[data-g="d1"]').strip() == '+2',
          'at 0 s nothing has set out: each path slider shows its group waiting at the entry')
    paths = lambda: page.evaluate('() => window.siegeline.scrub.paths()')
    pbox = lambda g: page.locator(f'.pth[data-g="{g}"]').bounding_box()
    def px(box, D, L): return box['x'] + 1 + D / L * (box['width'] - 2)  # a route distance on a path slider (inside its 1 px border)
    # spec test 1: the spread track spans the release window, 0-20 s; spreading keeps the front's release time
    lane = page.locator('.lane[data-i="0"]').bounding_box(); y = lane['y'] + 16
    drag(page, lane['x'] + lane['width'] * 0.15, y, lane['x'] + lane['width'] * 0.40, y)
    tl = S(page, 'S.designs[0].tl')
    check(abs(tl['s'] - 0.25) < 0.02 and abs((tl['e'] - tl['s']) - 0.3) < 1e-9, f'sliding a band on its spread track moves its release time, spread kept ({tl["s"] * 20:.1f}–{tl["e"] * 20:.1f}s)')
    s0 = tl['s']; hb = page.locator('.lane[data-i="0"] .hdl.e').bounding_box()
    drag(page, hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2, lane['x'] + lane['width'] * 0.75, hb['y'] + hb['height'] / 2)
    tl = S(page, 'S.designs[0].tl')
    check(tl['s'] == s0 and abs(tl['e'] - 0.75) < 0.02, f'spec test 1: the tab changes the spread and keeps the front’s release time ({s0 * 20:.2f}s → {tl["s"] * 20:.2f}s, the end at {tl["e"] * 20:.1f}s)')
    hb = page.locator('.lane[data-i="0"] .hdl.e').bounding_box()
    drag(page, hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2, lane['x'] + lane['width'] + 60, hb['y'] + hb['height'] / 2)
    tl = S(page, 'S.designs[0].tl'); dots = page.locator('.lane[data-i="0"] .clip'); first, last = dots.nth(0).bounding_box(), dots.nth(2).bounding_box()
    check(tl['s'] == s0 and tl['e'] == 1 and abs(last['x'] + last['width'] / 2 - (lane['x'] + lane['width'] - 1)) < 3 and abs(first['x'] + first['width'] / 2 - (lane['x'] + 1 + (lane['width'] - 2) * s0)) < 3
          and page.inner_text('.tl-ruler').split() == ['0s', '5s', '10s', '15s', '20s'],
          f'spec test 1: the spread track spans 0–20 s, and a spread pulled past 20 s stops there (front {tl["s"] * 20:.1f}s, end {tl["e"] * 20:.1f}s)')
    # spec test 3: with the same spread, the fast group's band is longer on the route than the slow one's
    page.click('.mini[data-act=rush]'); page.wait_for_timeout(150); set_slider(page, '#scrub-t', 5); page.wait_for_timeout(50)
    P = paths(); fast, slow = P['rows']['d0'], P['rows']['d1']
    bf, bs = fast['on'][-1] - fast['on'][0], slow['on'][-1] - slow['on'][0]
    wf, ws = page.locator('.pth[data-g="d0"] .band').bounding_box()['width'], page.locator('.pth[data-g="d1"] .band').bounding_box()['width']
    check(len(fast['on']) == 3 and len(slow['on']) == 2 and bf > bs * 1.5 and wf > ws * 1.5,
          f'spec test 3: with the same spread the Runners’ band is longer than the Brutes’ ({bf:.2f} vs {bs:.2f} cells, {wf:.0f} vs {ws:.0f} px)')
    # spec test 5: every path slider shares one scale: the same route distance sits at the same x on every row
    b0, b1 = pbox('d0'), pbox('d1')
    marks = page.evaluate("() => [...document.querySelectorAll('#tl .pth .mk')].map(m => m.innerHTML)")
    ticks = page.evaluate("() => Object.fromEntries([...document.querySelectorAll('#tl .pth')].map(p => [p.dataset.g, [...p.querySelectorAll('.dyn .tk')].map(t => { const r = t.getBoundingClientRect(); return r.left + r.width / 2; })]))")
    off = max(abs(x - px(pbox(g), D, P['L'])) for g in ('d0', 'd1') for x, D in zip(ticks[g], P['rows'][g]['on']))
    check(abs(b0['x'] - b1['x']) < 0.5 and abs(b0['width'] - b1['width']) < 0.5 and len(set(marks)) == 1 and 'fire' in marks[0] and off < 1.5,
          f'spec test 5: every path slider has the same place, width and tower-range shading, and each unit sits at its route distance on that scale (off by {off:.2f} px)')
    page.screenshot(path=f'{OUT}/v201_rows.png')
    # spec test 2: a path drag at T = 10 s puts the front unit within 0.2 cells of the drop point, its spread unchanged
    set_slider(page, '#scrub-t', 10); page.wait_for_timeout(50)
    P = paths(); f0, L = P['rows']['d0']['front'], P['L']; box = pbox('d0'); y = box['y'] + box['height'] / 2
    tl0 = S(page, 'S.designs[0].tl'); x0 = px(box, f0, L); dx = -box['width'] * 0.2
    drag(page, x0, y, x0 + dx, y); page.wait_for_timeout(150)
    want = f0 + dx / box['width'] * L
    tl1 = S(page, 'S.designs[0].tl'); P1 = paths(); v = page.evaluate('() => window.siegeline.scrub.view()')
    d = next((x for x in v['dots'] if x['g'] == 'd0' and x['k'] == P1['rows']['d0']['frontK']), None)
    wx, wy = page.evaluate(f'() => window.siegeline.scrub.pointAt({want})')
    gap = ((d['x'] - wx) ** 2 + (d['y'] - wy) ** 2) ** 0.5 if d else 9
    check(tl1['s'] > tl0['s'] and abs((tl1['e'] - tl1['s']) - (tl0['e'] - tl0['s'])) < 1e-9 and gap < 0.2 and abs(P1['rows']['d0']['front'] - want) < 0.2,
          f'spec test 2: dragged along its path slider at T = 10 s, the Runners’ front unit is {gap:.3f} cells from the drop point ({f0:.1f} → {want:.1f} of {L:.1f}), spread kept ({(tl1["e"] - tl1["s"]) * 20:.2f}s)')
    check(page.evaluate("() => document.querySelector('.pth[data-g=\"d0\"] .was').classList.contains('go')"),
          'after a path drag the group’s old place fades out on its path slider')
    page.screenshot(path=f'{OUT}/v201_path_drag.png')
    # spec test 4: past 0 s or 20 s the group stops at the limit, and a toast says why
    P = paths(); box = pbox('d0')
    drag(page, px(box, P['rows']['d0']['front'], P['L']), y, box['x'] + box['width'] - 3, y); page.wait_for_timeout(100)
    check(abs(S(page, 'S.designs[0].tl.s')) < 1e-9 and toast(page) == 'Can’t release before 0 s', f'spec test 4: dragged toward the keep, the group stops when its front would leave before 0 s ({toast(page)})')
    page.wait_for_timeout(150); set_slider(page, '#scrub-t', 40); page.wait_for_timeout(50)
    P = paths()
    check(P['rows']['d0']['keep'] == 3 and not P['rows']['d0']['on'] and page.inner_text('.pth[data-g="d0"]').strip() == '×3', f'at 40 s all three Runners stack at the keep end ({P["rows"]["d0"]})')
    drag(page, box['x'] + box['width'] - 4, y, box['x'] + 4, y); page.wait_for_timeout(100)
    check(abs(S(page, 'Math.max(...window.siegeline.tlPositions(window.siegeline.state.designs[0]))') - 1) < 1e-9 and toast(page) == 'Must be released by 20 s',
          f'spec test 4: dragged back from the keep at 40 s, the group stops when its last unit would leave after 20 s ({toast(page)})')
    # dragged to the left end at T: the front releases at T, so the group waits at the entry
    page.wait_for_timeout(150); page.click('.mini[data-act=rush]'); page.wait_for_timeout(150); set_slider(page, '#scrub-t', 6); page.wait_for_timeout(50)
    P = paths(); box = pbox('d0')
    drag(page, px(box, P['rows']['d0']['front'], P['L']), y, box['x'] + 2, y); page.wait_for_timeout(150)
    pos = page.evaluate('() => window.siegeline.tlPositions(window.siegeline.state.designs[0])'); P = paths()
    check(abs(min(pos) * 20 - 6) < 1e-6 and P['rows']['d0']['wait'] == 3 and not P['rows']['d0']['on'], f'dragged to the left end at 6 s, the front releases at 6 s and the group waits at the entry ({min(pos) * 20:.2f}s)')
    # dragged to the right end at T: the front reaches the keep exactly then
    set_slider(page, '#scrub-t', 15); page.wait_for_timeout(50)
    P = paths(); box = pbox('d0')
    drag(page, px(box, P['rows']['d0']['front'], P['L']), y, box['x'] + box['width'] + 30, y); page.wait_for_timeout(150)
    k = paths()['rows']['d0']['frontK']
    set_slider(page, '#scrub-t', 14.8); page.wait_for_timeout(50); A = paths()['rows']['d0']
    set_slider(page, '#scrub-t', 15.2); page.wait_for_timeout(50); B = paths()['rows']['d0']
    check(A['frontK'] == k and A['keep'] == 0 and A['front'] > A['on'][-1] - 1e-9 and A['front'] > paths()['L'] - 1 and B['keep'] >= 1,
          f'dragged to the right end at 15 s, the front reaches the keep then (at 14.8 s it is {A["front"]:.2f} along, at 15.2 s {B["keep"]} at the keep)')
    # spec test 6: dragging on the map does nothing
    set_slider(page, '#scrub-t', 10); page.wait_for_timeout(50)
    v = page.evaluate('() => window.siegeline.scrub.view()'); d = max((x for x in v['dots'] if x['g'] == 'd0'), key=lambda d: d['w'])
    timing = lambda: S(page, 'JSON.stringify([S.designs.map(d => d.tl), [...S.charges].map(([i, c]) => c.t)])')
    t0 = timing()
    drag(page, *page.evaluate(f"() => window.siegeline.worldToClient({d['x'] + d['ox']}, {d['y'] + d['oy']})"), *page.evaluate(f'() => window.siegeline.cellToClient({v["route"][2]})')); page.wait_for_timeout(150)
    check(timing() == t0 and S(page, 'S.phase') == 'attack' and S(page, 'S.step') == 2, 'spec test 6: dragging a unit on the map changes nothing (the map only shows the preview)')
    # play runs the preview at 1×, and moving the slider pauses it
    set_slider(page, '#scrub-t', 2); page.click('#scrub-play'); page.wait_for_timeout(600)
    T = page.evaluate('() => window.siegeline.scrub.T')
    check(page.evaluate('() => window.siegeline.scrub.playing') and 2.3 < T < 3.5, f'Play runs the preview at 1× ({T:.2f}s after 0.6 s)')
    def press(sel):  # a press held a tenth of a second, like a finger: frames go by between down and up
        bx = page.locator(sel).bounding_box(); page.mouse.move(bx['x'] + bx['width'] / 2, bx['y'] + bx['height'] / 2)
        page.mouse.down(); page.wait_for_timeout(100); page.mouse.up(); page.wait_for_timeout(150)
    press('#scrub-play')
    check(not page.evaluate('() => window.siegeline.scrub.playing'), 'the play button pauses on the next press while playing, with nothing in between')
    press('#scrub-play')
    check(page.evaluate('() => window.siegeline.scrub.playing'), 'and plays again on the press after')
    press('#scrub-play')
    set_slider(page, '#scrub-t', 5)
    check(not page.evaluate('() => window.siegeline.scrub.playing') and page.evaluate('() => window.siegeline.scrub.T') == 5, 'moving the slider pauses the preview')
    # spec test 8 (v19): with a bridge planned, Lands changes the route the moment its sapper arrives; Fails never does
    atk_back(page); page.wait_for_timeout(150)
    # without the tower the seen route runs beside the wall at (7,5), so a bridge there is a real shortcut
    page.evaluate(f'() => {{ const S = window.siegeline.state; S.seenGrid[{idx(8, 9)}] = null; S.seenVer++; }}')
    bw = idx(7, 5)
    click_cell(page, 7, 5); page.click('#atk-next'); page.wait_for_timeout(250)
    check(page.is_visible('#scrub-br') and page.get_attribute('#scrub-br [data-lands="1"]', 'aria-pressed') == 'true' and 'plan with bridge' in page.inner_text('#scrub-br').lower(),
          'a planned bridge shows the toggle, Plan with bridge: Lands / Fails, on Lands')
    R = page.evaluate('() => window.siegeline.scrub.routes()'); sp = page.evaluate('() => window.siegeline.scrub.saps()')[0]
    at = lambda T: (set_slider(page, '#scrub-t', T), page.evaluate('() => window.siegeline.scrub.view().route'))[1]
    check(len(R) == 2 and R[1]['by'] == bw and sp['end'] == 'used' and abs(R[1]['t'] - sp['tEnd']) < 1e-9 and R[0]['path'] != R[1]['path']
          and at(round(sp['tEnd'] - 0.15, 1)) == R[0]['path'] and at(round(sp['tEnd'] + 0.15, 1)) == R[1]['path'],
          f'spec test 8: on Lands the route changes when the sapper reaches its tile ({sp["tEnd"]:.2f}s), and the map shows it when the slider passes then {[(r["t"], r["by"], len(r["path"])) for r in R]} {sp} bridge {bw}')
    before, after = (at(round(sp['tEnd'] - 0.15, 1)), paths())[1], (at(round(sp['tEnd'] + 0.15, 1)), paths())[1]
    n_pth = page.locator('#tl .pth').count()
    check(before['cells'] == len(R[0]['path']) and after['cells'] == len(R[1]['path']) and after['L'] < before['L'] and n_pth == 3 and page.locator('#tl .pth .brk').count() == n_pth,
          f'the path sliders follow the route at T: {before["cells"]} cells before the bridge lands, {after["cells"]} after; the planned bridge is marked on every row')
    at(round(sp['t0'] + 1, 1))
    check(page.locator(f'.pth[data-g="s{bw}"] .dyn .tk').count() == 1 and '+' not in page.inner_text(f'.pth[data-g="s{bw}"]'), 'the sapper has a path slider too, with a single tick')
    page.screenshot(path=f'{OUT}/v19_lands.png')
    page.click('#scrub-br [data-lands="0"]'); page.wait_for_timeout(100)
    R = page.evaluate('() => window.siegeline.scrub.routes()'); sp = page.evaluate('() => window.siegeline.scrub.saps()')[0]
    check(len(R) == 1 and sp['tFail'] == sp['t0'] and at(30) == R[0]['path'], 'spec test 8: on Fails the route never changes and the sapper fails at once')
    page.screenshot(path=f'{OUT}/v19_fails.png')
    check(not errors, f'v19 and v20.1: no errors {errors[:3]}')
    ctx.close()
    # the path slider on a phone: drag a group by touch
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); no_terrain(page)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    page.tap('#def-lock'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    for _ in range(3): page.tap('.step.plus[data-i="0"]')
    page.tap('#atk-next'); page.wait_for_timeout(100); page.tap('#atk-next'); page.wait_for_timeout(250)
    set_slider(page, '#scrub-t', 6); page.wait_for_timeout(50)
    P = page.evaluate('() => window.siegeline.scrub.paths()'); page.locator('.pth[data-g="d0"]').scroll_into_view_if_needed(); box = page.locator('.pth[data-g="d0"]').bounding_box()
    x0 = box['x'] + 1 + P['rows']['d0']['front'] / P['L'] * (box['width'] - 2); y0 = box['y'] + box['height'] / 2
    x1 = x0 - box['width'] * 0.15  # back toward the entry: it releases later
    s0 = S(page, 'S.designs[0].tl.s')
    cdp = ctx.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
    for k in range(1, 9): cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * k / 8, 'y': y0}]}); page.wait_for_timeout(20)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); page.wait_for_timeout(150)
    check(S(page, 'S.designs[0].tl.s') > s0 and box['x'] + box['width'] <= 390 and not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'),
          f'phone: a group dragged along its path slider by touch leaves later ({s0 * 20:.2f}s → {S(page, "S.designs[0].tl.s") * 20:.2f}s); the rows fit, no horizontal overflow')
    page.screenshot(path=f'{OUT}/m13_scrub.png')
    check(not errors, f'phone path slider: no errors {errors[:3]}')
    ctx.close()
    # ---------- v20.2 (the "Wave planner layout" spec), on a device that hasn't seen the wave plan's How to use card
    ctx = b.new_context_fresh(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
    page.goto('file://' + HARNESS); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page); hints_off(page)
    for r in range(4, 9): click_cell(page, 7, r)  # a short wall: the route goes round it, 20 cells
    page.click('.tool[data-tool=tower]'); click_cell(page, 1, 10); page.click('#def-ctx [data-act=close]')  # a tower the route never comes near
    page.click('#def-lock'); hand(page)
    for _ in range(2): page.click('.step.plus[data-i="0"]')
    page.click('.step.plus[data-i="1"]')
    page.click('#atk-next'); page.click('#atk-next'); page.wait_for_timeout(250)
    guide = page.inner_text('#ov-guide') if page.is_visible('#ov-guide') else ''
    lines = ['Plan your wave', 'Press play.', 'Watch your units walk the route. Drag the big slider to jump to any moment.', 'Choose WHEN units leave (top track of each group).',
             'Drag the left knob to set when the first unit leaves.', 'Drag the right knob to set when the last unit leaves.', 'Close together = a tight bunch. Far apart = a long line.',
             'Drag the middle to move the whole group earlier or later.', 'Choose WHERE they are (thin strip under it).', 'Stop the big slider at a moment, say 12 s.',
             'Drag the group along the strip to where you want it at 12 s.', 'The game works out when it has to leave.', 'Line them up.', 'Every strip is the same route, left = entry, right = keep.',
             'Put groups at the same spot, or one just behind another.', 'Sappers work the same way.', 'Drag a sapper to where you want it, and it leaves at the right time.',
             'All units must leave between 0 s and 20 s.', 'If a group won’t move further, that’s the limit.', 'Frost and the defender’s changes can still slow you down.']
    check(all(l.lower() in guide.lower() for l in lines) and page.is_visible('#guide-ok') and page.is_visible('#guide-x'), f'spec test 8: the How to use card opens by itself on the first visit, with the spec’s text ({[l for l in lines if l.lower() not in guide.lower()]})')
    page.screenshot(path=f'{OUT}/v202_guide.png')
    page.click('#guide-ok')
    check(page.is_hidden('#ov-guide'), 'Got it closes the card')
    atk_back(page); page.click('#atk-next'); page.wait_for_timeout(150)
    check(page.is_hidden('#ov-guide'), 'spec test 8: back on the Wave step the card stays closed')
    check(page.is_hidden('.wp-help') and page.is_hidden('.wp-hist') and page.is_visible('#tl [data-act=more]'), 'v21: once the card has been seen, How to use and the busiest-second bars sit behind More')
    page.click('#tl [data-act=more]'); page.wait_for_timeout(60)
    check(page.is_visible('.wp-help') and page.is_visible('.wp-hist'), 'More shows them again')
    page.click('.wp-help'); page.wait_for_timeout(100)
    check(page.is_visible('#ov-guide'), 'spec test 8: the How to use button opens it')
    page.mouse.click(20, 20); page.wait_for_timeout(100)
    check(page.is_hidden('#ov-guide'), 'a tap outside the card closes it')
    page.click('.wp-help'); page.click('#guide-x'); page.wait_for_timeout(50)
    check(page.is_hidden('#ov-guide'), 'and so does its ×')
    # the layout: one column, the master panel first, then a block per design (header, spread track, path strip)
    play = lambda: page.evaluate('() => window.siegeline.scrub.playing'); T = lambda: page.evaluate('() => window.siegeline.scrub.T')
    sizes = page.evaluate("() => ['#scrub-lbl', '.wp-title', '.blk-name', '.wp-help', '.wp-pre .mini', '.blk-sub', '.tl-ruler'].map(s => getComputedStyle(document.querySelector(s)).fontSize)")
    biggest = page.evaluate("() => Math.max(...[...document.querySelectorAll('#tl *')].filter(e => e.offsetParent && !e.closest('.wp-title') && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim())).map(e => parseFloat(getComputedStyle(e).fontSize)))")
    order = page.evaluate("() => ['.wp-head', '.wp-master', '.wp-hist', '.wp-pre', '.wp-route', '.blk'].map(s => Math.round(document.querySelector(s).getBoundingClientRect().top))")
    help_box, title_box = page.locator('.wp-help').bounding_box(), page.locator('.wp-title').bounding_box()
    check(sizes == ['11px', '22px', '16px', '11px', '11px', '12px', '11px'] and biggest < 22 and order == sorted(order) and page.inner_text('.wp-title').lower() == 'wave plan'
          and 0 < help_box['x'] - (title_box['x'] + title_box['width']) < 24 and abs(help_box['y'] + help_box['height'] / 2 - (title_box['y'] + title_box['height'] / 2)) < 3,
          f'v20.3: the title is the biggest text (22 px; the next biggest {biggest:.0f}) with How to use beside it; T, buttons and axis 11, names 16, details 12 ({sizes}); top to bottom: title, master panel, histogram, presets, route, blocks')
    play_box, lbl_box, sl_box = page.locator('#scrub-play').bounding_box(), page.locator('#scrub-lbl').bounding_box(), page.locator('#scrub-t').bounding_box()
    mb = page.locator('#a-scrub').bounding_box()
    check(abs(play_box['width'] - 34) < 1 and abs(play_box['height'] - 34) < 1 and page.evaluate("() => getComputedStyle(document.querySelector('#scrub-play')).borderRadius") == '50%'
          and play_box['x'] - mb['x'] < 30 and lbl_box['y'] >= play_box['y'] + play_box['height'] and abs((lbl_box['x'] + lbl_box['width'] / 2) - (play_box['x'] + play_box['width'] / 2)) < 2
          and sl_box['x'] > play_box['x'] + play_box['width'] and abs((sl_box['y'] + sl_box['height'] / 2) - (play_box['y'] + play_box['height'] / 2)) < 2,
          'v20.3: the master panel: a 34 px round play button at its left, T under it, the slider to its right')
    check(page.locator('.wp-rel').count() == 1 and page.get_attribute('.wp-ticks .rel', 'title') == 'Releases end at 20 s' and page.inner_text('.wp-ticks .rel') == '20s'
          and page.inner_text('.wp-ticks').split()[:7] == ['0s', '10s', '20s', '30s', '40s', '50s', '60s'],
          'the master panel: ticks every 10 s to 60 s and a marker at 20 s, where releases end')
    lanes = page.evaluate("() => [...document.querySelectorAll('#tl .lane')].map(l => l.getBoundingClientRect().height)")
    knob = page.evaluate("() => { const h = document.querySelector('#tl .lane .hdl'); const s = getComputedStyle(h, '::before'); return [h.getBoundingClientRect().height, parseFloat(s.height), parseFloat(s.width)]; }")
    dot = page.locator('.lane[data-i="0"] .clip').nth(1).bounding_box()
    check(all(abs(h - 39) < 0.5 for h in lanes) and knob == [17, 17, 7] and abs(dot['width'] - 8) < 0.5,
          f'v20.3: the spread tracks are 70% as tall as before (39 px: {lanes}), their knobs 7 × 17 px ({knob}) and dots 8 px ({dot["width"]:.1f})')
    check('nudge' in (page.get_attribute('#scrub-play', 'class') or '') and page.inner_text('#scrub-nudge') == 'Press play, or drag the dot, to watch your wave move.',
          'until the first touch in a match the play button pulses and the line under the slider says what to do')
    blocks = page.evaluate("() => [...document.querySelectorAll('#tl .blk')].map(b => [...b.children].map(c => c.className.split(' ')[0]))")
    check(blocks == [['blk-head', 'lane', 'tl-ruler', 'pth']] * 2 and page.inner_text('#trk-sub-0') == '×2 · leaves 0.0–6.0 s',
          f'each design is a block: its header (“×2 · leaves 0.0–6.0 s”), its spread track and its path strip under it ({blocks})')
    # spec test 5: every spread track and path strip starts and ends at the same x
    boxes = [page.locator(s).nth(k).bounding_box() for s in ('#tl .lane', '#tl .pth') for k in range(2)]
    check(max(b_['x'] for b_ in boxes) - min(b_['x'] for b_ in boxes) < 0.5 and max(b_['x'] + b_['width'] for b_ in boxes) - min(b_['x'] + b_['width'] for b_ in boxes) < 0.5
          and all(abs(page.locator('#tl .pth').nth(k).bounding_box()['height'] - 16) < 0.5 for k in range(2)),
          'spec test 5: spread tracks and path strips all share the same left and right x; the strips are 16 px tall')
    # spec test 1: play runs T at real speed from where it is, stops at 60 s, and starts again from 0
    page.click('#scrub-play'); page.wait_for_timeout(1000)
    t1 = T()
    check(play() and 0.7 < t1 < 1.6 and 'nudge' not in (page.get_attribute('#scrub-play', 'class') or '') and page.is_hidden('#scrub-nudge'),
          f'spec test 1: on a fresh match, play runs T at real speed ({t1:.2f} s after 1 s); the pulse and the line are gone')
    mh = page.locator('#a-scrub').bounding_box()['height']
    check(mh <= 73, f'v20.3: the master panel is half as tall as v20.2’s (146 px): {mh:.0f} px')
    lane = page.locator('.lane[data-i="0"]').bounding_box(); tnow = page.locator('.lane[data-i="0"] .tnow').bounding_box()
    check(tnow and abs(tnow['x'] - (lane['x'] + 1 + (lane['width'] - 2) * T() / 20)) < 4, 'while T is under 20 s a line on each spread track marks it')
    set_slider(page, '#scrub-t', 58.5); page.click('#scrub-play'); page.wait_for_timeout(2300)
    check(T() == 60 and not play() and page.get_attribute('#scrub-play', 'aria-pressed') == 'false' and page.is_hidden('.lane[data-i="0"] .tnow'),
          f'spec test 1: playback stops at 60 s and shows the play icon (T {T():.1f}); past 20 s the spread tracks’ line is gone')
    page.click('#scrub-play'); page.wait_for_timeout(250)
    check(play() and T() < 1, f'spec test 1: pressed at 60 s, play starts again from 0 s ({T():.2f})')
    # spec test 2: dragging the master slider, a knob, a band or a path strip pauses playback
    def pauses(label, act):
        if not play(): page.click('#scrub-play')
        page.wait_for_timeout(120); was = play(); act(); page.wait_for_timeout(80)
        check(was and not play(), f'spec test 2: {label} pauses playback')
    sb = page.locator('#scrub-t').bounding_box()
    pauses('dragging the master slider', lambda: drag(page, sb['x'] + sb['width'] * 0.2, sb['y'] + sb['height'] / 2, sb['x'] + sb['width'] * 0.3, sb['y'] + sb['height'] / 2))
    hb = page.locator('.lane[data-i="0"] .hdl.s').bounding_box()
    pauses('dragging a knob', lambda: drag(page, hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2, hb['x'] + hb['width'] / 2 + 3, hb['y'] + hb['height'] / 2))
    pauses('dragging a band', lambda: drag(page, lane['x'] + lane['width'] * 0.15, lane['y'] + 16, lane['x'] + lane['width'] * 0.15 + 4, lane['y'] + 16))
    pb = page.locator('.pth[data-g="d0"]').bounding_box()
    pauses('dragging a path strip', lambda: drag(page, pb['x'] + pb['width'] * 0.3, pb['y'] + 8, pb['x'] + pb['width'] * 0.3 + 6, pb['y'] + 8))
    # spec test 3: the space bar plays and pauses; leaving the Wave step pauses, and coming back keeps T
    page.click('.mini[data-act=rush]'); page.wait_for_timeout(100)
    page.focus('#scrub-play'); page.keyboard.press(' '); page.wait_for_timeout(100)
    a = play(); page.keyboard.press(' '); page.wait_for_timeout(100)
    b_ = play(); page.evaluate('() => document.activeElement.blur()'); page.keyboard.press(' '); page.wait_for_timeout(300)
    check(a and not b_ and play(), 'spec test 3: the space bar toggles play and pause (once a press, with the play button focused too)')
    atk_back(page); page.wait_for_timeout(100); left = T()
    check(not play(), 'spec test 3: leaving the Wave step pauses the preview')
    page.click('#atk-next'); page.wait_for_timeout(150)
    check(not play() and abs(T() - left) < 1e-9 and page.inner_text('#scrub-lbl') == f'T = {left:.1f} s', f'coming back keeps the same T ({left:.1f} s)')
    # the play button after editing the army
    atk_back(page); atk_back(page); page.click('.step.plus[data-i="0"]'); page.click('#atk-next'); page.click('#atk-next'); page.wait_for_timeout(150)
    page.click('#scrub-play'); page.wait_for_timeout(200)
    check(play() and page.locator('.lane[data-i="0"] .clip').count() == 3, 'after editing the army the play button still plays')
    page.click('#scrub-play')
    # spec test 4: both knobs on every design's spread track, each moving only its own end
    page.click('.mini[data-act=even]'); page.wait_for_timeout(100)
    knobs = page.evaluate("() => [...document.querySelectorAll('#tl .lane:not(.sap)')].map(l => [l.querySelectorAll('.hdl.s').length, l.querySelectorAll('.hdl.e').length])")
    lane = page.locator('.lane[data-i="1"]').bounding_box()
    tl0 = S(page, 'S.designs[1].tl'); hb = page.locator('.lane[data-i="1"] .hdl.s').bounding_box()
    drag(page, hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2, lane['x'] + lane['width'] * 0.3, hb['y'] + hb['height'] / 2)
    tl1 = S(page, 'S.designs[1].tl'); hb = page.locator('.lane[data-i="1"] .hdl.e').bounding_box()
    drag(page, hb['x'] + hb['width'] / 2, hb['y'] + hb['height'] / 2, lane['x'] + lane['width'] * 0.6, hb['y'] + hb['height'] / 2)
    tl2 = S(page, 'S.designs[1].tl')
    check(knobs == [[1, 1], [1, 1]] and page.is_visible('.lane[data-i="0"] .hdl.s') and abs(tl1['s'] - 0.3) < 0.02 and tl1['e'] == tl0['e'] and abs(tl2['e'] - 0.6) < 0.02 and tl2['s'] == tl1['s'],
          f'spec test 4: both knobs on every spread track; the start knob moves only the first release ({tl0["s"] * 20:.1f} → {tl1["s"] * 20:.1f} s, end kept), the end knob only the last ({tl1["e"] * 20:.1f} → {tl2["e"] * 20:.1f} s)')
    check(page.inner_text('#trk-sub-1') == f'×1 · leaves {(tl2["s"] + tl2["e"]) / 2 * 20:.1f} s', f'a one-unit group’s header gives its one release time ({page.inner_text("#trk-sub-1")})')
    page.screenshot(path=f'{OUT}/v202_round1.png')
    # round 2: the defense seen, a bridge and a knock-out planned
    page.click('#atk-lock'); hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    page.click('#sum-next'); hand(page); page.click('#def-lock'); hand(page)
    sure_sappers(page)
    page.evaluate('() => { const d = window.siegeline.state.designs[0]; d.count = 2; d.tl = { s: 0, e: 10 / 2.3 / 20, pos: null }; }')  # two Runners (2.3 cells/s) leaving 10 cells apart
    page.click('#atk-next'); page.click('#atk-next'); page.wait_for_timeout(250)
    # spec test 6: a group whose front and rear are 10 cells apart on a 20-cell route fills half its path strip
    set_slider(page, '#scrub-t', 7); page.wait_for_timeout(100)
    P = page.evaluate('() => window.siegeline.scrub.paths()'); on = P['rows']['d0']['on']
    band = page.locator('.pth[data-g="d0"] .dyn .band').bounding_box(); pin = page.locator('.pth[data-g="d0"] .pin').bounding_box()
    check(P['cells'] == 20 and abs(P['L'] - 20) < 1e-6 and len(on) == 2 and abs(on[1] - on[0] - 10) < 0.25 and abs(band['width'] / (pin['width'] - 2) - 0.5) < 0.015
          and page.inner_text('#pth-len').lower() == '20 cells',
          f'spec test 6: two Runners 10 cells apart ({on[1] - on[0] if len(on) == 2 else "?"}) on a {P["cells"]}-cell route fill half the strip ({band["width"] / (pin["width"] - 2):.3f})')
    atk_back(page); page.wait_for_timeout(150)
    w = spot(page)
    click_cell(page, *w)
    click_cell(page, 1, 10); page.click('#atk-ctx [data-act=plant]'); page.click('#atk-ctx [data-act=close]')
    page.click('#atk-next'); page.wait_for_timeout(250)
    # spec test 7: sapper blocks: a release knob and a dot; dragging the dot changes the release time; the header says when
    # it reaches its target, or that it won't
    bw = w[1] * COLS + w[0]; ko = idx(1, 10)
    heads = [page.inner_text(f'.blk[data-g="s{c}"] .blk-head') for c in (bw, ko)]
    check(heads[0].startswith('Sapper · Bridge 1') and 'reaches target' in heads[0] and heads[1].startswith('Sapper · Knock-out: Basic') and 'won’t reach target' in heads[1]
          and page.locator(f'.blk[data-g="s{ko}"] .blk-sub .bad').count() == 1,
          f'spec test 7: “Sapper · Bridge 1 … reaches target”, and the knock-out on a tower the route never nears “won’t reach target” in red {heads}')
    t0 = S(page, f'S.charges.get({bw}).t'); sp = [x for x in page.evaluate('() => window.siegeline.scrub.saps()') if x['cell'] == bw][0]
    set_slider(page, '#scrub-t', round(sp['t0'] + 1, 1)); page.wait_for_timeout(100)
    page.locator(f'.blk[data-g="s{bw}"]').scroll_into_view_if_needed()  # the panel scrolls; the strip may sit under the nav
    P = page.evaluate('() => window.siegeline.scrub.paths()'); pb = page.locator(f'.pth[data-g="s{bw}"]').bounding_box()
    x0 = pb['x'] + 1 + P['rows'][f's{bw}']['front'] / P['L'] * (pb['width'] - 2)
    check(page.locator(f'.pth[data-g="s{bw}"] .dyn .tk').count() == 1 and page.locator(f'.pth[data-g="s{bw}"] .brk').count() == 1 and page.locator(f'.lane.sap[data-sap="{bw}"] .clip').count() == 1
          and abs(page.locator(f'.lane.sap[data-sap="{bw}"]').bounding_box()['height'] - 24) < 0.5,
          'a sapper’s block has one release knob on a 24 px track (70% of v20.2’s), and one dot on its strip with a “B” for its bridge')
    drag(page, x0, pb['y'] + 8, x0 - pb['width'] * 0.1, pb['y'] + 8); page.wait_for_timeout(150)
    t1 = S(page, f'S.charges.get({bw}).t'); head = page.inner_text(f'.blk[data-g="s{bw}"] .blk-head')
    check(t1 > t0 and f'leaves {t1 * 20:.1f} s' in head and 'reaches target' in head, f'spec test 7: dragging the sapper’s dot back along the strip makes it leave later ({t0 * 20:.1f} → {t1 * 20:.1f} s): {head}')
    page.screenshot(path=f'{OUT}/v202_sappers.png')
    # the play button after switching the bridge toggle
    page.click('#scrub-br [data-lands="0"]'); page.wait_for_timeout(150); page.click('#scrub-play'); page.wait_for_timeout(200)
    check(play(), 'after switching the bridge toggle the play button still plays')
    page.click('#scrub-play')
    # v20.5: dragging a strip past where its group's recorded walk ends (a sapper used up on the way, or a route at T
    # longer than the walk, over a bridge) froze the page: the search for when a unit gets there never stopped
    def fling(g):
        el = page.locator(f'.pth[data-g="{g}"]'); el.scroll_into_view_if_needed(); bb = el.bounding_box()
        page.mouse.move(bb['x'] + bb['width'] * 0.3, bb['y'] + 8); page.mouse.down()
        for k in range(1, 13): page.mouse.move(bb['x'] + bb['width'] * (0.3 + 0.09 * k), bb['y'] + 8)
        for k in range(1, 13): page.mouse.move(bb['x'] + bb['width'] * (1.3 - 0.11 * k), bb['y'] + 8)
        page.mouse.up(); page.wait_for_timeout(30)
    flung = 0
    for lands in ('1', '0'):
        page.click(f'#scrub-br [data-lands="{lands}"]'); page.wait_for_timeout(80)
        for T in (5, 15, 30, 45):
            set_slider(page, '#scrub-t', T); page.wait_for_timeout(40)
            for g in page.evaluate("() => [...document.querySelectorAll('#tl .pth')].map(e => e.dataset.g)"): fling(g); flung += 1
    times = page.evaluate('() => { const S = window.siegeline.state; return [...S.designs.flatMap(d => [d.tl.s, d.tl.e, ...(d.tl.pos || [])]), ...[...S.charges.values()].map(c => c.t)]; }')
    check(page.evaluate('() => 1 + 1') == 2 and all(0 <= x <= 1 for x in times) and not errors,
          f'v20.5: every strip flung past both ends at 5, 15, 30 and 45 s, with the bridge landing and failing ({flung} drags): the page keeps answering and every release stays within 0–20 s')
    check(not errors, f'v20.2: no errors {errors[:3]}')
    # a new page on the same device: the card doesn't open by itself again
    page.reload(); page.wait_for_timeout(300); no_terrain(page)
    page.click('#info-go'); page.click('#mode-local'); hand(page)
    page.click('#def-lock'); hand(page); page.click('.step.plus[data-i="0"]'); page.click('#atk-next'); page.click('#atk-next'); page.wait_for_timeout(200)
    check(page.is_visible('#a-scrub') and page.is_hidden('#ov-guide'), 'spec test 8: on the same device the card only opens from its button')
    ctx.close()
    # the wave plan on a phone: one column, nothing wider than the screen
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); no_terrain(page)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    page.tap('#def-lock'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    for _ in range(3): page.tap('.step.plus[data-i="0"]')
    page.tap('#atk-next'); page.wait_for_timeout(100); page.tap('#atk-next'); page.wait_for_timeout(250)
    page.tap('#scrub-play'); page.wait_for_timeout(400)
    wide = page.evaluate("() => Math.max(...[...document.querySelectorAll('#tl *')].map(e => e.getBoundingClientRect().right))")
    tb = page.locator('#scrub-t').bounding_box()
    check(page.evaluate('() => window.siegeline.scrub.playing') and wide <= 390 and tb['height'] >= 44 and not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'),
          f'phone: the wave plan is one column within 390 px ({wide:.0f}), the slider’s touch area is 44 px, and the play button plays')
    page.screenshot(path=f'{OUT}/m14_waveplan.png')
    check(not errors, f'phone wave plan: no errors {errors[:3]}')
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
    page.evaluate('() => { window.siegeline.rules.planSecs = 180; }')
    page.click('#info-go'); page.click('#mode-local')
    check(page.is_hidden('#t-clock'), 'the clock waits behind the handoff screen')
    hand(page)
    check(page.is_visible('#t-clock') and page.inner_text('#t-clock') in ('5:00', '4:59'), f'v21: the defender gets 5:00 in the first round ({page.inner_text("#t-clock")})')
    page.click('#def-lock'); hand(page)
    check(page.is_visible('#t-clock') and page.inner_text('#t-clock') in ('5:00', '4:59'), f'v21: so does the attacker ({page.inner_text("#t-clock")})')
    page.click('#atk-lock'); page.click('#atk-lock'); hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(60)
    page.click('#sum-next'); hand(page)
    check(page.is_visible('#t-clock') and page.inner_text('#t-clock') in ('3:00', '2:59'), f'v21: from round 2 it is 3:00 ({page.inner_text("#t-clock")})')
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
    page.click('#atk-test'); page.wait_for_timeout(50)
    p0 = S(page, 'S.path')
    check(page.evaluate('() => window.siegeline.testing') and idx(4, 3) in p0, 'test run: units head for the far gap')
    landed = advance_until(page, f'S.grid[{KO}].off > 0')
    p1 = S(page, 'S.path')
    check(landed and p1 == p0 and idx(4, 6) not in p1, f'the knock-out lands mid-wave and the route stays as it was ({len(p0)} → {len(p1)} cells)')
    page.evaluate('() => window.siegeline.advance(30)')
    check(S(page, 'S.path') == p0, 'and it stays so for the rest of the wave')
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
    check(page.is_visible('#atk-test') and S(page, 'window.siegeline.scrub.view() && window.siegeline.scrub.view().route.length') == len(S(page, 'S.seenGrid.map(()=>0)')) * 0 + S(page, '(window.siegeline.seenRoute() || []).length'),
          'the attacker’s Test and the wave preview work in round 1, against the starter maze')
    page.click('#atk-test'); page.wait_for_timeout(100)
    check(page.evaluate('() => window.siegeline.testing') and page.evaluate('() => window.siegeline.tag') == 'TEST · STARTER MAZE', 'the attacker’s round-1 Test plays on the starter maze')
    page.click('#test-skip')
    check(page.is_visible('#a-test') and 'through' in page.inner_text('#a-test'), f'and reports ({page.inner_text("#a-test")})')
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
    check(page.inner_text('#sb-you') == f'+{L["dGain"]}' and page.inner_text('#sb-opp') == f'+{L["aGain"]}', 'summary: You (the defender, whose turn comes next) and Opponent, with their pot coins')
    check(page.is_hidden('#ov-sum .det') and page.is_visible('#ov-sum [data-act=details]'), 'summary: the details are under Details, closed')
    grp = page.inner_text('#mvp-group') if page.is_visible('#mvp-group') else ''
    check(not dealt and page.is_hidden('#mvp-tower') and 'Runner ×6' in grp and '100% of keep damage' in grp, f'summary: no tower, so no MVP tower; the MVP group is the one that did the keep damage ({grp})')
    page.click('#sum-next')
    check(page.inner_text('#hand-nums') == f'Keep −{L["Y"]:.0f} · Defender +{L["dGain"]} · Attacker +{L["aGain"]}'.replace(f'{L["Y"]:.0f}', page.evaluate(f'() => {{ const x = {L["Y"]}; return x >= 10 ? String(Math.round(x)) : String(Math.round(x * 10) / 10); }}')),
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
    check(res == 'splash+frost+shock' and costs == ['35 each', '46 each', '59 each', '87 each'], f'a design takes several resists, each ×1.3 on the price (the big-unit surcharge past 60): {res} {costs}')
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
