"""Pass-and-play suite: building, tuning, pricing, sappers (bridges and knock-outs), the timeline, test runs, win/loss,
   phone layout, and terrain (rough ground and rock). The fixed scenarios switch terrain off; the terrain checks come last.
   python tools/tests/test_local.py   (screenshots land in tools/.build/shots/local)"""
import os, sys, json, subprocess
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
    page.evaluate(f"""() => {{ const i = document.querySelector('{sel}'); i.value = {v}; i.dispatchEvent(new Event('input', {{bubbles:true}})); }}""")
def no_terrain(page):
    """The fixed scenarios click known cells, so their matches start without rough ground or rock."""
    page.evaluate('() => { const R = window.siegeline.rules; R.roughShare = 0; R.rockShare = 0; }')
def sure_sappers(page):
    """The fixed scenarios check what sappers do on arrival, so theirs get top health and always arrive."""
    page.evaluate('() => { window.siegeline.rules.sapper.hp = 9; }')
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
    check(S(page, 'S.phase') == 'defend' and S(page, 'S.step') == 0 and ''.join(page.inner_text('#def-steps').lower().split()).startswith('1build2ready'), 'defender starts on the Build step (Build, Ready)')
    check(page.get_attribute('#def-steps [data-act=hints]', 'aria-pressed') == 'true' and page.is_visible('#def-steps [data-act=hints]'), 'Hints switch beside the build tabs, on by default')
    hints_off(page)
    check(S(page, 'S.terrain.every(v => !v) && S.grid.every(g => !g)'), 'terrain shares at 0: a map without rough ground or rock')
    tops = page.evaluate("() => [...document.querySelectorAll('#def-body .tools.bar .tool')].map(b => b.dataset.tool + ':' + Math.round(b.getBoundingClientRect().top))")
    check([t.split(':')[0] for t in tops] == ['wall', 'tower', 'remove', 'shape'] and len({t.split(':')[1] for t in tops}) == 1, f'one toolbar: Wall, Tower, Remove, Shapes in a row {tops}')
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
    check(page.inner_text('#d-tprice') == '40', 'first tower costs 40')
    click_cell(page, 9, 5)
    check(S(page, f'S.grid[{idx(9,5)}].fee') == 0 and page.is_visible('#te-price'), 'first tower: no fee, editor opens')
    # v19 (spec test 1): a Basic tower still costs 40, and at the 100% accuracy step 64; the labels give the per-shot chance
    check(page.inner_text('#te-price') == '40' and page.inner_text('#te-accuracy-v') == '80% · 80% per shot at this fire rate'
          and page.inner_text('#te-rate-v') == '1 per second · 18 per hit · 80% accurate', f'a Basic tower costs 40 at 80% accuracy ({page.inner_text("#te-accuracy-v")} / {page.inner_text("#te-rate-v")})')
    set_slider(page, '#te-accuracy', 3)
    check(page.inner_text('#te-price') == '64' and page.inner_text('#te-accuracy-v') == '100% · 100% per shot at this fire rate', f'the 100% accuracy step on a Basic tower costs 64 ({page.inner_text("#te-price")})')
    set_slider(page, '#te-rate', 1)
    check(page.inner_text('#te-accuracy-v') == '100% · 95% per shot at this fire rate' and page.inner_text('#te-rate-v') == '2.5 per second · 7.2 per hit · 95% accurate',
          f'fire rate shifts the per-shot accuracy ({page.inner_text("#te-accuracy-v")} / {page.inner_text("#te-rate-v")})')
    set_slider(page, '#te-accuracy', 1)
    check(page.inner_text('#te-accuracy-v') == '87% · 82% per shot at this fire rate', f'the spec’s example label: 87% · 82% per shot at 2.5/s ({page.inner_text("#te-accuracy-v")})')
    set_slider(page, '#te-accuracy', 0); set_slider(page, '#te-rate', 3)
    up = page.evaluate(f'() => {{ const sl = window.siegeline, c = sl.state.grid[{idx(9,5)}].cfg; return sl.towerCost({{...c, dps: c.dps + 1}}) - sl.towerCost(c); }}')
    check(page.inner_text('#te-dps-n') == f'+{up}' and 'poor' not in page.get_attribute('#te-dps-n', 'class'), f'slider shows what the next step costs ({page.inner_text("#te-dps-n")})')
    check(page.is_hidden('#te-rate-n'), 'free slider shows no step price')
    fr = S(page, 'S.dFree')
    page.evaluate('() => { window.siegeline.state.dFree = 5; }'); page.click('[data-act=tips]')
    check('poor' in page.get_attribute('#te-dps-n', 'class') and 'poor' in page.get_attribute('#te-poison-n', 'class'), 'step price turns red when unaffordable')
    page.evaluate(f'() => {{ window.siegeline.state.dFree = {fr}; }}'); page.click('[data-act=tips]')
    set_slider(page, '#te-splash', 3)
    check(page.inner_text('#te-splash-n') == 'Max', 'top of a slider shows Max')
    set_slider(page, '#te-splash', 0)
    set_slider(page, '#te-range', 5); r_only = int(page.inner_text('#te-price'))
    set_slider(page, '#te-range', 2); set_slider(page, '#te-dps', 5); d_only = int(page.inner_text('#te-price'))
    set_slider(page, '#te-range', 5); both = int(page.inner_text('#te-price'))
    check(both - 40 > (r_only - 40) + (d_only - 40), f'stacked upgrades cost more ({both-40} > {r_only-40}+{d_only-40})')
    page.click('[data-act=tips]')
    check(page.is_visible('#def-ctx .shint'), 'Tips toggle reveals slider hints')
    page.click('[data-act=tips]')
    check(not page.is_visible('#def-ctx .shint'), 'hints hidden by default')
    set_slider(page, '#te-range', 2); set_slider(page, '#te-dps', 2)
    page.screenshot(path=f'{OUT}/d1_editor.png')
    page.click('[data-act=close]')
    check(page.inner_text('#d-tprice') == '50', 'second tower costs 40 + 10 fee')
    click_cell(page, 13, 5); page.click('[data-act=close]')
    check(page.inner_text('#d-tprice') == '60', 'third tower costs 40 + 20 fee')
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
    check(page.is_visible('#d-tlist .irow'), 'tower list shows towers')
    page.screenshot(path=f'{OUT}/d2_towers.png')
    page.click('#def-next')
    check(S(page, 'S.step') == 1 and page.is_visible('#d-sum'), 'Ready step shows summary')
    check(page.is_hidden('#def-test'), 'no Test in round 1: there is no last wave yet')
    page.screenshot(path=f'{OUT}/d3_ready.png')
    page.click('#def-next'); hand(page)
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
    check(page.locator('#ue-dodge').count() == 0 and 'dodge' not in page.inner_text('#atk-ctx').lower(), 'the designer has no Dodge slider')
    enc = page.evaluate('() => window.siegeline.encodeArmy(window.siegeline.state.designs)')
    check(all(len(a) == 11 for a in enc) and S(page, 'S.designs.every(d => !("dodge" in d))'), f'an encoded army has no dodge slot (11 fields: {enc[0]})')
    page.click('.pre[data-pre=Ghost]')
    check(S(page, '[S.designs[1].hp, S.designs[1].speed, S.designs[1].armor, S.designs[1].regen, S.designs[1].resist].join()') == '2,5,0,0,none' and page.inner_text('#ue-price') == '16',
          f'the Ghost preset is Health 112, Speed 1.9 and nothing else, at 16 ({page.inner_text("#ue-price")})')
    page.click('.pre[data-pre=Brute]')
    up = page.evaluate('() => { const sl = window.siegeline, d = sl.state.designs[1]; return (sl.unitCost({...d, hp: d.hp + 1}) - sl.unitCost(d)) * d.count; }')
    check(page.inner_text('#ue-hp-n') == f'+{up}', f'unit slider prices the next step for every unit of the design ({page.inner_text("#ue-hp-n")})')
    page.click('#atk-ctx [data-act=close]')
    page.screenshot(path=f'{OUT}/a0_army.png')
    page.click('#atk-next')
    check(S(page, 'S.step') == 1 and 'sabotage' in page.inner_text('#atk-steps [aria-current=step]').lower() and 'locked' in page.get_attribute('#a-chg-note', 'class'),
          'Sabotage is step 2, before the wave, and locked in round 1')
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
    cb = page.locator('.lane[data-i="2"] .clip').nth(0).bounding_box()
    lb2 = page.locator('.lane[data-i="2"]').bounding_box()
    drag(page, cb['x'] + cb['width'] / 2, cb['y'] + cb['height'] / 2, lb2['x'] + lb2['width'] * 0.5 / 3, cb['y'] + cb['height'] / 2)  # the tracks show 60 s; 10 s is a sixth
    pos = S(page, 'S.designs[2].tl.pos')
    check(pos is not None and abs(pos[0] - 0.5) < 0.05, f'dragging a single dot places it ({pos[0] if pos else None})')
    # the whole wave: drag the swarm's track (away from its tabs and dots) 5 s later; its spread stays
    s0, e0 = S(page, 'S.designs[2].tl.s'), S(page, 'S.designs[2].tl.e')
    y = lb2['y'] + lb2['height'] - 4
    drag(page, lb2['x'] + lb2['width'] * 0.8, y, lb2['x'] + lb2['width'] * (0.8 + 5 / 60), y)
    s1, e1 = S(page, 'S.designs[2].tl.s'), S(page, 'S.designs[2].tl.e')
    check(abs((s1 - s0) * 20 - 5) < 0.3 and abs((e1 - s1) - (e0 - s0)) < 1e-9, f'dragging a track moves the whole wave, keeping its spread ({s0 * 20:.1f}s → {s1 * 20:.1f}s)')
    drag(page, lb2['x'] + lb2['width'] * 0.8, y, lb2['x'] + lb2['width'] * 0.99, y)
    check(abs(S(page, 'Math.max(...window.siegeline.tlPositions(window.siegeline.state.designs[2]))') - 1) < 1e-9 and toast(page) == 'Must be released by 20 s',
          f'a wave dragged past 20 s stops there ({toast(page)})')
    peak = page.inner_text('#tl-peak')
    page.screenshot(path=f'{OUT}/a1_wave.png')
    page.click('.mini[data-act=rush]')
    check(S(page, 'S.designs.every(d=>d.tl.e<=0.12 && !d.tl.pos)'), 'All at once bunches every track')
    page.click('.mini[data-act=even]')
    check(S(page, 'S.designs.every(d=>d.tl.s===0 && d.tl.e===1)'), 'Even spreads every track')
    page.click('.mini[data-act=rush]')
    page.click('#atk-next')
    check(page.is_visible('#a-sum') and page.inner_text('#atk-next').lower() == 'ready', 'Ready step')
    army = S(page, 'S.designs.reduce((v,d)=>v+d.count*window.siegeline.unitCost(d),0)')
    page.click('#atk-next'); hand(page)
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
    page.click('#def-next'); page.click('#def-next'); hand(page)
    page.evaluate('() => { window.siegeline.state.aFree = 500; }'); sure_sappers(page)
    page.click('#atk-next')
    page.wait_for_timeout(300)
    check(S(page, 'S.step') == 1 and 'locked' not in page.get_attribute('#a-chg-note', 'class'), 'Sabotage open in round 2')
    check(page.is_visible('[data-sabo=bridge]') and page.is_visible('[data-sabo=tower]') and 'pick one' in page.inner_text('#a-chg-note').lower(),
          'Sabotage shows two options: bridge a wall, knock out a tower')
    check('sapper' in page.inner_text('#a-sabo-lead').lower() and '25% more' in page.inner_text('#a-sabo-lead'), f'the lead says sappers carry it and each attempt costs 25% more ({page.inner_text("#a-sabo-lead")})')
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
    cap_l = page.inner_text('#a-cap').lower()
    check(page.is_visible('#a-cap') and (f'knock-out cap: {v95} of {int(cap)}' in cap_l or 'cap reached' in cap_l) and f'{p95} coins' in cap_l
          and S(page, 'parseFloat(document.querySelector("#a-cap .fill").style.width)') > 0, f'the cap bar under the knock-out card fills with the target and shows its coins ({cap_l})')
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
    check('One bridge per wave.' in page.inner_text('#a-sabo-bridge') and 'off' in page.get_attribute('[data-sabo=bridge]', 'class'), 'with one planned the bridge card greys out: One bridge per wave.')
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
    check(S(page, 'S.step') == 2 and page.locator('.lane.sap').count() == 2 and 'there ~' in page.inner_text('#tl'), 'Wave step: a track for each sapper, with when it gets there')
    t0 = S(page, f'S.charges.get({bw}).t')
    db = page.locator(f'.lane.sap[data-sap="{bw}"] .clip').bounding_box(); lb = page.locator(f'.lane.sap[data-sap="{bw}"]').bounding_box()
    drag(page, db['x'] + db['width'] / 2, db['y'] + db['height'] / 2, lb['x'] + lb['width'] * 0.25 / 3, db['y'] + db['height'] / 2)
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
    page.click('#atk-next')
    page.click('#atk-next'); hand(page)
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
    check(L2['bridges'] == 1 and L2['sapOk'] == 2 and L2['sappers'] == 2 and 'bridged' in page.inner_text('#ov-sum').lower() and 'Sappers landed' in page.inner_text('#ov-sum'),
          'summary counts the bridge and the sappers that landed')
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
    check('bridge' in page.inner_text('#def-body').lower(), 'the build step explains the bridge')
    page.screenshot(path=f'{OUT}/d3_bridge.png')
    W2 = spot(page, 7); w2 = idx(*W2)  # a wall beside the route the attacker saw
    page.click('.tool[data-tool=remove]'); click_cell(page, *W2)
    check(S(page, f'S.grid[{w2}]') is None, 'defender takes down a wall the attacker saw')
    page.click('.tool[data-tool=tower]'); click_cell(page, T95 % COLS, T95 // COLS)
    check(page.is_visible('#te-price'), 'the knocked-out tower is back: it can be retuned')
    page.click('#def-ctx [data-act=close]')
    page.click('#def-next')
    page.click('#def-body [data-act=replay]')
    check(page.evaluate('() => window.siegeline.replaying') and S(page, 'S.round') == 2, 'Ready step replays the last wave while planning')
    page.keyboard.press('Escape')
    check(S(page, 'S.phase') == 'defend' and S(page, 'S.step') == 1 and S(page, 'S.round') == 3, 'Escape closes the replay back to planning')
    page.click('#def-next'); hand(page)
    page.click('#atk-next'); page.wait_for_timeout(300)
    a0 = S(page, 'S.aFree'); click_cell(page, *W2)
    check(S(page, 'S.totals.bridgeTries') == 1 and S(page, 'S.totals.koTries') == 1 and S(page, f'S.charges.get({w2}).cost') == 31 and S(page, 'S.aFree') == a0 - 31,
          'one bridge and one knock-out sent so far: this bridge costs 25 × (1 + 0.25) = 31')
    at2 = S(page, f'S.charges.get({w2}).at')
    on_route = S(page, f'S.path.includes({at2})')  # the defender's real route, after taking the wall down
    page.click('#atk-next'); page.click('#atk-next'); page.click('#atk-next')
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
    page.click('#def-next'); page.click('#def-next'); hand(page)
    page.evaluate('() => { const S = window.siegeline.state; S.aFree = 3000; }')
    for _ in range(15): page.click('.step.plus[data-i="0"]')
    page.click('#atk-next'); page.wait_for_timeout(300)
    a0 = S(page, 'S.aFree'); click_cell(page, *W3)
    check(S(page, f'S.charges.get({w3}).cost') == 38 and S(page, 'S.aFree') == a0 - 38, 'the third bridge costs 25 × (1 + 2 × 0.25) = 38')
    page.click('#atk-next'); page.click('.mini[data-act=rush]'); page.click('#atk-next'); page.click('#atk-next'); hand(page)
    check(advance_until(page, f'S.sapList[0].state !== "go" && S.sapList[0].state !== "wait"'), 'the sapper gets to the end of its job')
    check(S(page, f'S.grid[{w3}].t') == 'tower' and not S(page, f'S.bridges.has({w3})') and S(page, 'S.wave.missed + S.wave.sapMissed') >= 1, 'a bridge on a wall that became a tower misses')
    page.evaluate('() => window.siegeline.advance(120)'); page.wait_for_timeout(2000)
    check(S(page, 'S.winner') == 'attacker' and page.is_visible('#ov-end'), 'attacker wins when the keep falls')
    page.click('#end-again')
    check(S(page, 'S.round') == 1 and S(page, 'S.keep') == 1000 and S(page, 'S.grid.every(g=>!g)') and S(page, 'S.charges.size') == 0 and S(page, 'S.bridges.size') == 0, 'rematch resets, bridges too')
    # defender win
    for rnd in range(1, 9):
        hand(page); page.click('#def-next'); page.click('#def-next'); hand(page)
        page.click('#atk-next')
        if rnd == 8:
            page.wait_for_timeout(150)
            check('locked' in page.get_attribute('#a-chg-note', 'class') and 'final wave' in page.inner_text('#a-chg-note'), 'no sabotage in the final wave')
        page.click('#atk-next'); page.click('#atk-next')
        page.click('#atk-next')
        if rnd == 1: check('nothing' in page.inner_text('#atk-next').lower(), 'empty army needs confirm')
        page.click('#atk-next'); hand(page)
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
    page.tap('#def-ctx [data-act=close]')
    page.tap('#def-next'); page.wait_for_timeout(100); page.tap('#def-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    for _ in range(4): page.tap('.step.plus[data-i="0"]')
    for _ in range(6): page.tap('.step.plus[data-i="2"]')
    page.screenshot(path=f'{OUT}/m2_army.png')
    page.tap('#atk-next'); page.wait_for_timeout(100); page.tap('#atk-next'); page.wait_for_timeout(200)
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
    page.tap('#atk-next'); page.wait_for_timeout(100)
    page.screenshot(path=f'{OUT}/m4_ready.png')
    page.tap('#atk-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(2500)
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
    page.tap('#def-next'); page.wait_for_timeout(100); page.tap('#def-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    sure_sappers(page)
    page.tap('#atk-next'); page.wait_for_timeout(300)
    check(page.evaluate(f'() => window.siegeline.canBridgeAt({idx(4,4)})'), 'phone: the wall at (4,4) sits beside the route')
    tap_cell(4, 4)
    check(S(page, f'S.charges.has({idx(4,4)}) && S.charges.get({idx(4,4)}).kind') == 'bridge', 'phone: tapping a seen wall plans a bridge')
    page.screenshot(path=f'{OUT}/m7_bridge_planned.png')
    page.tap('#atk-next'); page.wait_for_timeout(300)
    check(page.is_visible('.lane.sap') and not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: the sapper’s track fits the Wave step')
    page.screenshot(path=f'{OUT}/m7b_sapper_track.png')
    page.tap('#atk-next'); page.wait_for_timeout(100); page.tap('#atk-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(1200)
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
    page.click('#def-next'); page.click('#def-next'); hand(page)
    for _ in range(8): page.click('.step.plus[data-i="0"]')
    for _ in range(4): page.click('#atk-next')
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
    page.goto('file://' + HARNESS); page.wait_for_timeout(400)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(300)
    tops = page.evaluate("() => [...document.querySelectorAll('#def-body .tools.bar .tool')].map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.top), Math.round(r.right)]; })")
    check(len({t for t, _ in tops}) == 1 and max(r for _, r in tops) <= 390 - 16, f'phone: the four tools fit one row {tops}')
    v0 = page.evaluate('() => [window.siegeline.view.rot, window.siegeline.view.cs]')
    page.tap('.tool[data-tool=shape]'); page.wait_for_timeout(200)
    v1 = page.evaluate('() => [window.siegeline.view.rot, window.siegeline.view.cs]')
    check(v0[0] and v1[0] and v1[1] >= 20, f'phone: the board stays turned with Shapes open, cells {v0[1]} → {v1[1]} px (a 5×5 ghost is {5 * v1[1]} px)')
    x, y = page.evaluate(f'() => window.siegeline.cellToClient({idx(12, 2)})'); page.touchscreen.tap(x, y); page.wait_for_timeout(100)
    g0 = S(page, 'S.grid.filter(Boolean).length'); page.touchscreen.tap(x, y); page.wait_for_timeout(100)
    check(S(page, 'S.grid.filter(Boolean).length') > g0, 'phone: tap shows the ghost, a second tap on it places the shape')
    page.screenshot(path=f'{OUT}/m11_shapes.png')
    page.tap('#def-next'); page.wait_for_timeout(100); page.tap('#def-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    for _ in range(6): page.tap('.step.plus[data-i="0"]')
    for _ in range(4): page.tap('#atk-next'); page.wait_for_timeout(60)
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
    page.click('#def-next'); page.click('#def-next'); hand(page)
    for _ in range(3): page.click('.step.plus[data-i="0"]')
    for _ in range(3): page.click('.step.plus[data-i="1"]')
    # a hand-made defense as if seen last wave: a Sniper, a Mid and a Big tower (with fees, which sabotage ignores) beside a wall
    seen = f'''([towers, tries]) => {{ const S = window.siegeline.state, T = (cfg, fee) => ({{ t: 'tower', cfg: {{ range: 2, dps: 2, rate: 3, splash: 0, slow: false, poison: false, chain: false, ...cfg }}, fee, off: 0, n: 1, fresh: false, cd: 0, ang: 0, kick: 0, dealt: 0 }});
      S.seenGrid = S.seenGrid.map(() => null); for (const [i, cfg, fee] of towers) S.seenGrid[i] = T(cfg, fee);
      for (let r = 0; r < 10; r++) S.seenGrid[r * 16 + 7] = {{ t: 'wall', fresh: false }};
      S.seenVer++; S.seenRound = 1; Object.assign(S.totals, tries); S.aFree = 2000; }}'''
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
    check('139 coins' in page.inner_text('#a-cap').lower() and 'cap reached' in page.inner_text('#a-cap').lower(),
          f'with the Big tower too dear to fit, the cap is reached; the bar shows this round’s knock-out coins ({page.inner_text("#a-cap")})')
    click_cell(page, BG % COLS, BG // COLS); page.wait_for_timeout(60)
    check(f'over the cap by {int(over + 0.999)}' in page.inner_text('#a-cap-card').lower(), f'the cap counts slider prices, not fees: the Big tower is over by {over:.0f} ({page.inner_text("#a-cap-card")})')
    page.click('#atk-ctx [data-act=close]')
    check(page.inner_text('#a-sabo-bridge').startswith('25 coins'), f'knock-outs don’t raise the bridge price: separate counters ({page.inner_text("#a-sabo-bridge")})')
    page.screenshot(path=f'{OUT}/v18_cap.png')
    # three knock-outs sent before: the next bridge still costs 25, the next knock-out on a Basic tower 23 × 1.75
    page.click(f'[data-rm="{SN}"]'); page.click(f'[data-rm="{MI}"]')
    page.evaluate(seen, [[[idx(4, 3), {}, 0], [idx(4, 7), {}, 10]], {'bridgeTries': 0, 'koTries': 3}])
    page.click('#atk-back'); page.click('#atk-next'); page.wait_for_timeout(200)
    check(page.inner_text('#a-sabo-bridge').startswith('25 coins') and page.inner_text('#a-sabo-tower').startswith('40 coins'),
          f'three knock-outs sent: the next bridge still costs 25, a Basic knock-out 40 ({page.inner_text("#a-sabo-bridge")} / {page.inner_text("#a-sabo-tower")})')
    # one tower always fits, even past the cap; after it nothing else can be added
    page.evaluate(seen, [[[BG, PRESETS['big'], 0], [SN, {}, 0]], {'bridgeTries': 0, 'koTries': 0}])
    page.click('#atk-back'); page.click('#atk-next'); page.wait_for_timeout(200)
    plant(BG)
    check(S(page, f'S.charges.has({BG})') and 'one tower always fits' in page.inner_text('#a-cap').lower() and S(page, 'document.querySelector("#a-cap .fill").style.width') == '100%',
          f'a first target worth more than the cap still fits, and the bar says so ({page.inner_text("#a-cap")})')
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
    page.click('#d-tune [data-act=tune]')
    cfg1, f1 = S(page, 'S.grid.map(g => g && g.t === "tower" ? { ...g.cfg } : null)'), S(page, 'S.dFree')
    nolower = all(c0 is None or all(c1[k] >= c0[k] for k in ('range', 'dps', 'accuracy', 'splash')) and c1['rate'] == c0['rate'] and all(c1[k] or not c0[k] for k in ('slow', 'poison', 'chain')) for c0, c1 in zip(cfg0, cfg1))
    check(nolower and cfg1 != cfg0 and f1 < f0 and S(page, 'S.grid.filter(Boolean).length') == n0, f'auto-tune spends coins on upgrades, never lowers a slider or changes fire rate, adds nothing ({f0} → {f1})')
    check(f'spent {f0 - f1} coins' in page.inner_text('#d-tune').lower() and f'{f1} left' in page.inner_text('#d-tune').lower(), f'auto-tune says what it spent ({page.inner_text("#d-tune")})')
    page.screenshot(path=f'{OUT}/v18_tune.png')
    page.click('#d-tune [data-act=tune-undo]')
    check(S(page, 'S.grid.map(g => g && g.t === "tower" ? { ...g.cfg } : null)') == cfg0 and S(page, 'S.dFree') == f0, 'auto-tune: Undo restores every tower and the coins')
    check(not errors, f'v18 auto-tune: no errors {errors[:3]}')
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
    page.click('#def-next'); page.click('#def-next'); hand(page)
    for _ in range(3): page.click('.step.plus[data-i="0"]')
    for _ in range(4): page.click('#atk-next')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    check(S(page, 'S.last.misses') > 0 and S(page, 'S.phase') == 'summary', f'towers at 80% miss some shots in a real wave ({S(page, "S.last.misses")} missed)')
    page.click('#sum-next'); hand(page); page.click('#def-next'); page.click('#def-next'); hand(page)
    # the attacker's card for a seen tower: Accuracy and Expected damage rows
    page.click('#atk-next'); page.wait_for_timeout(200)
    click_cell(page, 8, 9); page.wait_for_timeout(80)
    card = page.inner_text('#atk-ctx')
    check('72% per shot' in card and '18 per second · about 13 after misses' in card, f'a tower card shows its accuracy at 4 shots/s and expected damage ({card[:200]!r})')
    page.click('#atk-ctx [data-act=close]')
    # spec tests 6-8: the scrubber on the Wave step (Runners only, no bridge planned)
    page.click('#atk-next'); page.wait_for_timeout(250)
    check(page.is_visible('#a-scrub') and page.inner_text('#scrub-lbl') == 'T = 0.0 s' and page.is_hidden('#scrub-br') and page.locator('#tl [data-al]').count() == 0,
          'the Wave step opens the scrubber at T = 0 s, no bridge toggle without a bridge, and auto-align is gone')
    check(S(page, 'window.siegeline.scrub.view().dots.length') == 0 and '3 still to spawn' in page.inner_text('#tl'), 'at 0 s nothing has set out: the track says 3 still to spawn')
    set_slider(page, '#scrub-t', 10)
    v = page.evaluate('() => window.siegeline.scrub.view()')
    dots = sorted([d for d in v['dots'] if d['g'] == 'd0'], key=lambda d: d['w'])
    check(len(dots) == 3 and page.inner_text('#scrub-lbl') == 'T = 10.0 s', f'at T = 10 s the three Runners are on the map ({len(dots)})')
    route = v['route']; d = dots[1]
    ci = min(range(len(route)), key=lambda k: (route[k] % COLS + 0.5 - d['x']) ** 2 + (route[k] // COLS + 0.5 - d['y']) ** 2)
    tgt = route[max(2, ci - 3)]
    tl0 = S(page, 'S.designs[0].tl')
    x0, y0 = page.evaluate(f"() => window.siegeline.worldToClient({d['x'] + d['ox']}, {d['y'] + d['oy']})")
    drag(page, x0, y0, *page.evaluate(f'() => window.siegeline.cellToClient({tgt})')); page.wait_for_timeout(150)
    tl1 = S(page, 'S.designs[0].tl')
    v = page.evaluate('() => window.siegeline.scrub.view()')
    d1 = next((x for x in v['dots'] if x['g'] == 'd0' and x['k'] == d['k']), None)
    gap = ((d1['x'] - tgt % COLS - 0.5) ** 2 + (d1['y'] - tgt // COLS - 0.5) ** 2) ** 0.5 if d1 else 9
    check(tl1['s'] > tl0['s'] and abs((tl1['e'] - tl1['s']) - (tl0['e'] - tl0['s'])) < 1e-9 and gap < 0.2,
          f'spec test 6: a group dragged at T = 10 s keeps its spread ({tl0["e"] - tl0["s"]:.3f}) and the grabbed unit is {gap:.3f} cells from the drop point')
    page.screenshot(path=f'{OUT}/v19_scrub.png')
    # spec test 7: past 0 s or 20 s the group stops at the limit, and a toast says why
    lead = max(v['dots'], key=lambda d: d['w'])
    x0, y0 = page.evaluate(f"() => window.siegeline.worldToClient({lead['x'] + lead['ox']}, {lead['y'] + lead['oy']})")
    drag(page, x0, y0, *page.evaluate(f'() => window.siegeline.cellToClient({route[-2]})')); page.wait_for_timeout(100)
    check(abs(S(page, 'S.designs[0].tl.s')) < 1e-9 and toast(page) == 'Can’t release before 0 s', f'spec test 7: dragged too far ahead, the group stops at 0 s ({toast(page)})')
    page.wait_for_timeout(150); set_slider(page, '#scrub-t', 40)
    v = page.evaluate('() => window.siegeline.scrub.view()')
    check(v['keep'] == 3 and not v['dots'], f'at 40 s all three are at the keep ({v["keep"]})')
    drag(page, *page.evaluate('() => window.siegeline.worldToClient(16.33, 5.5)'), *page.evaluate(f'() => window.siegeline.cellToClient({route[3]})')); page.wait_for_timeout(100)
    check(abs(S(page, 'S.designs[0].tl.e') - 1) < 1e-9 and toast(page) == 'Must be released by 20 s', f'spec test 7: dragged back from the keep at 40 s, the group stops at 20 s ({toast(page)})')
    # dropped on the entry tile at T: it releases at T, so it isn't out yet
    page.wait_for_timeout(150); page.click('.mini[data-act=rush]'); page.wait_for_timeout(150); set_slider(page, '#scrub-t', 6)
    v = page.evaluate('() => window.siegeline.scrub.view()'); d = max(v['dots'], key=lambda d: d['w'])
    drag(page, *page.evaluate(f"() => window.siegeline.worldToClient({d['x'] + d['ox']}, {d['y'] + d['oy']})"), *page.evaluate(f'() => window.siegeline.cellToClient({idx(0, 5)})')); page.wait_for_timeout(150)
    pos = page.evaluate('() => window.siegeline.tlPositions(window.siegeline.state.designs[0])')
    v = page.evaluate('() => window.siegeline.scrub.view()')
    check(abs(pos[d['k']] * 20 - 6) < 1e-6 and not any(x['g'] == 'd0' and x['k'] == d['k'] for x in v['dots']), f'dropped on the entry tile at 6 s, it releases at 6 s and isn’t on the map yet ({pos[d["k"]] * 20:.2f}s)')
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
    lane = page.locator('.lane[data-i="0"]').bounding_box(); cur = page.locator('.lane[data-i="0"] .tcur').bounding_box()
    thumb = page.evaluate("() => { const i = document.querySelector('#scrub-t'), r = i.getBoundingClientRect(); return r.left + 8 + (r.width - 16) * i.value / i.max; }")
    check(abs(cur['x'] - (lane['x'] + lane['width'] * 5 / 60)) < 2 and abs(thumb - cur['x']) < 3, f'the T line sits at 5 s on the tracks, under the slider’s thumb ({cur["x"]:.0f} vs {thumb:.0f})')
    bar = page.locator('.lane[data-i="0"] .span').bounding_box()
    check(bar and bar['x'] < lane['x'] + lane['width'] / 3 and bar['x'] + bar['width'] > lane['x'] + lane['width'] / 3, f'the Runners’ bar runs from their release past 20 s, while they walk ({bar})')
    # spec test 8: with a bridge planned, Lands changes the route the moment its sapper arrives; Fails never does
    page.click('#atk-back'); page.wait_for_timeout(150)
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
    page.screenshot(path=f'{OUT}/v19_lands.png')
    page.click('#scrub-br [data-lands="0"]'); page.wait_for_timeout(100)
    R = page.evaluate('() => window.siegeline.scrub.routes()'); sp = page.evaluate('() => window.siegeline.scrub.saps()')[0]
    check(len(R) == 1 and sp['tFail'] == sp['t0'] and at(30) == R[0]['path'], 'spec test 8: on Fails the route never changes and the sapper fails at once')
    page.screenshot(path=f'{OUT}/v19_fails.png')
    check(not errors, f'v19: no errors {errors[:3]}')
    ctx.close()
    # the scrubber on a phone: drag a dot by touch
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); no_terrain(page)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    page.tap('#def-next'); page.wait_for_timeout(100); page.tap('#def-next'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(200)
    for _ in range(3): page.tap('.step.plus[data-i="0"]')
    page.tap('#atk-next'); page.wait_for_timeout(100); page.tap('#atk-next'); page.wait_for_timeout(250)
    set_slider(page, '#scrub-t', 6)
    v = page.evaluate('() => window.siegeline.scrub.view()'); d = min(v['dots'], key=lambda d: d['w'])
    x0, y0 = page.evaluate(f"() => window.siegeline.worldToClient({d['x'] + d['ox'] + 0.3}, {d['y'] + d['oy']})")  # a little off the dot: the grab area is wide
    x1, y1 = page.evaluate(f'() => window.siegeline.cellToClient({v["route"][2]})')  # back toward the breach: it releases later
    s0 = S(page, 'S.designs[0].tl.s')
    cdp = ctx.new_cdp_session(page)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x0, 'y': y0}]})
    for k in range(1, 9): cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x0 + (x1 - x0) * k / 8, 'y': y0 + (y1 - y0) * k / 8}]}); page.wait_for_timeout(20)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []}); page.wait_for_timeout(150)
    check(S(page, 'S.designs[0].tl.s') != s0 and not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: a dot dragged by touch moves its group; no horizontal overflow')
    page.screenshot(path=f'{OUT}/m13_scrub.png')
    check(not errors, f'phone scrubber: no errors {errors[:3]}')
    ctx.close()

    ctx = b.new_context(viewport={'width': 844, 'height': 390}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); no_terrain(page)
    page.tap('#info-go'); page.wait_for_timeout(200); page.tap('#mode-local'); page.wait_for_timeout(500); page.tap('#ov-hand'); page.wait_for_timeout(150)
    rb = page.locator('#def-next').bounding_box()
    check(rb and rb['y'] + rb['height'] <= 390, f'landscape phone: Next visible {rb}')
    page.screenshot(path=f'{OUT}/l0.png')
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
    page.click('#def-next'); page.click('#def-next'); hand(page)
    check(S(page, f'S.seenGrid[{j}] && S.seenGrid[{j}].t') == 'rock', 'the attacker sees the rock from round 1')
    for _ in range(5): page.click('.step.plus[data-i="0"]')
    for _ in range(4): page.click('#atk-next')
    hand(page); page.evaluate('() => window.siegeline.advance(200)'); page.wait_for_timeout(100)
    live = S(page, '[...S.terrain].join("")')
    page.click('#sum-replay'); page.wait_for_timeout(100)
    check(S(page, '[...S.terrain].join("")') == live and S(page, f'S.grid[{j}].t') == 'rock', 'the replay plays on the same map')
    page.click('#rp-close'); page.click('#sum-next'); hand(page)
    page.click('#def-next'); page.click('#def-next'); hand(page)
    page.click('#atk-next'); page.wait_for_timeout(300)
    click_cell(page, j % COLS, j // COLS)
    check(S(page, 'S.charges.size') == 0 and 'can’t be bridged' in toast(page), f'rock can’t be bridged ({toast(page)})')
    click_cell(page, i % COLS, i // COLS)
    check(S(page, 'S.charges.size') == 0 and 'rough ground' in toast(page).lower(), f'rough ground needs no bridge ({toast(page)})')
    page.evaluate('() => { window.siegeline.state.keep = 1; }')
    page.click('#atk-next'); page.click('#atk-next'); page.click('#atk-next'); hand(page)
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
    b.close()

print('\nFAILURES:', len(fails))
for f in fails: print(' -', f)
