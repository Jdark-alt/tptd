# v33: Layout pass (crowding fee, pot growth, Auto-maze, weak walls, move fee fix)

Built on v32 (`PROTO` 21). Base-game changes that push both modes toward big, spread-out mazes with many towers and more money. Economy mode builds on this later; nothing from it is in this build.

**Why:** the defender is strongest with a few maxed towers packed at a choke point, and the game is more fun with long mazes and towers spread across the map (user playtest: Auto-maze to the last block, towers as far apart as possible). Filling the map needs more coins on both sides.

**Design rules to keep** (from the user):

- Simple rules, no special cases. Every number goes in `RULES`.
- Two-sided where it applies.
- New players' defaults stay usable: a default tower (40 coins) placed on its own still costs 40.
- Balance from sims, not guesses. Where this spec gives a starting value, run the listed variants and report; don't retune past them silently.

**Which mode gets what:**

| Change | Simple (no sabotage) | Sabotage |
|---|---|---|
| 1. Crowding fee (replaces the +10 build fee) | Yes | Yes |
| 2. Move fee charged on the seen tuning | n/a (no move fee) | Yes |
| 3. Steeper pot | Yes | Yes |
| 4. Auto-maze: 5-press starter, bigger budget | Yes | Yes |
| 4b. Auto-maze thickens weak walls | Yes | Yes |
| 5. Weak-wall overlay for the defender | No | Yes |
| 6. 30 s release window | Yes | Yes |

This changes prices, the starter maze and the wave, so **bump `PROTO` to 22**. Version **v33** in the tagline and colophon.

Suggested order: 1, 2, 3, 4, 5, 6, then the sims.

---

## 1. Crowding fee (replaces the +10 per tower build fee)

### 1.1 Remove the build fee

Today every tower pays `RULES.towerFee × towers owned` (0, 10, 20 …), with bookkeeping so sells and rebuilds stay exact: `g.fee`, `nextFee`, `topFee`, `sellValue`'s top-fee shuffle, `sellOff` and `keepFees`. **Remove all of it.** A tower's price is its slider price (`towerCost(cfg)`), and selling it refunds that price (minus any move fee, unchanged), plus or minus the crowding change below.

### 1.2 The rule

Two towers form a **pair** when they are within 2 cells of each other, measured as Chebyshev distance (the 5×5 square centred on a tower).

- **Inner ring** (distance 1: the 8 touching cells): the pair costs `RULES.crowdInner` (start **0.10**) × (price of A + price of B).
- **Outer ring** (distance 2: the next 16 cells): the pair costs `RULES.crowdOuter` (start **0.05**) × (price of A + price of B).
- Farther apart: no pair, no charge.

Prices are each tower's **full current price** (`towerCost(cfg)`, sliders and effects included), not the 40-coin base. Towers knocked offline by sabotage still count; they stand on the board.

**Layout cost** = sum of tower prices + sum of every pair's charge.

**Every action pays the difference:** placing, moving, swapping, retuning, removing or Undo works out the layout cost before and after; a positive difference is paid, a negative one refunded. The defender's coins then depend only on the final layout, never on the order it was built in. The user's test case must hold: tuning a tower down, moving it, then tuning it back up costs exactly the same as moving it directly.

**Rounding:** compute the crowding total exactly and round only the total, then pay `round(new) − round(old)`. Never round per pair, or repeated moves drift.

**Worked example** (crowdInner 0.10): a lone tower worth 100, then a default tower (40) placed touching it. New pair: 0.10 × (100 + 40) = 14, so the new tower costs **54**. A third default tower touching both adds 0.10 × 140 + 0.10 × 80 = 22: it costs **62**. Removing that third tower refunds 62.

**An upgrade on a crowded tower** costs its price change × (1 + the sum of its pairs' rates). A tower touching two others pays 60 × 1.2 = 72 for a 60-coin upgrade.

### 1.3 Where it shows

- **Tower tool or dragging a tower:** every existing tower's range ring is highlighted, and each tower shows its crowding square: the inner ring a faint red, the outer ring fainter. Where squares overlap, the red deepens.
- **Live price on the ghost tower,** recomputed cell by cell: "40" outside every square, "54 · 40 + 14 crowding" inside. When dragging an existing tower, the ghost shows what the move costs or refunds at that cell (crowding change, plus the move fee where it applies).
- **Tower card:** a line with its share of the crowding fee, e.g. "Crowding +14 · 1 nearby". A tower's share is its price × the sum of its pairs' rates; the shares add up to the total.
- **Upgrades:** slider costs in the card include the crowding change, so the number shown is what the player pays.
- **Info overlay:** replace the build-fee text with the crowding rule and the worked example. Update the tower cost callout.

### 1.4 Everything that prices towers

- **Online:** both devices compute the same layout cost from the grid. `decodeGrid` and any coin check on a received plan use the new pricing. Add the crowding total to `defWorth` so the HUD worth is right.
- **Auto-tune** prices upgrades with the crowding change.
- **v32's tower suggestion** (item 6) scores spots by route covered per coin, including the crowding charge, so it favours open spots.
- **Computer defender and sim bots** (`counter`, `basic`, the game's levels) pay crowding like players. Their placement search should see the real price, so they learn to spread out. Report whether they do.
- **Undo** restores coins exactly (it already restores state; check it with a crowded sequence).

---

## 2. Move fee: charge it on the tuning the attacker saw

### 2.1 The bug

The Sabotage move fee is `round(moveRate × towerCost(g.cfg))` using the tower's **current** tuning (`moveFeeOf`, `removeFee`, `movePlan`, `relocFees`). A defender can tune a seen tower down to the minimum (refunded in full), move it for a tiny fee, and tune it back up at no extra cost. That dodges the fee meant to stop dodging sabotage.

### 2.2 The fix

Charge the fee on the tower **as the attacker saw it**: its tuning in `S.seenGrid` on its seen cell.

- Add `seenCfg(g)`: the `cfg` of the tower in `S.seenGrid` with the same number `n` (its seen home). Towers placed this round have no seen home and move free, as now.
- `moveFeeOf`, `removeFee` and `movePlan` use `towerCost(seenCfg(g))` instead of `towerCost(g.cfg)`. The stored `g.mfee` refund on moving back stays as it is (it already records what was paid).
- `relocFees` (computer defender) uses the seen tuning from `K.seenGrid` the same way.
- Retuning a seen tower in place stays free of move fees. The fee is fixed once the attacker has seen the tower, so retuning before or after a move changes nothing.
- Update the tower card and info overlay text: "10% of its tuning as the attacker saw it".

**Test:** a seen tower worth 200, tuned down to 40, moved, tuned back to 200, pays the same move fee as moving it at 200 directly. The crowding change is paid on top, the same either way (section 1).

---

## 3. Steeper pot

Today the pot grows from 200 to 320 across a match (`potGrowth` 0.6). The user wants enough coins for many more towers and units on the map.

- **Start value:** `potGrowth` **1.75**, so 200 after wave 1 rising to 550 after the second-to-last (2.75×). Keep the swing (`swingStart`, `swingEnd`) and the formula as they are.
- **Sim variants:** `potGrowth` 1.5, 1.75, 2.0. Optionally also `startDef`/`startAtk` +25%, and report it separately.
- **HUD and summary** already read the round's pot; check the numbers still fit at 390 px.
- Interest stays as it is in this build (it moves into Economy mode later).

---

## 4. Auto-maze: a bigger starter maze and weak-wall protection

### 4.1 Five presses, bigger budget

- `RULES.starterPresses` 3 → **5**.
- `RULES.autoMazeFirst` 60 → **90** (18 walls a press at 5 coins). The starter maze becomes up to about 90 walls, filling most of the board. The Auto-maze button's round 1 budget uses the same value.
- `RULES.autoMazeShare` (40% of free coins after round 1) stays; report whether players need more.
- Keep v32's double-pass (hairpin) preference.
- The starter maze is still a pure function of the map seed (and the mode, below), built synchronously, identical on both devices. Extend the determinism test.

### 4.2 Weak-wall protection (both modes)

With a long maze, one bridged wall can skip a large part of the route. Auto-maze (each press and the starter maze) protects the walls that matter most. **It works the same in both modes** (the user's call: one Auto-maze, whatever the mode), so a player learns one behaviour and the starter maze doesn't depend on the mode.

- **Weak wall:** a wall whose bridge would cut the route by `RULES.weakWallCut` (start **0.30**) or more: (route length − route length with that wall passable) ÷ route length. Reuse the bridge hypothesis code the Remove & Inspect hover already uses.
- **Thickening:** after a press lays its walls, it spends up to `RULES.thickenShare` (start **0.25**) of that press's budget on extra walls next to weak walls. For each weak wall, worst first, try the empty cells beside it, and keep the one that brings its cut below the threshold without shortening the route. Stop when the budget share is spent or no weak walls remain.
- New walls can create new weak walls: re-check after each added wall.
- The computer defender's own maze building uses the same rule.
- No minimum route-length rule: thickening must never shorten the route, which is enough on its own.

**Report:** over 1,000 maps, starter maze walls, route length and weak walls left, with and without thickening, plus the bridge cut of sappers that land (sabotage strategies vs `counter` and Hard).

---

## 5. Weak-wall overlay for the defender (Sabotage mode only)

A defender's tool that shows every wall a bridge could use to skip 30% or more of the route.

- **Toggle:** a "Weak walls" helper beside Auto-maze, Auto-tune and Undo. On by default from round 2 (sabotage starts in round 2); the player can switch it off. Hidden when Sabotage is off.
- **Display:** a red dot on each weak wall, brighter for a bigger cut. Hover (or hold on touch) shows the existing red bridge line and "Bridge here skips 42% of the route".
- **Computation:** one route search per wall on the current grid, cached on `gridVer`. Same function as 4.2, same threshold (`RULES.weakWallCut`). Check it stays fast on a 90-wall maze at 4× CPU throttling.
- **Display only:** it never changes the grid, coins or the simulation, and never shows on the attacker's screen.
- **Info overlay:** one line under Sabotage explaining the dots.

---

## 6. Longer release window: 20 s → 30 s

So the first groups are still in the maze while new ones leave, and spread-out towers keep firing all wave.

- The wave planner's release timeline runs 0–30 s (`RULES` value for the window). Presets, Split, Meet, Auto-sequence (±3 s) and the default spreads scale to the new window.
- The computer attacker's and sim bots' timings use the new window.
- Plans from v32 don't need to decode (`PROTO` bump).
- **Performance:** `gallery.py --perf` with a 30 s, 200-unit wave must not drop below v32's frame rate on the 160-unit test. The forecast and test runs take longer; report their time at 4× throttling.

---

## Sims and report

Run against the v32 baseline, same bots and seeds, **both modes**, one change at a time and then all together. Write results to `docs/research/v33-sim-results.md`.

1. **Crowding fee:** `match.py`, all strategies vs `counter` and `game:hard`. Rate variants: 0.10/0.05 (start), 0.15/0.075, 0.05/0.025. Re-run v23's `concentrated` defense in `scan.py`: the goal is that packing maxed towers leaks more than it does today.
2. **Spread metrics** (new, logged per match): towers owned in the last round, average distance between towers, and **fill rate** (share of buildable cells holding a wall or tower in the last round).
3. **Move fee fix:** the computer defender's fees and dodges vs v32 at Hard.
4. **Pot:** the three `potGrowth` variants; attacker win rate, the round the keep falls, coins spent per side.
5. **Auto-maze:** starter maze stats over 1,000 maps (walls, route length, weak walls), 3 vs 5 presses, 60 vs 90 budget; `match.py` before and after.
6. **Thickening:** sapper landing rate and bridge cut, with and without.
7. **Release window:** 20 vs 30 s, breach and win rates.
8. **All together:** `compare.py` against baseline, both modes.

**Gate:** if the overall attacker win rate moves by more than 10 points in either mode, or any strategy by more than 20, flag it in the CLAUDE.md entry and don't retune other numbers in this build. The user decides from the data.

---

## Tests

1. A lone default tower costs 40; the build fee is gone (the second tower also costs 40 when far away).
2. The worked examples in 1.2 price exactly (54, then 62, refund 62).
3. **Path independence:** the same final layout reached by different sequences (place vs place-far-then-drag; tune down, move, tune up vs move directly; swap vs remove-and-rebuild) leaves identical coins.
4. Undo through a crowded sequence restores coins exactly.
5. The ghost price matches what placing there actually charges, on every cell (sample many cells).
6. Move fee on a seen tower tuned down before moving equals the fee at its seen tuning.
7. Online: both devices agree on coins after crowded builds, moves and retunes, and on the starter maze.
8. Starter maze: 5 presses, identical across two runs on one seed, and identical in Sabotage and Simple modes.
9. Weak-wall dots appear exactly on walls whose bridge cut is ≥ 30%; none in Simple mode; never on the attacker's screen.
10. The release timeline accepts 0–30 s; nothing leaves after 30 s.
11. The four test suites pass; update tests that hardcode tower prices, the build fee or the 20 s window.

## Docs

- CLAUDE.md: "What v33 changed", the rules as they stand, the sim results, and test suite notes.
- Info overlay: crowding fee, move fee wording, weak walls, Auto-maze budget, release window.
- Save this spec as `docs/specs/v33-layout-pass.md`.

## Out of scope (later)

Economy mode (Mines, Prospectors, interest moving into it, Call it), Power-ups mode, target priority, formations, special tiles, Classic/Advanced naming.
