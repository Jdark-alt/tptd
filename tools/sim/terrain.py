"""Terrain check: the same matches with and without terrain, on many maps (one map per seed).

  python tools/sim/terrain.py --maps 1000                       # only the map generator's stats
  python tools/sim/terrain.py --seeds 30                        # counter bot vs every sim strategy, seeds 1-30
  python tools/sim/terrain.py --defenders game:normal --attackers 'swarm,rush,counter + bridges' --seeds 20
  python tools/sim/terrain.py --seed0 31 --seeds 10 --out tools/.build/terrain_b.jsonl   # split across processes
  python tools/sim/terrain.py --summary tools/.build/terrain_a.jsonl tools/.build/terrain_b.jsonl

Every match runs twice, with the game's terrain shares and with none (the same seed, so the same spawn jitter).
The summary gives the attacker win rate and keep left both ways, then per map the attacker win rate across all
its matches, and flags maps where the attacker wins far more or far less often than on the same seeds without
terrain (--flag, in percentage points). Flagged maps are drawn as text: # rock, : rough ground, E entry, K keep.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import sim_page, launch, BUILD
from playwright.sync_api import sync_playwright
from match import ATTACKERS, DEFENDERS, GAME_RULES_OPTS

ap = argparse.ArgumentParser()
ap.add_argument('--maps', type=int, default=0, help='print map generator stats over this many seeds and stop')
ap.add_argument('--attackers', default='all', help='comma-separated names (substring match), "all", or "computer"')
ap.add_argument('--defenders', default='counter')
ap.add_argument('--seeds', type=int, default=30)
ap.add_argument('--seed0', type=int, default=1)
ap.add_argument('--rules', default='{}', help='JSON overrides for RULES in both runs (the "without" run also sets the shares to 0)')
ap.add_argument('--out', default=os.path.join(BUILD, 'terrain.jsonl'))
ap.add_argument('--summary', nargs='*', help='summarise result files and stop')
ap.add_argument('--flag', type=float, default=35, help='flag maps whose attacker win rate moves this many points')
a = ap.parse_args()

MAP_SEED = 'seed => Math.imul(seed, 2654435761) >>> 0'  # the map each match seed gets in ai.js runMatch

def draw(T):
    rows = []
    for r in range(11):
        row = ''
        for c in range(16):
            i = r * 16 + c
            row += 'E' if i == 80 else 'K' if i == 95 else '#' if T[i] == 2 else ':' if T[i] == 1 else '.'
        rows.append('      ' + row)
    return '\n'.join(rows)

def summary(files):
    rows = [json.loads(l) for f in files for l in open(f)]
    on = [r for r in rows if r['terrain']]; off = {(r['seed'], r['d'], r['a']): r for r in rows if not r['terrain']}
    pairs = [(r, off[(r['seed'], r['d'], r['a'])]) for r in on if (r['seed'], r['d'], r['a']) in off]
    if not pairs: print('no paired results'); return
    w_on = sum(r['winner'] == 'attacker' for r, _ in pairs); w_off = sum(o['winner'] == 'attacker' for _, o in pairs)
    k_on = sum(r['keep'] for r, _ in pairs) / len(pairs); k_off = sum(o['keep'] for _, o in pairs) / len(pairs)
    print(f'{len(pairs)} matches on {len({r["seed"] for r, _ in pairs})} maps')
    print(f'  attacker wins with terrain {w_on}/{len(pairs)} ({100 * w_on / len(pairs):.0f}%), without {w_off}/{len(pairs)} ({100 * w_off / len(pairs):.0f}%)')
    print(f'  mean keep left with terrain {k_on:.0f}, without {k_off:.0f}')
    flips = sum((r['winner'] == 'attacker') != (o['winner'] == 'attacker') for r, o in pairs)
    print(f'  matches whose winner changes with terrain: {flips} ({100 * flips / len(pairs):.0f}%)')
    by = {}
    for r, o in pairs: by.setdefault(r['d'], []).append((r, o))
    for d, ps in sorted(by.items()):
        print(f'  {d:12s} attacker wins with terrain {sum(r["winner"] == "attacker" for r, _ in ps)}/{len(ps)}, without {sum(o["winner"] == "attacker" for _, o in ps)}/{len(ps)}')
    print('per map (attacker wins with terrain / without, across its matches):')
    seeds = {}
    for r, o in pairs: seeds.setdefault(r['seed'], []).append((r, o))
    flagged = []
    for s, ps in sorted(seeds.items()):
        n = len(ps); on_r = sum(r['winner'] == 'attacker' for r, _ in ps) / n; off_r = sum(o['winner'] == 'attacker' for _, o in ps) / n
        d = 100 * (on_r - off_r)
        mark = '  <-- FLAG' if abs(d) >= a.flag else ''
        print(f'  seed {s:3d}: {100 * on_r:4.0f}% / {100 * off_r:4.0f}%  ({d:+4.0f})  keep {sum(r["keep"] for r, _ in ps) / n:4.0f} / {sum(o["keep"] for _, o in ps) / n:4.0f}{mark}')
        if mark: flagged.append((s, ps[0][0].get('map')))
    print(f'{len(flagged)} flagged map(s) (attacker win rate moved {a.flag:.0f}+ points)')
    for s, T in flagged:
        if T: print(f'  seed {s}:\n' + draw(T))

if a.summary:
    summary(a.summary); sys.exit()

page_path = sim_page()
with sync_playwright() as p:
    b = launch(p); pg = b.new_page()
    pg.goto('file://' + page_path); pg.wait_for_timeout(300)
    if a.maps:
        r = pg.evaluate('''([n, ms]) => {
          const I = window.siegeline._i, COLS = 16, N = 176, mapSeed = eval(ms);
          const out = { tries: {}, fallback: 0, rough: {}, rock: {}, zoneMax: 0, clusterMax: 0, room: [] };
          const empty = I.mazeRoom(new Uint8Array(N)), ZC = [0, 5, 11, 16], ZR = [0, 4, 7, 11];
          for (let seed = 1; seed <= n; seed++) {
            const m = I.makeTerrain(mapSeed(seed)), T = m.T, cnt = k => T.filter(v => v === k).length;
            out.tries[m.tries] = (out.tries[m.tries] || 0) + 1; if (m.scale < 1) out.fallback++;
            out.rough[cnt(I.ROUGH)] = (out.rough[cnt(I.ROUGH)] || 0) + 1; out.rock[cnt(I.ROCK)] = (out.rock[cnt(I.ROCK)] || 0) + 1;
            for (const k of [I.ROUGH, I.ROCK]) for (let zr = 0; zr < 3; zr++) for (let zc = 0; zc < 3; zc++) {
              let z = 0; for (let r = ZR[zr]; r < ZR[zr + 1]; r++) for (let c = ZC[zc]; c < ZC[zc + 1]; c++) if (T[r * COLS + c] === k) z++;
              out.zoneMax = Math.max(out.zoneMax, z);
            }
            const seen = new Set();
            for (let i = 0; i < N; i++) if (T[i] && !seen.has(i)) {
              const st = [i]; seen.add(i); let sz = 0;
              while (st.length) { const j = st.pop(); sz++; for (const k of [j - 1, j + 1, j - COLS, j + COLS]) if (k >= 0 && k < N && Math.abs((k % COLS) - (j % COLS)) <= 1 && T[k] && !seen.has(k)) { seen.add(k); st.push(k); } }
              out.clusterMax = Math.max(out.clusterMax, sz);
            }
            out.room.push(I.mazeRoom(T) / empty);
          }
          out.room.sort((x, y) => x - y);
          out.room = { min: out.room[0], p10: out.room[Math.floor(n / 10)], median: out.room[Math.floor(n / 2)], max: out.room[n - 1] };
          return out;
        }''', [a.maps, MAP_SEED])
        print(f'{a.maps} maps: rough tiles {r["rough"]}, rock tiles {r["rock"]}, tries {r["tries"]}, fell back to fewer tiles {r["fallback"]}')
        print(f'  most of one kind in a 3x3 zone: {r["zoneMax"]}; largest cluster: {r["clusterMax"]} tiles')
        print('  longest route the computer\'s mazes can force, as a share of an empty board: ' + ', '.join(f'{k} {v:.0%}' for k, v in r['room'].items()))
        b.close(); sys.exit()
    rules = json.loads(a.rules)
    atk = ({k: v for k, v in ATTACKERS.items() if not k.startswith('computer')} if a.attackers == 'all'
           else {k: v for k, v in ATTACKERS.items() if any(s.strip() in k for s in a.attackers.split(','))})
    with open(a.out, 'a') as out:
        for seed in range(a.seed0, a.seed0 + a.seeds):
            T = pg.evaluate('([s, ms, r]) => { const I = window.siegeline._i; Object.assign(I.RULES, window.__baseRules, r); return [...I.makeTerrain(eval(ms)(s)).T]; }', [seed, MAP_SEED, rules])
            for dn in a.defenders.split(','):
                for an, ao in atk.items():
                    opts = {**GAME_RULES_OPTS, **ao}
                    for terrain in (True, False):
                        rr = {**rules} if terrain else {**rules, 'roughShare': 0, 'rockShare': 0}
                        res = pg.evaluate('([d,a,s,r]) => runMatch(d,a,s,r)', [DEFENDERS[dn], opts, seed, rr])
                        out.write(json.dumps({'seed': seed, 'd': dn, 'a': an, 'terrain': terrain, 'winner': res['winner'], 'keep': res['keep'], 'round': res['round'],
                                              'map': T if terrain else None}) + '\n')
                    out.flush()
            print(f'seed {seed} done', flush=True)
    b.close()
summary([a.out])
