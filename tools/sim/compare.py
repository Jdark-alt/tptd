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

def last_spread(rows):
    """v33: towers owned, mean distance between towers (all pairs, and each one's nearest) and the fill rate (walls and
    towers ÷ buildable cells), in the last round each match played (matches from before v33 logged none)."""
    xs = [r['log'][-1].get('spread') for r in rows if r['log'] and r['log'][-1].get('spread')]
    if not xs: return None
    m = lambda k: sum(x[k] for x in xs) / len(xs)
    return {'towers': m('towers'), 'dist': m('dist'), 'near': m('near'), 'fill': m('fill')}

def econ(rows):
    """Coins in play per side (defender's and attacker's worth, every round played), and the round the keep fell."""
    d = [x['defWorth'] for r in rows for x in r['log'] if x.get('defWorth') is not None]
    a = [x['atkWorth'] for r in rows for x in r['log'] if x.get('atkWorth') is not None]
    fell = [r['round'] for r in rows if r['winner'] == 'attacker']
    avg = lambda v: sum(v) / len(v) if v else 0
    mf = [sum(x.get('mf') or 0 for x in r['log']) for r in rows]  # the move fees the defender paid, a match
    return {'d': avg(d), 'a': avg(a), 'fell': avg(fell), 'nf': len(fell), 'mf': avg(mf)}

def cuts(rows):
    """v33: each landed bridge's share of the route it skipped (logged since v33)."""
    c = [v for r in rows for x in r['log'] for v in (x.get('cuts') or [])]
    return (sum(c) / len(c), len(c), sum(v >= 0.3 for v in c)) if c else None

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
    print('\nspread in the last round (towers · mean distance · nearest · fill), and coins in play per side · round the keep fell')
    for k in ga:
        b, n = gb.get(k, []), ga[k]
        f = lambda x: f"{x['towers']:4.1f} · {x['dist']:4.2f} · {x['near']:4.2f} · {100 * x['fill']:4.1f}%" if x else '   -'
        eb, en = econ(b), econ(n)
        fr = lambda e: f"r{e['fell']:.2f} ({e['nf']})" if e['nf'] else 'never'
        print(f"  {k:32s} {f(last_spread(b))} → {f(last_spread(n))}   def {eb['d']:5.0f} → {en['d']:5.0f}  atk {eb['a']:5.0f} → {en['a']:5.0f}  fell {fr(eb)} → {fr(en)}  move fees/match {eb['mf']:.0f} → {en['mf']:.0f}")
    print('\nlanded bridges: how much of the route each skipped (mean · bridges · skipping 30%+)')
    for k in ga:
        cb, cn = cuts(gb.get(k, [])), cuts(ga[k])
        f = lambda c: f"{100 * c[0]:4.1f}% · {c[1]:3d} · {c[2]:3d}" if c else '   -'
        if cb or cn: print(f"  {k:32s} {f(cb)} → {f(cn)}")
    print('\nmean breach by round (%), before → after')
    for k in ga:
        rb, ra = by_round(gb.get(k, [])), by_round(ga[k])
        print(f"  {k:32s} " + '  '.join(f"r{r} {100 * rb.get(r, 0):3.0f}→{100 * ra[r]:3.0f}" for r in ra))
    key = lambda r: (r['defender'], r['attacker'])
    sb, sa = groups(B, key), groups(A, key)
    strat_swings = []
    for k in sa:
        b, n = sb.get(k, []), sa[k]
        if b and abs(sum(r['winner'] == 'attacker' for r in n) / len(n) - sum(r['winner'] == 'attacker' for r in b) / len(b)) > 0.2:
            strat_swings.append((k, 100 * (sum(r['winner'] == 'attacker' for r in n) / len(n) - sum(r['winner'] == 'attacker' for r in b) / len(b))))
    if a.strategies:
        print('\nby strategy: attacker wins, mean keep left')
        for k in sa:
            b, n = sb.get(k, []), sa[k]
            kb = sum(r['keep'] for r in b) / max(1, len(b)); kn = sum(r['keep'] for r in n) / len(n)
            print(f"  {k[0]:11s} {k[1]:30s} {sum(r['winner'] == 'attacker' for r in b)}/{len(b)} → {sum(r['winner'] == 'attacker' for r in n)}/{len(n)}   keep {kb:5.0f} → {kn:5.0f}")
    print('\nstrategies whose win rate moved by more than 20 points: ' + (', '.join(f'{k[0]} vs {k[1]} ({d:+.0f})' for k, d in strat_swings) if strat_swings else 'none'))
    print('\nswings over 20 points in the attacker win rate: ' + (', '.join(f'{k} ({d:+.0f})' for k, d in swings) if swings else 'none'))

if __name__ == '__main__':
    main()
