"""v34: reads match.py --out files and reports the economy's numbers (docs/specs/v34-economy.md, "Sims and report").
   python tools/sim/economy.py runs/*.jsonl   (each file one mode or variant; its name is the label)
   Per file: attacker wins by defender, the economy's coins (Mines, Prospectors, scrape, bounties, bets), coins over a
   match for the economy strategies against the ones that ignore it, per-Prospector trickle + loot against bounty, Mine
   payback and the share looted, the Bet's picks and net coins, and whether a coin lead after wave 3 picks the winner."""
import json, sys, os
from collections import defaultdict

PAIRS = [('prospect', 'counter-picks'), ('bank+prospect', 'bank')]  # an economy strategy and the same army without it

def load(path):  # one match per defender, attacker and seed (overlapping --attackers runs write some twice)
    out = {}
    for l in open(path):
        if l.strip(): m = json.loads(l); out[m['defender'], m['attacker'], m['seed'], json.dumps(m.get('rules'), sort_keys=True)] = m
    return list(out.values())

def income(m, side):
    k = 'dTot' if side == 'd' else 'aTot'
    return sum(r.get(k) or 0 for r in m['log'])

def report(path):
    ms = load(path)
    name = os.path.basename(path).rsplit('.', 1)[0]
    print(f'\n=== {name}  ({len(ms)} matches)')
    by = defaultdict(list)
    for m in ms: by[m['defender']].append(m)
    for d, L in sorted(by.items()):
        w = sum(m['winner'] == 'attacker' for m in L)
        print(f'  vs {d:12s} attacker wins {w}/{len(L)} = {100 * w / len(L):.0f}%')
        per = defaultdict(lambda: [0, 0])
        for m in L: per[m['attacker']][0] += m['winner'] == 'attacker'; per[m['attacker']][1] += 1
        print('    ' + ', '.join(f'{a} {x}/{n}' for a, (x, n) in sorted(per.items())))
    # coins over a match, economy strategy against the same army without it (same defender and seed)
    idx = {(m['defender'], m['attacker'], m['seed']): m for m in ms}
    for eco, base in PAIRS:
        a = b = 0; n = 0
        for (d, at, s), m in idx.items():
            if at != eco or (d, base, s) not in idx: continue
            a += income(m, 'a'); b += income(idx[(d, base, s)], 'a'); n += 1
        if n and b: print(f'  attacker income over a match: {eco} {a / n:.0f} vs {base} {b / n:.0f} ({100 * (a - b) / b:+.0f}%, {n} pairs)')
    # the defender: miner against counter, by attacker and seed
    a = b = 0; n = 0
    for (d, at, s), m in idx.items():
        if d != 'miner' or ('counter', at, s) not in idx: continue
        a += income(m, 'd'); b += income(idx[('counter', at, s)], 'd'); n += 1
    if n and b: print(f'  defender income over a match: miner {a / n:.0f} vs counter {b / n:.0f} ({100 * (a - b) / b:+.0f}%, {n} pairs)')
    # the economy's coins
    R = [r for m in ms for r in m['log']]
    P = sum(r.get('prospN', 0) for r in R)
    if P:
        tr, lo, bo = (sum(r.get(k, 0) for r in R) for k in ('trickle', 'loot', 'bounty'))
        died = sum(r.get('prospDied', 0) for r in R)
        print(f'  Prospectors: {P} sent, {100 * died / P:.0f}% shot down; per Prospector trickle {tr / P:.2f} + loot {lo / P:.2f} = {(tr + lo) / P:.2f} vs bounty {bo / P:.2f} ({(tr + lo) / max(bo, 1e-9):.1f}x)')
    MN = sum(r.get('mineN', 0) for r in R)
    if MN:
        inc, lo, sc = (sum(r.get(k, 0) for r in R) for k in ('mineInc', 'loot', 'scrape'))
        kept = inc - lo - sc
        print(f'  Mines: {MN} live Mine-waves, {inc / MN:.1f} held a wave, {kept / MN:.1f} kept; {100 * lo / inc:.0f}% looted, {100 * sc / inc:.0f}% scraped; payback {45 / max(kept / MN, 1e-9):.1f} waves')
    bets = [(r.get('bdk'), r.get('bds', 0), r.get('dBetNet') or 0, 'd') for r in R if r.get('bds')] + [(r.get('bak'), r.get('bas', 0), r.get('aBetNet') or 0, 'a') for r in R if r.get('bas')]
    if bets:
        for sd in 'da':
            B = [x for x in bets if x[3] == sd]
            if not B: continue
            picks = [sum(1 for x in B if x[0] == k) for k in range(3)]
            nm = defaultdict(int)
            for m in ms:
                nm[m['seed'], m['defender'], m['attacker']] += sum((r.get('dBetNet' if sd == 'd' else 'aBetNet') or 0) for r in m['log'])
            print(f'  Bets ({"defender" if sd == "d" else "attacker"}): {len(B)} bets, picks Low/Medium/High {picks}, right {sum(x[2] > 0 for x in B)}, net a match {sum(nm.values()) / len(ms):+.1f}')
    # snowball: does the side ahead in worth after wave 3 win?
    hit = tot = 0
    for m in ms:
        r3 = next((r for r in m['log'] if r['r'] == 3 and 'defWorth' in r), None)
        if not r3: continue
        lead = r3['defWorth'] - r3['atkWorth']
        if lead == 0: continue
        tot += 1; hit += (lead > 0) == (m['winner'] == 'defender')
    if tot: print(f'  snowball: the side ahead in worth after wave 3 wins {hit}/{tot} = {100 * hit / tot:.0f}%')

for p in sys.argv[1:]: report(p)
