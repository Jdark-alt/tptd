# v23 sim results (Nov 10, 2026)

What the build ran for the user's v23 balance spec ([docs/specs/v23-balance-pass.md](../specs/v23-balance-pass.md)), and
for the three rule changes the user added while it was being built (free moves after a landed sabotage, regen from the
first hit, and 5:00 or untimed rounds; the clock can't change a sim). Bots, not humans: read the numbers against each
other, not as how people will play.

## How it was run

- **One build, every change behind a switch.** Each v23 change has a `RULES` value that turns it off: `rangePow: 2,
  dpsPow: 1.15` (spec 1, 2), `sapper.armor: 0` (3), `moveFeeToAtk: false` (4), `sapKillShare: 0` (5), `interestRate: 0`
  (7), `freeAfterSabotage: false`, `regenDelay: 3`. With all of them off the v23 build is v22.2: 32 matches (5
  strategies against the `counter` bot and the game's Hard defender, 2 seeds) played on v22.2 (`f806914`) and on v23
  with everything off matched round by round, every logged number equal. So "baseline" below is v23 with everything off,
  and each change is measured alone against it, same bots, seeds and maps.
- **Matches:** `tools/sim/match.py --seeds 4` (8 for the sabotage-only runs), the 18 sim strategies against the
  `counter` bot, the `basic` bot and the game's Hard defender, and the game's computer attacker (Easy, Normal, Hard)
  against `counter`, `basic` and Hard. Compared with `tools/sim/compare.py`.
- **Single waves:** `tools/sim/scan.py`, extended for this build (see "Tools" at the end).

## 1. The playtest build (spec test 1)

`scan.py`'s new `concentrated` defense: three towers at range 1.5 (step 0), 75 damage a second (step 8), 100% accuracy
(step 3, at 1 shot a second), one with chain, one with splash (0.9 cells), one with poison, set into the tips of a tight
serpentine (six wall columns with one-cell lanes, about 85 route cells) so the route wraps round each tower (7 of a
tower's 8 neighbours are route). No sabotage. Against it: every design on a grid (health 50–900 in 8 steps × all 8
speeds × armor 0–3 × regen 0 or 3, all coins in that design, bunched and spread), the 11 sim strategies' armies, and
armies the game makes itself: the Army step's **Auto-army** (what the playtester used) and the **computer attacker** at
each level.

What the defense costs: **891** coins at v22.2 prices (towers 178, 226 and 172, fees 30, walls 285), **1,689** at v23's
(425, 538 and 411).

| | v22.2 (army 891) | v23, same towers (army 1,689) | v23, same coins (891: the towers fit at 38 damage) |
|---|---|---|---|
| best design's breach | 41% | 55% | 74% |
| mean breach over every army | 2.8% | 10.1% | 28.9% |
| armies with breach > 10% / > 30% | 106 / 13 of 937 | 323 / 130 of 991 | 663 / 469 of 937 |
| Auto-army | 10% (7 of 47 units) | 21% (21 of 83) | 44% (16 of 47) |
| computer attacker, Easy | 7% (10 of 55) | 17% (47 of 105) | 40% (35 of 55) |
| computer attacker, Normal and Hard | 27% (3 of 9) | 50% (9 of 17) | 69% (7 of 9) |
| sim armies: runner rush / regen bruisers / fat regen | 16% / 32% / 0% | 27% / 55% / 45% | 46% / 72% / 57% |

The middle column is the same three towers with the attacker as rich as the defense now costs; the right column is
what the playtest's coins buy at v23 prices (three towers at damage step 5, 38 a second, otherwise identical; 845
coins). The best armies against it are fast mid-health units bunched at v22.2 (200 HP at 2.3 cells/s: 16 of 25 through)
and regen units at v23 (the regen bruiser, 500 HP at 1.6 cells/s with regen 3).

**Read:** the spec's goal holds. At v22.2 an optimised army (the computer's) got 27% through, Auto-army 10%, and almost
every design next to nothing (mean 2.8%), which is the playtest (0 of 30 through). At v23 a defender with the
playtest's coins can't buy that build: the same coins buy towers with half the damage, and the best armies get 70%
through, Auto-army 44%. A defender who saves up for the full build still sees a fifth to half of an optimised army
through.

## 2. New-player defense (spec test 2)

The `basic` bot: default towers (2.5 cells, 18 a second) plus damage upgrades, never retuned, bridges left open.

| | attacker wins | mean breach | keep fell in round (mean) |
|---|---|---|---|
| baseline | 72/72 | 58.1% | 4.54 |
| v23 prices (1 + 2) | 72/72 | 61.2% | 4.39 |
| all of v23 | 72/72 | 61.6% | 4.36 |

Breach by round, baseline → prices: 75 → 76, 69 → 74, 71 → 73, 39 → 38, 23 → 27, 15 → 12, 23 → 27, 4 → 3. A default tower
still costs 40, so round 1 is unchanged within noise; later the bot's damage upgrades cost more (75 a second is ×7.4
now, ×5.2 before), so it falls about a sixth of a round sooner. It lost every match before and after, so the bot can't
say more than "barely moved", which is the spec's test.

## 3. Snipers (spec test 3)

`scan.py --fit --budget 750`: seven defenses (`basic`, `heavy`, `splash`, `mixed`, `chain`, `doctrine`, and the new
`sniper`, six towers at range step 7, 5 cells, slow heavy shots), each fitted to 750 coins under each rule set (towers
lose damage steps, the highest first, until it fits, then gain them back while one does), against the default design
grid (72 designs, bunched and spread; 122 runs within budget).

| | sniper's damage per tower | sniper's mean let-through | runs where the sniper is strictly the best defense | within 2 points of the best | splash strictly best |
|---|---|---|---|---|---|
| v22.2 prices | 9 (step 0) | 64.8% | 2 | 4 | 25 |
| v23 prices | 13–18 | 36.1% | 14 | 36 | 29 |

The best-of-seven let-through goes 7.0% → 5.4% on average (more than 30%: 12 → 7 runs; none above 50% either way).

**Read:** at v22.2 a 5-cell tower cost ×4 for its range, so 750 coins bought towers too weak to matter. At v23 it's ×2 and
snipers become a real choice, about as good as `heavy` on average and the best answer in a ninth of the runs, but not
the new best defense: splash is still that, and the mean of the best defense improves a little because there are more
good answers.

## 4. Sapper armor (spec 3, spec test 4)

Sappers landed, the five sabotage strategies (8 seeds) and the computer attacker (4 seeds):

| | baseline | armor 1 |
|---|---|---|
| sabotage strategies vs `counter` | 179/276 (65%), 43 shot down | 184/272 (68%), 36 shot down |
| sabotage strategies vs Hard | 137/347 (39%), 99 shot down | 129/349 (37%), 89 shot down |
| bots, both defenders | 316/623 (51%) | 313/621 (50%) |
| computer attacker, `counter` and Hard | 61/88 (69%) | 69/91 (76%) |

Attacker wins are unchanged (counter 26/40 both, Hard 5/40 both). The bots' land rate stays in the 44–65% band. Fewer are
shot down, but against Hard about as many more miss (it moves towers, and a sapper that lives longer has longer to find
its target gone).

The bots' towers fire 18-damage shots or heavier, which armor 3 trims by a sixth, so the matches can't show what the
spec aims at, the cheap front tower. A targeted wave (the bot's 4-column maze with five default towers; one knock-out
sapper for the last of them; 20 seeds × alone leaving at 2% of the wave, or with 6 runners leaving at 2% or 15%; `tools/sim/sapscreen.py`):

| front tower (in the first wall column) | landed, armor 0 | landed, armor 1 |
|---|---|---|
| none | 20% | 43% |
| cheap rapid fire: 18 a second at 4 shots/s (40 coins) | **0%** | **20%** |
| cheap: 13 a second at 4 shots/s, 2 cells | 5% | 32% |
| default: 18 a second at 1 shot/s (40 coins) | 10% | 18% |
| heavy: 30 a second at 0.4 shots/s | 2% | 5% |

**Read:** armor does what the spec wants. A 40-coin rapid-fire tower took every sapper down before; it still halves
their chances now, but no longer zeroes them. Heavy shots barely notice it, so the defender's counter is to put a real
tower there, not a cheap one. No band problem: the bots land 50%.

## 5. Move fees to the attacker (spec 4, spec test 5)

The game's Hard defender relocates towers (it rebuilds every round and pays the fee for each seen tower it doesn't put
back, `relocFees`). Against it, all 18 strategies (4 seeds), and the five sabotage strategies alone (8 seeds):

| | attacker wins | keep left | fees paid / credited to the attacker, per match |
|---|---|---|---|
| baseline (fees go to no one) | 20/72 | 325 | 93 / 0 |
| fees to the attacker | 22/72 | 300 | 120 / 103 |
| fees to the attacker, flat 10% (`moveFeeRise: 0`) | 12/72 | 359 | 51 / 47 |
| sabotage strategies, baseline | 5/40 | 326 | – |
| sabotage strategies, fees to the attacker | 8/40 | 240 | 216 credited |

The computer attacker against Hard: 10/12 → 11/12 (flat: 8/12), with about 105 coins a match credited (Hard), 46
(Normal), 118 (Easy).

**Read:** about 100 coins a match moves from a relocating defender to the attacker, a third to half of one round's pot
share, and more where sabotage makes the defender dodge (216 a match). It nudges the attacker up a couple of matches.
The flat 10% variant is the surprise: cheaper relocations let Hard move more freely and it wins 10 more matches (12/72
attacker wins). So the rising fee is what makes dodging costly; keep it.

## 6. A sapper shot down pays the defender (spec 5, spec test 6)

The five sabotage strategies against `counter` and Hard (4 seeds) and the computer attacker:

| | vs `counter`: attacker wins, payout per match | vs Hard: attacker wins, payout per match |
|---|---|---|
| no payout | 15/20 | 5/20 |
| `sapKillShare` 0.5 | 16/20, 9 | 4/20, 78 |
| `sapKillShare` 1.0 | 14/20, 23 | 4/20, 140 |

Computer attacker against Hard: the defender earns 0–30 a match at 0.5 (Easy's sappers are never shot down), 0–75 at 1.0; wins 10/12 → 10/12 → 9/12.

**Read:** the payout is small where sappers get through (`counter`: 9 a match) and real where the defense shoots them
(Hard: 78). It doesn't move wins at 0.5. On "does the cheap front tower get stronger": the bots don't build one, so from
section 4's wave, a 40-coin rapid-fire tower now lets 20% of sappers through (armor), and when it does shoot one down it
earns half the sabotage's price (11 coins for a first knock-out on a Basic tower). The two changes pull opposite ways; with armor the screen
is weaker than in v22.2 even counting its payout. 1.0 doubles the payout without changing outcomes in these runs; 0.5
is enough to make shooting sappers pay without paying the defender for doing nothing.

## 7. Interest (spec 7, spec test 7)

Against `counter`, all strategies, 4 seeds:

| rate / cap | 100 | 150 | 200 |
|---|---|---|---|
| 0.10 | 48/72, def 1 / atk 2 a match | 48/72, same | 48/72, same |
| 0.15 | 47/72, def 2 / atk 3 a match | 47/72, same | 47/72, same |

(baseline 49/72). Against Hard: 20/72 → 19/72 (0.10) and 20/72 (0.15), interest 1–5 coins a match.

**Read:** the bots spend everything every round (they rebuild from their whole worth), so they leave 5–8 coins and earn
almost no interest, and the cap never binds: all three caps play out identically. The sims can't measure banking. By
arithmetic: a side that keeps 150 free every round earns 22 a round at 0.15 (15 at 0.10), about 150 over an 8-wave
match, against a pot share of 70–240 a round. It's a small reward for holding back, and a player who banks 150 has 150
fewer coins on the board that round. Whether people bank is a playtest question.

## 8. All together (spec test 8)

Baseline against all of v23 (the spec's seven changes plus free moves after a landed sabotage; regen below), every
pairing:

| pairing | attacker wins | mean breach | sappers landed |
|---|---|---|---|
| `counter` vs 18 strategies | 49/72 → 49/72 | 36.0% → 37.7% | 64% → 65% |
| `basic` vs 18 strategies | 72/72 → 72/72 | 58.1% → 61.6% | 78% → 88% |
| Hard vs 18 strategies | 20/72 → 20/72 | 17.1% → 17.5% | 45% → 47% |
| computer attacker vs `counter` | 11/12 → 11/12 | 55.3% → 56.3% | 86% → 84% |
| computer attacker vs `basic` | 12/12 → 12/12 | 68.7% → 71.1% | 83% → 100% |
| computer attacker vs Hard | 10/12 → 9/12 | 35.2% → 30.5% | 61% → 44% |
| all (without the `basic` computer row) | 162/240 → 161/240 | 34.5% → 35.5% | 60% → 60% |

Over 20 points: the computer attacker against Hard, Easy +25, Normal −25, Hard −25 (one match each of 4). The prices
alone (1 + 2) give 168/240 (+2 points; Hard vs strategies 24/72), and the rest brings it back: fees to the attacker +2
matches, free moves after sabotage −3 against the sabotage strategies (5/40 → 2/40 alone; 5/40 with the fees), kill
payout −1. By strategy against Hard, big tanks 2/4 → 4/4 and slow fat regen 2/4 → 3/4 (damage costs more, so the
defender's coins buy less of it), the bridge strategies 2/4 → 0/4 (free moves after a bridge lands).

**Free moves after a landed sabotage** (the user's addition), alone against Hard: sabotage strategies 5/40 → 2/40 (keep
326 → 344), computer attacker 10/12 → 7/12. With fees going to the attacker too, the fees credited fall from 216 to 141
a match and the sabotage strategies win 5/40, where they started.

## Regen from the first hit (the user's addition)

The user: "make regen act from the moment a unit takes damage, currently it feels useless, but if that is too strong,
tweak the numbers a bit". Regen waited 3 s after the last direct hit (`regenDelay`), so under steady fire it hardly ever
healed. `regenDelay: 0` heals from the first hit, every step, still at most `regenCap` × level % of max health a wave.

`scan.py` on v23's rules, the six defenses of v22's scan (`basic`, `heavy`, `splash`, `mixed`, `chain`, `doctrine`), regen
designs only: health 375–900, speed 0.9–2.3, armor 0 (and armor 6 for the full grid), regen 1–3, bunched and spread. The
88 runs every variant shares:

| | mean let through (best defense) | regen 1 / 2 / 3 | runs > 40% | runs > 50% | worst | the regen bruiser (500 HP, 1.6 c/s, regen 3, bunched) |
|---|---|---|---|---|---|---|
| 3 s delay, cap 10 (v22.2) | 16.6% | 18.6 / 15.9 / 15.2 | 12 | 4 | 58% | 56% |
| from the first hit, cap 10 | 20.1% | 20.7 / 18.7 / 21.0 | 15 | 8 | 61% | 61% |
| **from the first hit, cap 8 (shipped)** | **17.6%** | **18.7 / 16.5 / 17.5** | **9** | **4** | **55%** | **55%** |
| from the first hit, cap 7 | 16.5% | 18.4 / 15.2 / 15.9 | 9 | 2 | 53% | 52% |
| from the first hit, price ×1.3 / 1.6 / 1.95 | 15.0% | 16.8 / 14.9 / 13.2 | 10 | 2 | 51% | 43% |
| from the first hit, cap 8, price ×1.25 / 1.5 / 1.8 | 14.8% | 16.2 / 14.9 / 13.0 | 9 | 1 | 51% | 47% |

On the full grid (280 runs, armor 0 and 6), from the first hit at cap 10: runs over 50% 4 → 8, over 30% 35 → 44, mean
10.3% → 12.1%.

**Read:** healing from the first hit at the old cap is too strong where regen was already the problem: the slow regen
designs that v6, v21 and v22 flagged get 3–5 points more through and four more cross 50%. The cap is the small tweak
that keeps the new feel (it heals under fire, visibly) and the price: at 8 (regen 3 heals at most 24% of its health a
wave, was 30%), regen designs get a point more through than in v22.2 on average (regen 3 +2.3), the worst get less
(55% against 58%), and no more cross 50%. Cap 7 or dearer regen would go further, back to v22.2's average or below,
which would leave regen feeling about as weak as before. Shipped: `regenDelay: 0, regenCap: 8`.

## What I'd change

Nothing in the spec's numbers; this is what the data says about each.

- **Prices (1, 2): keep.** They hit the playtest build where it hurt: it costs 1,689 instead of 891, and with the old
  coins it leaks 29% on average and 74% at best instead of 3% and 41%. Everywhere else they move little (+2 points of
  attacker wins over all pairings, the `basic` bot a sixth of a round sooner), and a new player's tower still costs 40.
  Snipers become a real option without becoming the answer. Watch open maps in playtests, where a 5-cell tower covers
  more than in the sims' mazes.
- **Sapper armor (3): keep.** It breaks the 40-coin rapid-fire screen (0% → 20% of lone sappers through) and costs heavy
  towers almost nothing; the bots' land rate stays at 50%.
- **Move fees to the attacker (4): keep, with the rising fee.** About 100 coins a match change hands from a defender who
  relocates. The flat 10% variant made relocating cheap enough that Hard won 10 more matches of 72: the rise is what makes
  dodging a cost.
- **Shot-down payout (5): keep 0.5.** It pays where the defense earned it (78 a match against Hard, 9 against `counter`)
  and moves no wins; 1.0 only adds coins.
- **Interest (7): ship 0.15 / 150 as the spec says.** The bots can't test it (they bank nothing); the cap only matters to
  a player who holds back 100+ coins, which is the playtest question.
- **Free moves after a landed sabotage: as built.** Alone it helps the defender against sabotage (2/40 instead of 5/40
  against Hard); together with the fees going to the attacker the two cancel. If defenders feel bridges are still too
  punishing, it's working; if attackers feel sabotage no longer pays, the knock-out half (free moves for knocked-out
  towers) is the part to drop first, since a knock-out only lasts the wave.
- **Regen (the user's addition): cap 8, shipped.** If regen still feels weak, 9 is the next step up; the slow regen
  designs are still the scans' strongest (about half through the best defense, and the best armies against the
  playtest build at v23), so I wouldn't go back to 10 without a playtest that says so.

## Final build

What ships (the spec's seven changes, free moves after a landed sabotage, regen from the first hit at cap 8) against the
baseline, every pairing, 4 seeds:

| pairing | attacker wins | mean breach | sappers landed |
|---|---|---|---|
| `counter` vs 18 strategies | 49/72 → 49/72 | 36.0% → 37.6% | 64% → 65% |
| `basic` vs 18 strategies | 72/72 → 72/72 | 58.1% → 61.5% | 78% → 88% |
| Hard vs 18 strategies | 20/72 → 21/72 | 17.1% → 17.4% | 45% → 46% |
| computer attacker vs `counter` | 11/12 → 11/12 | 55.3% → 56.3% | 86% → 84% |
| computer attacker vs `basic` | 12/12 → 12/12 | 68.7% → 71.2% | 83% → 100% |
| computer attacker vs Hard | 10/12 → 11/12 | 35.2% → 33.5% | 61% → 50% |
| all | 174/252 → 176/252 (+1 point) | 35.6% → 36.7% | 61% → 62% |

Over 20 points: Hard against the computer's Easy attacker, 2/4 → 3/4. By strategy against Hard: big tanks and slow fat
regen 2/4 → 4/4 (damage costs more; regen heals under fire), the bridge strategies 2/4 → 0/4 (free moves after a bridge
lands), counter + tower charges 0/4 → 1/4. Mean breach by round against Hard: 24 → 25, 30 → 32, 17 → 21, 19 → 21, 16 → 14,
14 → 11, 6 → 6, 5 → 4.

**Read:** over everything the bots play, v23 is within a point of v22.2: the spec's changes are aimed at one build
(the concentrated defense) and one tower (the cheap screen), and that's where they act. The economy changes move coins
around (about 100 a match of fees, 10–80 of payouts) without moving wins.

## Tools

- `scan.py`: `concentrated` (with `LAYOUTS['tight']`) and `sniper` defenses; `--budget-of`, `--fit`, `--armies`,
  `--bots auto,easy,normal,hard`; units through on every row; the summary says which defense was best how often.
- `ai.js`: `runWave` takes a layout; `defenseCost`, `armyOf`, `botArmyVs`; each round's log carries the wave's income.
- `sapscreen.py` (new): section 4's targeted wave.
- `common.py`: the tools' page is written to a side file and renamed into place, so runs started in parallel never load a
  half-written copy.
