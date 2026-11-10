"""v23: a cheap tower at the front against a knock-out sapper. How often does the sapper reach the tower it's sent
for, with and without sapper armor? The bots' maze (4 wall columns) with five default towers further on; the screen is
a tower in the first wall column, where the route passes it on both sides. One knock-out sapper aimed at the last
tower: alone leaving at 2% of the wave, or with 6 runners leaving at 2% or 15%; 20 seeds each. v22.2's tower prices (they don't
change a wave).

  python tools/sim/sapscreen.py
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import sim_page, launch
from playwright.sync_api import sync_playwright

JS = r"""
([front, armor, sapT, seed, runners, rules]) => {
  const I = window.siegeline._i, COLS = 16, at = (c, r) => r * COLS + c;
  Object.assign(I.RULES, window.__baseRules, rules); I.RULES.sapper = { hp: 2, speed: 4, armor };
  I.S = I.newState(); const S = I.S;
  const WC = [3, 6, 9, 12], cells = [];
  WC.forEach((c, k) => { const gap = k % 2 ? 10 : 0; for (let r = 0; r < 11; r++) if (r !== gap) S.grid[at(c, r)] = { t: 'wall', fresh: false }; });
  const T = (cfg, n) => ({ t: 'tower', cfg: { ...I.defaultTower(), ...cfg }, fee: 0, off: 0, fresh: false, n, cd: 0, ang: Math.PI, kick: 0, dealt: 0 });
  // the screen: in the first wall column, where the route passes it on both sides; then five default towers further on
  if (front) S.grid[at(3, 7)] = T(front, 1);
  [[6, 5], [9, 5], [12, 5], [6, 2], [12, 8]].forEach(([c, r], k) => { S.grid[at(c, r)] = T({}, k + 2); });
  S.seenGrid = S.grid.map(g => (g ? { ...g, cfg: g.cfg ? { ...g.cfg } : undefined } : null));
  S.seenVer++; S.seenRound = 1; S.round = 2; S.rounds = 8; S.keep = 1e9; I.recompute();
  const target = at(12, 8);
  S.designs = [I.makeDesign('Runner', 'Runner', I.COLORS[0])]; S.designs[0].count = runners; S.designs[0].tl = { s: 0, e: 0.25, pos: null };
  S.charges = I.sapPlan(S.seenGrid, S.bridges, [[target, 'tower']], sapT, { bridgeTries: 0, koTries: 0 });
  const cost = [...S.charges.values()][0] ? [...S.charges.values()][0].cost : 0;
  I.startWave(seed); window.siegeline.advance(600);
  return { state: S.sapList.map(s => s.state)[0] || 'none', cost, dKill: S.last ? S.last.dKill : null };
}
"""
FRONTS = {
    'none (no screen)': None,
    'cheap rapid fire: 18 dmg/s at 4 shots/s (40 coins)': {'rate': 0},
    'cheap: 13 dmg/s at 4 shots/s, 2 cells': {'dps': 1, 'range': 1, 'rate': 0},
    'default: 18 dmg/s at 1 shot/s (40 coins)': {},
    'heavy: 30 dmg/s at 0.4 shots/s': {'dps': 4, 'rate': 5},
}
with sync_playwright() as p:
    b = launch(p); pg = b.new_page()
    pg.goto('file://' + sim_page()); pg.wait_for_timeout(300)
    rules = {"rangePow": 2, "dpsPow": 1.15, "sapKillShare": 0.5, "moveFeeToAtk": False, "interestRate": 0, "freeAfterSabotage": False}
    for name, front in FRONTS.items():
        row = []
        for armor in (0, 1):
            n = ok = lost = 0
            for seed in range(1, 21):
                for sapT, runners in ((0.02, 0), (0.02, 6), (0.15, 6)):
                    r = pg.evaluate(JS, [front, armor, sapT, seed, runners, rules])
                    n += 1; ok += r['state'] == 'done'; lost += r['state'] == 'lost'
            row.append(f'{100 * ok / n:3.0f}% landed, {100 * lost / n:3.0f}% shot down')
        print(f'{name:52s} armor 0: {row[0]}   armor 1: {row[1]}', flush=True)
    b.close()
