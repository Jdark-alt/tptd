# v33 sim results: the layout pass

Bots, not humans. Every number below compares two builds or rule sets with the same bots, seeds and maps; read them
relatively. Spec: [docs/specs/v33-layout-pass.md](../specs/v33-layout-pass.md).

## How it was run

- **Baseline:** v32.6 (`a6256d0`, a worktree), with v33's sim tools copied in. The rewritten bots (ai.js prices builds
  through `towersValue` when the page has crowding, through the old build fee otherwise) play v32 exactly as the old
  bots did: 72 of 72 matches identical, round by round.
- **The standard set**, both modes (sabotage on, and off with `--rules '{"sabotage": false}'`):
  - the 18 sim strategies against the `counter` bot, 10 seeds (180 matches a mode);
  - the 18 against the computer's Hard defender, 3 seeds (54);
  - the computer attacker (Easy, Normal, Hard) against `counter` and Hard, 4 seeds (24).
  Each seed is its own map. "Core" sets leave out the computer-attacker matches.
- **One change at a time.** v33 can't bring the build fee back, so the first step, **crowding** (the build fee gone,
  crowding in), is v33 with every other number at its v32 value
  (`potGrowth 0.6, starterPresses 3, autoMazeFirst 60, thickenShare 0, waveLen 20`), compared with v32. Each other
  change is that set with one number at its v33 value, compared with crowding alone: **pot** (`potGrowth 1.75`),
  **Auto-maze** (5 presses of 90, no thickening), **thickening** (that, plus `thickenShare 0.25`, compared with
  Auto-maze), **release window** (`waveLen 30`). **All** is v33 as it ships, compared with v32.
- `tools/.build/v33/` holds every match (`<set>_<job>_<mode>.jsonl`) and every comparison (`cmp_*.txt`, from
  `tools/sim/compare.py --strategies`).

## Summary

- **The gate is tripped, toward the defender.** All of v33 against v32: attacker wins 129/258 → 80/258 (−19 points)
  with sabotage and 157/258 → 89/258 (−26) without; many strategies move more than 20 points (section 8). Nearly all of
  it is the **build fee's removal**: the bots and the computer never place towers within 2 cells of each other, so
  crowding costs them nothing, while every tower now costs 40 instead of 40 + 10 × the towers owned. They end matches
  with about 13 towers instead of 9. With crowding switched off the numbers are the same (section 1). Nothing else was
  retuned, as the spec asks.
- **Crowding does what it's for:** at the same coins, v23's three maxed towers packed at one choke point went from
  clearly the strongest layout (5.6% of an army through, against 9.6% spread out) to level with it (9.9%).
- **The pot** (`potGrowth` 1.75): more coins in play on both sides (round 7: about +250 defender, +530 attacker),
  +2 points for the attacker; 1.5 and 2.0 the same within a point.
- **Auto-maze:** the starter is about 53 walls (v32 34) and a route of 71 (55); it can't reach the spec's "up to about
  90" because the search stops when nothing lengthens the route. Thickening takes the weak walls left from 5 to 1 (none
  on 377 of 1,000 maps) and, against a defender that thickens, the bridges that land skip 30% of the route instead of
  37% (sapper landings 45% → 35%).
- **The move fee fix** changes nothing for the computer (it relocates from the grid the attacker saw); it closes the
  human dodge.
- **The 30 s window:** ±2 points; performance holds (section 10).

## The gate: flagged

The spec's gate is an overall attacker win-rate move of more than 10 points in either mode, or any strategy more than
20. v33 trips both, toward the defender, and nearly all of it is the build fee's removal. Nothing else was retuned:
the user decides from the data.

## 1. Crowding (the build fee gone, crowding in)

Against v32. Attacker wins, mean breach (strength through ÷ strength sent, every round played), sappers landed:

| Pairing | Sabotage on | Sabotage off |
|---|---|---|
| `counter` vs 18 strategies (10 seeds) | 95/180 → 57/180 (−21), breach 28.6% → 18.0% | 116/180 → 67/180 (−27), 29.7% → 19.9% |
| Hard vs 18 strategies (3 seeds) | 14/54 → 4/54 (−19), 16.9% → 9.0% | 19/54 → 5/54 (−26), 19.7% → 9.9% |
| Computer attacker vs `counter` and Hard (4 seeds a level) | 20/24 → 16/24, 42.4% → 30.2% | 22/24 → 16/24, 38.5% → 27.7% |
| **All** | **129/258 → 77/258 (−20)**, 26.9% → 17.0%; sappers 53% → 47% | **157/258 → 88/258 (−27)**, 28.1% → 18.3% |

**It's the build fee, not crowding.** The same set with crowding switched off (`crowdInner: 0, crowdOuter: 0`, so the
fee gone and nothing in its place), sabotage on: `counter` 57/180 and Hard 4/54, exactly the crowding run's numbers
(the `counter` matches identical round by round, Hard's within a match). Neither defender ever puts towers within 2
cells of each other: the `counter` bot's twelve slots are 3 columns and 3 rows apart, and the computer's maze columns are
3 apart with its towers at least 3 rows apart in a column. In the last round the computer's nearest tower is 3.0 cells
away on average (v32 3.27; one match in 54 had a crowded pair, three in v32). What changed is that a tower costs 40, not
40 + 10 × the towers owned: by the last round the Hard defender owns 13.1 towers (v32 9.1) and the `counter` bot 10.8
(8.8), and both upgrade less (each upgrade is now weighed against a 40-coin tower). The mean breach falls in every round,
most from round 2 on (Hard: round 2 32% → 20%, round 3 20% → 8%).

Over 20 points, sabotage on: Hard vs big tanks and slow fat regen −100, mini-tanks −67, runner rush and maxed tanks −33;
`counter` vs counter + bridges & towers and alternate + bridges & towers −70, runner rush, maxed tanks, big tanks,
counter + bridges, counter + tower charges and always bridge −30; the computer's Easy attacker −50 (`counter`) and −25
(Hard), its Normal vs Hard −25. Sabotage off: Hard vs runner rush, maxed tanks, big tanks and slow fat regen −100,
ghosts only and mini-tanks −33; `counter` vs runner rush and maxed tanks −70, counter-picks, big tanks and the bridge
strategies −40, brutes + runners and ghosts only −30; the computer's Easy attacker −75 and −50, its Hard vs Hard −25.

**Do the bots spread?** They were never packed: see above. Their fill rate (walls and towers ÷ buildable cells) barely
moves (`counter` 23.6% → 23.7%, Hard 27.3% → 26.9%); towers owned is what grows.

### Crowding where it bites: packed towers (`scan.py`)

v23's playtest build (three 1.5-cell, 75-damage, 100% towers, one each with chain, splash and poison) in the tight
serpentine, in two layouts: **concentrated** (v23's: at three column tips, 4+ cells apart) and **packed** (new: touching,
rows 1-3 of one wall column, the route wrapping its tip). Every defense fitted to the same 1,689 coins (`--fit`: towers
lose damage steps until it fits), then every design of the default grid (bunched and spread) and the sim strategies'
armies sent at it (143 runs). Release window 20 s in all four, to isolate crowding.

| Rules | Packed: cost, damage steps | Mean let through: concentrated / packed | Packed the better defense |
|---|---|---|---|
| v32 (build fee) | 1,689, 75/75/75 | 9.6% / **5.6%** | 60 of 143 |
| crowding 5% / 2.5% | 1,653, 60/75/75 | 9.6% / 7.0% | 53 |
| **crowding 10% / 5% (v33)** | 1,588, 60/60/75 | 9.6% / **9.9%** | 36 |
| crowding 15% / 7.5% | 1,682, 60/60/75 | 9.6% / 9.9% | 36 |

So at the same coins, packing maxed towers went from clearly the stronger layout (a 40% smaller leak) to level with
spreading them, as the spec wanted. 15% / 7.5% fits the same damage steps as 10% / 5% (the slider's steps are coarse);
it only leaves 94 fewer coins spare. With the 30 s window (v33 as it ships) the packed layout lets 9.3% through and the
concentrated 8.7%.

## 2. Spread

Logged per round since v33 (ai.js `spread`): towers owned, mean distance between towers (all pairs, and to the nearest),
fill rate. In the last round, all of v33 against v32, sabotage on:

| Defender | Towers | Mean distance (nearest) | Fill rate |
|---|---|---|---|
| Hard vs 18 strategies | 9.1 → 12.8 | 6.54 → 6.34 (3.27 → 3.01) | 27.3% → 28.5% |
| `counter` vs 18 strategies | 8.9 → 10.8 | 5.53 → 5.66 (3.01 → 3.00) | 23.6% → 23.6% |
| Hard vs the computer attacker (Hard) | 8.8 → 13.2 | 6.44 → 6.44 (3.24 → 3.01) | 26.8% → 28.8% |

The bots' layouts are their own fixed shapes, so these numbers say little about how humans will spread: they never pack.

## 3. The move fee on the seen tuning

The computer defender relocates from the grid the attacker saw (it rebuilds from the round's start), so a tower's
seen tuning and its tuning when it pays are always the same: the fix can't change what it pays. Measured, Hard against
the 18 strategies, sabotage on: move fees 52 a match (v32), 62 (crowding alone), 51 (all of v33), in 208, 163 and 141
of about 420 rounds; the sabotage strategies' sappers landed 43/116, 43/124, 45/136. The differences come from the other
changes (more towers, more coins). The fix matters for human defenders, who could tune a seen tower down, move it and
tune it back up; `test_local.py` checks that path pays the fee on the tuning the attacker saw.

## 4. The pot

`potGrowth` on top of crowding alone (v32's 0.6 is the "before"), sabotage on, the 18 strategies against `counter` and
Hard. Coins in play: each side's worth (free coins plus what's built or bought), the mean over every round played, and
in round 7.

| `potGrowth` | Pot after wave 1 → second-to-last | Attacker wins | Mean breach | Worth, mean (round 7): defender / attacker | The keep fell (round) |
|---|---|---|---|---|---|
| 0.6 (v32) | 200 → 320 | 61/234 | 15.8% | 907 (1,170) / 851 (1,312) | 6.49 (vs `counter`) |
| 1.5 | 200 → 500 | 65/234 (+2) | 15.4% | 997 (1,368) / 1,030 (1,739) | 6.25 |
| **1.75 (v33)** | 200 → 550 | 66/234 (+2) | 15.4% | 1,022 (1,426) / 1,077 (1,847) | 6.13 |
| 2.0 | 200 → 600 | 65/234 (+2) | 15.3% | 1,045 (1,481) / 1,128 (1,970) | 5.92 |

Sabotage off, 1.75 against 0.6: 72/234 → 77/234 (+2), breach 17.4% → 16.6%. The bigger pot puts many more coins in
play (round 7: about +250 for the defender and +530 for the attacker, who wins the bigger share when waves fail) and
nudges the attacker up a little; it's not the lever that moves the balance. Over 20 points (1.75, sabotage on): Hard vs
mini-tanks and big tanks +33 (one match in three each).

## 5. Auto-maze: the starter maze

`starter.py` over 1,000 maps (seeds 1-1,000, each with its gates and terrain). A weak wall touches the route and its
bridge would skip 30% or more of it (lengths by breadth-first search; a starter has no towers).

| Starter | Walls, median (p10, max) | Route, median (shortest) | Weak walls, median (mean; maps with none) | Worst bridge cut, median | Build, median (max) |
|---|---|---|---|---|---|
| v32 (3 presses of 60) | 34 (28, 36) | 55 (35) | 5 (5.2; 73) | 44% | 57 ms (265) |
| v33's search, 3 of 60 | 34 (28, 36) | 55 (35) | 5 (5.2; 73) | 44% | 63 ms (351) |
| 5 presses of 60 | 46 (33, 60) | 70 (35) | 5 (5.5; 57) | 43% | 86 ms (247) |
| 3 presses of 90 | 46 (33, 54) | 69 (32) | 5 (5.5; 51) | 44% | 80 ms (284) |
| 5 of 90, no thickening | 46 (33, 71) | 70 (32) | 5 (5.4; 56) | 44% | 95 ms (447) |
| **5 of 90, thickening (v33)** | **53 (41, 69)** | **71 (36)** | **1 (1.6; 377)** | **33%** | 108 ms (399) |

- v33's search with v32's numbers builds v32's starter on every map (the same walls, route and weak walls).
- **The starter doesn't reach "up to about 90 walls".** Auto-maze stops when no straight run (or hairpin) lengthens the
  route, and on this board that happens at about 46 walls: 5 presses of 60, 3 of 90 and 5 of 90 all stop there. The rest
  of the budget goes unspent. With thickening the starter is 53 walls (the most 69); the route is about 70 cells long
  (v32 55), against an empty board's 63-67.
- Thickening cuts the weak walls left from a median of 5 to 1 (none at all on 377 maps, 57 without it) and the worst
  bridge cut from 44% to 33%, with the route as long. It adds about 7 walls.
- Building it takes about twice v32's time at match start (108 ms median, 399 ms at worst, in headless Chromium on a busy
  machine), synchronously, as before.

In matches (crowding alone against crowding with 5 presses of 90, no thickening; the bots sell the starter and rebuild,
so for them it's coins: about 5 × 12 more walls): sabotage on 61/234 → 59/234 (−1), breach 15.8% → 13.4%; off 72/234 →
67/234 (−2), 17.4% → 14.8%; no strategy moved more than 20 points with sabotage, Hard vs mini-tanks −33 without.
`autoMazeShare` (40% after round 1) wasn't changed; nothing in the sims says players need more (the bots don't use it).

## 6. Thickening

5 presses of 90 with thickening (`thickenShare 0.25`) against the same without, on crowding alone. The `counter` bot
keeps its fixed maze, so for it nothing changes but the starter's coins; the computer's Hard defender thickens its own
serpentine (`mazeThick`). The sabotage strategies (counter + bridges, counter + tower charges, counter + bridges &
towers, alternate + bridges & towers, always bridge), sabotage on:

| Defender | Sappers landed | Bridges landed | Mean share of the route a landed bridge skipped | Landed bridges skipping 30%+ |
|---|---|---|---|---|
| Hard, no thickening | 62/139 (45%) | 10 | 37.4% | 9 |
| **Hard, thickening** | **49/141 (35%)** | 7 | **29.7%** | **4** |
| `counter`, no thickening | 216/439 (49%) | 57 | 28.1% | 30 |
| `counter`, thickening | 214/445 (48%) | 55 | 28.5% | 30 |

Win rates don't move: sabotage on 59/234 → 60/234, off 67/234 → 66/234; over 20 points only Hard vs regen bruisers −33
(one match in three). Thickening makes the bridges that do land much less damaging against a defender that thickens, at
no cost to the attacker's other strategies. (The starter maze's own numbers are in section 5.)

## 7. The release window: 20 s → 30 s

`waveLen 30` on top of crowding alone. Plans keep release times as shares of the window, so every bot's and the
computer's army spreads out by half again.

| | Sabotage on | Sabotage off |
|---|---|---|
| `counter` vs 18 strategies | 57/180 → 58/180, breach 18.0% → 17.4% | 67/180 → 62/180 (−3), 19.9% → 19.4% |
| Hard vs 18 strategies | 4/54 → 6/54, 9.0% → 8.6% | 5/54 → 5/54, 9.9% → 9.1% |
| All | 61/234 → 64/234 (+1) | 72/234 → 67/234 (−2) |

Round 1's breach falls (`counter`: 57% → 48% with sabotage, 63% → 54% without: the starting armies arrive more
strung out) and the later rounds move by a point or two either way. Over 20 points: `counter` vs slow fat regen −60
(on) and −40 (off), its slow, bunched tanks spread thinner; Hard vs mini-tanks +67 (on; two matches in three).

## 8. All together

v33 as it ships against v32, every pairing (section 1's table is crowding alone):

| Pairing | Sabotage on | Sabotage off |
|---|---|---|
| `counter` vs 18 strategies | 95/180 → 60/180 (−19), breach 28.6% → 14.3% | 116/180 → 67/180 (−27), 29.7% → 16.0% |
| Hard vs 18 strategies | 14/54 → 3/54 (−20), 16.9% → 5.9% | 19/54 → 5/54 (−26), 19.7% → 6.9% |
| Computer attacker vs both | 20/24 → 17/24, 42.4% → 24.8% | 22/24 → 17/24, 38.5% → 23.1% |
| **All** | **129/258 → 80/258 (−19)**, 26.9% → 13.3%; sappers 53% → 47% | **157/258 → 89/258 (−26)**, 28.1% → 14.5% |

Mean breach by round, Hard vs the strategies, sabotage on: 26 → 13, 32 → 15, 20 → 3, 19 → 5, 14 → 4, 10 → 3, 6 → 3,
4 → 1. The keep falls later when it falls (`counter`: round 5.85 → 6.62). Coins in play, mean per round: defender
924 → 1,084, attacker 743 → 1,066 (vs `counter`); 916 → 1,045 and 846 → 1,223 (vs Hard). Landed bridges skip about 30%
of the route (37% against `counter` for the computer attacker, 26-28% against Hard). The computer's Normal and Hard
attackers still win every match against both defenders; Easy wins 1 of 8 in each mode (v32 4 of 8 with sabotage, 6 of 8 without).

Over 20 points, sabotage on: Hard vs big tanks and slow fat regen −100, mini-tanks −67, runner rush, maxed tanks and
regen bruisers −33; `counter` vs big tanks −70, counter + bridges & towers and alternate + bridges & towers −60, runner
rush and maxed tanks −30; the computer's Easy attacker −50 and −25. Sabotage off: Hard vs runner rush, maxed tanks and slow
fat regen −100, mini-tanks and big tanks −67, ghosts only −33; `counter` vs runner rush and maxed tanks −70, big
tanks −50, counter-picks and the bridge strategies −40, ghosts only −30; the computer's Easy attacker −75 and −50.

How the changes add up, attacker wins (`counter` and Hard vs the strategies), sabotage on / off: crowding (the fee gone)
−21 / −27; then the pot +2 / +2, Auto-maze −1 / −2, thickening +0 / −0, the window +1 / −2.

### What I'd look at (not done: the gate says the user decides)

The swing is the build fee's removal, and it's big against bots that spend everything on towers. Crowding itself is
working as meant (it bites packed towers: section 1's scan) but can't pull this back, since the bots never pack and a
default tower spread out still costs 40, as the spec requires. The levers that would move it, each a single number:

- **The attacker's coins:** `startAtk` and the pot's split (`swingStart`/`swingEnd`) favour the attacker directly. The
  +25% start for both sides (section 9) changed nothing, so it would have to be the attacker's alone.
- **Unit health** (`US.hp` steps, or `noSabHp` in Simple mode): v5 and v24 used it.
- **Tower prices** (`towerBase`, `dpsPow`): towers cost what they did before the fee came in, in v3.
- Or keep it: humans don't play like these bots (they keep the starter, pack towers, bank coins), and v32's balance
  was measured with the build fee taxing exactly the many-towers play the user wants. A playtest would say whether the
  defender now feels too strong.

## 9. +25% starting coins (`startDef` and `startAtk` 375)

On top of v33: sabotage on 63/234 → 65/234 (+1), breach 12.3% → 11.3%; off 72/234 → 70/234 (−1), 13.8% → 12.6%. More coins
in play from round 1 (round 1 worth about +60 a side), no change in who wins. Over 20 points: Hard vs mini-tanks,
regen bruisers and slow fat regen +33 (on), big tanks −33 (off); one match in three each. Not shipped (the spec's option
only); `startDef`/`startAtk` stay 300.

## 10. Performance (headless Chromium, software rendering, CPU slowed 4×)

- **The busy wave** (`gallery.py --perf 4 --seed 1`, three runs each, alternated): v32's test wave (about 180 units over
  20 s) 65, 66, 65 frames in 6 s, median frame 83-100 ms; v33 with about 200 units over 30 s (`--per 45`) 72, 76, 78
  frames, median 83 ms. Not below v32's: with the window half again as long, about 60 units are on the board at the
  measured moment against 85.
- **The forecast** (the Wave step's full wave on a scratch copy, 120 units against six towers on the starter maze):
  about 145-150 ms with the 30 s window, 175-220 ms with 20 s (v32 about 230 ms at 20 s). Spread out, each step has
  fewer units in range, so the longer wave costs less. A defender's test run plays at 5×, so a 30 s window adds up to
  2 s to it.
- **Weak walls** (`weakWalls`, one route search per wall beside the route): 6-8 ms on a starter maze, 7-12 ms with 80-90
  walls, once per change of the build (cached on `gridVer`).
- **The starter maze** at match start: see section 5 (108 ms median, unthrottled).
