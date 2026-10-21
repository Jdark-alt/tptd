# Siegeline v19 spec: Tower Accuracy & Wave Scrubber

Oct 21, 2026 · @Jerry

## Summary and scope

v19 gives the attacker more control: units lose dodge, towers miss unless the defender pays for accuracy, and a wave scrubber lets the attacker place each unit group on the map at any moment of the wave.

- **Branch:** build on `bridges` (currently v18). Leave `main` untouched.
- **Protocol:** bump `PROTO` from 8 to 9. Army and grid encoding both change.
- **Version label:** v19. Add a v19 entry to the history in `CLAUDE.md` that links to this spec.
- **Everything not named here stays exactly as in v18.** That includes all other prices, the pot split, sabotage rules, sapper stats and the 20 s release window.

**Rules for Claude Code**

1. Where this spec gives a number, use that number. Put every new number in `RULES` (or the slider tables `TS`/`US`) so it can be tuned later without code changes.
2. Where the spec is silent and you have to choose, do not guess silently. Pick the simplest option, then list every such choice under a "Decisions made in the build" note in the `CLAUDE.md` v19 entry, as previous versions did.
3. Do not retune any other balance number to compensate. If the sims show a problem, report it; don't fix it.
4. Keep both online devices in exact agreement: any random roll uses the seeded `srand`, never `Math.random`.

## Part A: Remove dodge

Dodge is removed completely. Tower accuracy (Part B) replaces it as the source of misses.

- **Unit designer:** remove the Dodge slider, its hint, its price multiplier and its row on the unit card. Unit price becomes `15 × health × speed × armor × regen × resist`, then the big-unit surcharge as before.
- **Data:** remove `dodge` from `US`, `UKEYS`, `unitParts`, design objects and `encodeArmy`/`decodeArmy`. Drop the field from the encoding rather than keeping an always-zero slot. Old saved armies that still carry a dodge value: ignore it.
- **Presets:** Ghost used Dodge 20%. New Ghost = Health 112, Speed 1.9 (index 5), no other traits. Its price changes; that's expected.
- **Damage code:** remove every dodge roll. A shot's only chance to miss is now the tower's accuracy.
- **Rules page and counters table:** delete the row "Direct shots → Dodge → Splash". Replace it with "Inaccurate towers → Swarms and bunched waves (misses waste shots) → Accuracy upgrades, splash".
- **Sapper:** it never had dodge; nothing changes.

## Part B: Tower accuracy

Every tower starts at 80% accuracy. A new paid slider raises it to 100%, and fire rate shifts it per shot: heavy shots are more accurate, rapid fire less.

### The Accuracy slider

Add `accuracy` to `TS` and `TKEYS`, after Damage and before Fire rate. It multiplies the tower price like the other sliders.

| Step (index) | 0 (default) | 1 | 2 | 3 |
| --- | --- | --- | --- | --- |
| Slider accuracy | 80% | 87% | 94% | 100% |
| Price multiplier | ×1 | ×1.15 | ×1.35 | ×1.6 |

Tower price becomes `40 × range × damage × accuracy × splash × effects + build fee`. Default is index 0, so a Basic tower still costs 40 and all four presets keep their current prices.

### Fire rate shifts accuracy

Each shot's accuracy = slider accuracy + the fire-rate offset below, clamped to 0–100%. Store the offsets as `RULES.rateAcc = [-8, -5, -2, 0, 3, 6]`, one per fire-rate step.

| Fire rate (shots/s) | 4 | 2.5 | 1.6 | 1 (default) | 0.6 | 0.4 |
| --- | --- | --- | --- | --- | --- | --- |
| Offset | −8 | −5 | −2 | 0 | +3 | +6 |
| At 80% slider | 72% | 75% | 78% | 80% | 83% | 86% |
| At 87% slider | 79% | 82% | 85% | 87% | 90% | 93% |
| At 94% slider | 86% | 89% | 92% | 94% | 97% | 100% |
| At 100% slider | 92% | 95% | 98% | 100% | 100% | 100% |

So 100% on every shot needs the top slider at a fire rate of 1/s or slower, or the 94% step at the slowest rate. Rapid fire never reaches 100%. That is intended.

Fire rate stays **free**. Its trade-off is now: heavy shots hit more often and beat armor; rapid fire applies frost and poison more often and wastes less damage on units that are about to die.

### How a shot resolves

1. When a tower fires, draw exactly **one** roll from `srand()` for that shot, always, even when the shot's accuracy is 100%. This keeps the random stream identical on both devices.
2. Roll < shot accuracy ÷ 100 → **hit**. Otherwise → **miss**.
3. **Hit:** everything works exactly as in v18 (armor, the 20% armor floor, splash, effects).
4. **Miss, single-target tower:** no damage, no effects. The shot is spent.
5. **Miss, splash tower:** the blast still goes off at the target's position. The target takes nothing. Every other unit in the blast takes the same splash damage it would have taken on a hit. No second roll for them.
6. **Effects only land on units that take damage from the shot.** A missed target gets no frost and no poison. Units caught in the blast of a missed splash shot do get the tower's effects, as they would on a hit.
7. **Chain:** only jumps from a hit. Chain jumps never roll; they always land, at half damage as today.
8. **Sappers** are shot like any unit, so they benefit from misses too.

### What the players see

- **Miss on the board:** the projectile lands about 0.3 cells to one side of the target with a small grey puff and no damage number.
- **Accuracy slider label:** "87% · 82% per shot at this fire rate".
- **Fire rate slider label:** "2.5 per second · 7.2 per hit · 82% accurate". Replace its hint ("Same damage either way…") with: "Free. Heavy shots hit more often and punch through armor. Rapid fire keeps frost and poison going."
- **Tower card:** add an Accuracy row ("82% per shot") and an "Expected damage" row = damage per second × per-shot accuracy, e.g. "18 per second · about 14 after misses".
- **Price formula line** on the tower card gains the accuracy multiplier.

### Encoding

Add the accuracy index to each tower in `encodeGrid`/`decodeGrid` as a new slot after the effect flags (`a[10]`). A missing or invalid value decodes as 0 (80%).

## Part C: Wave scrubber

The scrubber replaces auto-align. A master time slider previews the whole wave on the map, and at any paused time the attacker can drag a unit group along the route; the group's spawn time moves so it is exactly there at that moment.

### Where it lives

- On the attacker's **Wave** step, above the existing per-design timeline tracks.
- Remove the auto-align button, its tile picker and its code. The scrubber does the same job, and more.
- The existing tracks (start, end, spread, dot positions) stay and keep working. The tracks and the scrubber edit the same data, so a change in either shows in the other immediately.

### The master slider

- Runs from 0 s to `RULES.planMax` = **60 s**, in steps of 0.1 s. Label: "T = 10.0 s".
- A play/pause button next to it plays the preview at 1× from the current T, and stops at 60 s. Dragging the slider pauses play.
- Default T when the Wave step opens: 0 s.
- 60 s is fixed for now, not computed from the route. The 20 s release window is unchanged; the extra time is walking time.

### What the map shows at time T

- Every unit that has spawned by T is drawn as a ghost dot at its planned position, in its design's colour, slightly transparent so the real board stays readable.
- Sappers are drawn too, as their usual diamonds.
- Units not yet spawned are not drawn. Each design's track shows "3 still to spawn".
- Units that would have reached the keep by T are drawn stacked at the keep with a count badge ("×4").
- The dotted route shown is the route at time T (see Part D for how bridges change it).
- A small label on the board: "Planned positions on the defense you saw. Frost, knock-outs and the defender's changes will move them."

### How positions are computed

Positions must match what a real wave would do if no tower fired. So:

1. Run a **ghost wave**: the real wave simulation on the defense the attacker saw (`S.seenGrid`, bridges on the map included), with every tower disabled and no damage, using the real unit movement code.
2. Record every unit's and sapper's position every 0.1 s, from 0 to 60 s.
3. Scrubbing only reads these samples. Interpolate between samples for smooth play.
4. Rerun the ghost wave whenever the army, the timeline, the sabotage plan or the Part D toggle changes. Rerun it once when a drag ends, not on every pointer move.
5. The ghost wave must not touch the real random stream, the match state or anything sent online. It runs on a copy, like `trial`.

Routing note: units avoid tower range in the real game. The ghost wave keeps that, because towers still count in the route's danger cost even though they don't fire.

### Dragging a group

At any paused T, the attacker can grab any ghost dot and drag it along the dotted route. The whole design group moves with it, keeping its spacing.

1. The pointer snaps to the nearest point on the route at time T. That gives a route distance D for the grabbed unit.
2. In the ghost wave, find the time at which that unit would reach distance D if it spawned at time 0: call it `walk(D)`.
3. The grabbed unit's new spawn time = T − `walk(D)`.
4. Shift the group by the difference: add (new spawn time − old spawn time) to the design's `tl.s`, `tl.e`, and every entry of `tl.pos` if it has custom positions. Convert seconds to the track's 0–1 scale by dividing by 20.
5. Spread (`tl.e − tl.s`) and the gaps between dots never change during a drag.
6. **Limits:** the group's first unit can't spawn before 0 s and its last unit can't spawn after 20 s. When a drag would break a limit, the group stops at the limit and a short toast says why: "Can't release before 0 s" or "Must be released by 20 s".
7. Dragging back to the entry tile or behind it means "spawns at T or later": spawn time = T, the dot disappears, and the track shows it as still to spawn.
8. While dragging, move the dots by shifting the recorded samples in time (fast). On release, rerun the ghost wave (step 4 above).
9. Sappers can be dragged the same way; each sapper is a group of one. Its launch time updates on its sapper track.
10. Groups are independent: dragging one never moves another.

### Most recent setup wins

- A drag simply rewrites the spawn times. Nothing remembers "this group should be at tile X at T".
- So arranging groups at T = 10 s and then dragging one at T = 15 s keeps the new spawn times only; the 10 s arrangement may no longer hold. That is intended.
- After each drag, show a faint ghost of every dot's previous position at the current T, fading out over 1 s, so a drag that undid an earlier arrangement is visible.

### Input and devices

- Works with mouse and touch. On phones the dots are small, so the grab area is at least 24 px around each dot.
- If several dots overlap, grab the one from the design whose track is selected; otherwise the one closest to the keep.
- The scrubber is local planning only. Online, only the resulting timeline values are sent, through the existing `makeAtkPlan`. The defender never sees the scrubber.

## Part D: Bridge toggle in the scrubber

A two-way toggle lets the attacker preview the wave with planned bridges landing or failing. It only changes the preview, never the real wave.

- **Shown only when a bridge is planned this wave.** Otherwise hidden, and the ghost wave runs as "Off".
- **Label:** "Plan with bridge: Lands / Fails". Default: **Lands** (the same assumption auto-align made).
- **Lands:** in the ghost wave, the planned bridge opens at the exact moment its sapper reaches its tile, as in a real wave where the sapper survives. Units already walking reroute from that moment, using the real rerouting code. Before that moment the route is the old one; after it, the new one. The dotted route on the map changes when the slider passes that moment.
- **Fails:** the planned bridge never opens. The sapper walks on and does nothing, as a failed sapper does.
- **Bridges already on the map** count in both modes; they are part of the map.
- **Knock-outs are not previewed** in either mode, even though an offline tower changes the danger cost and can shift the route. The board label from Part C already warns about this.
- **Switching the toggle** reruns the ghost wave. Spawn times don't change; only the previewed positions do.
- **Dragging with a bridge:** `walk(D)` (Part C, step 2) is read from the ghost wave in the current mode. Because the bridge opens at a fixed moment, a unit's real position after release may differ slightly from where it was dropped. Keep the new spawn times as they are; don't re-solve to make it land exactly.

## Other places to update

These all follow from Parts A–D. Each must be done in this build.

| Area | Change |
| --- | --- |
| Auto-tune (defender) | Add "accuracy +1 step" to the steps it can buy. Multiply a tower's score by its per-shot accuracy ÷ 100. Everything else about auto-tune stays. |
| Computer defender and sim bots | Remove dodge from every army idea. Let the defender's tuning consider accuracy as one more slider, priced as the slider is. |
| Computer attacker and sim bots | Remove dodge designs. Bots don't use the scrubber; they keep setting timelines directly. |
| Defender Test and attacker Test | Use the new hit rolls. No other change. |
| Time under fire, hot tiles, path preview | No change: they measure coverage, not hits. |
| Knock-out price and cap | Use slider price, which now includes the accuracy multiplier. No other change. |
| Rules / help page | Remove dodge everywhere. Add the accuracy slider, the fire-rate offset table and the "How a shot resolves" rules in short form. Update the counters table (Part A). Describe the scrubber in two sentences. |
| Unit and tower preset buttons | Ghost changes (Part A). Tower presets keep accuracy at 80%. |
| `CLAUDE.md` | Add the v19 history entry, the new rules under "The game as it stands", and the "Decisions made in the build" list. |

### Tests (`tools/tests/test_local.py`)

Add checks for at least these:

1. A Basic tower still costs 40; the 100% accuracy step on a Basic tower costs 64.
2. Per-shot accuracy matches the Part B table for all 24 slider × fire-rate pairs.
3. With accuracy forced to 0%, a single-target tower deals no damage and applies no effects; a splash tower still damages other units in its blast but not its target.
4. With accuracy at 100%, damage matches v18 exactly for the same seed (minus dodge).
5. Both online devices produce the same wave result with misses on (same seed, same plan).
6. Scrubber: dragging a group at T = 10 s keeps `tl.e − tl.s` unchanged and puts the grabbed unit within 0.2 cells of the drop point (no bridge planned).
7. Scrubber limits: a drag past 0 s or 20 s stops at the limit and shows the toast.
8. Bridge toggle: with "Lands", the ghost route changes at the sapper's arrival time; with "Fails", it never changes.
9. No dodge field anywhere in an encoded army; the unit card and designer show no Dodge row.

### Balance sims (`tools/sim`)

Run the full-match sims before and after, and report in the v19 entry: attacker win rate per bot pairing, average breach per round, and sapper landed rate. Don't change any number because of the result. If the attacker win rate swings by more than 20 percentage points, say so at the top of the report.

## Not in this build, and open questions

**Do not build these yet.** They were discussed and deliberately held back:

- Hold points (a group waits at a tile, then continues)
- Route choice per design (safest or fastest)
- Kill map for the attacker after each wave
- Two releases per round
- A planning timer. Players use 3 minutes per round as a house rule; the game has no timer and this build doesn't add one.

**Open questions for playtesting** (no code needed now):

- **80% or 70% base?** The spec starts at 80% to avoid cutting tower damage too hard at once. To try 70%, change only the first accuracy step and its rate-offset rows follow automatically.
- **Is free fire rate still fair?** Heavy shots now beat armor *and* hit more often. If everyone picks the slowest rate, either shrink the positive offsets (+3/+6) or give rapid fire a small bonus elsewhere.
- **Is 60 s long enough** for the slowest units on long mazes? If the scrubber often ends before units reach the keep, raise `RULES.planMax`.
