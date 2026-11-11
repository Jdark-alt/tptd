# v25 sim results (Nov 11, 2026)

v25 changes how the move fee rises, at the user's request: "the first time you move a tower, the fee should be 10% of
the cost, the second time … 10.5%, no matter the tower number or price … so that the cost of moving towers keeps steadily
increasing, and the final amount of the fee is only based on the tower's current price." The user also asked whether
the fee should go in the mode without sabotage. These runs measure both. Bots, not humans: read the numbers against each
other.

## How it was run

- `tools/sim/match.py`, the 18 sim strategies against the game's Hard defender (4 seeds, 72 matches), and the game's
  computer attacker (Easy, Normal, Hard) against Hard (8 seeds, 24 matches). Only the game's own defender pays move fees
  (the `counter` and `basic` bots never relocate), so Hard is the defender that shows the fee.
- Every variant plays the same seeds and maps; the tables pair the matches one to one.
- The fee schedules: **+5 points** a relocation (v22-v24: 10%, 15%, 20%… 40% after six), **+2 points** (10%, 12%,
  14%… 40% after 15), **+0.5 points** (v25: 10%, 10.5%, 11%… 40% after 60), and, without sabotage, **no fee**
  (`moveFeeBase: 0, moveFeeRise: 0`). The fee is always on the tower's tuning as it is when it moves, and since v23 it
  goes to the attacker.

## With sabotage

| fee rise a relocation | Hard vs 18 strategies (wins, keep left, breach) | fees the defender paid a match | computer attacker vs Hard | Easy | fees paid a match |
|---|---|---|---|---|---|
| +5 points (v24) | 20/72 (28%), 330, 17.2% | 71 | 21/24 | 5/8 | 105 |
| +2 points | 18/72 (25%), 344, 16.9% | 56 | 20/24 | 4/8 | 75 |
| **+0.5 points (v25)** | **16/72 (22%), 367, 16.4%** | **37** | **18/24** | **2/8** | **58** |

The computer's Normal and Hard attackers win every match whatever the fee. Against the five sabotage strategies Hard
wins every match either way; the fee only moves the keep (360 at +5 points, 410 at +0.5).

**Read:** the computer defender dodges knock-outs and bridges by moving towers. The cheaper that gets, the more it
does it and the less it pays: about half the coins go to the attacker at +0.5 points, and the attacker loses about six
points of wins against it (the weakest attacker, Easy, most). +2 points sits between the two. v23 found the same with a
flat 10% fee (attacker wins 22 → 12 of 72): what makes the fee bite is how fast it rises.

## Without sabotage

| fee rise a relocation | Hard vs 18 strategies (wins, keep left, breach) | fees the defender paid a match | computer attacker vs Hard |
|---|---|---|---|
| +5 points (v24) | 31/72 (43%), 251, 19.2% | 37 | 20/24 |
| **+0.5 points (v25)** | **24/72 (33%), 266, 18.4%** | **20** | **20/24** |
| no fee | 22/72 (31%), 287, 17.8% | 0 | 20/24 |

**Read:** without sabotage the defender has less reason to move towers (nothing to dodge), so it pays about half the
fees it pays with sabotage. With v24's steep fee, dropping it cost the attacker 12 points of wins against Hard; with
v25's gentle one, the fee is worth about two matches in 72 and nothing against the computer attacker. Keeping it costs
nothing and keeps the two modes alike; it's also a little income for the side this mode is meant to help.

## Both modes together

Against Hard, over all 96 matches of each mode (the strategies and the computer attacker), attacker wins fall by the same
amount in both modes: with sabotage 41 → 34, without 51 → 44. So the gap between the modes that v24's health bonus was
set against stays where it was; the defender as a whole gains about seven points.

## What ships

The user's schedule, as asked (`moveFeeRise` 0.005), the fee kept without sabotage, and nothing else retuned. If
defenders start moving towers freely, `moveFeeRise` 0.01 or 0.02 is the lever: +2 points gives back about half of what
the attacker lost here.
