"""Versus-computer suite: the mode card, both sides at every level, the computer thinking in the background
without touching the live game, its plan staying fixed whatever the player does, its coins adding up, sappers
(bridges and knock-outs) at every level under the game's rules, its defense never standing on a bridge, the computer's notes, the wait card when the player locks in first,
replays against the computer (also while it thinks), full matches to the end screen, phone layout, and the computer
on terrain (rock where it should be, nothing on rough ground, the same plan for the same seed). The fixed scenarios
play without terrain.
   python tools/tests/test_solo.py   (screenshots land in tools/.build/shots/solo)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, launch
from playwright.sync_api import sync_playwright

OUT = os.path.join(BUILD, 'shots', 'solo'); os.makedirs(OUT, exist_ok=True)
HARNESS = write_build('solo.html', game_html())

COLS = 16
fails = []
def check(cond, msg):
    print(('PASS ' if cond else 'FAIL ') + msg)
    if not cond: fails.append(msg)
def idx(c, r): return r * COLS + c
def S(page, expr): return page.evaluate('() => { const S = window.siegeline.state, SOLO = window.siegeline.solo; return ' + expr + '; }')
def click_cell(page, c, r):
    x, y = page.evaluate(f'() => window.siegeline.cellToClient({idx(c,r)})'); page.mouse.click(x, y)
def thought(page): page.wait_for_function('() => !window.siegeline.solo.think', timeout=30000)
def hand(page):
    """After Ready: the wave card shows once the computer is done (a wait card may come first)."""
    page.wait_for_selector('#ov-hand', state='visible', timeout=30000)
    page.wait_for_timeout(480); page.click('#ov-hand'); page.wait_for_timeout(60)
def run_wave(page):
    """Plays the wave out; when the keep falls the end screen follows a short animation."""
    page.evaluate('() => window.siegeline.advance(300)'); page.wait_for_timeout(60)
    if S(page, 'S.over'): page.wait_for_selector('#ov-end', state='visible', timeout=5000)
def text(page, sel): return page.evaluate(f'() => document.querySelector("{sel}").textContent')
PLAN = 'JSON.stringify(SOLO.plan)'
LIVE = 'JSON.stringify([S.grid.map(g => g && [g.t, g.cfg, g.off, g.fresh]), S.designs, S.dFree, S.aFree, S.charges.size, S.path && S.path.length, S.keep, S.round, S.phase])'
DWORTH = 'S.dFree + S.grid.reduce((v, g) => v + (!g || g.t === "rock" ? 0 : g.t === "wall" ? 5 : window.siegeline.towerValue(g)), 0)'
AWORTH = 'S.aFree + S.designs.reduce((v, d) => v + d.count * window.siegeline.unitCost(d), 0) + [...S.charges.values()].reduce((v, c) => v + c.cost, 0)'
# sabotage on the live wave: all on cells the attacker saw (bridges on walls, knock-outs on towers), within the bridge
# cap and the tower value cap (one tower always fits), each sapper leaving within the wave and each bridge with its tile
CHARGES_OK = '''[...S.charges].every(([i, c]) => S.seenGrid[i] && S.seenGrid[i].t === (c.kind === "bridge" ? "wall" : c.kind))
  && [...S.charges.values()].filter(c => c.kind === "bridge").length <= window.siegeline.rules.bridgesPerWave
  && (() => { const sl = window.siegeline, t = [...S.charges].filter(([, c]) => c.kind === "tower");
       return t.length <= 1 || t.reduce((v, [i]) => v + sl.towerValue(S.seenGrid[i]), 0) <= sl.rules.towerCapShare * S.seenGrid.reduce((v, g) => v + (g && g.t === "tower" ? sl.towerValue(g) : 0), 0); })()
  && [...S.charges.values()].every(c => c.t >= 0 && c.t <= 1 && (c.kind === "tower" || c.at >= 0))'''
# terrain on the live board: rock in the grid where the map has it, nothing on rough ground
TERRAIN_OK = 'S.grid.every((g, i) => S.terrain[i] === 2 ? !!(g && g.t === "rock") : S.terrain[i] === 1 ? !g : !(g && g.t === "rock"))'
def terrain(page, on):
    page.evaluate(f'() => {{ const R = window.siegeline.rules; R.roughShare = R.rockShare = {0.05 if on else 0}; }}')

def start(page, side, level, seed=None):
    page.evaluate(f'() => {{ window.siegeline.solo.seed = {"null" if seed is None else seed}; }}')
    page.click(f'.pick button[data-side={side}]'); page.click(f'.pick button[data-level={level}]')
    page.click('#mode-solo'); page.wait_for_timeout(60)

def hints_off(page):
    """The fixed scenarios click known cells; with hints on, a glowing tile would place the hint's whole set."""
    if page.get_attribute('#def-steps [data-act=hints]', 'aria-pressed') == 'true': page.click('#def-steps [data-act=hints]')
def build_maze(page, strong=False):
    """A 3-column serpentine clicked in like a player: a tower in the middle of each column (285 coins), or with
    strong=True three towers per column on 900 coins, a defense worth charging."""
    rows = (2, 5, 8) if strong else (5,)
    if strong: page.evaluate('() => { window.siegeline.state.dFree = 900; }')
    hints_off(page)
    for k, c in enumerate((3, 7, 11)):
        for r in range(11):
            if r not in rows and r != (10 if k % 2 else 0): click_cell(page, c, r)
    page.click('.tool[data-tool=tower]')
    for r in rows:
        for c in (3, 7, 11): click_cell(page, c, r)
    page.click('#def-next')  # to Ready, so the next click locks in

def play_out(page, side, label, ready):
    """Plays rounds until the match ends: ready() does the player's turn. Checks the computer's side each round."""
    rounds, coins_ok, worth_ok, rules_ok, most, notes, sent, landed = 0, True, True, True, 0, 0, 0, 0
    charges, first_last = 0, []
    for _ in range(8):
        rounds += 1
        before = S(page, AWORTH if side == 'def' else DWORTH)
        ready(); hand(page)
        worth_ok &= before == S(page, AWORTH if side == 'def' else DWORTH)
        coins_ok &= S(page, 'S.aFree >= 0 && S.dFree >= 0 && S.path !== null')
        n = S(page, 'S.charges.size'); charges += n; most = max(most, n)
        rules_ok &= S(page, CHARGES_OK) and S(page, '[...S.bridges].every(i => !S.grid[i])') and S(page, TERRAIN_OK)
        if S(page, 'S.round') in (1, 8): first_last.append(n)
        run_wave(page)
        sent += S(page, 'S.wave.sappers'); landed += S(page, 'S.wave.sapOk')
        notes += bool(S(page, 'SOLO.note'))
        if page.is_visible('#ov-end'): break
        page.click('#sum-next'); page.wait_for_timeout(60)
    check(worth_ok, f'{label}: the computer\'s plan moves no coins in or out of its worth')
    check(coins_ok, f'{label}: no side overspends and the route stays open')
    check(rules_ok and not any(first_last), f'{label}: sabotage only on what was seen, within the caps, none in round 1 or 8, nothing built on a bridge or rough ground, rock in place')
    check(notes == rounds, f'{label}: the computer explains every wave ({notes}/{rounds})')
    if sent: print(f'      {label}: {landed} of {sent} sappers landed')
    check(page.is_visible('#ov-end') and text(page, '#end-title') in ('You win', 'The computer wins'), f'{label}: match ends with a solo result ({text(page, "#end-title")}, {rounds} rounds)')
    return charges, most

with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
    page.goto('file://' + HARNESS); page.wait_for_timeout(500); terrain(page, False)
    page.click('#info-go')
    check(page.is_visible('#mode-solo') and page.get_attribute('.pick button[data-side=def]', 'aria-pressed') == 'true', 'mode screen shows Versus computer, defender picked by default')
    check(page.is_visible('.pick button[data-level=hard]'), 'mode screen offers Easy, Normal and Hard')
    page.screenshot(path=f'{OUT}/0_mode.png')

    # ---------- player defends, Easy: basics
    start(page, 'def', 'easy')
    check(S(page, 'SOLO.on') and S(page, 'S.phase') == 'defend' and not page.is_visible('#ov-hand'), 'defender vs computer starts building at once, no handoff')
    thought(page)
    plan0 = S(page, PLAN)
    check(S(page, 'SOLO.plan && SOLO.plan.a.reduce((n, a) => n + a[8], 0) > 0 && SOLO.plan.c.length === 0'), 'computer attacker planned an army, no sabotage in round 1')
    build_maze(page)
    check(S(page, PLAN) == plan0, 'computer\'s plan is unchanged by what the player builds')
    check(S(page, 'S.designs.every(d => d.count === 0)'), 'computer\'s army stays out of the live state while the player plans')
    page.click('#def-next')
    page.wait_for_selector('#ov-hand', state='visible', timeout=30000)
    check(text(page, '#hand-title') == 'Wave 1' and 'pass' not in page.inner_text('#hand-sub').lower(), 'Ready leads to the wave card, no pass-the-device screen')
    page.screenshot(path=f'{OUT}/1_def_wavecard.png')
    page.wait_for_timeout(480); page.click('#ov-hand')
    check(S(page, 'S.phase') == 'wave' and S(page, 'S.designs.reduce((n, d) => n + d.count, 0)') > 0, 'computer army marches')
    page.wait_for_timeout(900); page.screenshot(path=f'{OUT}/2_def_wave.png')
    run_wave(page)
    check(page.is_visible('#ov-sum .ainote') and 'opened with' in page.inner_text('#ov-sum .ainote'), f'summary shows the computer\'s thinking ({S(page, "SOLO.note")})')
    page.screenshot(path=f'{OUT}/3_summary_note.png')
    page.click('#sum-next'); page.wait_for_timeout(30)
    check(S(page, 'S.round') == 2 and S(page, 'S.phase') == 'defend' and not page.is_visible('#ov-hand'), 'round 2 goes straight back to the defender')
    thought(page)
    check(S(page, 'SOLO.plan.c.length') <= 1, 'easy computer sends at most one sapper a wave')
    def def_ready(): page.click('#def-next'); page.click('#def-next')
    play_out(page, 'def', 'defend/easy', def_ready)
    check(not page.is_visible('#end-swap') and page.is_visible('#end-menu'), 'end screen offers Menu, not Swap sides')
    page.click('#end-again')
    check(S(page, 'SOLO.on') and S(page, 'S.round') == 1 and S(page, 'S.keep') == 1000 and S(page, 'S.phase') == 'defend', 'rematch restarts against the computer on the same side')
    page.evaluate('() => { window.siegeline.state.keep = 1; }')
    def_ready(); hand(page); run_wave(page)
    check(page.is_visible('#ov-end') and text(page, '#end-title') == 'The computer wins', 'keep falls: the computer wins')
    page.click('#end-menu')
    check(page.is_visible('#ov-mode') and not S(page, 'SOLO.on'), 'Menu returns to the mode screen')

    # ---------- player defends a real maze at every level: the computer attacks it, sappers included
    for level in ('easy', 'normal', 'hard'):
        start(page, 'def', level)
        build_maze(page, strong=True)
        page.click('#def-next'); hand(page); run_wave(page)
        if page.is_visible('#ov-end'): page.click('#end-menu'); check(False, f'{level}: keep fell in round 1'); continue
        page.click('#sum-next')
        def maze_ready(): page.click('#def-next'); page.click('#def-next')
        charges, most = play_out(page, 'def', f'defend/{level}', maze_ready)
        check(charges > 0, f'{level} computer attacker sends sappers against a walled defense ({charges} over the match)')
        if level == 'easy': check(most <= 1, f'easy computer sends at most one sapper a wave (most {most})')
        page.click('#end-menu')

    # ---------- player attacks at every level
    for level in ('easy', 'normal', 'hard'):
        start(page, 'atk', level)
        check(S(page, 'S.phase') == 'attack' and not page.is_visible('#ov-hand'), f'attack/{level}: attacker starts planning at once')
        thought(page)
        check(S(page, 'SOLO.plan && Array.isArray(SOLO.plan.g.w)') and S(page, 'S.grid.every(g => !g)'), f'attack/{level}: computer defense planned, but not on the board while the player plans')
        for _ in range(10): page.click('.step.plus[data-i="0"]')
        def atk_ready():
            for _ in range(4): page.click('#atk-next')
        atk_ready(); hand(page)
        check(S(page, 'S.grid.some(g => g && g.t === "tower") && S.grid.some(g => g && g.t === "wall")'), f'attack/{level}: computer defense appears when the wave starts')
        if level == 'easy': page.wait_for_timeout(900); page.screenshot(path=f'{OUT}/4_atk_wave.png')
        run_wave(page)
        check('hadn’t seen your army' in S(page, 'SOLO.note'), f'attack/{level}: round 1 note says it hadn\'t seen an army yet')
        # round 2: the player lays a bridge on a wall of the computer's maze
        page.click('#sum-next'); page.click('#atk-next')
        page.wait_for_timeout(300)
        # a wall halfway up a column, beside the route: the computer guards the wall it would bridge itself, usually by
        # a column's end (any wall beside the route if it built none there: Normal sometimes plays its second-best plan)
        wall = S(page, 'S.seenGrid.findIndex((g, i) => window.siegeline.canBridgeAt(i) && i % 16 > 1 && i % 16 < 14 && Math.abs(Math.floor(i / 16) - 5) <= 2)')
        if wall < 0: wall = S(page, 'S.seenGrid.findIndex((g, i) => window.siegeline.canBridgeAt(i))')
        if wall >= 0:
            click_cell(page, wall % COLS, wall // COLS)
            check(S(page, f'S.charges.has({wall}) && S.charges.get({wall}).kind') == 'bridge', f'attack/{level}: the player plans a bridge on a wall of the computer\'s maze')
        else: print(f'SKIP attack/{level}: the computer built no walls in round 1, nothing to bridge')
        page.click('#atk-next'); page.click('#atk-next'); page.click('#atk-next'); hand(page); run_wave(page)
        check('Your last wave was 10 × Runner' in S(page, 'SOLO.note'), f'attack/{level}: round 2 note names the army it defended against ({S(page, "SOLO.note")[:60]}…)')
        if wall >= 0:
            L = S(page, 'S.last')
            check(L['sappers'] == 1 and L['sapOk'] + L['sapLost'] + L['sapMissed'] == 1 and S(page, f'S.bridges.has({wall})') == (L['sapOk'] == 1),
                  f'attack/{level}: the bridge goes down if its sapper gets there (landed {L["sapOk"]}, shot down {L["sapLost"]}, missed {L["sapMissed"]})')
        page.click('#sum-next')
        if S(page, 'S.bridges.size'):
            atk_ready(); hand(page)
            check(S(page, '[...S.bridges].every(i => !S.grid[i])') and 'bridge' in S(page, 'SOLO.note'), f'attack/{level}: the computer builds nothing on the bridge and says what it did about it ({S(page, "SOLO.note")[-110:]})')
            if level == 'hard': page.wait_for_timeout(700); page.screenshot(path=f'{OUT}/4b_atk_bridge.png')
            run_wave(page)
            if page.is_visible('#ov-end'): page.click('#end-menu'); continue
            page.click('#sum-next')
        play_out(page, 'atk', f'attack/{level}', atk_ready)
        page.click('#end-menu')

    # ---------- knock-outs against the computer: targets are tied to the cell, so Hard moves the towers it expects the
    # player to target, and sappers sent for their old cells find nothing
    start(page, 'atk', 'hard', seed=11)
    for _ in range(12): page.click('.step.plus[data-i="0"]')
    for _ in range(4): page.click('#atk-next')
    hand(page); run_wave(page); page.click('#sum-next')
    dodges, planted, knocked, moved_note = 0, 0, 0, False
    for rnd in range(2, 8):
        thought(page)
        dodges += 1 if S(page, 'SOLO.mem.def.info && SOLO.mem.def.info.dodged') else 0
        page.evaluate('() => { window.siegeline.state.aFree += 120; }')  # coins for a knock-out every round
        page.click('#atk-next'); page.wait_for_timeout(250)  # to Sabotage
        # the seen tower worth most: the obvious target
        cell = S(page, 'S.seenGrid.reduce((b, g, i) => g && g.t === "tower" && !(g.off > 0) && (b < 0 || window.siegeline.towerValue(g) > window.siegeline.towerValue(S.seenGrid[b])) ? i : b, -1)')
        if cell >= 0:
            click_cell(page, cell % COLS, cell // COLS)
            if page.is_visible('#atk-ctx [data-act=plant]'): page.click('#atk-ctx [data-act=plant]'); planted += 1
            if page.is_visible('#atk-ctx [data-act=close]'): page.click('#atk-ctx [data-act=close]')
        page.click('#atk-next'); page.click('#atk-next'); page.click('#atk-next'); hand(page); run_wave(page)
        knocked += S(page, 'S.last ? S.last.jammed : 0')
        moved_note |= 'to a new cell' in S(page, 'SOLO.note')
        if page.is_visible('#ov-end'): break
        page.click('#sum-next')
    check(dodges > 0 and moved_note, f'hard computer moves the towers it expects to be targeted, and says so ({dodges} of the rounds)')
    check(planted > 0 and knocked < planted, f'player knock-outs on the old cells miss ({knocked} of {planted} knocked a tower out)')
    if page.is_visible('#ov-end'): page.click('#end-menu')
    else:
        page.evaluate('() => { window.siegeline.state.keep = 1; }')
        for _ in range(4): page.click('#atk-next')
        hand(page); run_wave(page); page.click('#end-menu')

    # ---------- the computer's plan can't depend on the player's: same seed, player busy or idle while it thinks
    plans = []
    for busy in (True, False):
        start(page, 'atk', 'hard', seed=7)
        if busy:
            for _ in range(10): page.click('.step.plus[data-i="0"]')
        thought(page); plans.append(S(page, PLAN))
        page.evaluate('() => { window.siegeline.state.keep = 1; }')
        for _ in range(10): page.click('.step.plus[data-i="1"]')
        for _ in range(4): page.click('#atk-next')
        hand(page); run_wave(page); page.click('#end-menu')
    check(plans[0] == plans[1], 'same match seed: the computer\'s plan is identical whether or not the player acts while it thinks')

    # ---------- locking in before the computer is done: wait card, Keep planning, then the wave
    cdp = ctx.new_cdp_session(page); cdp.send('Emulation.setCPUThrottlingRate', {'rate': 8})
    start(page, 'atk', 'hard')
    check(S(page, '!!SOLO.think'), 'the computer is still thinking as the player starts')
    live0 = S(page, LIVE)
    # step to Ready and lock in (an empty army takes a second press) in one go, while it is surely still thinking
    page.evaluate('() => { for (let k = 0; k < 5; k++) document.querySelector("#atk-next").click(); }')
    waited = S(page, 'SOLO.locked') and page.is_visible('#ov-wait')
    check(waited and 'computer' in page.inner_text('#wait-sub').lower(), 'locking in early shows the wait card')
    page.screenshot(path=f'{OUT}/5_wait.png')
    if waited:
        page.click('#wait-back')
        check(not page.is_visible('#ov-wait') and S(page, 'S.phase') == 'attack' and not S(page, 'SOLO.locked'), 'Keep planning goes back to planning')
        thought(page)
        check(S(page, LIVE) == live0, 'thinking (its hidden test waves) leaves the live game untouched')
        page.click('#atk-next'); page.wait_for_timeout(30)
        if S(page, 'S.phase') == 'attack': page.click('#atk-next')
    page.wait_for_selector('#ov-hand', state='visible', timeout=60000)
    check(text(page, '#hand-title') == 'Wave 1', 'the wave card follows once the computer is done')
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
    page.wait_for_timeout(480)
    if page.is_visible('#ov-hand'): page.click('#ov-hand')
    run_wave(page)

    # ---------- replay against the computer: from the summary, and from the Ready step while it is still thinking
    live0 = S(page, LIVE)
    page.click('#sum-replay'); page.wait_for_timeout(100)
    check(page.evaluate('() => window.siegeline.replaying') and S(page, 'S.phase') == 'wave', 'solo: summary Replay plays the wave again')
    page.evaluate('() => window.siegeline.advance(300)'); page.wait_for_timeout(60)
    page.click('#rp-close')
    check(S(page, LIVE) == live0 and page.is_visible('#ov-sum') and not page.evaluate('() => window.siegeline.replaying'), 'solo: closing the replay returns to the summary, match untouched')
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 8})
    page.click('#sum-next'); page.wait_for_timeout(30)
    thinking, live1 = S(page, '!!SOLO.think'), S(page, LIVE)
    page.evaluate('() => { for (let k = 0; k < 3; k++) document.querySelector("#atk-next").click(); }')  # to the Ready step
    page.click('#atk-body [data-act=replay]')
    check(thinking and page.evaluate('() => window.siegeline.replaying'), 'solo: the Ready step replays the last wave while the computer is still thinking')
    page.evaluate('() => window.siegeline.advance(300)')
    thought(page)  # the computer finishes its plan while the replay is open
    page.click('#rp-close')
    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 1})
    check(S(page, LIVE) == live1 and S(page, 'S.phase') == 'attack' and S(page, 'SOLO.plan && Array.isArray(SOLO.plan.g.w)'),
          'solo: a replay during thinking leaves the match and the computer\'s plan intact')
    page.click('#atk-next'); page.wait_for_timeout(30)
    if S(page, 'S.phase') == 'attack': page.click('#atk-next')  # an empty army takes a second Ready
    hand(page); run_wave(page)
    check(S(page, 'S.round') == 2 and (page.is_visible('#ov-sum') or page.is_visible('#ov-end')), 'solo: the next wave plays normally after the replay')

    # ---------- terrain: the computer reads the map on both sides
    terrain(page, True)
    page.evaluate('() => { document.querySelectorAll(".overlay").forEach(o => o.hidden = true); document.querySelector("#ov-mode").hidden = false; }')
    for level in ('normal', 'hard'):
        start(page, 'atk', level)
        check(S(page, 'S.terrain.some(v => v) && S.seenGrid.some(g => g && g.t === "rock")'), f'terrain attack/{level}: the match has rough ground and rock, and the player sees the rock')
        for _ in range(10): page.click('.step.plus[data-i="0"]')
        play_out(page, 'atk', f'terrain attack/{level}', atk_ready)
        page.click('#end-menu')
    start(page, 'def', 'hard')
    play_out(page, 'def', 'terrain defend/hard', def_ready)
    page.click('#end-menu')
    plans = []
    for _ in range(2):
        start(page, 'atk', 'hard', seed=11); thought(page)
        plans.append((S(page, '[...S.terrain].join("")'), S(page, PLAN)))
        page.evaluate('() => { document.querySelectorAll(".overlay").forEach(o => o.hidden = true); document.querySelector("#ov-mode").hidden = false; }')
    check(plans[0] == plans[1] and '2' in plans[0][0], 'terrain: the same match seed gives the same map and the same computer plan')
    terrain(page, False)

    # ---------- pass-and-play never shows a computer note
    page.evaluate('() => { window.siegeline.solo.on = false; }')
    page.evaluate('() => { document.querySelector("#ov-sum").hidden = true; document.querySelector("#ov-mode").hidden = false; }')
    page.click('#mode-local'); page.wait_for_timeout(480); page.click('#ov-hand')
    for _ in range(2): page.click('#def-next')
    page.wait_for_timeout(480); page.click('#ov-hand')
    for _ in range(5): page.click('#atk-next')  # an empty army takes a second Ready
    page.wait_for_timeout(480); page.click('#ov-hand'); run_wave(page)
    check(page.is_visible('#ov-sum') and not page.is_visible('#ov-sum .ainote'), 'pass-and-play summary has no computer note')
    check(not errors, f'no errors on desktop {errors[:3]}')
    ctx.close()

    # ---------- phone portrait
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400); terrain(page, False)
    page.tap('#info-go'); page.wait_for_timeout(200)
    page.locator('#mode-solo').scroll_into_view_if_needed()
    bx = page.locator('#mode-solo').bounding_box()
    check(bx and bx['x'] >= 0 and bx['x'] + bx['width'] <= 390 and bx['y'] + bx['height'] <= 844, f'phone: Play the computer button visible {bx}')
    lv = page.locator('.pick button[data-level=hard]').bounding_box()
    check(lv and lv['x'] + lv['width'] <= 390, f'phone: all three difficulty buttons fit {lv}')
    check(not page.evaluate('() => document.documentElement.scrollWidth > innerWidth || document.querySelector("#ov-mode .modes").scrollWidth > document.querySelector("#ov-mode .modes").clientWidth'), 'phone: mode screen has no horizontal overflow')
    page.screenshot(path=f'{OUT}/m0_mode.png')
    page.tap('.pick button[data-side=atk]'); page.tap('.pick button[data-level=normal]'); page.tap('#mode-solo'); page.wait_for_timeout(300)
    check(S(page, 'S.phase') == 'attack', 'phone: attacker vs computer starts')
    for _ in range(6): page.tap('.step.plus[data-i="0"]')
    for _ in range(4): page.tap('#atk-next'); page.wait_for_timeout(80)
    page.wait_for_selector('#ov-hand', state='visible', timeout=30000)
    page.wait_for_timeout(500); page.screenshot(path=f'{OUT}/m1_wavecard.png'); page.tap('#ov-hand'); page.wait_for_timeout(1500)
    check(S(page, 'S.phase') == 'wave', 'phone: wave plays')
    page.screenshot(path=f'{OUT}/m2_wave.png')
    check(not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: no horizontal overflow in the match')
    page.evaluate('() => window.siegeline.advance(300)'); page.wait_for_timeout(300)
    nb = page.locator('#ov-sum .ainote').bounding_box()
    check(nb and nb['x'] >= 0 and nb['x'] + nb['width'] <= 390, f'phone: the computer\'s note fits on the summary {nb}')
    page.locator('#ov-sum .ainote').scroll_into_view_if_needed(); page.screenshot(path=f'{OUT}/m3_note.png')
    page.tap('#sum-next'); page.wait_for_timeout(200)
    # a big enough wave that something gets through whatever the computer builds (its seed is random here)
    page.evaluate('() => { const S = window.siegeline.state; S.keep = 1; S.designs[0].count += 40; S.designs[0].tl = { s: 0, e: 0.1, pos: null }; }')
    for _ in range(4): page.tap('#atk-next'); page.wait_for_timeout(80)
    page.wait_for_selector('#ov-hand', state='visible', timeout=30000); page.wait_for_timeout(500); page.tap('#ov-hand')
    page.evaluate('() => window.siegeline.advance(300)'); page.wait_for_selector('#ov-end', state='visible', timeout=5000)
    boxes = [page.locator(sel).bounding_box() for sel in ('#end-replay', '#end-menu', '#end-again')]
    check(all(bx and bx['x'] >= 0 and bx['x'] + bx['width'] <= 390 and bx['y'] + bx['height'] <= 844 for bx in boxes), f'phone: solo end screen buttons (Replay, Menu, Rematch) fit {boxes}')
    page.screenshot(path=f'{OUT}/m4_end.png')
    check(not errors, f'phone: no errors {errors[:3]}')
    ctx.close()
    b.close()

print('\nFAILURES:', len(fails))
for f in fails: print(' -', f)
