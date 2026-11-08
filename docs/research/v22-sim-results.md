# v22 sim results (Nov 8, 2026)

The spec's own evidence for Part B lives in `claude/sim-findings-2026-11-08.md` in the TPTD project; it couldn't be
reached from the build session, so it isn't copied here yet. This file holds what the build itself ran: the same bots,
seeds and maps on v21.1 (commit `c601237`) and on v22, through the repository's tools. Bots, not humans: read the
numbers relative to each other.

## Part B: which price rule shipped

`tools/sim/scan.py` with six defenses of about 750 coins each (`basic`, `heavy`, `splash`, `mixed`, `chain`, and the
spec's doctrine mix `doctrine`: 2 splash+frost, 2 chain, 2 heavy). Every design gets the whole budget, sent bunched and
spread; a run counts against the best of the six defenses.

**The spec's must-check** (armor 0-3 × regen 0-3 for health 5-9 and speed 0-4, since dropping the coin-based surcharge
makes armor/regen-stacked slow units cheaper), under the spec's rule (`toughK` 0.5, no big-unit surcharge):

```
python tools/sim/scan.py --rules '{"bigUnit": 0, "toughK": 0.5}' --hp 5,6,7,8,9 --speed 0,1,2,3,4 --armor 0,1,2,3 --regen 0,1,2,3 --defenses basic,heavy,splash,mixed,chain,doctrine
```

782 runs (391 designs; the others cost more than the budget). 4 runs got more than 50% through the best defense, all
slow regen designs sent bunched:

| design | unit price | best defense lets through |
|---|---|---|
| 900 HP, 0.9 c/s, regen 3 | 188 | 56% |
| 500 HP, 1.3 c/s, regen 3 | 117 | 52% |
| 500 HP, 0.9 c/s, armor 3, regen 3 | 120 | 52% |
| 900 HP, 0.7 c/s, armor 1, regen 3 | 147 | 51% |

So, as the spec says for that case, **the old big-unit surcharge stays and `toughK` is 0.25**: price = 15 × health ×
speed × armor × regen × resists, past 60 coins 60 × (price ÷ 60)^1.5, then × (1 + 0.25 × max(0, toughness − 2.5)).

The same scan under the shipped rule (`--rules '{"bigUnit": 60, "toughK": 0.25}'`, the game's defaults now):

| rule | runs | > 30% | > 40% | > 50% | worst |
|---|---|---|---|---|---|
| the spec's rule | 782 | 123 | 46 | 4 | 56% |
| shipped | 764 | 103 | 31 | 3 | 53% |

On the 764 designs both rules priced within budget, the shipped rule lets 1.2 points less through on average (better
for the defender in 156 runs, worse in 84). Its three runs over 50%, all bunched, against v21.1 (the same scan on
`c601237` for these designs):

| design | unit price v21.1 → v22 | v21.1 | v22 |
|---|---|---|---|
| 500 HP, 1.3 c/s, regen 2 | 76 → 91 | 61% | 53% |
| 500 HP, 1.3 c/s, regen 3 | 97 → 117 | 46% | 52% |
| 900 HP, 0.9 c/s, regen 1 | 83 → 118 | 48% | 51% |

The spec stops at the fallback, so nothing else was tuned in this build. Slow regen designs were the v6 scan's worst
offenders too; regen's price on slow high-health units is the lever if playtests agree.

**The extended grid** (health 5-9 × speed 1-7, no armor or regen; the spec's test 3):

```
python tools/sim/scan.py --hp 5,6,7,8,9 --speed 1,2,3,4,5,6,7 --armor 0 --regen 0 --defenses basic,heavy,splash,mixed,chain,doctrine
```

| rule | runs | best defense lets > 40% through | > 50% | worst |
|---|---|---|---|---|
| v21.1 (big-unit surcharge) | 70 | 18 | 7 | 500 HP at 1.9 c/s, 60% |
| the spec's rule (toughK 0.5, no big-unit surcharge) | 66 | 2 | 0 | 275 HP at 2.3 c/s, 45% |
| shipped (both surcharges, toughK 0.25) | 66 | 5 | 0 | 50% |

v21.1's runs over 50% (all bunched): 500 HP at 1.9 c/s 60%, 900 HP at 1.3 58%, 675 HP at 1.6 57%, 375 HP at 2.3 54%,
900 HP at 1.1 53%, 500 HP at 2.3 51%, 675 HP at 1.3 51%.

## Full matches

`tools/sim/match.py --seeds 4`, the 18 sim strategies against the `counter` bot and the game's Hard defender, v21.1
against v22 with the shipped rule (`tools/sim/compare.py --strategies`):

| pairing | attacker wins | mean breach | sappers landed |
|---|---|---|---|
| `counter` vs sim strategies | 50/72 → 49/72 | 36.9% → 36.0% | 64% → 64% |
| Hard vs sim strategies | 18/72 → 20/72 | 15.9% → 17.1% | 42% → 45% |
| all | 68/144 (47%) → 69/144 (48%) | 25.1% → 25.5% | 51% → 53% |

No pairing moved more than 20 points. Overall attacker wins didn't drop (the spec's flag was a drop of more than 3). The
spec's own rule gave the same totals (49/72 and 20/72).

The big-unit strategies, wins over both defenders:

| strategy | v21.1 | v22 |
|---|---|---|
| maxed tanks (900 HP, 2.8 c/s, armor 3) | 8/8 | 4/8 |
| big tanks (500 HP, 2.3, armor 3) | 7/8 | 5/8 |
| mini-tanks (275 HP, 1.9, armor 2) | 8/8 | 8/8 |
| regen bruisers (375 HP, 1.6, regen 3) | 8/8 | 8/8 |
| slow fat regen (900 HP, 0.7, regen 3) | 6/8 | 6/8 |

Against the Hard defender the bridge strategies gained (counter + bridges and always bridge 0/4 → 2/4 each, counter +
bridges & towers 0/4 → 1/4), runner rush and counter-picks 0/4 → 1/4, and keep left fell for most strategies: the
computer defender now pays the move fee when it relocates seen towers (Part C), so it dodges knock-outs less, and a
bridge that lands next to a knocked-out tower is taken (Part A). Against the `counter` bot, which never relocates and
pays no fee (a fixed reference), only the tank strategies moved.
