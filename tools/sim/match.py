"""Full 8-round matches between the computer players (tools/sim/ai.js), on the real game code in index.html.

  python tools/sim/match.py                                   # every attacker strategy vs both defenders, 2 seeds
  python tools/sim/match.py --rules '{"wallCharge": 80}'      # try a rule change (any RULES key, plus knobs)
  python tools/sim/match.py --defenders counter --attackers swarm,rush,counter --seeds 3 --log
  python tools/sim/match.py --rules '{"US": {"hp": {"steps": [50,75,112,150,200,275,375,450,550,650]}}}'

Read results relatively: run the current rules and the variant with the same bots, and compare.
Two CPUs make a full run take a few minutes; split strategies across processes with --attackers if needed.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import sim_page, launch
from playwright.sync_api import sync_playwright

ATTACKERS = {  # name -> attacker options for ai.js
    'swarm only': {'army': 'swarm'},
    'runner rush': {'army': 'rush'},
    'brutes + runners': {'army': 'brute'},
    'ghosts only': {'army': 'ghost'},
    'mixed army': {'army': 'mixed'},
    'counter-picks': {'army': 'counter'},
    'alternates swarm/brute': {'army': 'alternate'},
    'maxed tanks': {'army': 'tank'},
    'tanks + swarm': {'army': 'tankswarm'},
    'mini-tanks': {'army': 'minitank'},
    'big tanks': {'army': 'bigtank'},
    'regen bruisers': {'army': 'regenbruiser'},
    'slow fat regen': {'army': 'fatregen'},
    'counter + wall charges': {'army': 'counter', 'charges': 'walls', 'chargeShare': 0.2},
    'counter + tower charges': {'army': 'counter', 'charges': 'towers', 'chargeShare': 0.25},
    'counter + both charges': {'army': 'counter', 'charges': 'both', 'chargeShare': 0.3},
    'alternate + both charges': {'army': 'alternate', 'charges': 'both', 'chargeShare': 0.3},
}
DEFENDERS = {'counter': {'style': 'counter'}, 'basic': {'style': 'basic'}}
# The game's current charge rules, applied to every attacker unless --opts overrides them.
GAME_RULES_OPTS = {'cap': True, 'noLastCharges': True}

ap = argparse.ArgumentParser()
ap.add_argument('--rules', default='{}', help='JSON overrides for RULES / knobs / US slider tables')
ap.add_argument('--opts', default='{}', help='JSON merged into every attacker option set')
ap.add_argument('--attackers', default='all', help='comma-separated names (substring match) or "all"')
ap.add_argument('--defenders', default='counter,basic')
ap.add_argument('--seeds', type=int, default=2)
ap.add_argument('--log', action='store_true', help='print the round-by-round log of the first seed')
a = ap.parse_args()
rules, extra = json.loads(a.rules), json.loads(a.opts)
atk = ATTACKERS if a.attackers == 'all' else {k: v for k, v in ATTACKERS.items() if any(s.strip() in k for s in a.attackers.split(','))}

page_path = sim_page()
with sync_playwright() as p:
    b = launch(p); pg = b.new_page()
    pg.goto('file://' + page_path); pg.wait_for_timeout(300)
    print(f'rules {json.dumps(rules)}  attacker opts {json.dumps({**GAME_RULES_OPTS, **extra})}', flush=True)
    total = wins = 0
    for dn in a.defenders.split(','):
        for an, ao in atk.items():
            opts = {**GAME_RULES_OPTS, **ao, **extra}
            res = [pg.evaluate('([d,a,s,r]) => runMatch(d,a,s,r)', [DEFENDERS[dn], opts, s + 1, rules]) for s in range(a.seeds)]
            w = sum(r['winner'] == 'attacker' for r in res); wins += w; total += len(res)
            fell = [r['round'] for r in res if r['winner'] == 'attacker']
            br = [x['breach'] for r in res for x in r['log'] if 'breach' in x]
            print(f'  defender {dn:8s} vs {an:26s} attacker wins {w}/{len(res)}  keep left {sum(r["keep"] for r in res)/len(res):5.0f}'
                  f'  avg breach {sum(br)/max(1, len(br)):4.1f}%' + (f'  fell in rounds {fell}' if fell else ''), flush=True)
            if a.log:
                for x in res[0]['log']: print('      ', x)
    print(f'ATTACKER WINS {wins}/{total} = {100 * wins / max(1, total):.0f}%')
    b.close()
