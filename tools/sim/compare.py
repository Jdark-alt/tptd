"""Compare two sets of full-match runs written by match.py --out (the same bots and seeds on two builds or rule sets).

  python tools/sim/compare.py --before tools/.build/before_*.jsonl --after tools/.build/after_*.jsonl
  python tools/sim/compare.py --before a.jsonl --after b.jsonl --strategies     # also every strategy on its own

Prints, per pairing (a defender against the 18 sim strategies, or against one level of the computer attacker): attacker
wins, the mean breach, and the share of sappers that landed; then the mean breach in each round of the match; then the
pairings whose attacker win rate moved by more than 20 points. Breach is the strength that got through ÷ the strength
sent, each round, over the rounds played (a match the attacker won early has no later rounds).
"""
import argparse, glob, json
from collections import defaultdict

def load(paths):
    rows = []
    for p in paths:
        for f in sorted(glob.glob(p)):
            rows += [json.loads(l) for l in open(f) if l.strip()]
    return rows

def pairing(r):
    who = r['attacker'] if r['attacker'].startswith('computer') else 'sim strategies'
    return f"{r['defender']} vs {who}"

def stats(rows):
    wins = sum(r['winner'] == 'attacker' for r in rows)
    br = [x['Y'] / x['X'] for r in rows for x in r['log'] if x.get('X')]
    sent = sum(x.get('sappers') or 0 for r in rows for x in r['log'])
    landed = sum(x.get('sapOk') or 0 for r in rows for x in r['log'])
    return {'n': len(rows), 'wins': wins, 'rate': wins / max(1, len(rows)), 'breach': sum(br) / max(1, len(br)), 'sent': sent, 'landed': landed}

def by_round(rows):
    out = defaultdict(list)
    for r in rows:
        for x in r['log']:
            if x.get('X'): out[x['r']].append(x['Y'] / x['X'])
    return {k: sum(v) / len(v) for k, v in sorted(out.items())}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--before', nargs='+', required=True)
    ap.add_argument('--after', nargs='+', required=True)
    ap.add_argument('--strategies', action='store_true', help='also list every strategy on its own')
    a = ap.parse_args()
    B, A = load(a.before), load(a.after)
    groups = lambda rows, key: {k: [r for r in rows if key(r) == k] for k in dict.fromkeys(key(r) for r in rows)}
    gb, ga = groups(B, pairing), groups(A, pairing)
    sap = lambda s: f"{s['landed']}/{s['sent']} ({100 * s['landed'] / s['sent']:.0f}%)" if s['sent'] else '-'
    print(f"{'pairing':34s} {'attacker wins':>22s} {'mean breach':>16s}   sappers landed")
    swings = []
    for k in ga:
        sb, sa = stats(gb.get(k, [])), stats(ga[k])
        d = 100 * (sa['rate'] - sb['rate'])
        if abs(d) > 20: swings.append((k, d))
        print(f"{k:34s} {sb['wins']:3d}/{sb['n']:<3d}→ {sa['wins']:3d}/{sa['n']:<3d}({d:+4.0f} pts) {100 * sb['breach']:5.1f}% → {100 * sa['breach']:5.1f}%   {sap(sb)} → {sap(sa)}")
    tb, ta = stats(B), stats(A)
    print(f"{'all':34s} {tb['wins']:3d}/{tb['n']:<3d}→ {ta['wins']:3d}/{ta['n']:<3d}({100 * (ta['rate'] - tb['rate']):+4.0f} pts) {100 * tb['breach']:5.1f}% → {100 * ta['breach']:5.1f}%   {sap(tb)} → {sap(ta)}")
    print('\nmean breach by round (%), before → after')
    for k in ga:
        rb, ra = by_round(gb.get(k, [])), by_round(ga[k])
        print(f"  {k:32s} " + '  '.join(f"r{r} {100 * rb.get(r, 0):3.0f}→{100 * ra[r]:3.0f}" for r in ra))
    if a.strategies:
        print('\nby strategy: attacker wins, mean keep left')
        key = lambda r: (r['defender'], r['attacker'])
        sb, sa = groups(B, key), groups(A, key)
        for k in sa:
            b, n = sb.get(k, []), sa[k]
            kb = sum(r['keep'] for r in b) / max(1, len(b)); kn = sum(r['keep'] for r in n) / len(n)
            print(f"  {k[0]:11s} {k[1]:30s} {sum(r['winner'] == 'attacker' for r in b)}/{len(b)} → {sum(r['winner'] == 'attacker' for r in n)}/{len(n)}   keep {kb:5.0f} → {kn:5.0f}")
    print('\nswings over 20 points in the attacker win rate: ' + (', '.join(f'{k} ({d:+.0f})' for k, d in swings) if swings else 'none'))

if __name__ == '__main__':
    main()
