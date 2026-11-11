# v24 sim results (Nov 11, 2026)

v24 adds a Sabotage On / Off choice to the mode screen, and with it on, a sapper shot down pays the defender its
sabotage's whole price (v23: half). The user asked for the Off mode for players who don't want sabotage, and for it to
be balanced: "without sabotage the defender is too strong … either the attacker is buffed or the defender is nerfed".
These runs pick that buff. Bots, not humans: read the numbers against each other.

## How it was run

- `tools/sim/match.py`, the 18 sim strategies against the game's Hard defender (4 seeds) and the `counter` bot (4
  seeds), and the game's computer attacker (Easy, Normal, Hard) against Hard over 20 seeds (`--first 9 --seeds 12` on
  top of 8). Sabotage off is `--rules '{"sabotage": false}'`.
- The baseline is the game with sabotage on (v24's rules). Every variant plays the same seeds and maps.
- `tools/sim/scan.py --defenses concentrated --budget-of concentrated --armies --bots auto,easy,normal,hard`: the
  playtest build from v23 (three maxed 1.5-cell towers in a tight serpentine, 1,689 coins) against an army as rich, from
  the sim strategies' armies, Auto-army and the computer attacker. No sabotage in a single wave either way.
- Two kinds of buff were tried: units cheaper (`noSabUnit`, ×0.85, ×0.75, ×0.65; it was a candidate rule while the
  runs were made and is gone) and units tougher (unit health ×1.1, ×1.15, ×1.2, measured with the tools' `hpScale`
  knob). The shipped rule, `noSabHp` 1.15, plays exactly as the knob at 1.15: 12 matches compared round by round.

## Sabotage off, before any buff

Against Hard, switching sabotage off costs the attacker:

| | attacker wins | Easy | mean breach |
|---|---|---|---|
| computer attacker, sabotage on | 52/60 | 12/20 | 37.0% (rounds 1–5) |
| computer attacker, sabotage off | 45/60 | 5/20 | 33.8% |
| the 5 sabotage strategies, on | 0/20 | | 17.6% |
| the 5 sabotage strategies, off (their sabotage coins go to the army) | 0/20 | | 11.5% |

The computer's Normal and Hard attackers win every match either way; what sabotage buys is the weaker attacker's wins
(Easy 12 → 5 of 20) and a few points of breach. The 13 strategies that never sabotage play the same either way
(18–20 of 52).

## Cheaper units don't do it

| units cost | Hard vs 18 strategies (wins, keep left, breach) | computer vs Hard (wins, Easy, breach rounds 1–5) |
|---|---|---|
| sabotage on | 20/72, 330, 17.2% | 52/60, 12/20, 37.0% |
| off, ×1 | 18/72, 357, 15.5% | 45/60, 5/20, 33.8% |
| off, ×0.85 | 25/72, 339, 16.8% | (8 seeds) 18/24 |
| off, ×0.75 | 20/72, 321, 18.0% | 45/60, 5/20, 38.5% |
| off, ×0.65 | 18/72, 367, 17.5% | 45/60, 5/20, 40.0% |

Breach rises, but wins don't: keep damage is counted in what the units cost, so cheaper units that get through also hit
the keep for less. Easy's wins never come back (5 of 20 at every price).

## Tougher units do

| unit health | Hard vs 18 strategies | Hard vs the 13 army-only strategies | computer vs Hard | Easy | breach rounds 1–5 | keep fell (round) |
|---|---|---|---|---|---|---|
| sabotage on | 20/72, keep 330 | 20/52 | 52/60 | 12/20 | 37.0% | 6.31 |
| off, ×1 | 18/72, keep 357 | 18/52 | 45/60 | 5/20 | 33.8% | 5.98 |
| off, ×1.1 | 25/72, keep 279 | 21/52 | 47/60 | 7/20 | 37.0% | 5.96 |
| **off, ×1.15 (shipped)** | **31/72, keep 251** | **26/52** | **49/60** | **9/20** | **38.0%** | **5.96** |
| off, ×1.2 | 34/72, keep 209 | 29/52 | 50/60 | 10/20 | 39.9% | 5.78 |

Over every attacker against Hard together: sabotage on 72/132 (55%); off with ×1 63/132 (48%), ×1.1 72/132 (55%),
×1.15 80/132 (61%), ×1.2 84/132 (64%). Against the `counter` bot (which never plays sabotage's game: it doesn't move towers or guard walls) little moves: sabotage on 48/72, off ×1 49/72, off ×1.15 52/72 (keep left 138 → 119).

The playtest build (three maxed short-range towers), army as rich as the defense:

| unit health | Auto-army | computer Easy | computer Normal/Hard | runner rush | mini-tanks | regen bruisers |
|---|---|---|---|---|---|---|
| ×1 | 21% | 17% | 60% | 27% | 37% | 58% |
| ×1.1 | 28% | 27% | 64% | 30% | 43% | 64% |
| ×1.15 | 29% | 21% | 65% | 31% | 44% | 65% |
| ×1.2 | 32% | 22% | 67% | 32% | 47% | 68% |
| (cheaper, ×0.75) | 27% | 18% | 62% | 30% | 44% | 67% |

**Read:** health is the lever: every unit that gets through still hits the keep for its full price, so a tougher army
turns into keep damage where a cheaper one doesn't. +10% brings the attackers' wins against Hard level with the game
with sabotage (55% both) and the computer's breach exactly level (37.0%). **+15% ships**: it leans a little to the
attacker (61%), and brings the weaker attacker closer to what sabotage gave it (Easy 9 of 20 against 12), because the
defense you described, a few well-optimised towers, is harsher than anything these bots build, and the players this
mode is for don't sabotage. It's one number, `noSabHp`: 1.1 if defenders struggle, 1.2 if they still win too easily.

## Sabotage on: the whole shot-down price

Same bots and seeds, half the price (v23) against the whole (v24):

| | attacker wins | keep left | paid to the defender per match | sappers shot down |
|---|---|---|---|---|
| Hard vs the 5 sabotage strategies | 1/20 → 0/20 | 325 → 360 | 50 → 135 | 46 → 57 |
| Hard vs all 18 | 21/72 → 20/72 | 321 → 330 | 14 → 38 | |
| `counter` vs all 18 | 49/72 → 48/72 | 135 → 138 | 4 → 8 | |
| computer attacker vs Hard (4 seeds) | 11/12 → 11/12 | 6 → 6 | 8 → 23 | 11 → 11 |

**Read:** a defense that shoots sappers down now earns real coins from it (135 a match against the sabotage
strategies), and wins move by a match at most. That's the risk on the attacker's side the user asked for.

## The move fee

Unchanged: it already rises, 10% of the tower's tuning for the defender's first relocation in the match, then 15%, 20%…
at most 40%, and since v23 it goes to the attacker when the wave ends. v23's sims found the flat 10% variant made the
computer defender much stronger (it relocated freely), which is why the rise stays.
