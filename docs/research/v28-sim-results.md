# v28 balance study: advanced and amateur play (Nov 11, 2026)

The user, after v28 went to `main`: "Run extensive simulation to test out the balance … advanced defenders don't make
vertical mazes and spread out towers. The towers are close, they are tied together, and they have as much path walking
through them as possible … one tower with splash and frost … one more tower with if possible frost, otherwise splash and
poison … one tower with chain and poison, and … one tower which has the lowest range but highest damage and highest fire
rate … An advanced attacker plays by adjusting the unit every time … and also trying to adjust the timing … amateur
defenders just place towers on unoptimal places … unorganized or amateur attackers just make whatever units and just
throw at the game. So we want the game to get balanced on both ends."

Everything here is v28 as on `main` (`914b8b3`), 8 waves, keep 1,000, unless a row says otherwise. Bots, not humans: read
the numbers against each other, and the absolute rates as what these bots manage.

## How it was run

**The board is the user's screenshot.** `tools/sim/pro.js` rebuilds it cell for cell: the 9 rocks and 9 patches of
rough ground, the 15 walls, and the four roster towers on the turns (the short-range damage tower at C1, splash + frost at
C5, chain + poison at D8, splash + poison at B9, as columns A–P and rows 0–10). The sim's route is the screenshot's
dashed line exactly, 43 cells. Route cells in range: the damage tower 7 (at 1.5 cells, the route wraps three sides of it),
splash + frost 12, chain + poison 10, splash + poison 10 (at 2.5 cells).

**Defenders**
- **Pro (recipe):** that maze and roster, upgraded every round by a fixed rule (most expected damage on the route per
  coin, within each role's sliders), more towers on the maze's walls as coins grow. Never adapts to the army.
- **Pro (adaptive):** the same maze and roster, but every round it tries 16 ways of spending its coins (which roles get
  the money, fire rates for armor or not, splash 0.9 or 1.3) in hidden waves against the army it saw last (scaled to the
  attacker's coins, which both players see) and three stock threats, and builds the best. It repairs the maze with walls
  after a bridge lands, and with sabotage on turns the two walls a bridge would hurt most into towers.
- **Pro (adaptive, predicts):** the same, and it also works out the attacker's best answer to the defense the attacker
  saw (its own last build) and defends against that too: one step further ahead.
- **Amateur:** keeps the free starter maze, puts towers on random cells beside the route, picks presets at random and
  spends the rest on random upgrades. Never sells or moves.
- **Computer Hard:** the game's own defender (serpentine columns, towers spread along them).

**Attackers**
- **Advanced:** every wave, 150–250 hidden waves against the defense it saw: about 35 designs (archetypes, random ones,
  resist variants for the effects it sees), each slider and resist nudged until nothing improves, mixes of two or three
  designs, a cheap screen ahead or behind, one design split into two or three groups, release-time nudges, and sabotage
  (a knock-out, two within the cap, the best bridge, a bridge and a knock-out, sappers early or late in the first group)
  whenever it adds more keep damage than its coins would as units. It starts from last wave's best army. It sends the
  army that does the most keep damage in those hidden waves.
- **Amateur:** one to three random designs with random release windows, kept or replaced at random each wave; random
  sabotage in about a third of the waves when it's on.
- **Computer Hard:** the game's own attacker.
- **Banker:** sends one 3-coin unit until wave 5, saving everything, then plays as the advanced attacker.

**Two methods.** Full matches (1,768 in all, 8 to 40 seeds a pairing). And a matrix game: at the coins both sides have
in each wave of a pro-vs-pro match, every pro defense candidate (15–18) against every army the search finds against
any of them (47–65), two seeds each, solved for both sides' best mixed strategy. Its value is the keep damage a wave when
neither side can do better by changing alone: "both sides play perfectly, and neither can read the other".

## The answer, in short

| | advanced attacker | amateur attacker | computer Hard attacker |
|---|---|---|---|
| **pro defender (adaptive)** | no sabotage **25/48 (52%)**; sabotage **29/48 (60%)** | 0/16 and 0/16 (the keep ends 840–990) | 0/16; 8/16 |
| **pro defender (recipe)** | 8/8, keep falls in wave 6.2; 8/8, wave 4.6 | 0/8; 0/8 | 0/8; 6/8 |
| **amateur defender** | 8/8, wave 4.1; 8/8, wave 4.2 | **29/40 (73%)**; **26/40 (65%)** | 8/8; 8/8 |
| **computer Hard defender** | 8/8; 8/8 | 5/8; 4/8 | 8/8; 8/8 |

Attacker wins, without sabotage first, then with.

- **Pro vs pro is close.** About half each, and the keep usually falls in wave 7–8 or survives with under 150 left. It's
  decided by who reads the other: the adaptive defender that only counters the last army loses 21/24 without sabotage;
  the one that also predicts the attacker's answer to its own build wins 20/24. (With sabotage the two are 14/24 and
  15/24.)
- **Amateur vs amateur leans to the attacker,** 65–73%.
- **Skill decides mismatches completely.** No amateur attacker took a pro keep in 48 matches; no amateur defender held
  against the advanced attacker (the keep fell in wave 4 on average).
- **Two things are broken:** saving coins and striking late (banking), and cheap bridges through compact mazes. Both
  have fixes measured below.

## Optimal play (the matrix game, no sabotage)

| wave | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| coins (defender : attacker) | 460 : 300 | 530 : 430 | 629 : 551 | 718 : 705 | 847 : 841 | 950 : 1,024 | 1,084 : 1,193 | 1,188 : 1,414 |
| keep damage, both playing perfectly | 57 | 88 | 107 | 164 | 161 | 263 | 322 | 322 |
| running total | 57 | 145 | 252 | 416 | 577 | 840 | 1,162 | – |
| breach | 20% | 21% | 20% | 24% | 21% | 27% | 27% | 23% |

- With both sides perfect the keep falls in wave 7: a little in the attacker's favour, against the bots' 50/50.
- The breach stays at 20–27% all match; the damage grows because both sides' coins grow (the pot and interest) while the
  keep doesn't. **Waves 6–8 decide most matches.**
- **Mixing matters.** A defender who always builds its single best defense lets the attacker's best answer through for
  1.3–1.7 times the perfect-play damage in most waves (847 : 841: 273 a wave against 161), and an attacker who always
  sends its single best army does 0.5–0.9 times it (111 there). Reading the opponent and changing every wave is most of the skill.
- In wave 7 one army nearly dominates (87% of the attacker's mix): fast 112-HP units with all four resists, released
  together in the first 5 s.

## Optimum strategies (what the best play looks like)

**Defender**
- **The compact maze is right.** The same attackers beat the game's own Hard defender (serpentine columns, towers spread
  out) every time, and even the amateur attacker wins 9/16 against it; against the compact maze the amateur attacker
  never wins.
- **Chain + poison is the workhorse.** Damage dealt, over 1,891 pro-defender waves: chain + poison 37%, splash + frost
  33%, splash + poison 19%, **the short-range, max-damage tower 9%**, guard towers 2%. In most perfect-play builds the chain tower
  gets the most coins (48–75 damage a second from wave 6), and splash is 0.9 cells as often as 1.3.
- **The short-range damage tower is the weak part of the roster.** At 1.5 cells it covers 7 route cells even wrapped on
  three sides, and at 4 shots a second each hit is small against armor and 8% less accurate. When it does work, it's
  maxed and firing slowly (75 a second at 0.4 shots a second) against armored waves.
- **Change fire rates every wave** (it's free): heavy, slow shots against armor, the roster's rates otherwise. The best
  defenses mix both.
- **Predict, don't just react.** Defend against what the attacker would send against what it saw of you (last wave's
  build), not only against the army it sent last. That one step was worth 17 matches in 24.
- **With sabotage on, guard the thin walls.** In the screenshot's maze the wall at A6 is a single wall between the entrance
  (A5) and the bottom loop (A7): a bridge there skips 18 of the route's 44 cells, the splash + frost tower's whole loop,
  and its sapper stands on the first route cell, where nothing can shoot it first. E0 and E1, at the top, skip 18 too
  (onto the open right side), B6 16. A wall that becomes a tower can't be bridged.

**Attacker**
- **Fast, mid-weight units, bunched.** In the waves that did the most damage (150+), 69% of the groups ran at 1.9–2.8
  cells a second and 67% had 112–275 HP, mostly released within the first 5 s.
- **Resists for the effects you see,** usually two or three (splash, poison, frost, shock against the roster).
- **A different army every wave.** The cat-and-mouse is real: against the defender that only counters the last army,
  the advanced attacker's damage averaged 0, 155, 22, 373, 8, 275, 23, 192 by wave.
- **With sabotage:** bridge the wall that skips the most of the maze and knock out the chain or splash tower, sappers
  early in the first group. Against the pro maze sappers landed 73% of the time (827 of 1,138), above the 40–60% the
  sapper spec called healthy.
- **Banking** is currently the strongest plan of all (below).

## What's working

- **Pro vs pro is balanced and decided late,** by reading and mixing rather than by one build or one army.
- **The compact maze and the roster do what the user said:** the amateur and the computer's Hard attacker can't touch it
  without sabotage.
- **Sabotage is the counter to compact mazes:** the computer Hard attacker goes from 0/16 to 8/16 against the pro maze
  with it. That's healthy in principle; the price of a bridge is the problem (below).
- **Stacked resists are not a balance problem,** though the best armies use them. Pricing each further resist higher
  (+0.3 or +0.6 on top of the last), allowing at most two, or making resists cut 40% instead of 60% all left the
  perfect-play damage of waves 4–8 within about 10% (1,070 as now; 981–1,098 with the changes): attackers switch to fast
  units with one or two resists.

## What's not working, and the fixes measured

### 1. Banking: save, hide your army, strike late

A banker (one 3-coin unit until wave 5) wins 9/12 against the pro defenders without sabotage, 12/12 with it; the normal
advanced attacker wins 7/12 and 8/12 on the same seeds. Three things add up. A wave that fails pays the attacker the
bigger pot share (65% in wave 1), and v27's interest pays 15% of what's saved, up to 150 a wave: the banker has 958 coins
in wave 4 to the defender's 679. Token waves tell the defender nothing about the army it will face. And with sabotage the
first real wave lands a bridge and a knock-out with the whole bank behind them: 590–890 keep in one wave.

Interest variants (both pro defenders, seeds 1–6, 12 matches a cell; the normal attacker's results don't change with any
of them, since it spends everything):

| rule | banker, no sabotage | banker, sabotage |
|---|---|---|
| v28: 15% interest, at most 150 a wave | 9/12 | 12/12 |
| at most 50 a wave | 8/12 | 10/12 |
| at most 30 a wave | 5/12 | 8/12 |
| v23–v26: 15% of at most 150 coins (22 a wave) | 3/12 | 11/12 |
| **interest only on as many coins as you have on the board** | **3/12** | 12/12 |
| that, and the pot's comeback share scaled by how much of its coins the attacker sent (a token army gets 50/50) | **0/12** | 11/12 |

So without sabotage, banking is an interest problem, and the cleanest fix keeps v27's big interest for honest saving:
**interest counts at most as many coins as you have on the board when the wave starts** (the attacker's army, the
defender's towers and walls). A defender with 900 in towers earns interest on up to 900 saved, as now; a token army earns
nothing. With sabotage the banker still wins, through the burst: that's the bridge price (next).

### 2. A bridge through a compact maze is too cheap

A bridge costs 25 (+25% per earlier bridge) whatever it skips; on a compact maze one wall can skip 18 cells and a tower's
whole loop, for good. With sabotage on, pro vs pro is 29/48 (60%) against 25/48 without. A **price per route cell the
bridge skips** (as the attacker sees the route), on top of today's (with the interest fix above, 24 seeds per pro
defender):

| bridge price | advanced attacker vs pro | banker vs pro | amateur vs amateur |
|---|---|---|---|
| 25 + 25% a bridge (v28) | 28/48 (58%) | 15/16 | 14/20 |
| **+1 coin per cell skipped** | **22/48 (46%)** | **1/16** | 13/20 |
| +2 per cell | 19/48 (40%) | 0/16 | 13/20 |
| +3 per cell | 5/16 | 0/16 | 12/20 |
| +6 per cell | 3/16 | 0/16 | 10/20 |

+1 a cell brings pro vs pro with sabotage in line with the game without it (46% against 52%) and ends the save-and-burst
plan; the screenshot's A6 bridge would cost 25 + 18 = 43. Amateurs barely notice (they rarely bridge the best wall).
Sappers still land about 70% of the time: the attacker now picks shorter bridges it can afford.

### 3. Amateur defense is weaker than amateur attack

Amateur vs amateur is 73% (no sabotage) and 65% (sabotage) for the attacker. Tower placement is the biggest single skill
in the game, and it's the one amateurs get wrong. An amateur defender who follows a **tower-spot hint** (put the tower on
the free cell beside the route with the most route in range) some of the time:

| amateur defender | no sabotage | sabotage |
|---|---|---|
| random placement (as now) | 29/40 (73%) | 26/40 (65%) |
| follows the hint half the time | **20/40 (50%)** | **13/40 (33%)** |
| always follows it | 13/40 (33%) | 7/40 (18%) |

A hint like the walls' hot tiles, but for tower cells, would balance the amateur level without touching pro play (pros
already put towers there). A bigger keep is the wrong lever: 140 a wave brings amateurs to 60% but pro vs pro to 42%, 150
a wave 55% and 25%.

### 4. Smaller things

- **The computer's Hard defender plays like an amateur** (serpentine columns, towers spread out): it loses to every
  attacker, the amateur 9/16. As a single-player opponent it neither challenges nor teaches what wins.
- **The short-range, max-damage tower** does 9% of the damage as one of the four roster towers. Not a rule problem;
  it's the roster to adjust (a second chain tower, or the damage tower firing slowly against armor).
- **Waves 6–8 decide most matches** (perfect-play damage rises from 57 to 322 a wave at the same breach). A design note
  rather than a fault: early waves still set up the coins.

## Recommendations

1. **Interest only on coins up to what you have on the board** (v27's 15% and 150 a wave otherwise). Ends banking without
   sabotage; normal play unchanged. Optionally the pot's comeback share scaled by how much the attacker sent (0/12).
2. **Bridges cost 1 coin more per route cell they skip.** Pro vs pro with sabotage 58% → 46%; ends save-and-burst.
3. **A tower-spot hint for defenders** (UI, the "later" the user mentioned): the amateur level goes from 73% to about 50%.
4. Later: the computer defender building compact, wrapped mazes, and maybe a starter maze shaped like one.

Not recommended: a bigger keep, any resist cap or price change, a nerf to fast units (they're what the attacker needs
against the compact maze, and pro vs pro is already close).

## Caveats

- One map (the screenshot's), one maze. The pro defender varies its tuning, not its walls, beyond repairs and guards.
- The bots' reasoning depth decides pro vs pro: the defender that predicts wins 20/24, the one that reacts loses 21/24.
  Humans sit somewhere between; the matrix game says perfect play on both sides leans a little to the attacker.
- The amateur bots are random, not human mistakes.
- Rules measured but not in the game: `intByBoard`, `commit`, `bridgePerCell`, `resEsc`, `resMax`, `resKeep`, and the
  amateur's `hint`: switches in the tools' copy only (`tools/sim/pro.py`, `tools/sim/pro.js`).

## Reproducing

```
python tools/sim/pro.py layout                     # the screenshot's maze: route, coverage, extra tower slots
python tools/sim/pro.py match --def proA --atk pro --seeds 4 --log --rules '{"sabotage": false}'
python tools/sim/pro.py matrix --pairs 847:841 --rules '{"sabotage": false}'
python tools/sim/pro.py batch --jobs tools/.build/v28/jobs1.json --part 0/4 --out tools/.build/v28/m1.jsonl
python tools/sim/pro_summary.py tools/.build/v28/m1.jsonl
```

Defenders `pro`, `proA` (`noPredict: true` for the one that only reacts, `guards: n`), `am` (`hint: 0.5`), `cpu`;
attackers `pro`, `am`, `cpu`, `bank` (`from: 5`). The batch job files were written by short scripts (the pairings, rules
and seeds in the tables above).
