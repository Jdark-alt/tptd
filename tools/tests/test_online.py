"""Online suite: lobby, ready gating, hidden plans, identical waves on both devices (also at 10x, and with towers missing), desyncs,
   rematch/swap, drop and rejoin, both devices building the same map (terrain), plus the peer-to-peer path.
   The room scenarios click known cells, so they play without terrain. Needs: npm install in tools/tests.
   python tools/tests/test_online.py        (add "peer" to run only the peer-to-peer part)"""
import os, sys, json, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, ROOT, TOOLS, launch, GUIDE_SEEN
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BUILD, 'web'); os.makedirs(WEB, exist_ok=True)
SHOTS = os.path.join(BUILD, 'shots', 'online'); os.makedirs(SHOTS, exist_ok=True)
import shutil
_html = game_html()
# room.html: the game with a stand-in for the claude.ai room capability; index.html: plain (peer-to-peer path)
open(os.path.join(WEB, 'room.html'), 'w').write(_html.replace('<head>', '<head><script src="mockroom.js"></script>', 1))
open(os.path.join(WEB, 'index.html'), 'w').write(_html)
shutil.copy(os.path.join(HERE, 'mockroom.js'), WEB)
# old.html: the build on main, if it speaks another protocol version, to check the two never join one match
try: _old = subprocess.run(['git', 'show', 'origin/main:index.html'], cwd=ROOT, capture_output=True, text=True).stdout
except Exception: _old = ''
OLD = bool(_old) and 'const PROTO = ' in _old and _old.split('const PROTO = ')[1].split(';')[0] != _html.split('const PROTO = ')[1].split(';')[0]
if OLD: open(os.path.join(WEB, 'old.html'), 'w').write(_old.replace('<head>', '<head><script src="mockroom.js"></script>', 1))
PEERJS = os.path.join(HERE, 'node_modules', 'peerjs', 'dist', 'peerjs.min.js')
if not os.path.exists(PEERJS):
    sys.exit('Run "npm install" in tools/tests first (installs peerjs and the local peer server).')
COLS = 16
def idx(c, r): return r * COLS + c

fails = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  {info}' if info != '' else ''), flush=True)
    if not ok: fails.append(name)

PRE = "const S=window.siegeline.state,N=window.siegeline.net;"
def ev(pg, expr): return pg.evaluate(f'()=>{{{PRE}return ({expr});}}')
def wait(pg, expr, t=15000): pg.wait_for_function(f'()=>{{{PRE}return !!({expr});}}', timeout=t)
def cell(pg, i):
    x, y = pg.evaluate(f'()=>window.siegeline.cellToClient({i})'); pg.mouse.click(x, y)
def snap(pg):
    return pg.evaluate('''()=>{const S=window.siegeline.state;return {keep:S.keep,dFree:S.dFree,aFree:S.aFree,last:S.last,totals:S.totals,round:S.round,over:S.over,winner:S.winner,
      grid:S.grid.map(g=>g?(g.t==="wall"?"w":"t"+g.off):0).join(","), bridges:[...S.bridges].sort((a,b)=>a-b).join(","), army:JSON.stringify(S.designs.map(d=>[d.name,d.count,d.hp,d.speed,d.tl.s,d.tl.e,d.tl.pos]))}}''')

def no_terrain(*pgs):
    """Known cells are clicked, so no terrain and no starter maze; sappers get top health so the planned sabotage always
    arrives; and no planning clock (it has checks of its own), so a slow machine never sends a plan early."""
    for pg in pgs: pg.evaluate('()=>{const R=window.siegeline.rules; R.roughShare=0; R.rockShare=0; R.starterPresses=0; R.sapper.hp=9; R.planSecs=0;}')
def join(pg, role, code, waves=None):
    """v26: rooms. 'def' hosts the room with this code (the host sits as Defender); 'atk' joins it and sits in the free seat.
    The host starts the match with start()."""
    pg.click('#info-go')
    pg.wait_for_selector('#ov-mode:not([hidden])')
    if waves: pg.click(f'#mode-waves [data-rounds="{waves}"]')
    pg.fill('#mode-code', code)
    pg.click('#mode-host' if role == 'def' else '#mode-join')
    pg.wait_for_selector('#ov-lobby:not([hidden])')
def start(pg, t=15000):
    """The host presses Start once both seats are taken."""
    pg.wait_for_selector('#lobby-start:not([disabled])', timeout=t); pg.click('#lobby-start')
def join_old(pg, role, code):
    """The build on main: before v26 sides were picked on the start screen, then Connect; since v26 it has the lobby."""
    if pg.query_selector('#mode-host'): return join(pg, role, code)
    pg.click('#info-go'); pg.wait_for_selector('#ov-mode:not([hidden])')
    pg.click(f'.rolepick button[data-role={role}]'); pg.fill('#mode-code', code); pg.click('#mode-online')

def defend_round(pg, walls=(), towers=(), lock=True):
    wait(pg, "S.phase==='defend' && S.step===0")
    # known cells are clicked: with hints on, a glowing tile would place the hint's whole set
    if pg.get_attribute('#def-steps [data-act=hints]', 'aria-pressed') == 'true': pg.click('#def-steps [data-act=hints]')
    for c in walls: cell(pg, c)
    if towers: pg.click('.tool[data-tool=tower]')
    for c, cfg in towers:
        cell(pg, c)
        if cfg: pg.evaluate(f'()=>{{const g=window.siegeline.state.grid[{c}]; Object.assign(g.cfg,{json.dumps(cfg)});}}')
    pg.wait_for_timeout(120)
    if lock: pg.click('#def-lock')

def attack_round(pg, counts, lock=True, extra=''):
    wait(pg, "S.phase==='attack' && S.step===0")
    pg.evaluate('''(counts)=>{const sl=window.siegeline,S=sl.state; counts.forEach((n,k)=>{ if(!S.designs[k]) return; const d=S.designs[k]; const add=n-d.count; S.aFree-=add*sl.unitCost(d); d.count=n; }); }''', counts)
    if extra: pg.evaluate(f'()=>{{{PRE}{extra}}}')
    pg.wait_for_timeout(80)
    if lock: pg.click('#atk-lock')

def same(a, b, name):
    sa, sb = snap(a), snap(b)
    diff = {k: (sa[k], sb[k]) for k in sa if sa[k] != sb[k]}
    check(name, not diff, json.dumps(diff)[:400] if diff else f"keep {round(sa['keep'],2)} breach {round(sa['last']['breach'],3) if sa['last'] else '-'}")
    return sa

def errors_hook(pg, bucket):
    pg.on('pageerror', lambda e: bucket.append(str(e)))
    pg.on('console', lambda m: bucket.append(m.text) if m.type == 'error' and 'Failed to load resource' not in m.text else None)

srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1'], cwd=WEB, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
peersrv = subprocess.Popen(['node', 'peer-server.cjs'], cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.5)
try:
    with sync_playwright() as p:
        br = p.chromium.launch(args=['--disable-features=WebRtcHideLocalIpsWithMdns', '--disable-background-timer-throttling', '--disable-renderer-backgrounding', '--disable-backgrounding-occluded-windows'])
        if 'peer' not in sys.argv:
            ctx = br.new_context(viewport={'width': 1280, 'height': 800})
            ctx.add_init_script(GUIDE_SEEN)  # the wave plan's How to use card has been seen
            errs = []
            A = ctx.new_page(); B = ctx.new_page()
            for pg in (A, B): errors_hook(pg, errs)
            A.goto('http://127.0.0.1:8765/room.html'); B.goto('http://127.0.0.1:8765/room.html')
            A.wait_for_timeout(400); no_terrain(A, B)

            # ---------- lobby ----------
            A.click('#info-go')
            check('mode picker opens after the intro', A.is_visible('#ov-mode'))
            check('v26: Join needs a code; Host a room is always there', A.is_disabled('#mode-join') and A.is_enabled('#mode-host'))
            A.fill('#mode-code', 'TEST'); A.click('#mode-host')
            A.wait_for_selector('#ov-lobby:not([hidden])'); A.wait_for_timeout(400)
            check('v26: the host lands in the room, sitting as Defender, with its code', A.inner_text('#lobby-code') == 'TEST' and ev(A, '[N.host, N.role, N.st]') == [True, 'def', 'lobby'])
            check('v26: the host waits for someone to join; Start waits too', 'Waiting for someone to join' in A.inner_text('#mode-status') and A.is_disabled('#lobby-start'), A.inner_text('#mode-status'))
            A.screenshot(path=f'{SHOTS}/o1_lobby_waiting.png')
            join(B, 'atk', 'test')
            B.wait_for_timeout(500)
            check('v26: the joiner sits in the free seat and waits for the host', ev(B, '[N.host, N.role]') == [False, 'atk'] and 'Waiting for the host' in B.inner_text('#mode-status'), B.inner_text('#mode-status'))
            check('v26: both seats show on both devices', 'You' in A.inner_text('#lobby-seats') and 'Friend' in A.inner_text('#lobby-seats') and 'Host' in B.inner_text('#lobby-seats'), A.inner_text('#lobby-seats').replace('\n', ' '))
            check('v26: nothing starts until the host presses Start', ev(A, 'N.st') == 'lobby' and ev(B, 'N.st') == 'lobby')
            start(A)
            wait(A, "N.st==='play' && S.phase==='defend'"); wait(B, "N.st==='play' && S.phase==='attack'")
            check('both start: defender plans', ev(A, "S.phase") == 'defend' and A.is_hidden('#ov-mode'))
            check('both start: attacker plans', ev(B, "S.phase") == 'attack' and B.is_hidden('#ov-mode'))
            check('no handoff screens online', A.is_hidden('#ov-hand') and B.is_hidden('#ov-hand'))
            check('net pill visible', A.is_visible('#netpill'), A.inner_text('#netpill'))

            # ---------- round 1: defender locks first ----------
            maze = [idx(3, r) for r in range(0, 9)] + [idx(7, r) for r in range(2, 11)]
            # v21: the splash tower also arrives with chain switched on (a plan from an older or edited build): both
            # devices decode it to Splash only
            defend_round(A, walls=maze, towers=[(idx(5, 4), None), (idx(9, 6), {'splash': 1, 'rate': 4, 'chain': True})])
            A.wait_for_timeout(300)
            check('defender sees the wait card', A.is_visible('#ov-wait'), A.inner_text('#wait-sub'))
            check('wait card names the attacker', 'attacker' in A.inner_text('#wait-sub'))
            check('attacker is told the defender is ready', 'ready' in B.inner_text('#netpill').lower(), B.inner_text('#netpill'))
            check('defender plan is not revealed before both lock', ev(B, "N.peer && N.peer.plan") is None and ev(B, "S.grid.every(g=>!g)"))
            check('wave has not started', ev(A, "S.phase") == 'defend' and ev(B, "S.phase") == 'attack')
            attack_round(B, [8, 2, 6])
            wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
            check('wave starts once both are ready', True)
            check('attacker now sees the real maze', ev(B, "S.grid.filter(g=>g&&g.t==='wall').length") == len(maze))
            check('defender now sees the army', ev(A, "S.designs.map(d=>d.count).join()") == '8,2,6')
            CH = f"[S.grid[{idx(9, 6)}].cfg.splash, S.grid[{idx(9, 6)}].cfg.chain]"
            check('a tower planned with both Chain and Splash decodes to Splash only, on both devices', ev(A, CH) == [1, False] and ev(B, CH) == [1, False], f'{ev(A, CH)} / {ev(B, CH)}')
            check('spawn schedules identical', A.evaluate('()=>JSON.stringify(window.siegeline.state.spawnList)') == B.evaluate('()=>JSON.stringify(window.siegeline.state.spawnList)'))
            A.screenshot(path=f'{SHOTS}/o2_wave_def.png')
            for pg in (A, B): pg.evaluate('()=>window.siegeline.advance(300)')
            wait(A, "S.phase==='summary'"); wait(B, "S.phase==='summary'")
            s1 = same(A, B, 'round 1 results identical on both devices')
            # v19 (spec test 5): towers miss now (80% by default), and both devices still agree shot for shot
            check('misses on: both devices missed the same shots', s1['last']['misses'] > 0 and ev(B, "S.last.misses") == s1['last']['misses'], s1['last']['misses'])
            check('defender published the result', ev(A, "N.res && N.res.r") == 1)
            # the attacker replays the wave while the defender moves on to round 2
            B.click('#sum-replay'); A.click('#sum-next')
            check('replay runs on one device only', B.evaluate('()=>window.siegeline.replaying') and ev(A, "S.phase") == 'defend')
            B.evaluate('()=>window.siegeline.advance(300)')
            check('replay matches the wave', ev(B, "S.wave.y") == ev(A, "S.last.Y"))
            B.click('#rp-close')
            check('closing the replay goes back to the summary', B.is_visible('#ov-sum') and ev(B, "S.phase") == 'summary')
            B.click('#sum-next')
            same(A, B, 'replay leaves the online match untouched')

            # ---------- round 2: a bridge and a knock-out, unlock and relock, real-time wave ----------
            wait(B, "S.phase==='attack'")
            tower_cell = idx(5, 4)
            # a bridge has to touch the route the attacker saw: take a wall of column 3 beside it
            bcell = B.evaluate('()=>{const S=window.siegeline.state; const ok=S.seenGrid.map((g,i)=>i).filter(i=>window.siegeline.canBridgeAt(i)); return ok.find(i=>i%16===3) ?? ok[0];}')
            attack_round(B, [10, 2, 6], lock=False,
                         extra=f"S.charges.set({tower_cell},{{kind:'tower',t:0.02,cost:23}}); S.aFree-=23; S.charges.set({bcell},{{kind:'bridge',t:0.05,cost:31}}); S.aFree-=31;")
            B.click('#atk-lock')
            B.wait_for_timeout(200)
            check('attacker locks in first', B.is_visible('#ov-wait'))
            B.click('#wait-back')
            check('keep planning unlocks', B.is_hidden('#ov-wait') and ev(B, "N.lk") == 0)
            A.wait_for_timeout(200)
            check('defender sees attacker planning again', 'planning' in A.inner_text('#netpill').lower(), A.inner_text('#netpill'))
            B.evaluate('()=>{const S=window.siegeline.state;S.designs[0].count=12;S.aFree-=2*window.siegeline.unitCost(S.designs[0]);}')
            B.click('#atk-lock')
            defend_round(A, walls=[idx(11, r) for r in range(0, 9)], towers=[(idx(13, 4), None)])
            wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
            check('relocked plan is the one used', ev(A, "S.designs[0].count") == 12)
            t0 = time.time()
            A.click('.speed button[data-speed="10"]')
            wait(A, "S.phase==='summary'", 60000); ta = time.time() - t0
            wait(B, "S.phase==='summary'", 120000); tb = time.time() - t0
            print(f'   real-time wave took {ta:.1f}s at 10x, {tb:.1f}s at 1x')
            check('10x finishes much sooner', ta * 3 < tb)
            s2 = same(A, B, 'round 2 identical with one device at 10x')
            check('knock-out landed on both', s2['last']['jammed'] == 1 and s2['last']['sapOk'] == 2 and ev(B, "S.last.sapOk") == 2, s2['last'])
            check('bridge laid on both', s2['last']['bridges'] == 1 and ev(A, f"S.bridges.has({bcell})") and ev(B, f"S.bridges.has({bcell})"), s2['bridges'])
            A.screenshot(path=f'{SHOTS}/o3_summary_def.png'); B.screenshot(path=f'{SHOTS}/o3_summary_atk.png')
            A.click('#sum-next'); B.click('#sum-next')

            # ---------- round 3: both lock at once ----------
            wait(A, "S.phase==='defend'"); wait(B, "S.phase==='attack'")
            # the attacker's plan also carries a bridge on a wall away from the route: both devices must drop it
            off = B.evaluate('()=>{const S=window.siegeline.state; return S.seenGrid.findIndex((g,i)=>g&&g.t==="wall"&&!S.bridges.has(i)&&!window.siegeline.canBridgeAt(i));}')
            # and a knock-out priced at 1: both devices price it by the rules, on the tower's slider price with one knock-out sent before
            stale = f"S.charges.set({idx(13, 4)},{{kind:'tower',t:0,cost:1}}); S.aFree-=1;"
            v13 = ev(B, f"window.siegeline.towerCost(S.seenGrid[{idx(13, 4)}].cfg)"); want = int((15 + 0.2 * v13) * 1.25 + 0.5)
            defend_round(A, lock=False); attack_round(B, [12, 3, 6], lock=False, extra=(f"S.charges.set({off},{{kind:'bridge',waves:0,cost:70}}); S.aFree-=70;" if off >= 0 else '') + stale)
            # v23: a bridge landed last wave, so this round every move is free on the defender's device; the fee checks
            # below need a paid move, so the test clears that (it lives only on the defender's device, nothing travels)
            check('v23: after a bridge landed, the defender moves towers free this round', ev(A, 'S.freeMv && S.freeMv.all') is True and ev(A, f'window.siegeline.state.grid[{idx(9, 6)}] && 1') == 1, ev(A, 'S.freeMv'))
            A.evaluate('()=>{window.siegeline.state.freeMv=null;}')
            # v22 Part C: the defender drags a tower the attacker saw (the splash tower) onto a wall: it pays the move fee
            fee_want = int(0.1 * ev(A, f"window.siegeline.towerCost(S.grid[{idx(9, 6)}].cfg)") + 0.5); d_before = ev(A, 'S.dFree')
            (x0, y0), (x1, y1) = [A.evaluate(f'()=>window.siegeline.cellToClient({i})') for i in (idx(9, 6), idx(7, 5))]
            A.mouse.move(x0, y0); A.mouse.down()
            for k in range(1, 9): A.mouse.move(x0 + (x1 - x0) * k / 8, y0 + (y1 - y0) * k / 8)
            A.mouse.up(); A.wait_for_timeout(100)
            check('v22 Part C: dragging a seen tower costs the defender the move fee', ev(A, 'S.dFree') == d_before - fee_want and ev(A, 'S.totals.moveTries') == 1, f"{d_before} → {ev(A, 'S.dFree')} (fee {fee_want})")
            A.evaluate("()=>document.querySelector('#def-lock').click()"); B.evaluate("()=>document.querySelector('#atk-lock').click()")
            wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
            check('simultaneous lock-in starts the wave on both', True)
            check('v22 Part C test 7: both devices have the same coins and relocation count after the fee', ev(A, '[S.dFree, S.totals.moveTries]') == ev(B, '[S.dFree, S.totals.moveTries]') == [d_before - fee_want, 1],
                  f"{ev(A, '[S.dFree, S.totals.moveTries]')} / {ev(B, '[S.dFree, S.totals.moveTries]')}")
            # v23: the fee goes to the attacker when the wave ends; both devices read it from the defender's plan
            check('v23: both devices carry the move fee into the wave, to be credited to the attacker', ev(A, '[S.wave.mf, S.mvFee]') == ev(B, '[S.wave.mf, S.mvFee]') == [fee_want, fee_want],
                  f"{ev(A, '[S.wave.mf, S.mvFee]')} / {ev(B, '[S.wave.mf, S.mvFee]')}")
            a_left = ev(B, 'S.aFree')
            check(f'a knock-out is priced by the rules on both devices (the second knock-out: {want})', ev(A, "S.wave.chargeCoins") == want and ev(B, "S.wave.chargeCoins") == want, f'{ev(A, "S.wave.chargeCoins")} / {ev(B, "S.wave.chargeCoins")}')
            # the charges each device started the wave with (the live list empties as they go off, sooner on the 10x device)
            pre = "S.preWave.charges.map(c => c[0])"
            if off >= 0: check('a bridge off the route in a plan is dropped on both devices', ev(A, pre) == ev(B, pre) and off not in ev(A, pre), f'{ev(A, pre)} / {ev(B, pre)}')
            # Desync on purpose: the attacker's copy drifts and must adopt the defender's result.
            B.evaluate('()=>{window.siegeline.state.keep -= 37;}')
            for pg in (A, B): pg.evaluate('()=>window.siegeline.advance(300)')
            wait(A, "S.phase==='summary'"); wait(B, "S.phase==='summary'")
            B.wait_for_timeout(300)
            same(A, B, 'attacker adopts the defender result after a desync')
            check('sync toast shown', 'Synced' in B.inner_text('#toast'), B.inner_text('#toast'))
            L3 = ev(B, '[S.last.aGain, S.last.aMove, S.last.aInt, S.aFree]')
            check('v23: the attacker’s coins match on both devices, the move fee credited (“Defender moved towers”)',
                  ev(A, '[S.last.aMove, S.aFree]') == [fee_want, L3[3]] and L3[1] == fee_want and L3[3] == a_left + L3[0] + L3[1] + L3[2] and ev(B, 'S.mvFee') == 0
                  and f'+{fee_want}' in B.inner_text('#sum-extra') and 'moved towers' in B.inner_text('#sum-extra').lower(), f"{ev(A, '[S.last.aMove, S.aFree]')} / {L3} from {a_left}")
            A.click('#sum-next'); B.click('#sum-next')

            # ---------- round 4: keep falls mid-wave ----------
            wait(A, "S.phase==='defend'"); wait(B, "S.phase==='attack'")
            for pg in (A, B): pg.evaluate('()=>{window.siegeline.state.keep = 20;}')
            defend_round(A); attack_round(B, [14, 3, 6])
            wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
            for pg in (A, B): pg.evaluate('()=>window.siegeline.advance(300)')
            wait(A, "S.phase==='over'", 8000); wait(B, "S.phase==='over'", 8000)
            same(A, B, 'match end identical')
            check('attacker wins on both', ev(A, "S.winner") == 'attacker' and ev(B, "S.winner") == 'attacker')
            check('swap button offered online', B.is_visible('#end-swap'))
            B.screenshot(path=f'{SHOTS}/o4_end_atk.png')

            # ---------- rematch with swapped sides ----------
            B.click('#end-swap')
            wait(B, "N.role==='def' && S.phase==='defend' && S.round===1"); wait(A, "N.role==='atk' && S.phase==='attack' && S.round===1")
            check('swap: other device follows', ev(A, "N.ep") == ev(B, "N.ep") == 2)
            check('swap: end screen closed on follower', A.is_hidden('#ov-end'))
            defend_round(B, walls=[idx(5, r) for r in range(1, 11)], towers=[(idx(9, 3), None), (idx(9, 7), None), (idx(12, 5), {'range': 4})]); attack_round(A, [5, 1, 4])
            wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
            for pg in (A, B): pg.evaluate('()=>window.siegeline.advance(300)')
            wait(A, "S.phase==='summary'"); wait(B, "S.phase==='summary'")
            same(A, B, 'swapped match round 1 identical')
            A.click('#sum-next'); B.click('#sum-next')

            # ---------- a player drops and comes back ----------
            wait(A, "S.phase==='attack'")
            B.close()
            A.wait_for_timeout(400)
            check('opponent offline shown', 'offline' in A.inner_text('#netpill').lower(), A.inner_text('#netpill'))
            attack_round(A, [5, 1, 4])
            A.wait_for_timeout(200)
            check('locked in while opponent offline: wave waits', ev(A, "S.phase") == 'attack' and 'offline' in A.inner_text('#wait-sub').lower(), A.inner_text('#wait-sub'))
            A.screenshot(path=f'{SHOTS}/o5_wait_offline.png')
            B = ctx.new_page(); errors_hook(B, errs)
            B.goto('http://127.0.0.1:8765/room.html'); B.wait_for_timeout(300); no_terrain(B)
            join(B, 'def', 'TEST')
            B.wait_for_selector('#mode-restart:not([hidden])', timeout=5000)
            check('rejoining device is offered a fresh match', 'lost track' in B.inner_text('#mode-status'), B.inner_text('#mode-status'))
            B.screenshot(path=f'{SHOTS}/o6_rejoin.png')
            B.click('#mode-restart')
            wait(B, "S.phase==='defend' && S.round===1"); wait(A, "S.phase==='attack' && S.round===1")
            check('both restart together', ev(A, "N.ep") == ev(B, "N.ep") == 3 and A.is_hidden('#ov-wait'))

            # ---------- lobby clash ----------
            C = ctx.new_page(); D = ctx.new_page()
            for pg in (C, D): errors_hook(pg, errs); pg.goto('http://127.0.0.1:8765/room.html')
            C.wait_for_timeout(300)
            join(C, 'def', 'CLSH'); join(D, 'def', 'CLSH')  # both host the same code at once
            C.wait_for_timeout(800)
            roles = [ev(pg, '[N.host, N.role]') for pg in (C, D)]
            check('v26: two hosts on one code: one keeps the room and the Defender seat, the other sits as Attacker', sorted(map(str, roles)) == sorted(map(str, [[True, 'def'], [False, 'atk']])), roles)
            H = C if roles[0][0] else D
            start(H)
            wait(C, "N.st==='play'"); wait(D, "N.st==='play'")
            check('v26: and the match starts', {ev(C, 'S.phase'), ev(D, 'S.phase')} == {'defend', 'attack'})
            check('max presence size', ev(A, 'window.__maxPresence||0') < 4096, max(ev(pg, 'window.__maxPresence||0') for pg in (A, B, C, D)))
            for pg in (C, D): pg.close()
            # ---------- terrain: both devices build the same map, play the same wave on it, and a rematch brings a new one ----------
            C = ctx.new_page(); D = ctx.new_page()
            for pg in (C, D): errors_hook(pg, errs); pg.goto('http://127.0.0.1:8765/room.html')
            C.wait_for_timeout(300)
            join(C, 'def', 'TERR'); join(D, 'atk', 'TERR'); start(C)
            wait(C, "N.st==='play' && S.phase==='defend'"); wait(D, "N.st==='play' && S.phase==='attack'")
            MAP = '[S.mapSeed,[...S.terrain].join(""),S.grid.map(g=>g&&g.t==="rock"?1:0).join("")]'
            m1 = ev(C, MAP)
            check('terrain: both devices build the same map', m1 == ev(D, MAP) and '1' in m1[1] and '2' in m1[1], m1[0])
            check('terrain: the attacker sees the rock from the start', ev(D, 'S.seenGrid.filter(g=>g&&g.t==="rock").length') == m1[1].count('2'))
            # v21: the starter maze is built on both devices from the shared seed; nothing about it travels
            ST = 'S.grid.map(g=>g&&g.t==="wall"?1:0).join("")'
            check('starter maze: built on both devices, identical, and seen by the attacker', ev(C, 'S.starter') > 20 and ev(C, ST) == ev(D, ST) and ev(D, 'S.seenGrid.map(g=>g&&g.t==="wall"?1:0).join("")') == ev(C, ST),
                  f"{ev(C, 'S.starter')} walls / {ev(D, 'S.starter')}")
            defend_round(C); attack_round(D, [6, 1, 8])
            wait(C, "S.phase==='wave'"); wait(D, "S.phase==='wave'")
            for pg in (C, D): pg.evaluate('()=>window.siegeline.advance(300)')
            wait(C, "S.phase==='summary'"); wait(D, "S.phase==='summary'")
            same(C, D, 'terrain: the wave on the map is identical on both devices')
            C.click('#sum-next'); D.click('#sum-next')
            wait(C, "S.phase==='defend'"); wait(D, "S.phase==='attack'")
            for pg in (C, D): pg.evaluate('()=>{window.siegeline.state.keep = 5;}')
            defend_round(C); attack_round(D, [12, 2, 10])
            for pg in (C, D): wait(pg, "S.phase==='wave'"); pg.evaluate('()=>window.siegeline.advance(300)')
            wait(C, "S.phase==='over'", 8000); wait(D, "S.phase==='over'", 8000)
            D.click('#end-again')
            wait(C, "N.ep===2 && S.round===1"); wait(D, "N.ep===2 && S.round===1")
            m2 = ev(C, MAP)
            check('terrain: a rematch brings a new map, the same on both devices', m2 == ev(D, MAP) and m2[1] != m1[1], m2[0])
            for pg in (C, D): pg.close()
            # ---------- the match length is the defender's pick; the planning clock locks a plan in when it runs out ----------
            C = ctx.new_page(); D = ctx.new_page()
            for pg in (C, D): errors_hook(pg, errs); pg.goto('http://127.0.0.1:8765/room.html')
            C.wait_for_timeout(300); no_terrain(C, D)
            # the defender's clock has room for building and locking in on a loaded machine; the attacker's runs out later
            C.evaluate('()=>{window.siegeline.rules.planSecs=6; window.siegeline.rules.planSecsFirst=6;}'); D.evaluate('()=>{window.siegeline.rules.planSecs=10; window.siegeline.rules.planSecsFirst=10;}')
            join(C, 'def', 'LONG', waves=6); join(D, 'atk', 'LONG', waves=10)
            D.wait_for_timeout(400)
            check("v26: the joiner's room shows the host's settings", 'KEEP 800' in D.inner_text('#lobby-set').upper() and D.is_disabled('#lobby-set [data-lset=n][data-v="10"]'), D.inner_text('#lobby-set').replace('\n', ' ')[:80])
            start(C)
            wait(C, "N.st==='play' && S.phase==='defend'"); wait(D, "N.st==='play' && S.phase==='attack'")
            check("match length: both devices play the defender's 6 waves with a keep of 800", ev(C, '[S.rounds,S.keep,S.keepMax]') == [6, 800, 800] and ev(D, '[S.rounds,S.keep,S.keepMax]') == [6, 800, 800],
                  f"{ev(C, '[S.rounds,S.keep]')} / {ev(D, '[S.rounds,S.keep]')}")
            for pg in (C, D):  # a page in the background draws its HUD once it's in front
                pg.bring_to_front()
                try: pg.wait_for_function("()=>document.querySelector('#v-rounds').textContent==='of 6'", timeout=3000)
                except Exception: pass
            check('match length: both HUDs say of 6', C.inner_text('#v-rounds') == D.inner_text('#v-rounds') == 'of 6')
            check('match length: the attacker is told the host picked it', '6 waves' in D.inner_text('#toast'), D.inner_text('#toast'))
            check('planning clock: each device shows its own', C.is_visible('#t-clock') and D.is_visible('#t-clock'), f"{C.inner_text('#t-clock')} / {D.inner_text('#t-clock')}")
            defend_round(C, walls=[idx(6, r) for r in range(0, 10)], towers=[(idx(8, 5), None)])
            C.wait_for_timeout(200)
            check('planning clock: locked in early, Keep planning is there', C.is_visible('#ov-wait') and C.is_visible('#wait-back') and C.is_hidden('#t-clock'))
            C.wait_for_selector('#wait-back', state='hidden', timeout=9000)
            check("planning clock: once the defender's time is up Keep planning is gone", ev(C, "S.phase") == 'defend' and ev(D, "S.phase") == 'attack')
            D.evaluate('(counts)=>{const sl=window.siegeline,S=sl.state; counts.forEach((n,k)=>{ const d=S.designs[k]; S.aFree-=(n-d.count)*sl.unitCost(d); d.count=n; }); }', [5, 1, 2])
            wait(C, "S.phase==='wave'", 14000); wait(D, "S.phase==='wave'", 14000)
            check('planning clock: the attacker who never pressed Ready is locked in when time runs out, army as planned', ev(C, "S.designs.map(d=>d.count).join()") == '5,1,2')
            for pg in (C, D): pg.evaluate('()=>window.siegeline.advance(300)')
            wait(C, "S.phase==='summary'"); wait(D, "S.phase==='summary'")
            same(C, D, 'planning clock: the wave is identical on both devices')
            C.click('#sum-next'); D.click('#sum-next')
            wait(C, "S.phase==='defend' && S.round===2"); wait(D, "S.phase==='attack' && S.round===2")
            check('planning clock: a fresh clock next round', C.is_visible('#t-clock') and ev(C, '[S.rounds,S.round]') == [6, 2] and ev(D, '[S.rounds,S.round]') == [6, 2])
            for pg in (C, D): pg.close()
            # ---------- v23: untimed rounds, the defender's pick: neither device runs a clock ----------
            C = ctx.new_page(); D = ctx.new_page()
            for pg in (C, D): errors_hook(pg, errs); pg.goto('http://127.0.0.1:8765/room.html')
            C.wait_for_timeout(300); no_terrain(C, D)
            for pg in (C, D): pg.evaluate('()=>{window.siegeline.rules.planSecs=4; window.siegeline.rules.planSecsFirst=4;}')
            C.click('#info-go'); C.wait_for_selector('#ov-mode:not([hidden])'); C.click('#mode-clock [data-timed="0"]'); C.click('#mode-sabo [data-sabo="0"]')
            C.fill('#mode-code', 'NOTM'); C.click('#mode-host')
            join(D, 'atk', 'NOTM'); start(C)
            wait(C, "N.st==='play' && S.phase==='defend'"); wait(D, "N.st==='play' && S.phase==='attack'")
            D.wait_for_timeout(5000)  # longer than the 4 s a timed round would have had here
            check("v23: untimed rounds (the defender's pick): no clock on either device, nobody locked in by time",
                  ev(C, '[N.tm, S.phase, N.lk]') == [0, 'defend', 0] and ev(D, '[N.tm, S.phase, N.lk]') == [0, 'attack', 0] and C.is_hidden('#clockbox') and D.is_hidden('#clockbox'),
                  f"{ev(C, '[N.tm, S.phase, N.lk]')} / {ev(D, '[N.tm, S.phase, N.lk]')}")
            check('v23: the attacker is told the defender picked untimed rounds', 'untimed' in D.inner_text('#toast').lower(), D.inner_text('#toast'))
            # v24: the defender picked sabotage off too: both devices play without it and price units alike
            price = '[S.sabo, window.siegeline.unitCost(S.designs[1])]'
            check("v24: sabotage off (the defender's pick) on both devices, units priced alike", ev(C, price) == ev(D, price) and ev(C, 'S.sabo') is False and ev(D, 'N.sb') == 0
                  and 'sabotage off' in D.inner_text('#toast').lower(), f"{ev(C, price)} / {ev(D, price)} · {D.inner_text('#toast')}")
            for pg in (C, D): pg.close()
            # ---------- v26: spectators. One by watch link before the start, one who joins the running match later; every
            # device plays every wave alike, and nothing secret reaches a spectator before both sides lock in. Terrain and the
            # starter maze stay on (the plans below don't click known cells: towers replace starter walls, so the route holds).
            ctx.grant_permissions(['clipboard-read', 'clipboard-write'], origin='http://127.0.0.1:8765')
            TOWERS = '(k0)=>{const S=window.siegeline.state; let k=0; S.grid.forEach((g,i)=>{ if (k<3 && g && g.t==="wall" && i%k0===0) { S.grid[i]={t:"tower",cfg:{range:2,dps:3,accuracy:0,rate:3,splash:0,slow:false,poison:false,chain:false},fee:0,off:0,fresh:true,n:++S.towerSeq,cd:0,ang:Math.PI,kick:0,dealt:0}; k++; } }); S.gridVer++; }'
            E = ctx.new_page(); F = ctx.new_page(); G = ctx.new_page()
            for pg in (E, F, G): errors_hook(pg, errs)
            E.goto('http://127.0.0.1:8765/room.html'); F.goto('http://127.0.0.1:8765/room.html'); E.wait_for_timeout(300)
            for pg in (E, F): pg.evaluate('()=>{window.siegeline.rules.planSecs=0;}')
            join(E, 'def', 'SPEC'); join(F, 'atk', 'SPEC')
            G.goto('http://127.0.0.1:8765/room.html#watch-SPEC')
            G.wait_for_selector('#ov-lobby:not([hidden])'); G.wait_for_timeout(700)
            check('v26: a watch link opens the room as a spectator, before the start', ev(G, '[N.role, N.st]') == ['spec', 'lobby'] and 'watch once the host starts' in G.inner_text('#mode-status'), G.inner_text('#mode-status'))
            check("v26: the host's room counts who's watching", '1 watching' in E.inner_text('#lobby-watchers'), E.inner_text('#lobby-watchers'))
            start(E)
            wait(E, "S.phase==='defend'"); wait(F, "S.phase==='attack'"); wait(G, "S.phase==='watch'")
            check('v26: the spectator watches the same map and starter maze', ev(G, MAP) == ev(E, MAP) and ev(G, ST) == ev(E, ST) and ev(G, 'S.rounds') == ev(E, 'S.rounds'))
            E.bring_to_front(); E.wait_for_timeout(300)
            check('v26: a player sees how many watch', E.is_visible('#btn-watch') and E.inner_text('#watch-n') == '1', E.inner_text('#watch-n'))
            E.click('#btn-watch'); E.wait_for_timeout(300)
            link = E.evaluate('()=>navigator.clipboard.readText().catch(()=>"")')
            check('v26: and copies the watch link (the page with #watch-CODE)', link.endswith('room.html#watch-SPEC') or 'watch-SPEC' in E.inner_text('#toast'), link or E.inner_text('#toast'))
            E.evaluate(TOWERS, 5); E.click('#def-lock'); E.wait_for_timeout(500)
            check('v26: a plan one side locked never reaches a spectator before the other locks', ev(G, 'Object.keys(window.siegeline.spec.dp).length + Object.keys(window.siegeline.spec.ap).length') == 0 and ev(G, 'S.phase') == 'watch' and ev(G, 'S.grid.some(g=>g&&g.t==="tower")') is False)
            G.bring_to_front(); G.wait_for_timeout(300)
            check("v26: the spectator's panel shows who's locked in", 'LOCKED IN' in G.inner_text('#spec-body').upper() and 'PLANNING' in G.inner_text('#spec-body').upper(), G.inner_text('#spec-body').replace('\n', ' '))
            G.screenshot(path=f'{SHOTS}/s1_watch.png')
            attack_round(F, [6, 2, 3])
            for pg in (E, F, G): wait(pg, "S.phase==='wave'")
            for pg in (E, F, G): pg.evaluate('()=>window.siegeline.advance(300)')
            for pg in (E, F, G): wait(pg, "S.phase==='summary'")
            same(E, F, 'v26 round 1: the players end alike')
            same(E, G, 'v26 round 1: the spectator played the same wave to the same end')
            check("v26: the spectator's summary names the sides and counts down to the next round", 'DEFENDER' in G.inner_text('#sum-body').upper() and 'watch round 2' in G.inner_text('#sum-next').lower(), G.inner_text('#sum-next'))
            for pg in (E, F): pg.click('#sum-next')
            if G.is_visible('#ov-sum'): G.click('#sum-next')
            wait(E, "S.phase==='defend' && S.round===2"); wait(G, "S.phase==='watch' && S.round===2")
            # a late arrival who joins with the code (not the watch link) watches the running match, from the current round
            Hp = ctx.new_page(); errors_hook(Hp, errs); Hp.goto('http://127.0.0.1:8765/room.html'); Hp.wait_for_timeout(300)
            Hp.click('#info-go'); Hp.fill('#mode-code', 'SPEC'); Hp.click('#mode-join')
            wait(Hp, "N.role==='spec' && S.phase==='watch'")
            SIG = '[S.round, S.keep, S.dFree, S.aFree, S.grid.map(g=>g?g.t[0]:0).join(""), [...S.bridges].join()]'
            check('v26: someone who joins a running match watches it, from where it is', ev(Hp, SIG) == ev(G, SIG), f"{ev(Hp, SIG)[:4]} / {ev(G, SIG)[:4]}")
            E.bring_to_front(); E.wait_for_timeout(300)
            check('v26: the players see two watching', E.inner_text('#watch-n') == '2', E.inner_text('#watch-n'))
            E.evaluate(TOWERS, 7); E.click('#def-lock'); attack_round(F, [8, 3, 4])
            for pg in (E, F, G, Hp): wait(pg, "S.phase==='wave'")
            for pg in (E, F, G, Hp): pg.evaluate('()=>window.siegeline.advance(300)')
            for pg in (E, F, G, Hp): wait(pg, "S.phase==='summary' || S.phase==='over'")
            same(E, G, 'v26 round 2: the first spectator still alike')
            same(E, Hp, 'v26 round 2: the late spectator played the same wave to the same end')
            # watching needs no taps: a spectator's summary closes by itself; a touch keeps it open; the bar reopens it
            G.click('#sum-body .sum-title')
            wait(Hp, "S.phase==='watch'", 9000)
            check("v26: a spectator's summary closes by itself after a few seconds", Hp.is_hidden('#ov-sum') and ev(Hp, 'S.round') == 3)
            check('v26: a touch on the summary keeps it open', G.is_visible('#ov-sum') and ev(G, 'S.phase') == 'summary')
            check("v26: the spectator's bar keeps the last wave in a line", 'Wave 2' in Hp.inner_text('#spec-last'), Hp.inner_text('#spec-last'))
            Hp.click('#spec-last [data-spec=sum]'); Hp.wait_for_timeout(200)
            check('v26: …and reopens its summary', Hp.is_visible('#ov-sum') and 'round 2 of' in Hp.inner_text('#sum-body').lower() and 'back' in Hp.inner_text('#sum-next').lower())
            Hp.click('#sum-next'); Hp.wait_for_timeout(200)
            check('v26: …which closes back to watching, the round unchanged', Hp.is_hidden('#ov-sum') and ev(Hp, '[S.phase, S.round]') == ['watch', 3])
            G.click('#sum-next'); wait(G, "S.phase==='watch'")
            G.click('#spec-leave'); G.wait_for_timeout(600)
            E.bring_to_front(); E.wait_for_timeout(300)
            check('v26: a spectator who leaves goes back to the start screen, and the count drops', G.is_visible('#ov-mode') and not ev(G, 'N.on') and E.inner_text('#watch-n') == '1', E.inner_text('#watch-n'))
            for pg in (E, F, G, Hp): pg.close()
            # ---------- a build with another protocol version (main) never joins this one ----------
            if OLD:
                C = ctx.new_page(); D = ctx.new_page()
                for pg in (C, D): errors_hook(pg, errs)
                C.goto('http://127.0.0.1:8765/old.html'); D.goto('http://127.0.0.1:8765/room.html'); C.wait_for_timeout(300)
                join_old(C, 'def', 'MIXD'); join(D, 'atk', 'MIXD')
                D.wait_for_timeout(2500)
                check('other protocol version: both stay in the lobby, apart', ev(C, "N.st") == 'lobby' and ev(D, "N.st") == 'lobby' and 'Nobody is in room' in D.inner_text('#mode-status'), D.inner_text('#mode-status'))
                for pg in (C, D): pg.close()
            else: print('SKIP protocol check: main speaks the same protocol')
            check('no page errors (room)', not errs, errs[:5])
            A.close(); B.close(); ctx.close()

        # ---------- PeerJS transport (outside Claude) ----------
        ctx = br.new_context(viewport={'width': 1280, 'height': 800})
        ctx.add_init_script(GUIDE_SEEN)  # the wave plan's How to use card has been seen
        ctx.add_init_script("window.SIEGE_PEER_OPTS={host:'127.0.0.1',port:9000,path:'/myapp',config:{iceServers:[]}};")
        ctx.route('https://cdn.jsdelivr.net/npm/peerjs@1.5.4/dist/peerjs.min.js', lambda r: r.fulfill(path=PEERJS, content_type='application/javascript'))
        errs = []
        A = ctx.new_page(); B = ctx.new_page()
        for pg in (A, B): errors_hook(pg, errs); pg.goto('http://127.0.0.1:8765/index.html')
        A.wait_for_timeout(300)
        join(A, 'atk', 'PEER'); A.wait_for_timeout(1500)
        check('peer: first player waits', 'Nobody is in room' in A.inner_text('#mode-status'), A.inner_text('#mode-status'))
        join(B, 'def', 'PEER'); start(B, 20000)
        wait(A, "N.st==='play'", 20000); wait(B, "N.st==='play'", 20000)
        check('v26: peer to peer has no watch link', A.is_hidden('#btn-watch') and ev(A, 'N.kind') == 'peer to peer')
        check('peer: connected and playing', ev(A, "N.kind") == 'peer to peer' and ev(B, "S.phase") == 'defend')
        defend_round(B, walls=[idx(4, r) for r in range(0, 10)], towers=[(idx(6, 5), None)]); attack_round(A, [6, 2, 4])
        wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
        for pg in (A, B): pg.evaluate('()=>window.siegeline.advance(300)')
        wait(A, "S.phase==='summary'"); wait(B, "S.phase==='summary'")
        same(A, B, 'peer: round 1 identical')
        A.click('#sum-next'); B.click('#sum-next')
        # the dialing side drops and reconnects
        wait(A, "S.phase==='attack'")
        B.close()
        try: A.wait_for_function("()=>document.querySelector('#netpill').textContent.toLowerCase().includes('offline')", timeout=10000)
        except Exception: pass
        check('peer: opponent offline shown', 'offline' in A.inner_text('#netpill').lower(), A.inner_text('#netpill'))
        B = ctx.new_page(); errors_hook(B, errs); B.goto('http://127.0.0.1:8765/index.html'); B.wait_for_timeout(300)
        join(B, 'def', 'PEER')
        B.wait_for_selector('#mode-restart:not([hidden])', timeout=15000)
        B.click('#mode-restart')
        wait(A, "S.round===1 && S.phase==='attack' && N.ep===2", 15000)
        check('peer: rejoin and restart works', ev(B, "S.phase") == 'defend')
        # The host side drops after the defender locked in: the rejoining device must restart the match.
        defend_round(B)
        A.close()
        A = ctx.new_page(); errors_hook(A, errs); A.goto('http://127.0.0.1:8765/index.html'); A.wait_for_timeout(300)
        join(A, 'atk', 'PEER')
        A.wait_for_selector('#mode-restart:not([hidden])', timeout=40000)
        A.click('#mode-restart')
        wait(B, "N.ep===3 && S.phase==='defend' && N.lk===0", 15000)
        check('peer: host rejoin works', ev(A, "S.phase") == 'attack' and B.is_hidden('#ov-wait'))
        check('no page errors (peer)', not errs, errs[:5])
        ctx.close()

        # ---------- phone layout of the new screens ----------
        ctx = br.new_context(viewport={'width': 390, 'height': 844}, has_touch=True, is_mobile=True, device_scale_factor=2)
        ctx.add_init_script(GUIDE_SEEN)  # the wave plan's How to use card has been seen
        P1 = ctx.new_page(); P1.goto('http://127.0.0.1:8765/room.html'); P1.wait_for_timeout(400)
        P1.tap('#info-go'); P1.wait_for_timeout(200)
        P1.screenshot(path=f'{SHOTS}/p1_mode.png')
        check('phone: mode picker fits', P1.evaluate('()=>document.documentElement.scrollWidth<=innerWidth'))
        P1.fill('#mode-code', 'FONE'); P1.tap('#mode-host')
        P2 = ctx.new_page(); P2.goto('http://127.0.0.1:8765/room.html'); P2.wait_for_timeout(300)
        P2.tap('#info-go'); P2.fill('#mode-code', 'FONE'); P2.tap('#mode-join')
        P1.wait_for_selector('#lobby-start:not([disabled])', timeout=10000)
        P1.screenshot(path=f'{SHOTS}/p1_lobby.png')
        check('v26 phone: the room fits 390 px', P1.evaluate('()=>document.documentElement.scrollWidth<=innerWidth && document.querySelector("#ov-lobby").scrollWidth<=innerWidth'))
        P1.tap('#lobby-start')
        P3 = ctx.new_page(); P3.goto('http://127.0.0.1:8765/room.html#watch-FONE')
        wait(P3, "S.phase==='watch'", 15000); P3.wait_for_timeout(2500)
        bar = P3.evaluate('()=>[Math.round(document.querySelector("#pane-spec").getBoundingClientRect().height), Math.round(document.querySelector("#board").getBoundingClientRect().height), document.documentElement.scrollWidth<=innerWidth]')
        P3.screenshot(path=f'{SHOTS}/p5_watch.png')
        check('v26 phone: the spectator bar is slim and the board keeps its room', bar[0] <= 200 and bar[1] >= 480 and bar[2], bar)
        P3.close()
        wait(P1, "S.phase==='defend'")
        P1.wait_for_timeout(300)
        P1.screenshot(path=f'{SHOTS}/p2_defend.png')
        P1.evaluate("()=>document.querySelector('#def-lock').click()")
        P1.wait_for_timeout(300)
        P1.screenshot(path=f'{SHOTS}/p3_wait.png')
        check('phone: wait card visible', P1.is_visible('#ov-wait'))
        P2.wait_for_timeout(200)
        P2.screenshot(path=f'{SHOTS}/p4_attack_clock.png')
        bx = lambda sel: P2.locator(sel).bounding_box()
        boxes = {k: bx(k) for k in ('#clockbox', '#netpill', '#potbox', '.keepbox', '.roundchip')}
        apart = lambda a, b: a['x'] + a['width'] <= b['x'] + 0.5 or b['x'] + b['width'] <= a['x'] + 0.5 or a['y'] + a['height'] <= b['y'] + 0.5 or b['y'] + b['height'] <= a['y'] + 0.5
        ks = list(boxes)
        check('phone: the HUD holds the clock, net pill and pot without overlap or clipping', all(boxes.values()) and all(b['x'] >= 0 and b['x'] + b['width'] <= 390 for b in boxes.values())
              and all(apart(boxes[a], boxes[b]) for i, a in enumerate(ks) for b in ks[i + 1:]), json.dumps(boxes)[:300])
        check('phone: no horizontal overflow', P1.evaluate('()=>document.documentElement.scrollWidth<=innerWidth'))
        ctx.close()
        br.close()
finally:
    srv.terminate(); peersrv.terminate()
print('\nFAILURES:', len(fails), fails)
