# Siegeline v22 spec: Attacker wave screen, bridge routing, unit pricing, tower move fee, Auto-army

Nov 8, 2026 · @Jerry

## Scope and ground rules

- Build on `main` (v21.1, `PROTO` 12). Label it v22. Bump `PROTO` to 13: Parts B and C change rules that both devices must agree on.
- Add a v22 entry to `CLAUDE.md`. Any choice this spec doesn't make goes in a "Decisions made in the build" list in that entry.
- Keep determinism exactly as `CLAUDE.md` describes: `srand()` only, `hyp()` not `Math.hypot`, integer route costs, fixed `STEP`.
- Use the numbers given here.
- Reference prototype: `lane-board.html` (in the TPTD project, saved as `claude/lane-board-prototype.html`). Commit it as `docs/prototypes/lane-board.html`.
  - It is the source of truth for the **layout and interactions** of Part E.
  - Its map, towers and simulation are stand-ins. Use the real game's map, defense, sabotage, route and wave code instead.
- Sim evidence for Part B is in `claude/sim-findings-2026-11-08.md` (TPTD project). Copy it to `docs/research/`.

Parts, in build order:

| Part | What | Rule change |
|---|---|---|
| A | A bridge re-route counts only towers that are firing | yes |
| B | Toughness surcharge replaces the big-unit surcharge | yes |
| C | Moving or removing a tower the attacker saw costs a fee | yes |
| D | Auto-army on the Army step | no |
| E | New Wave step | no (same plan data) |

---

## Part A: Bridge re-routing

### Problem

When a bridge lands mid-wave, units re-route through `recompute()`, which uses `dangerField(S.grid)`. Since v19 that field still counts knocked-out towers, on purpose: a knock-out must never move the route, or a bridge sapper can be walked away from its wall.

The side effect: when a bridge opens next to a tower the attacker has already knocked out, the new route is priced as if that silent tower were firing. Units walk past the bridge and into live fire. This was seen in a replay: wave 7, a knocked-out tower beside a new bridge, the army taking splash from the next tower instead.

### The rule

> The route changes only when the map changes, which means a bridge landing. When it changes, everyone, sappers included, takes the cheapest route counting only towers that are firing at that moment.

- **Bridge lands:** re-route with a danger field that skips towers with `off > 0`. Do this in the bridge-landing code (`layBridge`), not in `recompute()`.
- **Knock-out lands:** no re-route, exactly as now.
- **Before the wave and everywhere else:** unchanged. The route counts every tower.
- Sappers keep following the shared route, as now. Don't give sappers their own route: a sapper that leaves the army stops being covered by it.
- The ghost wave and the forecast (Part E) use the same rule. They already run the real wave code, so this comes for free.

### Sabotage step: warn about useless bridges

- After the forecast runs, compare the route just before the planned bridge lands with the route just after.
- If they're the same, the bridge's row and its card say: "Units won't take this bridge: the route over it is under more fire."
- The bridge can still be bought. This is a warning, not a block.

### Tests

1. Fixed scenario: a knock-out on a tower whose range covers a planned bridge's new route, with the knock-out landing before the bridge. After the bridge lands, units take the bridge route. On v21.1 the same plan keeps the old route.
2. A knock-out alone never changes `S.path` mid-wave (keep the v19 test).
3. A bridge that doesn't change the route shows the warning; one that does change it doesn't.
4. Two devices replaying the same online wave stay bit-identical (`test_online.py`).

---

## Part B: Unit pricing: toughness surcharge

### Problem

Units with high health and medium-to-high speed get through almost any defense. In a scan of every health × speed design against six ~750-coin defenses, including a doctrine mix of 2 splash+frost, 2 chain and 2 heavy:

- 19 of 35 designs got more than 40% through the *best* of the six;
- 7 got more than 50% (e.g. 500 HP at 1.9 cells/s: 60%; 900 HP at 1.3: 60%).

No tower mix answered it. Retuning the health or speed price tables alone didn't fix it either; the problem is the combination.

### The rule (replaces the big-unit surcharge)

```
toughness T = (HP ÷ 150) × (speed ÷ 1.3)
price = 15 × health × speed × armor × regen × resists × (1 + 0.5 × max(0, T − 2.5))
```

- Remove `RULES.bigUnit` and the `^1.5` surcharge. Add `RULES.toughK = 0.5` and `RULES.toughT0 = 2.5`.
- There is still one surcharge rule; it now measures what makes a unit hard to kill instead of its price.
- Minimum price stays 3.
- Update the Army help text and the price tooltip: "Tough units cost more: above a toughness of 2.5 (health × speed), each point adds 50% to the price."

| Design | T | Price now | Price v22 |
|---|---|---|---|
| Swarm | 0.41 | 6 | 6 |
| Runner | 1.32 | 20 | 20 |
| Ghost | 1.09 | 16 | 16 |
| Brute | 1.73 | 35 | 35 |
| Mini-tank (275 HP, 1.9, armor 2) | 2.68 | 73 | 74 |
| Regen bruiser (375 HP, 1.6, regen 3) | 3.08 | 86 | 98 |
| 500 HP, 1.9 | 4.87 | 81 | 160 |
| 675 HP, 1.6 | 5.54 | 98 | 209 |
| 900 HP, 1.3 | 6.00 | 110 | 248 |
| 900 HP, 0.7, regen 3 | 3.23 | 92 | 109 |
| 900 HP, 2.8 (max/max) | 12.92 | 348 | 1,204 |
| 900 HP, 2.8, armor 3 | 12.92 | 1,060 | 2,529 |

Scan result with this rule: designs above 40% drop from 19 to 2, and none get above 50%. Brute, Runner, Ghost and Swarm prices don't change.

### Must check before shipping

Removing the coin-based surcharge makes **armor/regen-stacked slow units** cheaper (e.g. 375 HP, 0.9, armor 3, regen 3: about 110 → 90). The scan above used armor 0 and regen 0.

Run `tools/sim/scan.py` over armor 0–3 × regen 0–3 for health 5–9 and speed 0–4.
- If any design gets more than 50% through the best defense, keep the old big-unit surcharge as well.
- In that case lower `toughK` to 0.25, which tested equally well in the scan.
- Record which rule shipped in the CLAUDE.md entry.

### Tests

1. Every row of the table above prices exactly as listed.
2. Prices of all four presets are unchanged.
3. `tools/sim/scan.py` (extended to health 5–9 × speed 1–7) shows no design above 50% through the best defense.

---

## Part C: Tower move fee

### Problem

Moving towers is free (v19). A defender can dodge every planned knock-out by dragging the target tower one cell, so sabotage rarely pays off.

### The rule

- **Moving a tower the attacker saw costs a fee.** Removing a seen tower refunds its value **minus the same fee**, so drag and delete-and-rebuild cost the same.
- **"Seen"** means the tower stood on that cell in `S.seenGrid` (not `fresh`).
- **Fee** = `round(rate × towerCost(cfg))`. `rate` starts at 10% for the defender's first relocation in the match, and rises 5 points per relocation, capped at 40%.
- **What counts as one relocation:**
  - every drag of a seen tower off its seen cell;
  - every removal of a seen tower;
  - swapping two seen towers counts as two.
- **Free:**
  - round 1 (nothing seen yet);
  - towers placed this round;
  - moving a tower back onto its own seen cell in the same round, which refunds that fee;
  - Undo, which puts back coins and the relocation count exactly.
- **The count** lives in `S.totals.moveTries` and travels with the defender's result, like `bridgeTries`/`koTries`. Prices are computed when a plan is decoded.
- **UI:**
  - the drag label reads "MOVE TOWER · 12 COINS" instead of "MOVE TOWER · FREE";
  - the Remove label shows the reduced refund;
  - the tower card shows "Next move: 15%".

### Tests

1. A seen tower moved in round 2 costs 10% of its tuning, the next relocation 15%, and so on, never above 40%.
2. Removing a seen tower refunds value minus the fee.
3. A tower placed this round moves and sells free.
4. Swapping two seen towers charges two fees.
5. Dragging a tower back onto its seen cell refunds the fee.
6. Undo restores coins and `moveTries` exactly.
7. Online: both devices compute the same fee and coins.
8. The computer defender pays the fee too: it rebuilds rather than drags, so this hits it through the reduced refund.

---

## Part D: Auto-army (Army step)

A helper button on the Army step, built like Auto-tune and Auto-maze.

**What it never does:**
- delete a design;
- lower a slider or remove a resist;
- spend more than the free coins.

**What it does:**
- **With designs already in the army:** adds units and upgrades to them.
- **With fewer than two designs:** creates one tank-type design and one cheap fast design first. It always ends with at least two designs.
- **Choosing:**
  1. Build candidates from the zone threats of the defense the attacker saw (Part E, zones):
     - splash or chain present → favour fewer, tougher units, plus a cheap group for cover;
     - heavy shots → more cheap units;
     - frost → frost resist;
     - poison → regen.
  2. Score each candidate with `trial` twice: against the seen defense, and against `retuneAgainst(seenGrid, army)`.
  3. Keep the candidate whose worse result is best.
- **After a press:** one Undo reverts it, and a line under the buttons says what it did, e.g. "Spent 140 coins: +4 Brutes, Swarm +1 speed".

### Tests

1. It never lowers a slider or deletes a design.
2. It spends no more than the free coins.
3. One Undo restores the army and coins.
4. With an empty army it creates at least two designs.

---

## Part E: The Wave step

The Wave step becomes one screen built around the real map and a Play button. Players shape the wave against the defense they saw and the sabotage they planned, then play it to see the result.

### E1. Layout (desktop; must fit 1440×900 and 1920×1080 without scrolling)

```
┌──────────────────────────────────┬──────────────────────────┐
│                                  │ 41.2%  GETS THROUGH      │
│   MAP (real board, seen defense, │ [Auto-sequence]  [?]     │
│   planned sabotage, zones glow)  ├──────────────────────────┤
│                                  │ RELEASES                 │
│                                  │ ALL GROUPS [Even][One    │
│                                  │  after another][All at   │
│                                  │  once]                   │
│ [▶ PLAY WAVE] ━━━━●━━━━━━  14.2s │ 20s ······ 0s ▶ GATE     │
│ [Z1 ✸✻ ★★☆ ✕2][Z2 ■ ★★★ ✕0]...   │ ⋮⋮ Brute ×5 ......[■■■]│ │
│ ┌ zone card ────────────────────┐│ ⋮⋮ Swarm ×16  [·······] │ │
│ │ threat · beat it │ last run   ││ ⋮⋮ ◆ Knock-out → T3  ◆  │ │
│ └───────────────────────────────┘│ ┌ selected group tools ┐ │
│ RUNS 38.0%·6★  41.2%·7★  AUTO 55%│ └──────────────────────┘ │
└──────────────────────────────────┴──────────────────────────┘
```

- Left column: map, Play row, zone strip, zone card, runs.
- Right column: score box (aligned with the top of the map), releases with the selected group's tools, then the change log when there is one.
- The map shrinks to fit the screen height; below 1120 px wide the columns stack.

### E2. Map and Play

- **The map** is the real board as the attacker saw it (`S.seenGrid`), with bridges already on the map and the planned sabotage shown as now.
- **The playback is a forecast**: the real wave code run on a scratch copy via `offstage`, like `trial`, with its own seed, with **towers firing**.
  - It includes misses, frost, chain, knock-outs landing and bridges landing (Part A routing).
  - It never touches the match state, the random stream or the plan sent online.
- **Rerun the forecast** after every change. During a drag, rerun at most every 150 ms; always rerun on release.
- **Units fade with their health.** A unit that dies leaves a small ✕ in its colour where it fell.
- **"N to leave"** shows beside the gate while units are still waiting.
- **When the clock reaches the end of the wave,** the map shows the result: "38.0% GOT THROUGH".
- **▶ PLAY WAVE** is the main action: large, orange, with a pulsing ring until the first press. Space toggles it.
  - The clock is a slider from 0 to the end of the forecast. It plays at 3× normal speed.
  - **Slow-mo:** while a zone is selected, playback drops to 1× whenever any unit is inside that zone.
- **Replaces** the Wave step's master time slider, path strips, busiest-second bars and the attacker's separate test run.
- The defender's test run is unchanged.

### E3. Score box and Auto-sequence

- **"GETS THROUGH"** shows the forecast's breach % and "N of M units".
- **"BEATS AUTO"** badge appears when the plan's forecast is higher than Auto-sequence's best (see E7).
- **Auto-sequence** improves the current plan in up to 4 steps. Each step:
  1. Try every one of these named moves on the current plan:
     - a group 3 s earlier;
     - a group 3 s later;
     - a group tighter (span × 0.5);
     - a group looser (span × 1.7, minimum 3 s);
     - a group in pulses;
     - a group leading the wave;
     - the sapper placed inside a group (35% of the way into its window).
  2. Score each move with the forecast.
  3. Keep the best one, if it beats the current plan.

  It never splits groups or times anything to a single zone, so a careful plan can beat it.
- **Locked zones (E6)** are hard limits: a move that raises a locked zone's losses is never kept.
- **It runs in chunks,** like Auto-maze's generator: "Working it out…", and the buttons are disabled while it runs. Any edit cancels it.
- **The **?** button** opens one paragraph: "Auto tries one small change at a time on your current plan: a group earlier or later, tighter, looser, in pulses, or leading, and the sapper inside a group. It keeps whichever change gets the most units through, then repeats, up to 4 changes. It never splits groups or times anything to a single zone, so a careful plan can beat it."
- **The change log card** appears under the releases after Auto-sequence, Optimize or Meet:
  - title: "Auto-sequenced" or "Optimized Z3 · kept Z1 locked";
  - every zone whose losses changed, e.g. "Z1 ✕2→0 ▲ · Z4 ✕6→8 ▼", plus overall "through 41.2% → 50.6%";
  - the moves as a numbered list, with repeats merged ("Swarm tighter (×2)").

  It clears on the next manual edit.

### E4. Releases panel

- **The axis is flipped:** 20 s on the left, **0 s ▶ GATE** on the right, with the gate edge in orange.
  - A bar nearer the gate leaves sooner, which matches the map: the rightmost bar is the front of the wave.
  - The header says "CLOSER TO THE GATE = LEAVES SOONER".
- **ALL GROUPS presets** above the rows: the game's existing three, **Even**, **One after another** and **All at once**, with the same behaviour as today. They don't move sappers.
- **One row per group:** a drag handle, colour swatch, name, ×count, speed (e.g. "1.6 c/s") and the forecast result for the group ("3 lost", "none lost"; for sappers "landed" / "shot down" / "missed").
  - Rows are reordered by dragging the ⋮⋮ handle. Row order has no meaning; only position in time does.
- **On a track:**
  - drag the bar to move the whole group;
  - drag the bar's right end (the earliest release) or left end (the latest) to stretch or squeeze it, keeping the pattern;
  - click empty track to centre the group there;
  - **every unit is a dot, and each dot can be dragged on its own.**
  - Nothing goes past 0 s or 20 s; the track simply ends there.
  - Sappers are a single ◆ on their own row.
- **A white playhead line** on every track shows the clock while it is under 20 s, and fades after.
- **Ghosts:** after Auto-sequence, Optimize or Meet, each group that moved shows a dashed outline of where it was. The header swaps to a key: "▭ BEFORE THE LAST CHANGE". Ghosts clear on the next manual edit.
- **Lens:**
  - hovering a dot lights up that unit on the map (white ring, others dimmed) and enlarges the dot;
  - if it died, its ✕ on the map is emphasised.
- **Selection:** clicking a row selects its group. Exactly one group is selected at all times, and it is the one the tools panel edits.
  - Its row in the release timeline is highlighted: an orange outline, a faint orange fill and its name in orange.
  - The tools panel has the same orange outline and starts with "EDITING ● Swarm ×8", plus "GROUP 1 OF 2" when the design is split.
  - Selection follows every action that picks a group: clicking its row or a dot, Split (the first half stays selected), Merge, Meet and Undo (if the group is gone, the first row is selected).
  - The selected group's units stay full brightness on the map; the others dim slightly.

### E5. Selected group tools

Shown under the rows, one labelled line per job:

| Line | Controls |
|---|---|
| POSITION | Lead · Middle · Last: move the whole window to the start, centre or end of the 20 s |
| DENSITY | One slider, TIGHT ↔ LOOSE: span from 0.3 s to 20 s, front fixed unless the end would pass 20 s |
| SHAPE | Even · Pulses (2–3 clusters) · Front-heavy · Trickle, inside the current window |
| MEET | [group or sapper] in [zone] [Meet] |
| GROUP | Split · Merge with [group] |

- **Meet** shifts this group so the middle of its time inside the zone matches the middle of the other one's time there.
  - It works from the forecast and corrects twice for frost and slowdowns.
  - **The list includes every planned sapper, named by its job:** "◆ Knock-out → Tower 3" and "◆ Bridge → wall C7" (use the same names the Sabotage step uses).
  - On success the note reads e.g. "Brutes now pass through Z3 with the Knock-out sapper", the clock jumps to that moment, and the zone is selected.
  - If the 20 s gate window can't reach it: "Closest possible: the gate closes at 20 s, and Brutes reach Z3 too late for Swarm to match."
  - If the other never reaches the zone: "Brutes never reach Z3".
- **Split** makes two groups of the same design, first half and second half.
- **Merge** joins groups of the same design back into one.
  - Groups of different designs with the same speed can't merge, because the plan sends release times per design. Offer **Link** instead: linked groups move and stretch together as one bar and show a chain icon.
- **Sapper rows** get only: "Inside [group]" buttons, which put the sapper 35% of the way into that group's window, plus Meet.

### E6. Zones

**Zones** are where the danger is.
- Built from the towers the attacker saw: towers whose ranges cover overlapping stretches of the route are merged into one zone.
- Numbered Z1, Z2… in the order the forecast's front unit first enters them.
- Rebuilt when the sabotage plan changes. A planned bridge can change the route, and a knocked-out tower stays in its zone but shows OFF from the moment it goes down.
- Each zone's tags come from its towers, with a fixed symbol, threat and counter:

| Tag | Symbol | Threat | Beat it |
|---|---|---|---|
| Splash | ✸ | hits everyone near its target | Spread out. Send tanks first. |
| Chain | ϟ | jumps between nearby units | Mix cheap units in with your tanks, or space out. |
| Heavy | ■ | big, slow single shots | Tank in front. Cheap units waste its shots. |
| Basic | • | steady single shots | Bunch up to swamp it. |
| Frost | ✻ | slows and clumps you | Expect bunching after it. |
| Poison | ☁ | damage over time | Regen outlasts it. |

**On the map:** each zone's route tiles glow red-orange (brighter when selected), with a label tile "Z3 ✕6". Selecting a zone draws its towers' range rings.

**Zone strip** (one chip per zone, under the Play row):
- id and symbols;
- **stars**: losses ÷ army units that entered the zone — 3★ ≤ 5%, 2★ ≤ 20%, 1★ ≤ 40%, else 0★;
- **✕ count**, which ticks up live during playback and shows the forecast total otherwise;
- after any change, a **delta** like "6→0 ▲" (green) or "5→8 ▼" (red), compared with the plan before that change;
- **LOCKED** tag when locked.

Clicking a chip selects the zone and jumps the clock to that zone's most crowded moment.

**Zone card** (under the strip):
- **Left:**
  - title, e.g. "Z4 Chain + Heavy ★★☆";
  - **THREAT**: one line per tag;
  - **BEAT IT**: the counters, deduplicated.
- **Right: LAST RUN · EVERY ZONE**, a row per zone with numbers only:
  - zone id;
  - deaths by unit type with colour dots (e.g. "● 7 Swarm ● 3 Runners", or "0 died");
  - total damage that zone's towers dealt (e.g. "826 dmg").

  The selected zone's row is highlighted. No sentences here.
- **Buttons:** **Optimize Z_** and **Lock Z_ / Unlock Z_**. Lock's tooltip explains it.

**Optimize Z_** is Auto-sequence with a different score: fewest losses in that zone first, then overall breach (`−zoneLossValue + 5 × breach`). Locks still apply.

**Lock** records the zone's current loss count as a cap. Auto-sequence and Optimize may never raise it. Manual edits can, and the chip's delta shows it.

With no zone selected, the card shows one line: "Pick a zone above to see what it does, how to beat it and how your wave did there."

### E7. Runs

- **Every press of ▶ PLAY WAVE saves a run,** unless the plan is identical to the last saved run. Keep the last 8.
- **Chips** show "41.2% · 7★" (total stars across zones). The best one is green, and flashes when a new best is set.
- **Tapping a chip** shows that run's losses as grey ✕s on the map, alongside the current ones, and offers **Restore this run**.
- **AUTO chip** (dashed): Auto-sequence's result from the plan as it stood when the Wave step opened. Compute it in the background on entering the step. This is also the score behind "BEATS AUTO".
- Runs belong to this round's planning only, like Undo.

### E8. Data model and protocol

- No protocol change for Part E. The plan still sends `tl.s`, `tl.e` and `tl.pos` per design, and each sapper's launch time, through `makeAtkPlan`.
- **Groups are UI only.** A design's groups are lists of its unit indices, kept with the attacker's local state.
  - When sending, every group's release times go into that design's `tl.pos` (sorted), with `tl.s` and `tl.e` set to the min and max.
  - Groups persist through the round. Next round they persist if the design's count is unchanged, otherwise they reset to one group.
- Release times are kept in seconds in the UI and converted to the 0–1 timeline scale when sent.
- Undo covers every change on this step, including Auto-sequence, Optimize, Meet, Split, Merge and presets. One press is one change.

### E9. Removed from the Wave step

The master time slider panel, per-group path strips, the busiest-second histogram, the "How to use" card, and the attacker's separate test-run button.

The ghost wave code stays: the forecast is built on it, with towers firing.

---

## Other places to update

- **Help page:**
  - Army section: the new price rule.
  - Defender section: the move fee.
  - New Wave plan section, short: releases, groups, zones, Play.
- **`CLAUDE.md`:**
  - v22 entry;
  - "The game as it stands": routing rule, price rule, move fee, Wave step;
  - "Determinism": the forecast runs offstage with its own seed (`seedFor('forecast', round)`).
- **Computer attacker (`tools/sim/ai.js` and the in-game bot):**
  - prices come from the new rule;
  - the bot's sequencing can call Auto-sequence.
- **Computer defender:** pays the move fee through reduced refunds.
- **`test_local.py`:** replace the Wave step tests that cover the removed controls.

## Tests (Part E)

1. The layout fits 1440×900 and 1920×1080 with no page scroll and no horizontal scroll. At 1280×800 the overflow is at most 30 px.
2. Dragging a bar toward the gate makes its units leave sooner, and they appear further along the route on the map at the same clock time.
3. A single dot drag changes only that unit's release.
4. Nothing goes outside 0–20 s.
5. Split then Merge restores the original release times.
6. Merge isn't offered across designs; Link is offered only for equal speeds.
7. Meet with a sapper lines the group up with that sapper in the chosen zone, or shows the 20 s message.
8. Every planned sapper appears in the Meet list with its job name.
9. The highlighted row in the release timeline is always the group named in the tools panel's EDITING line, after clicks, Split, Merge, Meet and Undo.
10. Zone stars, ✕ counts and the LAST RUN rows match the forecast's death list and each tower's damage dealt.
11. Locking a zone, then Optimizing another, never raises the locked zone's losses.
12. The change log lists every zone whose losses changed.
13. Each Play press saves a run; pressing again with no change doesn't.
14. Restore brings back that run's plan exactly.
15. The forecast never changes `S`, the match's random stream or the encoded plan (compare before and after).
16. The plan sent online for a split design equals the same release times entered without splitting.
17. No console errors through a full click-through of every control (the prototype's checklist).

## Sims to run after the build

- `tools/sim/match.py`: all 18 strategies against `counter` and `game:hard`, before and after. Report attacker win rate overall and for the big-unit strategies.
- `tools/sim/scan.py`: extended grid from Part B.
- Attackers were already a little weak. If overall attacker wins drop by more than 3 points, flag it in the CLAUDE.md entry rather than tuning other numbers in this build.
