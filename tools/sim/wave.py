"""One wave against a fixed maze, for quick what-ifs (e.g. "can 4 heavy towers stop one maxed unit?").

  python tools/sim/wave.py --towers '[{"dps":8,"rate":5}, {"dps":8,"rate":5}]' --army '[["Tank", 1, 0, 0.1]]'
  python tools/sim/wave.py --towers '[{}, {}, {}, {}]' --army '[[{"hp":6,"speed":4,"regen":3}, 8, 0, 0.15]]' --rules '{"regenCap": 8}'

towers: tower slider patches (index values, see TS in index.html), placed into a 4-column serpentine maze.
army:   [design, count, start, end]; design is a preset (Runner, Brute, Swarm, Ghost), a name from ai.js DESIGNS,
        or slider indexes like {"hp": 9, "speed": 7, "armor": 3}.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import sim_page, launch
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument('--towers', required=True)
ap.add_argument('--army', required=True)
ap.add_argument('--rules', default='{}')
ap.add_argument('--cols', type=int, default=4, help='how many wall columns of the maze to build (0-4)')
a = ap.parse_args()
with sync_playwright() as p:
    b = launch(p); pg = b.new_page()
    pg.goto('file://' + sim_page()); pg.wait_for_timeout(300)
    r = pg.evaluate('([t,a,r,c]) => runWave(t,a,r,c)', [json.loads(a.towers), json.loads(a.army), json.loads(a.rules), a.cols])
    print(json.dumps(r))
    b.close()
