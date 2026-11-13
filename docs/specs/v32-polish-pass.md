# v32: Polish pass (board, gates, maze help, panels, sound, motion, towers)

Built on v31 (`PROTO` 20). Mostly cosmetic. Two items touch rules and need checks: the random gates (4) and the new Auto-maze shape (5). Everything else is look, sound and feel.

**Ground rules for every item:**

- Anything visual is render-only. The simulation, its random numbers and the online state must not change (see "Determinism" in CLAUDE.md). Where a visual angle or position lags the real one, keep a separate display value.
- Respect reduced motion. Work at 390 px portrait. Keep one self-contained `index.html`.
- The fonts stay as they are.

Suggested order: 1–3 (board), 4–6 (gates and maze help), 7–8 (panels), 9 (sound), 10–11 (motion), 12 (towers).

---

## Board

### 1. A little brighter

The board reads too dark. Lift the overall map brightness slightly, about 10–15%: the board's ground fill, the cell grid, the terrain, and the darkness of the lighting pass (`lightBegin`/`lightEnd`). Towers, units, the route and effects must still stand out as much as they do now. Show before and after screenshots of a mid-wave board.

### 2. Rough ground: one uniform texture

Rough ground (the stippled tiles units can cross but nobody can build on) currently draws texture that changes from tile to tile and forms chunks across clusters, which can look like something it isn't. Give every rough tile **the same uniform, consistent texture**, the way rock tiles are all drawn alike. It must still be clearly different from rock, open ground and walls at a glance.

### 3. Menu scenes and hero

Apply the same brightness lift to the start screen scenes so the menu and the board feel like one game.

---

## Gates and maze help

### 4. Random entry and exit

Today `ENTRY` and `EXIT` are fixed: the middle row, left and right edges, every match.

**New:** the entry stays on the left edge and the exit on the right, but **each gate's row is picked per match from the map seed**, in **opposite halves**. If the entry is in the top half, the exit is in the bottom half, and the other way round. Keep each gate at least 2 rows from a corner so it can't be sealed off trivially.

- `ENTRY`/`EXIT` become per-match values set in `startMap`, along with `GATES` and anything else derived from them. Both online devices already build the map from the same seed, so they agree without sending anything new. Bump `PROTO` to 21 anyway, so a v31 device and a v32 device never share a match.
- Terrain generation, the starter maze, the bots and the hints must all use the new gates.
- Fixed-scenario tests click known cells. Add a rules switch (e.g. `RULES.fixedGates`) that keeps today's middle-row gates, and turn it on in those suites.
- **Check** with `terrain.py` over 1,000 maps: starter route length and attacker win rate before and after, plus any maps where the gates leave too little room to maze. Report it.

### 5. Auto-maze: build a double-pass wall

Today Auto-maze tends to lay a few long walls across the map. **New preference:** build a **single wall line of about 4–5 cells that the route is forced to pass along on both sides**, there and back like a hairpin around a spine, ideally tucked into a corner near a gate. A tower placed on that wall then covers the route twice.

- Add this to `mazeSearch`'s scoring: route length still counts, plus a bonus for route cells that pass close to the *same* wall cells from both sides. Tune it until the typical Auto-maze result shows at least one clear double-pass wall when the budget allows.
- The starter maze is built with Auto-maze presses (`buildStarter`), so it will change too. That's fine, but **report the starter maze stats over 1,000 maps** (walls, route length) against v31, and run `match.py` before and after, since the starter maze affects balance.
- The wall hints (glowing suggested walls) should follow the same preference where they reuse this search.

### 6. A subtle tower suggestion

Like the wall hints, the defender sometimes gets **one tower suggestion**: the spot that covers the most route, counting each pass of the route separately, which is usually the double-pass wall from item 5. Reuse the scoring Auto-tune already has (route cells in range).

- **Very subtle and ignorable:** a faint pulse or outline on one cell. No arrow, no text, no sound.
- **Occasional:** at most once per round, only in the first 20–30 seconds of planning, only while Hints are on, and only while the defender has the coins for a default tower. It fades away by itself, and disappears as soon as the player places any tower.
- Never covers or blocks a click. Never shows on the attacker's screen.

---

## Panels and pop-ups

### 7. A modern, animated look for pop-ups and side panels

Pop-ups (the round summary, handoff cards, the info overlay, toasts, confirm cards) and the side panels (the defender's tower card, the attacker's army and design editor) look flat and old-school next to the new menu.

- Keep the fonts. Restyle the surfaces: soft gradients, subtle depth, and backgrounds that blend into the backdrop. For example a faint, blurred slice of the board's own art, grain, or a glow in the side's colour (defender cyan, attacker orange), never loud.
- Animate entry and exit: a short rise or fade, not a slide-in from off-screen. Sections can stagger in. No animation with reduced motion.
- Text contrast must stay at least as readable as now. Check phone width and portrait.
- Show the user screenshots of the summary, the tower card and the army panel before and after.

### 8. Bigger unit icons on army cards

On the attacker's army cards the unit icon (`unitSVG` → `unitIconURL`) is tiny, so players can't see the shape. **Enlarge it** so the unit reads clearly at a glance, about two to three times its current size on desktop and still clear at 390 px. Re-render the icon at the larger size rather than scaling up a small bitmap. Check the design editor's icon too.

---

## Sound

### 9. Weightier sounds

The shots sound like a glass pin tapping ("needles"), and the Mortar sounds like a drum thump. They're distracting rather than immersive. Redesign the synthesised sounds in `SOUNDS` (keep them synthesised, no audio files):

- **Shooting towers:** a high-calibre crack: a sharp transient over a low body thump, with a short tail. Railgun deepest and heaviest, Blaster punchy, Gatling a low, rapid rattle, never glassy.
- **Mortar:** a real explosion: a low boom with sub-bass, a noise burst, and a short rumble on impact (the launch can be a muffled thud).
- **Tesla, Frost, Venom:** keep their character but less piercing. Frost and Venom are quiet layers under the shot, not separate pings.
- **Mix:** take the harsh top end off (a gentle low-pass) and add a master compressor so a busy wave becomes one dense texture, not a pile of clicks. Keep the per-sound gaps and the voice cap.
- **Mute:** confirm that the speaker button in the top bar silences every sound, new and old, plus the music. It should already; test it.

---

## Motion

### 10. Turrets turn with weight

Turrets currently swing freely and snap onto the target when they fire (the simulation sets `g.ang` straight to the target). They should **feel heavy**, as if what they fire will hit hard.

- Give each tower a **display angle** that follows the simulation's aim with a turn speed and acceleration limit: it builds up speed, slows as it nears the target, and settles with a slight overshoot.
- Heavier kinds turn heavier: Railgun and Mortar slowest, Gatling quickest.
- **Never change fire timing or aim.** It's purely how it's drawn. Tune it so the barrel is on target, or within a few degrees, when the shot leaves in nearly every case. Draw the muzzle flash at the drawn barrel and the shot to the real target.
- Keep the recoil kick, and give heavy kinds a slightly bigger, slower recoil.

### 11. Units bank into corners

Units with an engine trail currently turn on the corner itself. **New:** a unit starts its turn **one tile before** the corner and finishes **one tile after**:

1. The ship tilts or twists first, a short bank, then its heading swings through the turn.
2. Its trail follows the curve it actually drew.
3. It levels out, and the trail straightens, one tile after the corner.

Display only: the unit's simulated position and route don't change. A look-ahead on the route (aim the drawn heading at a point about one tile ahead) gives the early turn, and the bank amount can follow how fast the heading is changing. Apply it to all units; it's most visible on fast units with trails. This is an experiment, so show the user a short recording and expect tuning.

---

## Towers

### 12. More serious, more threatening towers

The towers have personality, but they read slightly cartoonish, their colours clash, Frost is far too bright, and the barrels are thin.

- **Palette:** a restrained gunmetal body for every tower. Element colours become **accents only** (lights, rims, canisters), desaturated and darker. **Frost especially:** a cold steel blue, not near-white. No tower should be the brightest thing on the board unless it's firing. Turn down the lamp and glow intensity.
- **Barrels:** thicker, heavier barrels with real muzzles (brakes, shrouds, cooling fins). Gatling barrels as a solid cluster, Railgun as a long heavy rail with capacitor blocks.
- **Silhouettes:** more angular and armoured, with less rounding and fewer cute details. Keep the attack-type silhouettes from v31 and every setting visible, as v31 required.
- Use `gallery.py` to render the full v31 sheet (every attack type × elements × damage × fire rate, range and accuracy extremes) before and after, at 2× and at phone width. Show the user.

---

## Wrap-up

- Version **v32** in the tagline and colophon. `PROTO` 21.
- CLAUDE.md checklist: info overlay text for the gates and the tower suggestion, plus the four test suites (with `fixedGates` in the fixed scenarios).
- `gallery.py --perf 4`: the 160-unit wave must not be slower than v31, banking and new effects included.
- Add "What v32 changed" to CLAUDE.md, including the gate and starter maze measurements.
