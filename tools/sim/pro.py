"""The v28 balance study: skill levels on both sides (tools/sim/pro.js).

  python tools/sim/pro.py layout                       # the screenshot's maze: route, coverage, extra tower slots
  python tools/sim/pro.py match --def pro --atk pro --seeds 4 [--rules '{"sabotage": false}'] [--out f.jsonl]
  python tools/sim/pro.py wave --def pro --worth 800 --budget 800 [--rules ...]   # one wave: the best army against a defense
  python tools/sim/pro.py grid --def pro --worths 400,800,1200,1600 --budgets 400,800,1200,1600 --out f.jsonl
"""
import argparse, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import sim_page, launch, write_build, BUILD
from playwright.sync_api import sync_playwright


def pro_page():
    path = sim_page()
    with open(path, encoding='utf-8') as f:
        html = f.read()
    html = html.replace('<script src="../sim/ai.js"></script>', '<script src="../sim/ai.js"></script><script src="../sim/pro.js"></script>', 1)
    # sim-only levers for the resist study: resEsc (each further resist on a design costs resEsc more than the one
    # before: 1.3, 1.3 + resEsc, ...) and resKeep (the share of splash, chain or poison damage a resist lets through, 0.4)
    for x, y in [("for (const k of resList(d.resist)) p.push({ label: RESIST[k].name.toLowerCase() + ' resist', m: RESIST[k].mult });",
                  "resList(d.resist).forEach((k, j) => p.push({ label: RESIST[k].name.toLowerCase() + ' resist', m: RESIST[k].mult + (RULES.resEsc || 0) * j }));"),
                 ("if (kind === 'splash' && R.splash) d *= 0.4;", "if (kind === 'splash' && R.splash) d *= (RULES.resKeep ?? 0.4);"),
                 ("if (kind === 'chain' && R.shock) d *= 0.4;", "if (kind === 'chain' && R.shock) d *= (RULES.resKeep ?? 0.4);"),
                 ("(resOf(u).poison ? 0.4 : 1)", "(resOf(u).poison ? (RULES.resKeep ?? 0.4) : 1)"),
                 # commit (sim-only): the pot's comeback share shrinks toward 50/50 when the attacker sent less than `commit`
                 # of its coins (army value ÷ army value + coins left), so a token army can't farm the bigger share
                 ("const X = S.wave.x, Y = S.wave.y, sp = splitFor(X, Y),",
                  "const X = S.wave.x, Y = S.wave.y, sp = (q => { if (RULES.commit > 0 && X > 0) { const c = X / (X + Math.max(0, S.wave.aLeft || 0)); q.share = 0.5 + (q.share - 0.5) * Math.min(1, c / RULES.commit); } return q; })(splitFor(X, Y)),"),
                 # intByBoard (sim-only): interest counts at most as many coins as the side has on the board when the wave
                 # starts (the attacker's army, the defender's towers and walls), so a token army earns next to nothing
                 ("S.wave.mf = S.mvFee || 0; S.wave.dLeft = S.dFree; S.wave.aLeft = S.aFree;",
                  "S.wave.mf = S.mvFee || 0; S.wave.dLeft = S.dFree; S.wave.aLeft = S.aFree; S.wave.dBoard = towersValue(S.grid) + wallCount(S.grid) * RULES.wall; S.wave.aBoard = armyValue(S.designs);"),
                 ("dInt: interestOn(W.dLeft), aInt: interestOn(W.aLeft)",
                  "dInt: interestOn(RULES.intByBoard ? Math.min(W.dLeft, W.dBoard || 0) : W.dLeft), aInt: interestOn(RULES.intByBoard ? Math.min(W.aLeft, W.aBoard || 0) : W.aLeft)")]:
        assert html.count(x) == 1, x
        html = html.replace(x, y)
    return write_build('pro.html', html)


ap = argparse.ArgumentParser()
ap.add_argument('cmd', choices=['layout', 'match', 'wave', 'grid', 'matrix', 'batch'])
ap.add_argument('--def', dest='dfn', default='pro')
ap.add_argument('--atk', default='pro')
ap.add_argument('--dopt', default='{}')
ap.add_argument('--aopt', default='{}')
ap.add_argument('--seeds', type=int, default=2)
ap.add_argument('--first', type=int, default=1)
ap.add_argument('--rules', default='{}')
ap.add_argument('--out', default='')
ap.add_argument('--worth', type=int, default=800)
ap.add_argument('--budget', type=int, default=800)
ap.add_argument('--worths', default='400,800,1200,1600')
ap.add_argument('--budgets', default='400,800,1200,1600')
ap.add_argument('--effort', type=int, default=2)
ap.add_argument('--log', action='store_true')
ap.add_argument('--jobs', default='', help='batch: a JSON file of [{def, atk, rules, seed}]')
ap.add_argument('--part', default='0/1')
ap.add_argument('--pairs', default='450:300,600:500,800:700,1000:900,1250:1150,1500:1450', help='matrix: defender worth:attacker coins pairs')
a = ap.parse_args()


def solve(Y, iters=60000):
    """Zero-sum game, the defender (rows) minimising keep damage, the attacker (columns) maximising it: fictitious play.
    Returns the defender's mix, the attacker's mix, and the value bracket [lower, upper] (the gap is how far from exact)."""
    import numpy as np
    M = np.array(Y, dtype=float); nd, na = M.shape
    cd, ca = np.zeros(nd), np.zeros(na)
    rd, ra = M.mean(axis=1) * 0, M.mean(axis=0) * 0  # cumulative payoffs against the other side's past plays
    i, j = 0, 0
    for _ in range(iters):
        cd[i] += 1; ca[j] += 1
        ra += M[i]; rd += M[:, j]
        i = int(np.argmin(rd)); j = int(np.argmax(ra))
    pd, pa = cd / cd.sum(), ca / ca.sum()
    upper = float((pd @ M).max())   # the attacker's best reply to the defender's mix
    lower = float((M @ pa).min())   # the defender's best reply to the attacker's mix
    return pd, pa, lower, upper

rules = json.loads(a.rules)

with sync_playwright() as p:
    b = launch(p); pg = b.new_page()
    pg.on('console', lambda m: print('console:', m.text) if m.type == 'error' else None)
    pg.goto('file://' + pro_page()); pg.wait_for_timeout(300)
    if a.cmd == 'layout':
        print(json.dumps(pg.evaluate('(m) => proLayoutInfo(m)', rules.get('map', 'shot'))))
    elif a.cmd == 'match':
        dopt = {'kind': a.dfn, **json.loads(a.dopt)}; aopt = {'kind': a.atk, **json.loads(a.aopt)}
        wins = 0; keeps = []
        for seed in range(a.first, a.first + a.seeds):
            t = time.time()
            r = pg.evaluate('([d, at, s, ru]) => proMatch(d, at, s, ru)', [dopt, aopt, seed, rules])
            wins += r['winner'] == 'attacker'; keeps.append(r['keep'])
            print(f"seed {seed}: {r['winner']} in round {r['round']}, keep {r['keep']}/{r['keepMax']}  ({time.time() - t:.0f}s)", flush=True)
            if a.log:
                for row in r['log']:
                    print(f"   r{row['r']} D{row['dWorth']} A{row['aWorth']} X{row['X']} Y{row['Y']} br{row.get('breach', '-')}% keep{row['keep']} sap{row['sapOk']}/{row['sappers']} | {row['a'].get('army', '')} {row['a'].get('sab', '')} pred{row['a'].get('predY', '')} | {row['d'].get('towers', '')} {('w' + str(row['d']['w'])) if 'w' in row['d'] else ''} ms{row['ms']}", flush=True)
            if a.out:
                with open(a.out, 'a') as f:
                    f.write(json.dumps({'def': dopt, 'atk': aopt, 'seed': seed, 'rules': rules, **r}) + '\n')
        print(f"attacker wins {wins}/{a.seeds}, mean keep left {sum(keeps) / len(keeps):.0f}")
    elif a.cmd in ('wave', 'grid'):
        worths = [a.worth] if a.cmd == 'wave' else [int(x) for x in a.worths.split(',')]
        budgets = [a.budget] if a.cmd == 'wave' else [int(x) for x in a.budgets.split(',')]
        for w in worths:
            d = pg.evaluate('([k, w, ru, o]) => proDefense(k, w, ru, o)', [a.dfn, w, rules, json.loads(a.dopt)])
            print(f"{a.dfn} defense worth {d['worth']} (left {d['left']}), route {d['route']}: {d['towers']}", flush=True)
            for B in budgets:
                t = time.time()
                if a.atk == 'am':
                    r = pg.evaluate('([g, B, ru]) => amArmies(g, B, ru, 24)', [d['grid'], B, rules])
                    print(f"   amateur armies {B}: keep damage {r['Y']}, breach {r['breach']}%", flush=True)
                    row = {'def': a.dfn, 'atk': 'am', 'worth': w, 'budget': B, 'rules': rules, **r}
                else:
                    r = pg.evaluate('([g, B, ru, o]) => bestArmy(g, B, ru, o)', [d['grid'], B, rules, {'effort': a.effort}])
                    bb = r['best']
                    print(f"   best army {B}: keep damage {bb['Y']}, breach {bb['breach']}%  {bb['army']} {bb['sab']}  ({r['trials']} trials, {time.time() - t:.0f}s)", flush=True)
                    if a.log:
                        for x in r['top']: print(f"      {x['Y']:5d} {x['breach']:3d}%  {x['army']}")
                    row = {'def': a.dfn, 'atk': 'pro', 'worth': w, 'budget': B, 'rules': rules, 'best': bb, 'top': r['top'], 'towers': d['towers']}
                if a.out:
                    with open(a.out, 'a') as f: f.write(json.dumps(row) + '\n')
    elif a.cmd == 'batch':
        jobs = json.load(open(a.jobs)); k, n = map(int, a.part.split('/'))
        done = set()
        if a.out and os.path.exists(a.out):
            for l in open(a.out):
                try: r = json.loads(l); done.add(json.dumps([r['def'], r['atk'], r['rules'], r['seed']], sort_keys=True))
                except Exception: pass
        for job in jobs[k::n]:
            key = json.dumps([job['def'], job['atk'], job['rules'], job['seed']], sort_keys=True)
            if key in done: continue
            t = time.time()
            try:
                r = pg.evaluate('([d, at, s, ru]) => proMatch(d, at, s, ru)', [job['def'], job['atk'], job['seed'], job['rules']])
            except Exception as e:
                print('error', job, str(e)[:300], flush=True); continue
            print(f"{job['def']['kind']}{job['def'].get('tag', '')} vs {job['atk']['kind']}{job['atk'].get('tag', '')} {json.dumps(job['rules'])} seed {job['seed']}: {r['winner']} r{r['round']} keep {r['keep']} ({time.time() - t:.0f}s)", flush=True)
            with open(a.out, 'a') as f: f.write(json.dumps({**job, **r}) + '\n')
    elif a.cmd == 'matrix':
        import numpy as np
        for pair in a.pairs.split(','):
            D, B = [int(x) for x in pair.split(':')]
            t = time.time()
            m = pg.evaluate('([D, B, ru, o]) => matrixGame(D, B, ru, o)', [D, B, rules, {'effort': a.effort if a.effort != 2 else 1, 'dopt': json.loads(a.dopt)}])
            Y = np.array(m['Y'], dtype=float)
            pd, pa, lo, hi = solve(Y)
            X = np.array(m['X'], dtype=float)
            print(f"defender {D} vs attacker {B}: {Y.shape[0]} defenses x {Y.shape[1]} armies ({time.time() - t:.0f}s)")
            print(f"   value with both sides playing their best mix: keep damage {lo:.0f}-{hi:.0f} a wave (breach {100 * (Y @ pa).dot(pd) / max(1, X.dot(pa)):.0f}%)")
            print(f"   pure play: the defender's best single build holds the best answer to {Y.max(axis=1).min():.0f}; the attacker's best single army forces {Y.min(axis=0).max():.0f}")
            for k in np.argsort(-pd)[:4]:
                if pd[k] > 0.02: print(f"   defender {pd[k] * 100:4.0f}%  {m['defs'][k]['name']}: {m['defs'][k]['towers']}")
            for k in np.argsort(-pa)[:5]:
                if pa[k] > 0.02: print(f"   attacker {pa[k] * 100:4.0f}%  {m['armies'][k]}  (vs defense mix {float(pd @ Y[:, k]):.0f})")
            if a.out:
                with open(a.out, 'a') as f:
                    f.write(json.dumps({'D': D, 'B': B, 'rules': rules, 'lo': lo, 'hi': hi, 'pd': pd.tolist(), 'pa': pa.tolist(), **m}) + '\n')
    b.close()
