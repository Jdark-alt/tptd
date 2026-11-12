"""Exploit scan: every unit design on a grid, all coins in that one design, sent bunched and spread, against four
defenses of the same cost (plain, slow heavy hits, splash, a mix with frost and poison). A design is suspicious
when even the defense that suits it best lets a lot through.

  python tools/sim/scan.py                       # default grid, ~15 min on 2 CPUs (use --part 0/2 and 1/2 in parallel)
  python tools/sim/scan.py --rules '{"regenCap": 8}' --regen 3 --hp 6,9
  python tools/sim/scan.py --summary tools/.build/scan.jsonl
  python tools/sim/scan.py --resist none,shock     # v21: each design with and without the Shock resist (chain is a defense here)
  python tools/sim/scan.py --hp 5,6,7,8,9 --speed 1,2,3,4,5,6,7 --armor 0 --regen 0 --defenses basic,heavy,splash,mixed,chain,doctrine
                                                   # v22: the toughness scan (six defenses, the doctrine mix among them)
  python tools/sim/scan.py --defenses concentrated --budget-of concentrated --armies
                                                   # v23: the playtest's three maxed short-range towers, the army as rich as it
  python tools/sim/scan.py --defenses basic,heavy,splash,sniper --budget 750 --fit
                                                   # v23: every defense's damage fitted to the same 750 coins under the rules

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
    # v21: chain towers (with --defenses), the defense the Shock resist answers
    'chain': [{'dps': 3, 'chain': 3}, {'dps': 2, 'chain': 3}] * 3,
    # v22: the doctrine mix, 2 splash+frost, 2 chain and 2 heavy (the v22 spec's scan used it as one of its six)
    'doctrine': [{'dps': 2, 'rate': 4, 'splash': 2, 'slow': True}, {'dps': 2, 'chain': 3}, {'dps': 3, 'rate': 5}] * 2,
    # v23: long range, 5 cells (range step 7), slow heavy shots; the question is whether linear range makes it the best
    'sniper': [{'range': 7, 'dps': 2, 'rate': 5}] * 6,
    # v23: the playtest build. Three towers at range 1.5 (step 0), 75 damage a second (step 8), 100% accuracy (step 3,
    # at 1 shot a second), one with chain, one with splash (0.9 cells, the Cannon's), one with poison, set into the
    # tips of a tight serpentine (TIGHT) so the route wraps round each: 7 of a tower's 8 neighbours are route.
    'concentrated': {'towers': [{'range': 0, 'dps': 8, 'accuracy': 3, 'rate': 3, 'chain': 3},
                                {'range': 0, 'dps': 8, 'accuracy': 3, 'rate': 3, 'splash': 2},
                                {'range': 0, 'dps': 8, 'accuracy': 3, 'rate': 3, 'poison': True}], 'layout': 'tight'},
}
# v23: a serpentine of one-cell lanes: wall columns 2, 4, … 12 with gaps at alternate ends (2 at the bottom, 4 at the
# top, …), so the route runs down, up, down … about 85 cells; slots at the tips of columns 4, 6 and 8
LAYOUTS = {'tight': {'walls': [[c, r] for k, c in enumerate(range(2, 13, 2)) for r in range(11) if r != (10 if k % 2 == 0 else 0)],
                     'slots': [[4, 1], [6, 9], [8, 1]]}}
towers_of = lambda d: d['towers'] if isinstance(d, dict) else d
layout_of = lambda d: LAYOUTS[d['layout']] if isinstance(d, dict) and d.get('layout') else None
ints = lambda s: [int(x) for x in s.split(',')]
ap = argparse.ArgumentParser()
ap.add_argument('--rules', default='{}')
ap.add_argument('--hp', default='0,3,6,9'); ap.add_argument('--speed', default='0,4,7'); ap.add_argument('--armor', default='0,2,3')
ap.add_argument('--regen', default='0,3')
ap.add_argument('--resist', default='none', help='comma-separated resists to try on every design (v21: none,shock)')
ap.add_argument('--defenses', default='basic,heavy,splash,mixed', help='comma-separated defenses from DEFENSES (chain needs a v21 build to mean v21 chain)')
ap.add_argument('--budget', type=int, default=0, help='army coins (default: the cost of the plain defense)')
ap.add_argument('--budget-of', default='', help='v23: army coins = what this defense costs under the rules')
ap.add_argument('--fit', action='store_true', help='v23: fit every defense to the budget: towers lose damage steps (the highest first) until it fits, then gain them back while one does')
ap.add_argument('--bots', default='', help='v23: also let the game build the army against each defense: auto (Auto-army), easy, normal, hard (the computer attacker)')
ap.add_argument('--armies', action='store_true', help='v23: also send the sim strategies\' armies (ai.js ARMIES), not only one design at a time')
ap.add_argument('--part', default='0/1', help='k/n: run every n-th design starting at k, to split across processes')
ap.add_argument('--out', default=os.path.join(BUILD, 'scan.jsonl'))
ap.add_argument('--summary', default='', help='print a summary of an existing results file and exit')
a = ap.parse_args()

def name(d):
    if isinstance(d, str): return 'army ' + d
    return ' '.join(f'{k}{d[k]}' for k in ('hp', 'speed', 'armor', 'regen') if k in d) + (f" {d['resist']}" if d.get('resist', 'none') != 'none' else '')
if a.summary:
    rows = [json.loads(l) for l in open(a.summary)]
    rows.sort(key=lambda r: -r['best'])
    print(f'{len(rows)} runs; best defense still lets >30% through: {sum(r["best"] > 30 for r in rows)}, >50%: {sum(r["best"] > 50 for r in rows)}')
    for r in rows[:20]:
        print(f"  {name(r['design']):34s} {r['wave']:7s} unit {r['unitCost']:4d} x{r['count']:3d}  best defense lets {r['best']:3d}% through  {r['byDefense']}"
              + (f"  units through {r['leaks']}" if r.get('leaks') else ''))
    # v23: which defense was the best answer how often, and how much each let through on average
    names = sorted({k for r in rows for k in r['byDefense']})
    if len(names) > 1:
        best = {k: sum(min(r['byDefense'], key=r['byDefense'].get) == k for r in rows) for k in names}
        print('best defense (ties to the first): ' + ', '.join(f'{k} {best[k]}' for k in names))
        print('mean let through: ' + ', '.join(f"{k} {sum(r['byDefense'][k] for r in rows) / len(rows):.1f}%" for k in names))
    sys.exit()

rules = json.loads(a.rules)
grid = list(itertools.product(ints(a.hp), ints(a.speed), ints(a.armor), ints(a.regen), a.resist.split(',')))
DEF = {k: DEFENSES[k] for k in a.defenses.split(',')}
RUN = '([t,a,r,l]) => runWave(t, a, r, 4, 7, l)'

k, n = map(int, a.part.split('/'))
with sync_playwright() as p:
    b = launch(p); pg = b.new_page()
    pg.goto('file://' + sim_page()); pg.wait_for_timeout(300)
    cost_of = lambda t, l: pg.evaluate('([t,r,l]) => defenseCost(t, r, 4, l)', [t, rules, l])
    budget = a.budget or (cost_of(towers_of(DEFENSES[a.budget_of]), layout_of(DEFENSES[a.budget_of])) if a.budget_of
                          else pg.evaluate('([t,r]) => runWave(t, [["Swarm", 1, 0, 0.1]], r)', [DEFENSES['basic'], rules])['defenseCost'])
    print(f'army budget {budget}', flush=True)
    if a.fit:  # v23: every defense's damage fitted to the budget, one tower step at a time
        for dn, d in DEF.items():
            t, l = [dict(x) for x in towers_of(d)], layout_of(d)
            for x in t: x['dps'] = 8
            while cost_of(t, l) > budget and any(x['dps'] > 0 for x in t):
                max(t, key=lambda x: x['dps'])['dps'] -= 1
            for x in sorted(t, key=lambda x: x['dps']):
                if x['dps'] < 8:
                    x['dps'] += 1
                    if cost_of(t, l) > budget: x['dps'] -= 1
            DEF[dn] = {'towers': t, 'layout': d.get('layout') if isinstance(d, dict) else None}
    for dn, d in DEF.items():
        print(f"  {dn}: costs {cost_of(towers_of(d), layout_of(d))}, damage steps {[x.get('dps', 2) for x in towers_of(d)]}", flush=True)
    # v22: rows already in the output file are kept (a run cut short picks up where it stopped), and a design's price is
    # read once (it doesn't depend on the defense)
    done = set()
    if os.path.exists(a.out):
        for l in open(a.out):
            try: r = json.loads(l); done.add((json.dumps(r['design'], sort_keys=True) if isinstance(r['design'], dict) else json.dumps(r['design']), r['wave'], json.dumps(r.get('rules', {}), sort_keys=True)))
            except Exception: pass
    jobs = [{'hp': hp, 'speed': sp, 'armor': ar, 'regen': rg, 'resist': rs} for hp, sp, ar, rg, rs in grid]
    if a.armies: jobs += pg.evaluate('ARMY_KEYS')  # v23: the sim strategies' armies too
    if a.bots: jobs += ['bot:' + x for x in a.bots.split(',')]  # v23: armies the game makes itself
    for d in jobs[k::n]:
        if isinstance(d, str) and d.startswith('bot:'):
            if (json.dumps(d), 'own', json.dumps(rules, sort_keys=True)) in done: continue
            res, lk, armies = {}, {}, {}
            for dn, dd in DEF.items():
                r = pg.evaluate('([k,t,b,r,l]) => botArmyVs(k, t, b, r, l)', [d[4:], towers_of(dd), budget, rules, layout_of(dd)])
                res[dn] = r['breach']; lk[dn] = f"{r['leaks']}/{r['sent']}"; armies[dn] = r['army']
            row = {'design': d, 'wave': 'own', 'unitCost': 0, 'count': 0, 'byDefense': res, 'leaks': lk, 'armies': armies, 'best': min(res.values()), 'rules': rules}
            with open(a.out, 'a') as f: f.write(json.dumps(row) + '\n')
            continue
        if isinstance(d, str):  # a sim strategy's army: its own timing, shares of the budget
            if (json.dumps(d), 'own', json.dumps(rules, sort_keys=True)) in done: continue
            army = pg.evaluate('([k,b,r]) => armyOf(k, b, r)', [d, budget, rules])
            res, lk = {}, {}
            for dn, dd in DEF.items():
                r = pg.evaluate(RUN, [towers_of(dd), army, rules, layout_of(dd)])
                res[dn] = r['breach']; lk[dn] = f"{r['leaks']}/{r['sent']}"
            row = {'design': d, 'wave': 'own', 'unitCost': 0, 'count': sum(x[1] for x in army), 'byDefense': res, 'leaks': lk, 'best': min(res.values()), 'rules': rules}
            with open(a.out, 'a') as f: f.write(json.dumps(row) + '\n')
            continue
        cost = pg.evaluate('([t,a,r]) => runWave(t, a, r)', [DEFENSES['basic'][:1], [[d, 0, 0, 0.12]], rules])['unitCosts'][0]
        for wave, end in (('bunched', 0.12), ('spread', 1.0)):
            if (json.dumps(d, sort_keys=True), wave, json.dumps(rules, sort_keys=True)) in done: continue
            res, lk, info = {}, {}, None
            for dn, dd in DEF.items():
                count = budget // cost
                if not count: res = None; break
                r = pg.evaluate(RUN, [towers_of(dd), [[d, count, 0, end]], rules, layout_of(dd)])
                res[dn] = r['breach']; lk[dn] = f"{r['leaks']}/{r['sent']}"; info = (cost, count)
            if res is None: continue
            row = {'design': d, 'wave': wave, 'unitCost': info[0], 'count': info[1], 'byDefense': res, 'leaks': lk, 'best': min(res.values()), 'rules': rules}
            with open(a.out, 'a') as f: f.write(json.dumps(row) + '\n')
    b.close()
print('done; summarize with: python tools/sim/scan.py --summary', a.out)
