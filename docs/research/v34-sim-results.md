# v34 sim results: the economy (Advanced mode)

Bots, not humans. Built from `tools/sim/match.py --out` runs, read by `tools/sim/economy.py`; starter-maze numbers from
`tools/sim/starter.py`. Kept small at the user's request ("consume as little weekly usage as possible"): 3 seeds against
the sim bots, 2 against the computer's Hard defender (about 6 minutes a match), 3 for the computer against itself.

**Baseline.** The spec asks for v33 as the baseline. On the v34 build, Sabotage-only (`{"ecoAdvanced": false}`) is v33.2's
game with sabotage minus interest, and the starter maze is v33's (no sites). The bots spend everything, so interest paid
them 1-5 coins a match in v23's measurements; Sabotage-only stands in for v33 and no v33 build was run.

Modes: **Simple** `{"sabotage": false}` (no sabotage, no economy, units ×1.15 health). **Sabotage-only**
`{"ecoAdvanced": false}`. **Economy-only** `{"sabotage": false, "ecoSimple": true}` (keeps Simple's ×1.15 health). **Advanced**
the defaults.

New bot options: attackers `prospect` (counter-picks' army, every design a Prospector), `bank` (no units for the first 2
waves, then counter-picks), `bank+prospect`; defender `miner` (the counter bot plus a Mine on every site beside its route,
off it, where it can pay).

## 1. Economy's worth (target: +20-30% coins over a match)

Total coins a side earned over a match (pot, interest, fees, payouts, the economy), the economy strategy against the same
army or defense without it, same seeds and maps:

| | Simple | Sabotage-only | Economy-only | Advanced | Advanced vs Hard |
|---|---|---|---|---|---|
| Attacker: `prospect` vs `counter-picks` | 1,662 vs 1,662 | 1,706 vs 1,706 | 4,737 vs 1,680 (**+182%**) | 4,940 vs 1,715 (**+188%**) | 5,577 vs 2,260 (**+147%**) |
| Attacker: `bank+prospect` vs `bank` | +0% | +0% | +147% | +158% | +138% |
| Defender: `miner` vs `counter` | +0% | +0% | +0% | **+1%** | — |

**Prospectors are far over the target; Mines far under it.**

- **Prospectors:** the army is bought once and comes back every wave, so the trickle is a rebate of up to 30% of the
  army's value *every wave*. Against Hard 99% of Prospectors are shot down, yet each earns 7.1 coins before it dies. The
  attacker's win rate didn't move (the halved keep damage cancels the coins against these bots), but its coins nearly
  triple. Exploratory variants (not shipped, not in the spec's list): `prospTrickle` 0.01 / cap 0.10 gives +71%;
  0.005 / 0.06 gives +49% (and the trickle then falls under the bounty, 0.6×). The cap reaching +20-30% is about 0.03-0.04.
- **Mines:** few sites sit beside a maze's route, and scrape takes most of what they hold (section 5). The `miner` bot ends
  matches with about 1% more coins.

## 2. Win rates (gate: Advanced vs Sabotage-only, 10 points overall, 20 per strategy)

Attacker wins, the 18 strategies plus `prospect`, `bank`, `bank+prospect`:

| Defender | Simple | Sabotage-only | Economy-only | Advanced |
|---|---|---|---|---|
| `counter` (3 seeds) | 25/63 (40%) | 28/63 (44%) | 25/63 (40%) | 26/63 (41%) |
| `miner` (3 seeds) | 25/63 (40%) | 28/63 (44%) | 25/63 (40%) | 28/63 (44%) |
| `game:hard` (2 seeds, 13 strategies) | — | 2/26 (8%) | — | 1/26 (4%) |

**The gate holds:** Advanced moves the attacker by −3 / 0 points against the bots and −4 against Hard (one match). No
strategy moved by more than 20 points against the bots. Against Hard the one change is regen bruisers 2/2 → 1/2 (one
match of two, 50 points on two matches).

Per strategy, wins are almost identical across modes (most are 1/3: one map of three goes to the attacker whatever it
sends). Against Hard everything but regen bruisers loses in either mode.

## 3. Banking (target: viable but not a sure win, roughly 35-55% against Hard)

`bank` and `bank+prospect` against `game:hard`, 2 seeds each: **0/4 at every interest setting** (`interestMax` 100, 120,
150, and `interestRate` 0.12 with `interestMax` 150; the four give the same coins). Two banked waves never reach the
cap: about 300 and 450 left, 45 and 67 interest. Against the `counter` bot `bank` wins 1/3, the same as `counter-picks`.

So against these bots banking costs nothing and gains nothing. The cap only bites from about 670 banked, which takes a
side three or four empty waves. The bots can't say whether that's a winning plan; the user's playtests will. Nothing
was retuned (`interestMax` 100 as the spec starts it).

## 4. Prospectors (target: trickle + loot 2-3× the bounty)

| Run | Shot down | Trickle + loot per Prospector | Bounty per Prospector | Ratio |
|---|---|---|---|---|
| Advanced vs bots | 83% | 6.43 + 0.01 | 2.20 | 2.9× |
| Economy-only vs bots | 81% | 6.52 + 0.02 | 2.14 | 3.1× |
| Advanced vs Hard | 99% | 7.08 + 0.00 | 2.96 | 2.4× |
| `prospLootMax` 15 | 83% | 6.43 + 0.01 | 2.20 | 2.9× |
| Computer Normal vs Normal | 79% | 1.99 + 0.00 | 0.68 | 2.9× |

In the target band. Break-even is 5 s alive (2% × 5 = the 10% bounty); the mean Prospector here earns its trickle for about 13 s.
**Loot is almost nothing:** Mines are rare and scrape empties them first. `prospLootMax` 15 changes nothing for the same
reason (no single Prospector ever looted more than a few coins).

## 5. Mines (target: payback about 3 waves)

| `mineScrape` | Held a wave | Kept | Looted | Scraped | Payback (45 coins) |
|---|---|---|---|---|---|
| 0 | 5.0 | 4.0 | 20% | 0% | 11.3 waves |
| 0.005 | 5.0 | 2.2 | 20% | 35% | 20.4 |
| **0.01 (shipped)** | 5.0 | 1.6-2.0 | 8-20% | 53-66% | 28-37 |
| 0.02 | 5.0 | 1.3 | 20% | 53% | 33.5 |

**Mines can't pay back in a match.** The `miner` bot builds where one side touches the route (5 a wave). Even without
scrape that's 9 waves for 45 coins. The spec's 3 waves needs 15 a wave (3 sides), which sites rarely give beside a maze.
Scrape is the bigger problem: a late-match army of 1,000-1,500 coins scrapes 10-15 off every side it passes, more than a
Mine holds. The spec's example (a 600-coin army scrapes about 6 of 15) holds early; it doesn't later. Levers, for the
user: `mineIncome` up (10 a side), `mineCost` down (20), or scrape capped per Mine (say at most 25% of its store).

## 6. Snowball: does a coin lead after wave 3 pick the winner?

The side ahead in worth after wave 3 won Simple 63%, Sabotage-only 59%, Economy-only 60%, Advanced 58% (126 matches
each, bots); against Hard 65% (Sabotage-only) and 62% (Advanced). **The economy doesn't make a lead snowball** against
these bots (all within noise).

## 7. Bet

Only the computer bets (the sim bots don't):

| | Bets | Low / Medium / High | Right | Net a match |
|---|---|---|---|---|
| Hard defender vs the strategies | 175 in 26 matches | 171 / 4 / 0 | 90% | **+30.5** |
| Normal defender vs computer Normal | 16 in 3 | 15 / 1 / 0 | 50% | +6.7 |
| Computer Normal attacker | 12 in 3 | 0 / 3 / 9 | 17% | **−46.0** |

The defender bets Low and is right (the bots rarely break Hard). The attacker's forecast is against the defense as last
seen, and the computer defender rebuilds every round, so its High bets mostly lose. At 10% of committed value the stakes
are modest either way. If the user wants the computer's attacker to bet better, it could bet from its counter-trial
(`counterY`) rather than its first forecast.

## 8. Sites

All 1,000 maps checked place their 5 sites (none short). Starter maze, 300 maps (`starter.py`), sites reserved vs none:
walls median 51 vs 52 (min 25 vs 22), route median 68 vs 70 (mean 67 vs 69, shortest 37 vs 39), maps whose computer mazes
keep under 80% of the empty board's room 18 vs 0 (the computer's mazes now step round sites), corner hairpins 177 vs 224.
Build time median 127 ms.

## The computer and test 13

Computer Normal attacker against computer Normal defender, 3 seeds: it sent Prospectors in its army (149 over the three
matches). The defender's Mines: after the fix below, 1 Mine in 2 matches against `counter-picks` (round 3). It builds one
only where walling a site leaves 2+ sides on its route and the waves left pay back 40, which its serpentine rarely
offers. It once had its Mine step last, after its upgrades had spent everything, and never built one: fixed by moving the
step to right after its columns and first towers.

`ECO_W` (what the computer counts a Prospector's coin as, in points of keep damage) is 1. At 0.5 it never chose Prospectors
against its own defenders.

## Not measured

- Thinking time: the Hard defender takes 3.2-3.4 s a round at 4× CPU throttling (rounds 1-4); the computer attacker's wasn't re-measured.
- Bridged Mines: the online suite's round doesn't bridge one; the local suite checks the rule's parts.
