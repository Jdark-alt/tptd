"""Exploit scan: every unit design on a grid, all coins in that one design, sent bunched and spread, against four
defenses of the same cost (plain, slow heavy hits, splash, a mix with frost and poison). A design is suspicious
when even the defense that suits it best lets a lot through.

  python tools/sim/scan.py                       # default grid, ~15 min on 2 CPUs (use --part 0/2 and 1/2 in parallel)
  python tools/sim/scan.py --rules '{"regenCap": 8}' --regen 3 --hp 6,9
  python tools/sim/scan.py --summary tools/.build/scan.jsonl

Results append to tools/.build/scan.jsonl (or --out); --summary prints the strongest designs.
"""
import argparse, itertools, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import sim_page, launch, BUILD
from playwright.sync_api import sync_playwright

DEFENSES = {  # six towers each in a 4-column maze; all land near 750 coins
    'basic': [{'dps': 4}] * 6,
    'heavy': [{'dps': 4, 'rate': 5}] * 6,
    'splash': [{'dps': 2, 'rate': 4, 'splash': 2}] * 6,
    'mixed': [{'dps': 4, 'rate': 5}, {'dps': 2, 'rate': 4, 'splash': 2}, {'dps': 4, 'rate': 5}, {'dps': 2, 'rate': 4, 'splash': 2},
              {'range': 3, 'dps': 1, 'rate': 3, 'slow': True}, {'dps': 2, 'rate': 5, 'poison': True}],
}
ints = lambda s: [int(x) for x in s.split(',')]
ap = argparse.ArgumentParser()
ap.add_argument('--rules', default='{}')
ap.add_argument('--hp', default='0,3,6,9'); ap.add_argument('--speed', default='0,4,7'); ap.add_argument('--armor', default='0,2,3')
ap.add_argument('--dodge', default='0,3'); ap.add_argument('--regen', default='0,3')
ap.add_argument('--budget', type=int, default=0, help='army coins (default: the cost of the plain defense)')
ap.add_argument('--part', default='0/1', help='k/n: run every n-th design starting at k, to split across processes')
ap.add_argument('--out', default=os.path.join(BUILD, 'scan.jsonl'))
ap.add_argument('--summary', default='', help='print a summary of an existing results file and exit')
a = ap.parse_args()

def name(d): return ' '.join(f'{k}{d[k]}' for k in ('hp', 'speed', 'armor', 'dodge', 'regen'))
if a.summary:
    rows = [json.loads(l) for l in open(a.summary)]
    rows.sort(key=lambda r: -r['best'])
    print(f'{len(rows)} runs; best defense still lets >30% through: {sum(r["best"] > 30 for r in rows)}, >50%: {sum(r["best"] > 50 for r in rows)}')
    for r in rows[:20]:
        print(f"  {name(r['design']):34s} {r['wave']:7s} unit {r['unitCost']:4d} x{r['count']:3d}  best defense lets {r['best']:3d}% through  {r['byDefense']}")
    sys.exit()

rules = json.loads(a.rules)
grid = list(itertools.product(ints(a.hp), ints(a.speed), ints(a.armor), ints(a.dodge), ints(a.regen)))
k, n = map(int, a.part.split('/'))
with sync_playwright() as p:
    b = launch(p); pg = b.new_page()
    pg.goto('file://' + sim_page()); pg.wait_for_timeout(300)
    budget = a.budget or pg.evaluate('([t,r]) => runWave(t, [["Swarm", 1, 0, 0.1]], r)', [DEFENSES['basic'], rules])['defenseCost']
    print(f'army budget {budget}', flush=True)
    for hp, sp, ar, do, rg in grid[k::n]:
        d = {'hp': hp, 'speed': sp, 'armor': ar, 'dodge': do, 'regen': rg}
        for wave, end in (('bunched', 0.12), ('spread', 1.0)):
            res, info = {}, None
            for dn, towers in DEFENSES.items():
                cost = pg.evaluate('([t,a,r]) => runWave(t, a, r)', [towers, [[d, 1, 0, end]], rules])['unitCosts'][0]
                count = budget // cost
                if not count: res = None; break
                r = pg.evaluate('([t,a,r]) => runWave(t, a, r)', [towers, [[d, count, 0, end]], rules])
                res[dn] = r['breach']; info = (cost, count)
            if res is None: continue
            row = {'design': d, 'wave': wave, 'unitCost': info[0], 'count': info[1], 'byDefense': res, 'best': min(res.values()), 'rules': rules}
            with open(a.out, 'a') as f: f.write(json.dumps(row) + '\n')
    b.close()
print('done; summarize with: python tools/sim/scan.py --summary', a.out)
