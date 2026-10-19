"""Shared helpers for the Siegeline tools. Everything is relative to the repo, so the tools work in any checkout.

The game is one file (index.html). Tools never edit it: they write modified copies into tools/.build/ and load
those in headless Chromium through Playwright.
"""
import os

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)
GAME = os.path.join(ROOT, 'index.html')
BUILD = os.path.join(TOOLS, '.build')
os.makedirs(BUILD, exist_ok=True)


def game_html():
    with open(GAME, encoding='utf-8') as f:
        return f.read()


def inject_head(html, extra):
    """Put extra markup right after <head> (index.html is a full document)."""
    assert '<head>' in html, 'index.html should have a <head>'
    return html.replace('<head>', '<head>' + extra, 1)


def write_build(name, html):
    path = os.path.join(BUILD, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return path


# Internals the simulators need. Exposed only in the tools' copy of the page, never in the shipped game.
SIM_HOOK = ("window.siegeline = { _i: { startWave, recompute, newState, defaultTower, unitCost, towerCost, towerValue, "
            "UPRESETS, makeDesign, COLORS, pathLen, RULES, TS, US, brainPlan, decodeGrid, decodeArmy, decodeCharges, bridgePicks, bridgeCost, blockBridges, SOLO, makeTerrain, startMap, mazeRoom, ROUGH, ROCK, sellOff, keepFees, "
            "get S(){return S}, set S(v){S=v} },")

# Optional test-only knobs: each one rewrites a line of the copy so a sim can scale something without editing the
# game. If a line changed in index.html the knob is skipped (and reported), the rest still works.
KNOBS = [
    ('hit = dps / rate', 'hit = dps * (RULES.dmgScale || 1) / rate', 'dmgScale: multiply all tower damage'),
    ('speed: US.speed.steps[d.speed]', 'speed: US.speed.steps[d.speed] * (RULES.spdScale || 1)', 'spdScale: multiply all unit speed'),
    ('const d = S.sentArmy[di], hp = US.hp.steps[d.hp];', 'const d = S.sentArmy[di], hp = US.hp.steps[d.hp] * (RULES.hpScale || 1);', 'hpScale: multiply all unit health'),
    ('d = Math.max(d * 0.2, d - u.armor);', 'd = Math.max(d * (RULES.armorFloor || 0.2), d - u.armor);', 'armorFloor: share of a hit that always gets through armor'),
]


def sim_page():
    """index.html + internals hook + knobs + the AI players, written to tools/.build/sim.html."""
    src = game_html()
    assert src.count('window.siegeline = {') == 1, 'cannot find the window.siegeline handle in index.html'
    src = src.replace('window.siegeline = {', SIM_HOOK)
    for a, b, _ in KNOBS:
        if src.count(a) == 1:
            src = src.replace(a, b)
        else:
            print(f'note: knob skipped, line not found: {a}')
    tail = ('<script>window.__baseRules = JSON.parse(JSON.stringify(window.siegeline._i.RULES));</script>'
            '<script src="../sim/ai.js"></script>')
    src = src.replace('</body>', tail + '</body>', 1)
    return write_build('sim.html', src)


def launch(p):
    """Chromium with WebRTC host candidates visible (needed for the local peer-to-peer tests)."""
    return p.chromium.launch(args=['--disable-features=WebRtcHideLocalIpsWithMdns'])
