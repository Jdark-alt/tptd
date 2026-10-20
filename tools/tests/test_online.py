"""Online suite: lobby, ready gating, hidden plans, identical waves on both devices (also at 10x), desyncs,
   rematch/swap, drop and rejoin, both devices building the same map (terrain), plus the peer-to-peer path.
   The room scenarios click known cells, so they play without terrain. Needs: npm install in tools/tests.
   python tools/tests/test_online.py        (add "peer" to run only the peer-to-peer part)"""
import os, sys, json, subprocess, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import game_html, write_build, BUILD, ROOT, TOOLS, launch
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
    """Known cells are clicked, so no terrain; and sappers get top health so the planned sabotage always arrives."""
    for pg in pgs: pg.evaluate('()=>{const R=window.siegeline.rules; R.roughShare=0; R.rockShare=0; R.sapper.hp=9;}')
def join(pg, role, code):
    pg.click('#info-go')
    pg.wait_for_selector('#ov-mode:not([hidden])')
    pg.click(f'.rolepick button[data-role={role}]')
    pg.fill('#mode-code', code)
    pg.click('#mode-online')

def defend_round(pg, walls=(), towers=(), lock=True):
    wait(pg, "S.phase==='defend' && S.step===0")
    # known cells are clicked: with hints on, a glowing tile would place the hint's whole set
    if pg.get_attribute('#def-steps [data-act=hints]', 'aria-pressed') == 'true': pg.click('#def-steps [data-act=hints]')
    for c in walls: cell(pg, c)
    if towers: pg.click('.tool[data-tool=tower]')
    for c, cfg in towers:
        cell(pg, c)
        if cfg: pg.evaluate(f'()=>{{const g=window.siegeline.state.grid[{c}]; Object.assign(g.cfg,{json.dumps(cfg)});}}')
    pg.click('#def-next'); pg.wait_for_timeout(120)
    if lock: pg.click('#def-next')

def attack_round(pg, counts, lock=True, extra=''):
    wait(pg, "S.phase==='attack' && S.step===0")
    pg.evaluate('''(counts)=>{const sl=window.siegeline,S=sl.state; counts.forEach((n,k)=>{ if(!S.designs[k]) return; const d=S.designs[k]; const add=n-d.count; S.aFree-=add*sl.unitCost(d); d.count=n; }); }''', counts)
    if extra: pg.evaluate(f'()=>{{{PRE}{extra}}}')
    for _ in range(3): pg.click('#atk-next'); pg.wait_for_timeout(80)
    if lock: pg.click('#atk-next')

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
            errs = []
            A = ctx.new_page(); B = ctx.new_page()
            for pg in (A, B): errors_hook(pg, errs)
            A.goto('http://127.0.0.1:8765/room.html'); B.goto('http://127.0.0.1:8765/room.html')
            A.wait_for_timeout(400); no_terrain(A, B)

            # ---------- lobby ----------
            A.click('#info-go')
            check('mode picker opens after the intro', A.is_visible('#ov-mode'))
            check('connect disabled until a side is picked', A.is_disabled('#mode-online'))
            code = A.input_value('#mode-code')
            check('a match code is suggested', len(code) == 4, code)
            A.click('.rolepick button[data-role=def]'); A.fill('#mode-code', 'TEST'); A.click('#mode-online')
            A.wait_for_timeout(400)
            check('defender waits for opponent', 'Waiting for your opponent' in A.inner_text('#mode-status'), A.inner_text('#mode-status'))
            A.screenshot(path=f'{SHOTS}/o1_lobby_waiting.png')
            join(B, 'atk', 'test')
            wait(A, "N.st==='play' && S.phase==='defend'"); wait(B, "N.st==='play' && S.phase==='attack'")
            check('both start: defender plans', ev(A, "S.phase") == 'defend' and A.is_hidden('#ov-mode'))
            check('both start: attacker plans', ev(B, "S.phase") == 'attack' and B.is_hidden('#ov-mode'))
            check('no handoff screens online', A.is_hidden('#ov-hand') and B.is_hidden('#ov-hand'))
            check('net pill visible', A.is_visible('#netpill'), A.inner_text('#netpill'))

            # ---------- round 1: defender locks first ----------
            maze = [idx(3, r) for r in range(0, 9)] + [idx(7, r) for r in range(2, 11)]
            defend_round(A, walls=maze, towers=[(idx(5, 4), None), (idx(9, 6), {'splash': 1, 'rate': 4})])
            A.wait_for_timeout(300)
            check('defender sees the wait card', A.is_visible('#ov-wait'), A.inner_text('#wait-sub'))
            check('wait card names the attacker', 'attacker' in A.inner_text('#wait-sub'))
            check('attacker is told the defender is ready', 'ready' in B.inner_text('#netpill').lower(), B.inner_text('#netpill'))
            check('attacker hint mentions waiting opponent', 'ready and waiting' in B.inner_text('#t-hint'))
            check('defender plan is not revealed before both lock', ev(B, "N.peer && N.peer.plan") is None and ev(B, "S.grid.every(g=>!g)"))
            check('wave has not started', ev(A, "S.phase") == 'defend' and ev(B, "S.phase") == 'attack')
            attack_round(B, [8, 2, 6])
            wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
            check('wave starts once both are ready', True)
            check('attacker now sees the real maze', ev(B, "S.grid.filter(g=>g&&g.t==='wall').length") == len(maze))
            check('defender now sees the army', ev(A, "S.designs.map(d=>d.count).join()") == '8,2,6')
            check('spawn schedules identical', A.evaluate('()=>JSON.stringify(window.siegeline.state.spawnList)') == B.evaluate('()=>JSON.stringify(window.siegeline.state.spawnList)'))
            A.screenshot(path=f'{SHOTS}/o2_wave_def.png')
            for pg in (A, B): pg.evaluate('()=>window.siegeline.advance(300)')
            wait(A, "S.phase==='summary'"); wait(B, "S.phase==='summary'")
            same(A, B, 'round 1 results identical on both devices')
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
            B.click('#atk-next')
            B.wait_for_timeout(200)
            check('attacker locks in first', B.is_visible('#ov-wait'))
            B.click('#wait-back')
            check('keep planning unlocks', B.is_hidden('#ov-wait') and ev(B, "N.lk") == 0)
            A.wait_for_timeout(200)
            check('defender sees attacker planning again', 'planning' in A.inner_text('#netpill').lower(), A.inner_text('#netpill'))
            B.evaluate('()=>{const S=window.siegeline.state;S.designs[0].count=12;S.aFree-=2*window.siegeline.unitCost(S.designs[0]);}')
            B.click('#atk-next')
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
            A.evaluate("()=>document.querySelector('#def-next').click()"); B.evaluate("()=>document.querySelector('#atk-next').click()")
            wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
            check('simultaneous lock-in starts the wave on both', True)
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
            join(C, 'def', 'CLSH'); join(D, 'def', 'CLSH')
            C.wait_for_timeout(500)
            check('same side in lobby is flagged', 'also picked' in C.inner_text('#mode-status'), C.inner_text('#mode-status'))
            D.click('.rolepick button[data-role=atk]')
            wait(C, "N.st==='play' && S.phase==='defend'"); wait(D, "N.st==='play' && S.phase==='attack'")
            check('switching side in lobby starts the match', True)
            check('max presence size', ev(A, 'window.__maxPresence||0') < 4096, max(ev(pg, 'window.__maxPresence||0') for pg in (A, B, C, D)))
            for pg in (C, D): pg.close()
            # ---------- terrain: both devices build the same map, play the same wave on it, and a rematch brings a new one ----------
            C = ctx.new_page(); D = ctx.new_page()
            for pg in (C, D): errors_hook(pg, errs); pg.goto('http://127.0.0.1:8765/room.html')
            C.wait_for_timeout(300)
            join(C, 'def', 'TERR'); join(D, 'atk', 'TERR')
            wait(C, "N.st==='play' && S.phase==='defend'"); wait(D, "N.st==='play' && S.phase==='attack'")
            MAP = '[S.mapSeed,[...S.terrain].join(""),S.grid.map(g=>g&&g.t==="rock"?1:0).join("")]'
            m1 = ev(C, MAP)
            check('terrain: both devices build the same map', m1 == ev(D, MAP) and '1' in m1[1] and '2' in m1[1], m1[0])
            check('terrain: the attacker sees the rock from the start', ev(D, 'S.seenGrid.filter(g=>g&&g.t==="rock").length') == m1[1].count('2'))
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
            # ---------- a build with another protocol version (main) never joins this one ----------
            if OLD:
                C = ctx.new_page(); D = ctx.new_page()
                for pg in (C, D): errors_hook(pg, errs)
                C.goto('http://127.0.0.1:8765/old.html'); D.goto('http://127.0.0.1:8765/room.html'); C.wait_for_timeout(300)
                join(C, 'def', 'MIXD'); join(D, 'atk', 'MIXD')
                D.wait_for_timeout(2500)
                check('other protocol version: both stay in the lobby', ev(C, "N.st") == 'lobby' and ev(D, "N.st") == 'lobby' and 'Waiting' in D.inner_text('#mode-status'), D.inner_text('#mode-status'))
                for pg in (C, D): pg.close()
            else: print('SKIP protocol check: main speaks the same protocol')
            check('no page errors (room)', not errs, errs[:5])
            A.close(); B.close(); ctx.close()

        # ---------- PeerJS transport (outside Claude) ----------
        ctx = br.new_context(viewport={'width': 1280, 'height': 800})
        ctx.add_init_script("window.SIEGE_PEER_OPTS={host:'127.0.0.1',port:9000,path:'/myapp',config:{iceServers:[]}};")
        ctx.route('https://cdn.jsdelivr.net/npm/peerjs@1.5.4/dist/peerjs.min.js', lambda r: r.fulfill(path=PEERJS, content_type='application/javascript'))
        errs = []
        A = ctx.new_page(); B = ctx.new_page()
        for pg in (A, B): errors_hook(pg, errs); pg.goto('http://127.0.0.1:8765/index.html')
        A.wait_for_timeout(300)
        join(A, 'atk', 'PEER'); A.wait_for_timeout(1500)
        check('peer: first player waits', 'Waiting' in A.inner_text('#mode-status'), A.inner_text('#mode-status'))
        join(B, 'def', 'PEER')
        wait(A, "N.st==='play'", 20000); wait(B, "N.st==='play'", 20000)
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
        P1 = ctx.new_page(); P1.goto('http://127.0.0.1:8765/room.html'); P1.wait_for_timeout(400)
        P1.tap('#info-go'); P1.wait_for_timeout(200)
        P1.screenshot(path=f'{SHOTS}/p1_mode.png')
        check('phone: mode picker fits', P1.evaluate('()=>document.documentElement.scrollWidth<=innerWidth'))
        P1.tap('.rolepick button[data-role=def]'); P1.fill('#mode-code', 'FONE'); P1.tap('#mode-online')
        P2 = ctx.new_page(); P2.goto('http://127.0.0.1:8765/room.html'); P2.wait_for_timeout(300)
        P2.tap('#info-go'); P2.tap('.rolepick button[data-role=atk]'); P2.fill('#mode-code', 'FONE'); P2.tap('#mode-online')
        wait(P1, "S.phase==='defend'")
        P1.wait_for_timeout(300)
        P1.screenshot(path=f'{SHOTS}/p2_defend.png')
        P1.evaluate("()=>{const b=document.querySelector('#def-next'); b.click(); b.click();}")
        P1.wait_for_timeout(300)
        P1.screenshot(path=f'{SHOTS}/p3_wait.png')
        check('phone: wait card visible', P1.is_visible('#ov-wait'))
        check('phone: no horizontal overflow', P1.evaluate('()=>document.documentElement.scrollWidth<=innerWidth'))
        ctx.close()
        br.close()
finally:
    srv.terminate(); peersrv.terminate()
print('\nFAILURES:', len(fails), fails)
