"""Versus-computer suite: the mode card, both sides at both levels, the computer's plan staying hidden and
fixed while the player plans, its coins adding up, full matches to the end screen, and phone layout.
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
def hand(page):
    page.wait_for_timeout(480); page.click('#ov-hand'); page.wait_for_timeout(60)
def run_wave(page):
    """Plays the wave out; when the keep falls the end screen follows a short animation."""
    page.evaluate('() => window.siegeline.advance(300)'); page.wait_for_timeout(60)
    if S(page, 'S.over'): page.wait_for_selector('#ov-end', state='visible', timeout=5000)
def text(page, sel): return page.evaluate(f'() => document.querySelector("{sel}").textContent')
PLAN = 'JSON.stringify(SOLO.plan)'
DWORTH = 'S.dFree + S.grid.reduce((v, g) => v + (g ? (g.t === "wall" ? 5 : window.siegeline.towerValue(g)) : 0), 0)'
AWORTH = 'S.aFree + S.designs.reduce((v, d) => v + d.count * window.siegeline.unitCost(d), 0) + [...S.charges.values()].reduce((v, c) => v + c.cost, 0)'

def start(page, side, level):
    page.click(f'.pick button[data-side={side}]'); page.click(f'.pick button[data-level={level}]')
    page.click('#mode-solo'); page.wait_for_timeout(100)

def play_out(page, side, label, ready):
    """Plays rounds until the match ends: ready() does the player's turn. Checks the computer's side each round."""
    rounds, coins_ok, worth_ok, charges, last_round_charges = 0, True, True, 0, 0
    for _ in range(8):
        rounds += 1
        before = S(page, AWORTH if side == 'def' else DWORTH)
        ready()
        check(page.is_visible('#ov-hand') and 'computer' in page.inner_text('#hand-sub').lower(), f'{label} r{rounds}: wave card says the computer locked in') if rounds == 1 else None
        hand(page)
        after = S(page, AWORTH if side == 'def' else DWORTH)
        worth_ok &= before == after
        coins_ok &= S(page, 'S.aFree >= 0 && S.dFree >= 0') and S(page, 'S.path !== null')
        n = S(page, 'S.charges.size'); charges += n
        if S(page, 'S.round') == 8: last_round_charges = n
        run_wave(page)
        if page.is_visible('#ov-end'): break
        page.click('#sum-next'); page.wait_for_timeout(60)
        check(not page.is_visible('#ov-hand') and S(page, 'S.phase') == ('defend' if side == 'def' else 'attack'), f'{label}: next round goes straight to the player') if rounds == 1 else None
    check(worth_ok, f'{label}: the computer\'s plan moves no coins in or out of its worth')
    check(coins_ok, f'{label}: no side overspends and the route stays open')
    check(last_round_charges == 0, f'{label}: no computer charges in the final wave')
    check(page.is_visible('#ov-end') and text(page, '#end-title') in ('You win', 'The computer wins'), f'{label}: match ends with a solo result ({text(page, "#end-title")}, {rounds} rounds)')
    return charges

with sync_playwright() as p:
    b = launch(p)
    ctx = b.new_context(viewport={'width': 1366, 'height': 860})
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'ERR_' not in m.text else None)
    page.goto('file://' + HARNESS); page.wait_for_timeout(500)
    page.click('#info-go')
    check(page.is_visible('#mode-solo') and page.get_attribute('.pick button[data-side=def]', 'aria-pressed') == 'true', 'mode screen shows Versus computer, defender picked by default')
    page.screenshot(path=f'{OUT}/0_mode.png')

    # ---------- player defends, Easy
    start(page, 'def', 'easy')
    check(S(page, 'SOLO.on') and S(page, 'S.phase') == 'defend' and not page.is_visible('#ov-hand'), 'defender vs computer starts building at once, no handoff')
    plan0 = S(page, PLAN)
    check(S(page, 'SOLO.plan && SOLO.plan.a.reduce((n, a) => n + a[8], 0) > 0 && SOLO.plan.c.length === 0'), 'computer attacker planned an army, no charges in round 1')
    for r in range(0, 10): click_cell(page, 7, r)
    page.click('#def-next'); click_cell(page, 9, 5); click_cell(page, 5, 4)
    check(S(page, PLAN) == plan0, 'computer\'s plan is unchanged by what the player builds')
    check(S(page, 'S.designs.every(d => d.count === 0)'), 'computer\'s army stays out of the live state while the player plans')
    page.click('#def-next'); page.click('#def-next')
    check(text(page, '#hand-title') == 'Wave 1' and 'pass' not in page.inner_text('#hand-sub').lower(), 'Ready leads to the wave card, no pass-the-device screen')
    page.screenshot(path=f'{OUT}/1_def_wavecard.png')
    hand(page)
    check(S(page, 'S.phase') == 'wave' and S(page, 'S.designs.reduce((n, d) => n + d.count, 0)') > 0, 'computer army marches')
    page.wait_for_timeout(900); page.screenshot(path=f'{OUT}/2_def_wave.png')
    run_wave(page)
    page.click('#sum-next'); page.wait_for_timeout(60)
    check(S(page, 'S.round') == 2 and S(page, 'S.phase') == 'defend' and not page.is_visible('#ov-hand'), 'round 2 goes straight back to the defender')
    def def_ready():
        page.click('#def-next'); page.click('#def-next'); page.click('#def-next')
    play_out(page, 'def', 'defend/easy', def_ready)
    check(not page.is_visible('#end-swap') and page.is_visible('#end-menu'), 'end screen offers Menu, not Swap sides')
    page.screenshot(path=f'{OUT}/3_end.png')
    page.click('#end-again')
    check(S(page, 'SOLO.on') and S(page, 'S.round') == 1 and S(page, 'S.keep') == 1000 and S(page, 'S.phase') == 'defend', 'rematch restarts against the computer on the same side')
    page.evaluate('() => { window.siegeline.state.keep = 1; }')
    def_ready(); hand(page); run_wave(page)
    check(page.is_visible('#ov-end') and text(page, '#end-title') == 'The computer wins', 'keep falls: the computer wins')
    page.click('#end-menu')
    check(page.is_visible('#ov-mode') and not S(page, 'SOLO.on'), 'Menu returns to the mode screen')

    # ---------- player defends, Normal: the computer charges a maze it has seen
    start(page, 'def', 'normal')
    for r in range(0, 10): click_cell(page, 7, r)
    page.click('#def-next'); click_cell(page, 9, 5); click_cell(page, 9, 2); click_cell(page, 5, 7)
    page.click('#def-next'); page.click('#def-next'); hand(page)
    run_wave(page); page.click('#sum-next')
    check(S(page, 'SOLO.plan.c.length > 0 && SOLO.plan.c.every(([i, t]) => S.seenGrid[i] && S.seenGrid[i].t === (t ? "tower" : "wall"))'), f'normal computer plans charges, only on walls and towers it saw {S(page, "SOLO.plan.c")}')
    check(S(page, 'SOLO.plan.c.filter(c => c[1] === 1).length') <= 2, 'tower charges stay within the cap (half of 3 seen towers, rounded up)')
    play_out(page, 'def', 'defend/normal', def_ready)
    page.click('#end-menu')

    # ---------- player attacks, Easy and Normal
    for level in ('easy', 'normal'):
        start(page, 'atk', level)
        check(S(page, 'S.phase') == 'attack' and not page.is_visible('#ov-hand') and S(page, 'SOLO.plan && Array.isArray(SOLO.plan.g.w)'), f'attack/{level}: attacker starts planning at once, computer defense planned')
        check(S(page, 'S.grid.every(g => !g)'), f'attack/{level}: computer defense not on the board while the player plans')
        for _ in range(10): page.click('.step.plus[data-i="0"]')
        def atk_ready():
            for _ in range(4): page.click('#atk-next')
        if level == 'easy':
            plan0 = S(page, PLAN)
            atk_ready()
            check(S(page, 'S.grid.some(g => g && g.t === "tower") && S.grid.some(g => g && g.t === "wall")'), 'computer defense appears when the wave starts')
            hand(page); page.wait_for_timeout(900); page.screenshot(path=f'{OUT}/4_atk_wave.png')
            run_wave(page); page.click('#sum-next')
            check(S(page, 'S.seenGrid.some(g => g && g.t === "tower")'), 'attacker sees the computer defense after the wave')
        else:
            atk_ready(); hand(page); run_wave(page); page.click('#sum-next')
            atk_ready()
            check(S(page, 'S.grid.some(g => g && g.t === "tower" && g.cfg.splash > 0)'), 'normal computer adds splash after seeing cheap runners')
            hand(page); run_wave(page); page.click('#sum-next')
        play_out(page, 'atk', f'attack/{level}', atk_ready)
        page.click('#end-menu')
    check(not errors, f'no errors on desktop {errors[:3]}')
    ctx.close()

    # ---------- phone portrait
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    page = ctx.new_page(); errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('file://' + HARNESS); page.wait_for_timeout(400)
    page.tap('#info-go'); page.wait_for_timeout(200)
    page.locator('#mode-solo').scroll_into_view_if_needed()
    bx = page.locator('#mode-solo').bounding_box()
    check(bx and bx['x'] >= 0 and bx['x'] + bx['width'] <= 390 and bx['y'] + bx['height'] <= 844, f'phone: Play the computer button visible {bx}')
    check(not page.evaluate('() => document.documentElement.scrollWidth > innerWidth || document.querySelector("#ov-mode .modes").scrollWidth > document.querySelector("#ov-mode .modes").clientWidth'), 'phone: mode screen has no horizontal overflow')
    page.screenshot(path=f'{OUT}/m0_mode.png')
    page.tap('.pick button[data-side=atk]'); page.tap('#mode-solo'); page.wait_for_timeout(300)
    check(S(page, 'S.phase') == 'attack', 'phone: attacker vs computer starts')
    for _ in range(6): page.tap('.step.plus[data-i="0"]')
    for _ in range(4): page.tap('#atk-next'); page.wait_for_timeout(80)
    page.wait_for_timeout(500); page.screenshot(path=f'{OUT}/m1_wavecard.png'); page.tap('#ov-hand'); page.wait_for_timeout(2000)
    check(S(page, 'S.phase') == 'wave', 'phone: wave plays')
    page.screenshot(path=f'{OUT}/m2_wave.png')
    check(not page.evaluate('() => document.documentElement.scrollWidth > innerWidth'), 'phone: no horizontal overflow in the match')
    check(not errors, f'phone: no errors {errors[:3]}')
    ctx.close()
    b.close()

print('\nFAILURES:', len(fails))
for f in fails: print(' -', f)
