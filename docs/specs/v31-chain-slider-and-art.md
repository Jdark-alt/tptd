# v31: Chain slider, tower and unit looks, 3D menu scenes

Built on v30 (`PROTO` 19). Four small changes: one UI change with a pricing tweak, and three visual changes. No balance changes beyond what the Chain slider needs.

Do them in this order, because each one uses the one before it: **1** Splash and Chain sliders → **2** tower looks → **3** unit shapes → **4** menu scenes.

---

## 1. Splash and Chain: a checkbox that opens a slider

**What the player sees:** Splash joins Frost, Poison and Chain as a chip (checkbox) in the tower card. Splash and Chain each show a slider **only while checked**. Frost and Poison stay plain checkboxes.

| | Checking it | Slider | Unchecking it |
|---|---|---|---|
| **Splash** | Opens the slider at **step 1** (0.5-cell blast, ×1.5), which is what players get today when they turn Splash on | Steps 1–3, prices unchanged (×1.5 / ×1.9 / ×2.4) | Splash goes to 0 and the slider hides |
| **Chain** | Opens the slider at **3 jumps** (×1.5), exactly today's Chain | 1 / 2 / 3 jumps at **×1.2 / ×1.35 / ×1.5** | Chain goes to 0 and the slider hides |

Splash opens at its bottom step and Chain at its top step on purpose. Either way, checking the box gives exactly the tower people get today. Players who never touch the slider still get full Chain, which is one of the game's best counters.

**Rules:**

- Splash and Chain still can't combine. Checking one unchecks the other and hides its slider, with the existing toast.
- `cfg.chain` changes from a boolean to a **jump count 0–3**. The simulation uses `cfg.chain` jumps, each with `RULES.chainFall` as now (70 / 50 / 35%). `RULES.chainJumps` stays as the maximum.
- Chain pricing moves from the single `TFX.chain.mult` to per-step multipliers `[1, 1.2, 1.35, 1.5]`, held in the slider table like Splash's `m`. Update `fxBonus` and any score or optimiser code that assumes Chain is on or off.
- **Compatibility:** anywhere a tower config comes in (bots in `tools/sim/ai.js`, `scan.py` presets, `HERO_TOWERS`, `SCENES`, `TPRESETS`, the gallery), treat `chain: true` as 3 and `false` as 0. Then update those call sites to numbers.
- **Online:** the grid encoding currently packs Chain as a flag bit (`fl & 4`). Send the jump count instead, decode it clamped to 0–3, and bump `PROTO` to 20.
- Undo, retune pricing (`towerCost(next) − towerCost(old)`), move fees and knock-out prices all work through `towerCost`, so they follow automatically. Check them anyway.
- Text: the tower card hint, the info overlay's Chain line and the rules table (×1.2 / ×1.35 / ×1.5 per jump count), the pricing callout.
- Tests: update anything that hardcodes Chain as a boolean or reads the Splash slider as always visible.

---

## 2. Tower looks: every setting visible, the same way every time

**The problem:** the turret's colour comes from the *last* element added, so a Chain tower with Frost and Poison reads as a purple Chain tower, with Frost and Poison shrunk to small corner dots. The user wants **everything on a tower visible from its appearance, consistently**.

**The rule:** a tower's look is built from fixed layers. Each setting always draws in the same place, the same way, whatever else is on the tower. Nothing is decided by "the last one added".

**Silhouette = attack type.** Three clearly different shapes, readable at a glance at normal zoom and on a phone:

- **Shooting tower** (no Splash, no Chain): today's turret family. Fire rate keeps choosing Gatling / Blaster / Railgun, so barrels still read slow-heavy against rapid.
- **Splash tower:** a **disc**. Round plinth and round turret, like a mortar dish. Splash step = size of the dish or number of rings.
- **Chain tower:** its own silhouette, nothing like the other two. For example a spire, coil or pylon with conductor nodes. Chain jumps = number of nodes or coil rings (1–3).

**Every other setting gets its own fixed slot**, drawn independently:

| Setting | Must be visible as | Notes |
|---|---|---|
| Frost | Its own visual (e.g. ice rime or crystals on the rim, pale-cyan light) | Shows the same with or without Poison |
| Poison | Its own visual (e.g. venom canisters or tubes, green light) | Shows the same with or without Frost |
| Damage | Power lights (today's pips) or equivalent | Same place on all three silhouettes |
| Fire rate | Barrels on shooting towers. Splash and Chain towers need their own cue (e.g. a pulse or spin speed, or a cell indicator) | Must read on all three |
| Range | Barrel length today. Splash and Chain towers have no barrel, so give them an equivalent (e.g. antenna or mast height) | Must read on all three |
| Accuracy | Scope | Same on all three |

- **Colour:** the body stays the defender's metal. Elements add their own colour in their own slot and never recolour the whole tower. With both elements, both colours show. The tower's light (`towerRGB`, the lamp) may blend them or alternate, but must not drop one.
- **Names:** `towerName` lists every element, e.g. "Frost Venom Tesla". Chain becomes an attack type named **Tesla** (no longer an element in `ELEM`), and Splash is **Mortar**.
- Also update the tower icons in the card and toolbar, the knock-out card, and the art in `tools/art/gallery.py`.

**Check:** extend `gallery.py` to render every attack type × {none, Frost, Poison, both} × {low, max damage} × {slowest, fastest fire rate}, plus range and accuracy extremes. Screenshot at 2× and at phone width. For each tile, someone who knows the rules should be able to name every setting from the picture alone. Show the user the sheet.

---

## 3. Unit shapes: abstract shapes that read as speed

**The problem:** units look like vehicles (slow = tank with treads, mid = rover with wheels, fast = jet). That implies health and type. A tank looks tough, but a unit can be slow *and* fragile.

**The rule:**

- **Shape = speed only.** Abstract, minimal, futuristic, beautiful. **No vehicles:** no treads, wheels, wings, cockpits or engines. Not pixelated either, but at home in the game's tech/HUD look (hairline strokes, glows, the dark slate board).
- **Size = health**, exactly as now (`unitRadius`). The user likes this and it stays.
- **Colour = army colour**, as now.
- Speed has 8 steps (0.7 → 2.8 cells/s). Use **8 shapes**, or 4 shapes across pairs of steps if 8 can't be told apart. The progression must read on its own: slowest looks heavy and inert, fastest looks unmistakably fast.
- Every shape needs a clear **front**, so heading reads.
- Motion cues scale with speed, not with a class: e.g. trail or afterimage length, a pulse rate, hover height. They come from the speed step, so the change between steps is gradual.
- Keep the existing **armour, regeneration and resist** indicators, redesigned so they sit cleanly on every shape and every size. Frost and poison hit effects must still read.
- The **sapper** keeps a distinct look so it never reads as an ordinary unit.
- Replace `unitShape`'s three classes (`block` / `round` / `arrow`) and every place that branches on them: shadows, hover, afterimage, engines, treads/wheels, lamps, the design card icon, the menu scenes, the hero.

**Be bold.** The user explicitly asked not to play it safe. Explore before settling. Render **three different families of 8 in one gallery sheet**, all in the army colours at small, mid and max health, moving on a board. Directions to try, at least one of them wild:

- **Sharpening:** solid and blocky when slow, stretching and sharpening into a blade or needle when fast (monolith → hexagon → orb → teardrop → chevron → dart → split blade → needle with a comet tail).
- **Fragmenting:** slow units are one dense whole, and faster ones break into more shards flying in tight formation, like a body that speed pulls apart.
- **Energy:** slow units are heavy rings or stacked plates with slow pulses, and fast units are bright cores trailing streaks of light and particles.

Show the user the sheet before wiring a family into the game. They'll give feedback on individual shapes, and expect another round.

Check the frame rate with `gallery.py --perf 4` on a 160-unit wave. The new shapes and trails mustn't be slower than v30.

---

## 4. Menu scenes: from flat to 3D

The three cards on the start screen (Versus computer, This device, Multiplayer) each play a looping battle scene. The user loves them, but they look flat.

**Why they look flat:** `scnDraw` draws the whole battle top-down into a canvas, then lays that picture onto the card in perspective, band by band. Walls, towers, units and effects are all painted *on the floor*, so nothing has height. The camera only drifts slightly.

**What to change:**

- **Keep the camera angles.** The low, from-the-side shots are what the user likes. Don't switch to top-down.
- **Stand the world up.** Keep the ground as the projected plane, but draw everything on it as standing objects, projected with the same camera and sorted far to near:
  - Walls as extruded blocks with lit tops and shaded sides.
  - Towers standing: plinth with height, turret on top, using v31's new tower looks.
  - Units at their height, hovering where they hover, with shadows on the ground, using v31's new unit shapes.
  - Beams, chain arcs and shells in 3D space, from muzzle height to the unit. Shells fly in an arc. Blasts and debris rise.
  - Lighting, haze, depth of field and grade stay, and now shade the sides of things too.
- **Move the camera.** Each card gets a slow, deliberate camera move that loops seamlessly with the scene. For example: card 1 pushes in slowly along the lane toward the lead unit, card 2 tracks sideways with the column, card 3 orbits slowly toward the keep's gate. Keep it gentle. It's a menu, not a trailer.
- **Technique:** prefer a hand-built 2.5D renderer in canvas 2D (project each object's points with the existing camera maths). That keeps one self-contained `index.html` that works opened as a file, with no libraries. Only consider raw WebGL (no libraries) if 2.5D can't look right, and say why first.
- **Keep:** 30 frames a second, nothing drawn while a card is off-screen, one still frame with reduced motion, phone width (390 px) and portrait. The hero board is out of scope.
- Update the comments and scene scripts that describe "tanks", "rovers" and "jets" to the new unit shapes.

**Check:** before and after screenshots of each card at desktop and 390 px, plus a short frame strip or recording of each loop, for the user.

---

## Wrap-up

- Version **v31** in the tagline and colophon. `PROTO` 20, because the Chain encoding changes.
- Follow the CLAUDE.md checklist: info overlay, slider hints, the counter table and rules table, and the four test suites.
- Run `match.py` once before and after item 1 with the same seeds. Chain at 3 jumps is unchanged, so results should match apart from bots that now choose cheaper Chain steps.
- Add "What v31 changed" to CLAUDE.md.
