"""Relay server suite (server.js): same-origin play, server restart mid-match, 65 s idle, a page hosted elsewhere,
   and a sleeping server waking up. Needs: npm install in the repo root.
   python tools/tests/test_relay.py"""
import os, sys, json, subprocess, time
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import ROOT
SRV = ROOT
HERE = os.path.dirname(os.path.abspath(__file__))
if not os.path.isdir(os.path.join(ROOT, 'node_modules', 'ws')):
    sys.exit('Run "npm install" in the repo root first (installs ws for server.js).')
PORT = 10123
BASE = f'http://127.0.0.1:{PORT}'
fails = []
def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  {info}' if info != '' else ''), flush=True)
    if not ok: fails.append(name)
PRE = "const S=window.siegeline.state,N=window.siegeline.net;"
def ev(pg, e): return pg.evaluate(f'()=>{{{PRE}return ({e});}}')
def wait(pg, e, t=20000): pg.wait_for_function(f'()=>{{{PRE}return !!({e});}}', timeout=t)
def snap(pg):
    return pg.evaluate('()=>{const S=window.siegeline.state;return {keep:S.keep,dFree:S.dFree,aFree:S.aFree,last:S.last,round:S.round,grid:S.grid.map(g=>g?g.t[0]:0).join("")}}')
def join(pg, role, code):
    pg.click('#info-go'); pg.wait_for_selector('#ov-mode:not([hidden])')
    pg.click(f'.rolepick button[data-role={role}]'); pg.fill('#mode-code', code); pg.click('#mode-online')
def cell(pg, i):
    x, y = pg.evaluate(f'()=>window.siegeline.cellToClient({i})'); pg.mouse.click(x, y)
def start_server():
    return subprocess.Popen(['node', 'server.js'], cwd=SRV, env={**os.environ, 'PORT': str(PORT)}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
def play_round(A, B, walls=()):
    wait(A, "S.phase==='defend'"); wait(B, "S.phase==='attack'")
    for c in walls: cell(A, c)
    A.evaluate("()=>{const b=document.querySelector('#def-next'); b.click(); b.click(); b.click();}")
    B.evaluate("()=>{const sl=window.siegeline,S=sl.state; S.designs[0].count=6; S.aFree-=6*sl.unitCost(S.designs[0]);}")
    B.evaluate("()=>{const b=document.querySelector('#atk-next'); b.click(); b.click(); b.click(); b.click();}")
    wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
    for pg in (A, B): pg.evaluate('()=>window.siegeline.advance(400)')
    wait(A, "S.phase==='summary'"); wait(B, "S.phase==='summary'")
    sa, sb = snap(A), snap(B)
    return sa == sb, sa

srv = start_server()
web = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1'], cwd=SRV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1.2)
try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        errs = []
        def page(ctx, url):
            pg = ctx.new_page()
            pg.on('pageerror', lambda e: errs.append(str(e)))
            pg.goto(url); pg.wait_for_timeout(300)
            return pg

        # 1. Both players on the page served by the relay server itself
        ctx = br.new_context(viewport={'width': 1280, 'height': 800})
        A = page(ctx, BASE + '/'); B = page(ctx, BASE + '/')
        check('server injects same-origin relay', A.evaluate('()=>window.SIEGE_RELAY') == 'same-origin')
        join(A, 'def', 'RLY1'); A.wait_for_timeout(600)
        check('first player waits on the server', 'Waiting for your opponent' in A.inner_text('#mode-status'), A.inner_text('#mode-status'))
        join(B, 'atk', 'RLY1')
        wait(A, "N.st==='play'"); wait(B, "N.st==='play'")
        check('connected through the relay', ev(A, 'N.kind') == 'server relay' and ev(B, 'N.kind') == 'server relay')
        ok, s1 = play_round(A, B, walls=[16 * r + 4 for r in range(0, 9)])
        check('round 1 identical through the relay', ok, f"keep {round(s1['keep'],1)}")
        A.click('#sum-next'); B.click('#sum-next')

        # 2. Server restarts in the middle of planning (Render can restart free instances any time)
        wait(A, "S.phase==='defend'"); wait(B, "S.phase==='attack'")
        srv.terminate(); srv.wait()
        A.wait_for_timeout(1500)
        check('drop shows reconnecting', 'reconnect' in A.inner_text('#netpill').lower() or 'offline' in A.inner_text('#netpill').lower(), A.inner_text('#netpill'))
        A.evaluate("()=>{const b=document.querySelector('#def-next'); b.click(); b.click(); b.click();}")  # locks in while the server is down
        srv = start_server()
        wait(A, "N.linkUp && N.peer", 20000); wait(B, "N.linkUp && N.peer", 20000)
        check('both reconnect after a server restart', True)
        B.evaluate("()=>{const b=document.querySelector('#atk-next'); b.click(); b.click(); b.click(); b.click();}")
        wait(A, "S.phase==='wave'"); wait(B, "S.phase==='wave'")
        for pg in (A, B): pg.evaluate('()=>window.siegeline.advance(400)')
        wait(A, "S.phase==='summary'"); wait(B, "S.phase==='summary'")
        check('round 2 identical after the restart', snap(A) == snap(B))

        # 3. A long quiet stretch: heartbeats keep the connection alive (65 s with no game messages)
        A.click('#sum-next'); B.click('#sum-next')
        wait(A, "S.phase==='defend'")
        t0 = time.time(); A.wait_for_timeout(65000)
        check('still connected after 65 s idle', ev(A, 'N.linkUp') and ev(B, 'N.linkUp') and 'ATTACKER PLANNING' in A.inner_text('#netpill').upper(), A.inner_text('#netpill'))
        ctx.close()

        # 4. Page hosted elsewhere (like GitHub Pages) pointing at the relay
        ctx = br.new_context(viewport={'width': 1280, 'height': 800})
        ctx.add_init_script(f"window.SIEGE_RELAY='{BASE}';")
        A = page(ctx, 'http://127.0.0.1:8765/index.html'); B = page(ctx, 'http://127.0.0.1:8765/index.html')
        join(A, 'atk', 'GHP1'); join(B, 'def', 'GHP1')
        wait(A, "N.st==='play'"); wait(B, "N.st==='play'")
        ok, _ = play_round(B, A)
        check('cross-origin page plays through the relay', ok and ev(A, 'N.kind') == 'server relay')
        ctx.close()

        # 5. Server asleep when players connect: the page waits for it to wake
        srv.terminate(); srv.wait()
        ctx = br.new_context(viewport={'width': 1280, 'height': 800})
        ctx.add_init_script(f"window.SIEGE_RELAY='{BASE}';")
        A = page(ctx, 'http://127.0.0.1:8765/index.html'); B = page(ctx, 'http://127.0.0.1:8765/index.html')
        join(A, 'def', 'SLP1'); A.wait_for_timeout(5500)
        check('shows waking message', 'Waking the game server' in A.inner_text('#mode-status'), A.inner_text('#mode-status'))
        srv = start_server()
        join(B, 'atk', 'SLP1')
        wait(A, "N.st==='play'", 30000); wait(B, "N.st==='play'", 30000)
        check('connects once the server wakes', True)
        ctx.close()
        check('no page errors', not errs, errs[:4])
        br.close()
finally:
    srv.terminate(); web.terminate()
print('\nFAILURES:', len(fails), fails)
