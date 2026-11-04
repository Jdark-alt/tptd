# TPTD v21: First Round, Scaling Payout, Frost & Chain, Simpler UI

Built on v20.4. Work on `bridges` first; it reaches `main` only when the user says so.

The defender has too much to figure out in the first round, the pot pays the same in wave 2 as in wave 7, Frost is weak, and Chain is a small splash. The UI shows too much and splits one object's controls across screens. This spec fixes all of that and adds two display features (a live pot meter and an MVP round summary). **No other new mechanics.**

Contents:

1. First round: 5-minute clock and a starter maze
2. Scaling payout (an experiment, gated by sims)
3. Frost buff
4. Chain rework, mutually exclusive with Splash
5. Live pot meter
6. Round summary with MVPs
7. UI pass
8. Online, computer opponent and sim bots
9. Sims to run and report
10. Tests
11. Docs to update

Every number below goes in `RULES` (or the slider/effect tables), never hardcoded elsewhere. This changes the wave simulation and the start of a match, so **bump `PROTO` to 11**.

---

## 1. First round

### 1.1 Planning clock

- New rule `planSecsFirst: 300`. Round 1 gives **both sides 5:00**; rounds 2 onward stay at `planSecs` (180).
- Everything else about the clock is unchanged (when it starts, test runs counting, time up sending the plan as it stands, `planSecs: 0` switching it off).
- If `planSecs` is 0, round 1 has no clock either. The test suites rely on that.

### 1.2 Starter maze

When a match starts, after the terrain is laid (`startMap`), the board gets a free **starter maze**: the walls that `RULES.starterPresses` (3) presses of Auto-maze would build on the empty board, each press with the first-wave budget (`autoMazeFirst`, 60). That's roughly 30 walls, a three-column serpentine.

- **Free.** The defender still starts with `startDef` (300) coins free.
- **Ordinary walls.** They can be removed or swiped away for the usual 5-coin refund, built over by a tower (the tower replaces the wall, as now), bridged from round 2, and so on.
- **Seen by the attacker.** The starter walls are in `seenGrid` from round 1 and are not "new" (`fresh: false`). Moving away from the starter maze hides the new layout, as with any build, so a defender who keeps it trades secrecy for coins.
- **Deterministic.** The maze is a pure function of the map (seed and terrain). Online, both devices build it themselves from the shared seed, and nothing extra travels. Auto-maze's search is sliced between frames for the button. The starter maze must call the same search synchronously, and its result must not depend on the slicing. Add a test that two runs on the same seed give identical grids.
- **Undo.** The starter maze is the round's starting point. Undo never takes it away, and "back to how the round began" means with the starter maze.
- **The Auto-maze button** still works in round 1 with its normal 60-coin budget, building around the starter maze (it is add-only, as now).
- **If the search builds nothing useful** on a map (rock in the way, for example), the match simply starts with whatever it built. Log the starter maze's route length in the sims (section 9) so odd maps show up.

### 1.3 The attacker's round 1

- The attacker's board in round 1 shows the starter maze as the defense they saw. The corner label reads **STARTER MAZE** instead of "NOT SEEN YET".
- Rock was already visible in round 1. Nothing else changes.
- Because there is now a seen defense in round 1, the attacker's **Test** and the wave preview's ghost wave work in round 1 against the starter maze. Sabotage stays off in round 1, as now.
- The defender's Test still starts in round 2, since there is no army to replay before then.

---

## 2. Scaling payout (experiment)

The coins paid after the final wave are never spent, so the curve peaks at the **payout after the second-to-last wave**. It is keyed to the match length, so it works for 4 to 12 waves.

**How the pot works today, for reference:** the side that got the worse of the wave gets the bigger share. The defender's share rises with breach, from 30% at no breach to 70% at 50% breach or more. So a larger swing late is a stronger **catch-up** lever late. It is not a reward for whoever is winning.

### 2.1 Formula

With `R` the match length and `r` the wave just played (1 to R):

```
p      = R <= 2 ? 0 : clamp((r - 1) / (R - 2), 0, 1)     // 0 after wave 1, 1 after the second-to-last
pot_r  = round(RULES.pot * (1 + RULES.potGrowth * p))
w_r    = RULES.swingStart + (RULES.swingEnd - RULES.swingStart) * p
defShare = clamp((0.5 - w_r) + 2 * w_r * breach / RULES.breachCap, 0.5 - w_r, 0.5 + w_r)
```

New rules: `potGrowth: 0.6`, `swingStart: 0.15`, `swingEnd: 0.25`. These replace `shareMin` and `shareMax` and are kept in `RULES` with the same meaning at `p` = 0.

The final wave uses `p` = 1. Its payout is shown but doesn't matter.

If no army marched, the split stays 50/50 of `pot_r`.

For an 8-wave match:

| After wave | p | Pot | Split range | Biggest gap between the shares |
|---|---|---|---|---|
| 1 | 0 | 200 | 35 – 65 | 60 (today 80) |
| 2 | 0.17 | 220 | 33 – 67 | 73 |
| 4 | 0.5 | 260 | 30 – 70 | 104 |
| 7 | 1 | 320 | 25 – 75 | 160 |

Switching it off: `potGrowth: 0, swingStart: 0.2, swingEnd: 0.2` gives exactly today's payout.

### 2.2 Shipping gate

Run the sims in section 9.

- **Ship the scaling payout only if** the combined build passes these checks against the same build with the payout switched off:
  - No pairing's attacker win rate moves by more than 20 points.
  - The overall attacker win rate moves by no more than 10 points.
  - The average round the keep falls in (where it falls) moves by no more than one round.
- **If it fails,** ship v21 with the payout switched off (the values above), leave the rules in place, and report the numbers and what failed. The user decides from there.

### 2.3 Where the player sees it

- The summary's pot explanation uses the round's own numbers: "Defender share = 30% + 40% × (breach ÷ 50%)" becomes "35% + 30% × …" and so on, with the pot amount.
- The HUD shows the round's pot (see 7.1, item 3).

---

## 3. Frost buff

| | Today | v21 |
|---|---|---|
| Slow | 40% | **50%** (`frostSlow: 0.5`) |
| Duration | 1.5 s | **2.5 s** (`frostSecs: 2.5`) |
| Frost resist | slow 16% | slow **20%** (60% weaker, as now) and **no Brittle** |
| Brittle | — | a slowed unit takes **+20%** from direct hits and chain jumps (`brittle: 0.2`) |
| Price | ×1.35 | ×1.35 (unchanged) |

**Brittle** works like this:

- In `strike`, if the unit is slowed **before** this hit's effects are applied (`u.slowT > 0`) and doesn't resist frost, multiply the damage that lands (after armor and the 20% floor) by `1 + brittle`.
- So a unit's first frost hit isn't amplified; later hits from any tower are, for as long as the slow lasts.
- Poison ticks are not amplified.
- Splash and chain hits from a frost tower apply frost to everyone they strike, as now.

Player-facing text:

- **Frost hint:** "Slows each unit it hits by 50% for 2.5 s. Slowed units take 20% more damage from every tower."
- **Unit status line:** "Slowed 50% · Brittle".
- **Frost resist text:** "is slowed 60% less by frost and never brittle".
- Update the info overlay's tables to match.

---

## 4. Chain rework

Splash beats bunches. Chain should beat **spread-out lines and armor**.

| | Today | v21 |
|---|---|---|
| Jumps | 2, each within 1.4 cells of the **first target** | **3**, each within **2.5 cells of the previous unit struck** (`chainJumps: 3`, `chainReach: 2.5`) |
| Damage per jump | 50% | **70%, 50%, 35%** of the hit's damage (`chainFall: [0.7, 0.5, 0.35]`) |
| Armor | applies | **ignored**: no armor reduction and no 20% floor |
| Repeats | — | never the original target, never a unit twice in one chain |
| Effects | frost, poison | unchanged: each jump applies the tower's frost and poison |
| Price | ×1.5 | ×1.5 (unchanged) |

Further rules:

- **Rolls:** jumps still never roll for accuracy, and only start from a hit.
- **Target choice:** each jump goes to the nearest eligible unit within reach of the previous one. Ties go by the existing deterministic order. The chain stops early if none is in reach.
- **Brittle** applies to jumps (section 3).
- **Sappers** can be struck by jumps, as now.

### 4.1 Chain and Splash are mutually exclusive

- **In the tower card:** turning Chain on sets Splash to Off. Moving the Splash slider above Off turns Chain off.
  - The change shows in the price line at once.
  - A one-line toast says what happened: "Chain and Splash don't combine: Splash set to Off."
  - Both count as one change for Undo.
- **Presets:** none combine them today; keep it that way.
- **Auto-tune and the computer's tuning** never produce the combination. Auto-tune treats the one it would switch off as unavailable for that tower.
- **`decodeGrid` (online and saved plans):** a tower arriving with both keeps Splash and drops Chain, the same on both devices.
- **Older test fixtures** that set both (for example v19's `{chain: true, slow: true}` tower with splash 0) are fine. Fix any that set both.

### 4.2 New unit resist: Shock

- Added to the resist options beside splash, poison and frost: **Shock**, 60% less chain damage.
- Same price multiplier as the frost resist (×1.3).
- It gives the attacker a counter to the new Chain.
- Text: "takes 60% less chain damage".
- Encoded like the other resists (it changes `encodeArmy`, which `PROTO` 11 covers).

Text updates:

- **Chain hint:** "Each hit jumps up to 3 times, 2.5 cells from unit to unit, ignoring armor (70%, 50%, 35% damage). Can't be combined with Splash."
- **Counter table in the info overlay:** split the "Splash and chain" row. Splash is good against bunched waves and swarms and weak against fewer, tougher units that are spread out. Chain is good against spread-out lines and armor and weak against small, thin waves and Shock.

---

## 5. Live pot meter

During every wave (the real wave, replays and both sides' test runs), a slim bar sits in the HUD where the round's pot is shown (7.1, item 3).

- **Shape:** a tug-of-war bar. The cyan part is the defender's share and the orange part the attacker's, each with its coins as a number at its end ("+91 · +169"), and "POT 260" over it.
- **Live value:** it is the split the defender would get **if the wave ended now**. Breach is the keep damage dealt so far divided by the army's strength (Y so far / X). Use the round's formula (section 2).
  - It starts at the "no breach" split and moves toward the defender as units reach the keep.
  - It eases to each new value over about 0.3 s, and numbers tick rather than jump.
- **Empty army:** it shows the 50/50 split and doesn't move.
- **At the end of the wave:** it settles on the real result, which then shows on the summary.
- **Display only.** It reads the wave's state and never changes it, so determinism is untouched.
- **On phones:** it fits the HUD at 390 px. Drop the "POT" label before shrinking the numbers.

---

## 6. Round summary with MVPs

The summary leads with what matters. The details stay, collapsed.

- **Top row, three big numerals (Doto):**
  - **Keep −X**
  - **You +Y** (your coins from the pot, in your colour)
  - **Opponent +Z**
  - In pass-and-play, "You" is the side whose turn comes next. In the end screen, show totals.
- **MVP tower:**
  - Chosen by most damage dealt this wave (`g.dealt`). Ties go to the lower tower number.
  - Shown as "Tower 3 · 41% of all damage" with its effect dots.
  - The tower is ringed on the board while the summary is open.
  - Hidden if no tower dealt damage.
- **MVP group:**
  - Chosen by the most keep damage this wave. This needs a new per-design tally of Y. If nobody reached the keep, use the group that got furthest on average.
  - Shown as "Brute ×6 · 62% of keep damage".
- **Sappers:** if any were sent, one line: "Sappers landed 1 / 2".
- **Details:** everything the summary shows today goes under a **Details** toggle, closed by default. That includes the pot explanation with the round's numbers, bridges refunded and the rest.
- **Handoff card (pass-and-play):** shows the same three numbers in one line.

---

## 7. UI pass

The rules for this pass:

1. Everything you can do to a thing happens on that thing's card.
2. Cards never scroll, at 1366×860 desktop or at 390 px portrait.
3. Every card has the same footer.
4. Remove explanatory text from the panels. One contextual line at most; the rest lives under the global "?".

Keep the v13 look: Doto for big numerals, Geist Mono for labels, Geist for prose, the side colours, hairlines and 4–6 px radii. Check every item at 390 px portrait (the board transposes).

### 7.1 HUD

1. **Coins up top.** Your **free coins** become the biggest numeral in the bar, in your side's colour, beside the keep. Both sides' **worth** sits beside it, smaller but readable (at least 14 px numerals). This replaces the 11 px "WORTH DEF 300 ATK 300" line.
   - During a wave and on the summary, both sides' coins show.
   - The opponent's free coins stay hidden, as now; only their worth shows.
2. **Coin change.** After each wave, the pot result animates onto both numbers ("+120", "+80") over about 1 s.
3. **Pot in the HUD.** The round's pot shows during planning ("Pot 260 · 30–70"). It becomes the live meter during the wave (section 5).
4. **One bar.** Round ("1 of 8"), keep, clock and coins sit in one HUD bar.
   - The clock grows to a numeral size and turns red for the last 30 s.
   - On phones the bar may wrap to two rows: row 1 for round, keep and clock, row 2 for coins and pot.
5. **No hint sentence.** The line under the bar ("Walls bend the route…", "Choose which units march.") goes. Its content moves into "?".

### 7.2 Defender's build screen

6. **One step.** The Build and Ready steps merge. The panel footer has **Test** (from round 2) and **Lock in**; Lock in replaces "Next: Ready" and "Ready".
   - Ready's counters (towers, walls, route, unspent) are dropped: the coin bar and route readout already show them.
   - Online, Lock in still opens the wait card with Keep planning.
7. **Intel on the build screen.** The army seen last wave sits as a compact strip under the route readout: icon, count and name per design, one line ("Runner ×10 · Brute ×3").
   - Tapping it expands each design's stats.
   - In round 1 it is hidden.
8. **One tool row.** Wall · Tower · Remove · Shapes, then **Auto-maze · Auto-tune · Undo** as icon buttons, in one row on desktop.
   - On phones it may wrap to two rows, with no labels under icons beyond what fits.
   - Shapes opens its pieces in a popover.
   - Hints stays as the switch beside the panel title.
9. **No paragraphs.** The helper paragraphs in the side panel (drawing walls, rough ground and rock, "No towers yet…", bright walls) go.
   - One contextual line remains, for example "Tap a tower to tune it, drag to move it."
   - Terrain is explained by a legend under "?".
   - The helper row's result line after Auto-maze or Auto-tune stays; it's feedback, not instruction.
10. **Bare coin bar.** The coin bar's "Towers 40 · Walls 45" labels go; the coloured segments stay, with tooltips (a hold on touch).
11. **Tower strip.** One chip per tower in a scrollable row ("T1 40 · T2 76 · …") with effect dots.
    - Tapping a chip selects that tower and opens its card.
    - It sits above the tool row. Hide it when there are no towers.
12. **Effect dots on the board.** Each tower's board icon gets small dots in the effect colours (frost, poison, chain), so the defense reads at a glance. The same dots show in the attacker's view of seen towers.

### 7.3 Tower card

All of this fits on one card without scrolling: at 1366×860 in the side panel, and at 390×844 as a half-height bottom sheet.

13. **Header:** "Tower 3", its price, and "refund +X" small under the price.
14. **Presets:** one row of small chips: Basic · Cannon · Sniper · Frost, each with its price.
15. **Sliders:** five compact rows (Range, Damage, Accuracy, Fire rate, Splash), each about 32–36 px.
    - Each row has the name, one short value and the price of the next step (fire rate: FREE).
    - Short values: "2.5 cells", "18/s", "80%", "1/s · 18 per hit", "Off" or "0.9 cells".
    - Detail goes in a tooltip (hold on touch). For example "80% per shot at this fire rate" moves into the tooltip.
    - Per-row hints move to "?".
16. **Effects:** three toggle chips in one row: **Frost · Poison · Chain**, each with its price multiplier ("×1.35"). The Chain and Splash exclusivity applies (4.1).
17. **Stat line:** one line, "Expected 14/s · covers 9 route cells · 6.2 s under fire".
18. **Footer** (the same on every card in the game, see 7.6): **Remove (+refund) · Copy tuning · Done.**
    - **Remove** removes the tower with the existing toast and Undo. No trip to the Remove tool.
    - **Copy tuning** sets a tuning brush. The Tower tool's chip reads "Tower · T3 tuning ×". New towers are placed with that tuning (priced as usual) until the brush is cleared with × or a new copy.
19. **Phones:** a half-height bottom sheet. The board stays visible above it and scrolls or pans so the selected tower sits centred in the visible part. No scrolling inside the sheet; tighten spacing until it fits at 390×844. The "Tips" button goes (see 28).

### 7.4 Attacker

20. **Three steps.** The steps become **Army · Sabotage · Wave**. The footer has **Next** (on Army and Sabotage) and **Lock in** on every step, so a player can lock in from anywhere. The Ready step goes.
    - Its army summary is already in the coin bar and the Wave step.
    - An empty army still asks for a second press.
    - **Test** sits beside Lock in on the Wave step, from round 1 now (1.3).
    - In round 1 and the final wave, Sabotage stays in the tabs but shows its "no sabotage this wave" line.
21. **Inline unit editor.** Tapping a design's row expands it in place, instead of opening a separate card. The expanded row shows its sliders (same compact row style as 15), resist chips (none · splash · poison · frost · shock), name and colour, and the shared footer (**Delete design · Copy design · Done**). One design is open at a time.
22. **Readable unit rows.** Each row shows health, speed and armor as icon plus number, never truncated ("112 · 2.3 · 6"), with the count stepper on the right.
23. **Lean Sabotage.** Each card gets one line plus its price. The knock-out cap bar shows only while a tower is tapped and in that tower's card.
24. **Lean Wave step.** The busiest-second bars and the How to use pill collapse behind a small "More" toggle once the How to use card has been seen on this device (the existing `tptd-wave-guide`).

### 7.5 Wave and summary

25. **During the wave:** three live numbers in the HUD: **leaked** (units at the keep / sent), **keep damage**, and the pot meter (section 5).
26. **Summary:** as section 6.
27. **Handoff:** as section 6.

### 7.6 Everywhere

28. **One "?".** The per-card **Tips** buttons go. The global "?" opens the info overlay at the section for the current screen (build, tower, army, sabotage, wave).
29. **Shortcuts:** W, T, R, S pick the tools; Delete or Backspace removes the selected tower or closes and deletes the open design (with Undo for the defender); Escape is Done.
    - None of them fire while typing in a field.
    - List them under "?".
30. **One card pattern.** Tower card, unit design row, sapper card and any other editable thing use the same structure: header with name and price, controls, footer with Remove or Delete on the left and Done on the right.

---

## 8. Online, computer opponent and sim bots

- **`PROTO` 11.** Online changes:
  - The starter maze is built on both devices from the seed.
  - `decodeGrid` enforces Chain/Splash exclusivity.
  - `encodeArmy` carries Shock.
  - The payout uses the new formula on both devices.
  - Everything else travels as before.
- **Computer defender:**
  - It sells everything and rebuilds each round, so in round 1 it counts the starter walls in its worth (5 each) like any walls.
  - Its tuning never combines Chain and Splash.
  - Its upgrade scoring should value the new Frost and Chain fairly. At minimum, Chain's coverage term counts up to 3 jumps instead of 2. Brittle is a +20% on the damage of other towers in the frosted stretch; a simple +15% to frost's effect bonus is acceptable.
- **Computer attacker:** in round 1 it plans against the starter maze (it can use `trial` against it now). It may pick Shock against towers with Chain the way it already counter-picks resists.
- **Sim bots (`tools/sim/ai.js`):** the defender bots sell and rebuild, so starter walls are just coins. Make sure `runMatch` builds the starter maze, so the sims match the game. The `counter` bot's counter-tuning must not combine Chain and Splash.

---

## 9. Sims to run and report

Use `match.py` with `--out` and `compare.py`, same seeds throughout. Use at least 12 seeds per pairing, more if a result sits near a gate. Run against `counter` and `game:hard` defenders, the 18 strategies, and `--attackers computer` at all three levels.

1. **Baseline:** v20.4 (`git worktree` of the current `bridges`).
2. **A, Frost and Chain only:** v21 with the starter maze off and the payout off.
3. **B, Starter maze only:** v21 with Frost and Chain at v20.4 values and the payout off.
4. **C, Payout only.**
5. **D, Combined:** v21 as specced.
6. **D without the payout:** for the gate in 2.2.

Report:

- Attacker wins and mean breach per pairing, per run.
- Pairings that moved by more than 20 points.
- The round the keep fell in.
- Sappers landed.
- The starter maze's route length over 1,000 maps (min, median, max) and how many maps got fewer than 25 walls.
- How often towers in the sims took Frost, Chain and Splash before and after. Chain should now actually get picked.
- Whether the payout passed its gate.

Also run `scan.py` for Shock (unit pricing changed). Flag any design that beats the best defense by more than 50%.

Give your read with the data, as usual: what moved, and what you'd change. Don't tune numbers beyond this spec without saying so. The exception is the payout gate's fallback, which is already decided.

---

## 10. Tests

Run all four suites after the change. Expect to update a lot of them:

- The defender's Ready step and the attacker's Ready step are gone, so helpers like `quick_round`, `defend_round` and `attack_round` that click `#def-next` twice or `#atk-next` four times need a Lock-in click instead.
- The hardcoded numbers in round 1 (starter maze, 5:00 clock) and the effect values change.

New checks, at least:

- **Clock:** 5:00 in round 1 for both sides, 3:00 from round 2; off with `planSecs: 0`.
- **Starter maze:**
  - Built at match start, identical for the same seed (twice in a row, and on both devices online).
  - About 30 walls with the route clearly longer than the empty board's.
  - Coins still 300.
  - Removing a starter wall refunds 5.
  - Undo never removes it.
  - The attacker sees it in round 1 with the STARTER MAZE label; the attacker's Test works in round 1; no sabotage in round 1.
  - Starter walls are bridgeable in round 2.
- **Payout:**
  - Pots and splits for an 8-wave match match the table in 2.1, rounds 1, 2, 4 and 7.
  - The "off" values reproduce v20.4's payout exactly.
  - A 4-wave match reaches p = 1 after wave 3.
- **Frost:**
  - 50% slow for 2.5 s; frost resist 20% and no Brittle.
  - A slowed unit takes 1.2× from the next hit but not from the hit that slowed it.
  - Poison ticks are not amplified.
- **Chain:**
  - 3 jumps at 70/50/35%, each within 2.5 cells of the previous unit, no unit twice.
  - Armor ignored: an armored unit takes the full jump damage.
  - Shock takes 60% less.
- **Exclusivity:**
  - Turning Chain on sets Splash to Off, and the reverse, with the toast; one Undo restores both.
  - Auto-tune never combines them.
  - A plan with both decodes to Splash only on both devices.
- **Pot meter:** starts at the no-breach split, moves as units reach the keep, ends on the summary's numbers; 50/50 for an empty army; identical waves with and without it (it changes nothing).
- **Summary:** the three numbers, the MVP tower (most `dealt`) and the MVP group (most keep damage), Details collapsed.
- **UI:**
  - The tower card has every control (presets, five sliders, three effects, Remove, Copy tuning, Done) visible without scrolling at 1366×860 and at 390×844.
  - The unit row editor the same.
  - Remove on the card removes with Undo.
  - Copy tuning places the next tower with that tuning.
  - The tower strip opens the right card.
  - Coins are in the HUD at 390 px with nothing clipped.
  - Shortcuts work and don't fire while typing.

---

## 11. Docs to update

- `CLAUDE.md`: current build v21, "The game as it stands" (first round, starter maze, payout, Frost, Chain, Shock, the new step structure, pot meter, summary), the sim results under "Balance", and the test suite descriptions.
- The info overlay: How to play, Core mechanics, the counter table, the rules table and the payout line; the colophon and tagline version (`prototype v21`).
- Save this spec as `docs/specs/v21-first-round-payout-towers-ui.md`.

## Open questions (decide in playtests, not now)

- Is 3 presses the right starter maze, or does it make round 1 too comfortable for the defender?
- Is Brittle at +20% too strong on splash-frost towers?
- Does Copy tuning get used, or does the tower strip make it unnecessary?
