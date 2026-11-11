"""Summarise tools/sim/pro.py batch results: per pairing, attacker wins, keep left, when the keep fell, and the coins.

  python tools/sim/pro_summary.py tools/.build/v28/m1.jsonl [--by-round]
"""
import json, sys
from collections import defaultdict

files = [x for x in sys.argv[1:] if not x.startswith('--')]
by_round = '--by-round' in sys.argv
rows = [json.loads(l) for f in files for l in open(f)]
DN = {'proA': 'pro (adaptive, predicts)', 'proA-L1': 'pro (adaptive)', 'pro': 'pro (recipe)', 'am': 'amateur', 'cpu': 'computer Hard'}
AN = {'pro': 'advanced', 'am': 'amateur', 'cpu': 'computer Hard', 'bank': 'banker'}
label = lambda o, side='d': (DN if side == 'd' else AN).get(o['kind'] + o.get('tag', ''), o['kind'] + o.get('tag', ''))
groups = defaultdict(list)
for r in rows:
    key = (json.dumps({k: v for k, v in r['rules'].items()}, sort_keys=True), label(r['def']), label(r['atk'], 'a'))
    groups[key].append(r)
cur = None
for (rules, d, a), rs in sorted(groups.items()):
    if rules != cur:
        cur = rules; print(f"\n== rules {rules}")
        print(f"{'defender':26s} {'attacker':26s} {'atk wins':>9s} {'keep left':>10s} {'fell in':>8s} {'D coins r4/r8':>14s} {'A coins r4/r8':>14s} {'breach r1..r8':>40s}")
    n = len(rs); w = sum(r['winner'] == 'attacker' for r in rs)
    keep = sum(r['keep'] for r in rs) / n
    fell = [r['round'] for r in rs if r['winner'] == 'attacker']
    def worth(side, rd):
        v = [row[side] for r in rs for row in r['log'] if row['r'] == rd]
        return f"{sum(v) / len(v):.0f}" if v else '-'
    br = []
    for rd in range(1, 9):
        v = [row.get('breach', 100 if row.get('keep') == 0 else 0) for r in rs for row in r['log'] if row['r'] == rd]
        br.append(f"{sum(v) / len(v):.0f}" if v else '-')
    print(f"{d:26s} {a:26s} {w:4d}/{n:<4d} {keep:10.0f} {(sum(fell) / len(fell) if fell else 0):8.1f} {worth('dWorth', 4) + '/' + worth('dWorth', 8):>14s} {worth('aWorth', 4) + '/' + worth('aWorth', 8):>14s} {' '.join(f'{x:>4s}' for x in br):>40s}")
    if by_round:
        for r in rs[:2]:
            print('   seed', r['seed'], r['winner'], 'keep', r['keep'])
            for row in r['log']:
                print(f"      r{row['r']} D{row['dWorth']} A{row['aWorth']} X{row['X']} Y{row['Y']} | {row['a'].get('army', '')} {row['a'].get('sab', '')}")
