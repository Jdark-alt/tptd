# Siegeline: notes for Claude Code

Siegeline (working title) is an asymmetric 1v1 tower defense played in the browser. One player defends the keep with walls and towers. The other attacks with an army they design and choreograph. The game started in a long claude.ai chat and moves here now. This file carries over what that chat learned: how the game works, why the rules are what they are, where balance stands, and how to test changes. **Current build: v11, the bridges-and-terrain test build, on the `bridges` branch. `main` still runs v9 (wall charges) for the friends' Render link.**

## Working with the user

- The user designs the game and playtests it with friends, online and in pass-and-play. Their reports are the ground truth ("attackers never win without charges", "one maxed unit can't be stopped"). Take them seriously, then measure with the simulators before changing numbers.
- For balance, they like hearing your opinion with data behind it: what you ran, what it showed, and what you'd change. Then they decide. They're fine with action when they've asked for it.
- Explain in plain words: what the player sees and feels, not code internals.
- They deploy by pushing to this repo. Keep the game a single `index.html` that works opened as a file, on GitHub Pages and on Render.
- Phones matter. Every UI change must work in portrait (the board transposes) and at 390 px wide.

## Repo layout and deploy

| Path | What it is |
|---|---|
| `index.html` | The entire game: HTML, CSS and JS in one file. No build step. |
| `server.js` | Relay server for online play. It also serves `index.html` at `/` (injecting `window.SIEGE_RELAY="same-origin"`), plus `/health` and WebSocket `/relay`. Keeps no game state. |
| `package.json` | Root dependencies for Render: only `ws`. Don't add test tooling here (Render installs it). |
| `tools/` | Simulators and browser test suites (below). Only used locally; Render and Pages ignore them. |

- **Render** (free web service): Build `npm install`, Start `npm start`. Free instances sleep after 15 minutes without inbound traffic and take about a minute to wake. The page shows "Waking the game server" and retries for 90 s. Pages send a heartbeat every 15 s, so a match keeps the server awake.
- **GitHub Pages** serves the same `index.html`. Pages hosted elsewhere only use the relay if `const RELAY_HOST = ''` near the top of the script holds the Render URL. With it empty they fall back to PeerJS, which fails between different networks. The players currently use the Render link.
- **claude.ai artifact:** there is also a copy published as a Claude artifact, where online play uses the claude.ai room capability (`window.claude.use('room')`). That code path is inert elsewhere. Keep it working, but the repo is the source of truth now.
- **Branches:** `main` is what the friends play on Render (v9, wall charges). `bridges` is a test branch (v11: bridges and terrain) that GitHub Pages serves for solo testing. Don't touch `main` from the bridges work; it merges only once the user approves. The builds speak different protocol versions (`PROTO` 1 on main, 3 on bridges) and use protocol-named rooms, so a bridges page can never join a main match.

## How index.html is organised

Search for these names; the file is long.

- **Rules:** `RULES` (all tunable numbers), `TS` (tower sliders), `US` (unit sliders), `RESIST`, `TPRESETS`/`UPRESETS`, `towerCost`, `unitCost`/`unitRaw`.
- **Pathing:** `flow` (Dijkstra cost field from the exit, in 1/`FK` units so equal routes prefer bridges), `dangerField`, `nextStep`, `tracePath`, `recompute`, `routeOpenWithout` (connectivity check for "path must stay open").
- **Terrain:** `ROUGH`/`ROCK`, `S.terrain` (one value per cell) and `S.mapSeed`, `makeTerrain` (seeded, with rerolls), `scatterTerrain` (zones and clusters), `mazeRoom` (the validity check), `startMap`, `withRocks` (puts `{ t: 'rock' }` into a grid), `newMapSeed`, `terrainKey`, `drawGround` (drawn into the terrain layer).
- **Defender actions:** `canBuild` (also refuses bridges, rough ground and rock), `tryBuild`, `removeAt`, `setTowerCfg`, `seenAs`.
- **Attacker actions:** `setDesign`, `changeCount`, `plantBridge`, `canBridge`, `bridgeCost`/`nextBridgePrice`, `plannedBridges`, `repriceBridges`, `plantTower`, `canChargeTower`, `towerCap`, `offlineNext`, `chargeStatus`. Planned bridges live in `S.charges` with `kind: 'bridge'`; laid ones in `S.bridges` (a Set of cells, shared by both sides).
- **Wave simulation:** `startWave` (UI) and `prepWave` (setup), `buildSpawns`, `makeUnit`, `waveStep`, `moveUnit`, `updateTowers`, `strike`, `damage`, `leak`, `detonate` (tower charges and laying bridges), `endRound`.
- **Flow and UI:** `setPhase`, `startRound`, `defenderReady`, `attackerReady`, `nextRound`, `renderDef`, `renderAtk`, `renderWave`, the overlays (`#ov-info`, `#ov-mode`, `#ov-wait`, `#ov-hand`, `#ov-sum`, `#ov-end`), and `frame` (main loop with the 1×/5×/10× wave speed).
- **Slider prices:** `setSlider`/`setNext` show each slider's multiplier and what one more step costs (red when unaffordable). For units the step is priced for every unit of the design.
- **Replay:** `startReplay`, `exitReplay`, `stateFrom`. `startWave` saves `S.lastWave = { seed, snap }`. A replay swaps `S` for a scratch state built from that snapshot and plays it with the same seed; the real match waits in `replay.live` (`real()` returns it). `endRound`/`finishOver` only mark a replay done, and `netCheck`/`adoptResult` wait until it closes.
- **Online:** `NET`, `PROTO`, `roomName`, `netState`, `lockIn`, `unlock`, `netCheck`, `beginOnlineWave`, `netAfterWave`, `adoptResult`, `encodeGrid`/`decodeGrid`, `encodeArmy`/`decodeArmy`, `encodeCharges`/`decodeCharges` (kind 1 tower, 2 bridge), `decodeBridges`, `clearBridges`. Transports: `roomLink` (claude.ai), `relayLink` (server.js), `peerLink` (PeerJS), chosen in `connect()` in that order.
- **Versus computer:** `SOLO`, `SOLO_LEVELS`, `soloKnows`, `thinkAttack`, `thinkDefend`, `trial` (hidden test waves, `QUIET`), `aiArmy`/`AI_ARMIES`, `buildDefense`/`AI_MAZES`/`AI_MIXES`, `mazeCols`/`MAZE_KEYS`/`mazeInfo`/`pickMazes` (maze shifts on the map), `bridgePicks`, `bridgeBlock`/`blockBridges`, `killCells`, `BRIDGE_HOLD`, `towerPicks`, `retuneAgainst`, `threatsFor`, the notes (`attackNote`, `defendNote`), and the flow (`soloStartRound`, `pumpThink`, `soloReady`, `soloBeginWave`, `brainPlan` for the sims). See "Single-player" below.
- **Handle:** `window.siegeline` is a small handle for the console and tests: `state`, `net`, `solo`, `replaying`, `rules`, `cellToClient`, `advance(sec)`. The tools inject extra internals into their own copy only.

### Determinism (do not break)

Online play sends only plans. Both devices then run the same wave and must get bit-identical results. Inside the wave simulation:

- Use `srand()`, never `Math.random`. It's seeded per match, epoch and round. `Math.random` is fine for visual effects only.
- Use `hyp()` (sqrt), never `Math.hypot`. No trig either; `atan2`/`cos`/`sin` are only for drawing angles.
- Step in fixed 1/60 s increments (`STEP`). The speed buttons run more steps per frame; they never change the step size.
- The map is part of the match: both devices derive its seed from the match code and epoch (`seedFor('map', code, ep)`), the defender's plan carries it as `ms`, and if they ever differ the defender's wins. Terrain is never randomised inside a wave, and `trial` reuses the match's map.
- Keep path costs integers. The route field is kept in 1/`FK` (64) units and each bridge cell costs one unit less: that breaks exact ties toward the bridge and never outweighs a real difference. With no bridges it plays exactly like v9.
- Rebuild state on both sides from the encoded plans (`beginOnlineWave` decodes both players' plans, its own included). Bridges are priced and capped by the rules when a plan is decoded, and nothing in a decoded grid may stand on a bridge (`clearBridges`).
- After any change to wave logic, run `tools/tests/test_online.py`. It checks that both devices end identical, including with one device at 10× speed.
- The computer opponent runs waves out of sight (`trial`) with `QUIET` set. Anything new in the wave code that touches the DOM, redraws the terrain or ends the round must be skipped while `QUIET` is true, the way `leak`, `detonate` and `endRound` do it. Effects pushed to `fx`/`floaters` are trimmed by `trial` itself.
- The replay relies on the same determinism: `test_local.py` checks that a replay ends with exactly the real wave's numbers.

### Online protocol (presence-style, absolute state)

Each side publishes `{v, id, role, code, ep, st, rd, lk, go, at, plan, res}`. The same object travels over the claude.ai room, the relay or PeerJS. The flow:

1. A player who presses Ready sets `lk` to the round number.
2. Once both sides are locked, each sets `go` and reveals `plan`. Plans stay private until both commit.
3. The wave starts when both have `go === round`.
4. The defender publishes `res` (including the bridges on the map, `br`), and the attacker adopts it if their copy disagrees, so the defender's device is the referee. Its plan also carries the map seed (`ms`). Rock never travels in a grid: it comes from the map on each device.
5. `ep` is the match epoch. A rematch or a rejoin after a reload bumps it, and the other side follows. A device that reloads mid-match can't resume; the lobby offers to restart.

### Single-player (versus computer)

The mode screen has a third card, **Versus computer**. The player picks a side and a level (Easy, Normal or Hard), and the computer takes the other seat. There are no pass-the-device screens.

**Fair play:** the computer knows only what a human in its seat would.
- As attacker: `seenGrid`, and the bridges and terrain on the map (public: both sides see them).
- As defender: its own grid, `seenArmy`, and the attacker's coins (the HUD shows those to both players).
- `soloKnows` copies that at the start of the round, before the player does anything, and the computer never reads the live state again that round.

**Propose, test, pick:** principles generate candidate plans, each is played out in a hidden copy of the real wave (`trial`), and the best one is played.
- `trial` swaps in a scratch state and runs the real `waveStep` with `QUIET` set, then restores `S`, `srand`, `uid`, the effects and the route field.
- One trial costs about 6–15 ms on a desktop, and 16–22 ms with the CPU throttled 4×. The defender's round is 60–120 trials at Hard on a terrain map (walled-off variants are tested with one spending style only), about 0.5–0.7 s on a desktop and 2.2–2.9 s throttled 4×; the attacker's is lighter.
- **Attacker** (`thinkAttack`):
  - Army ideas (`AI_ARMIES`: swarm, rush, ghost, plated, bruiser, hulk, brutes screening a swarm, runners with ghosts), each bunched and spread, against the seen defense.
  - The best few against that defense retuned to counter them (`retuneAgainst`), then with bridge and charge options:
    - bridges on the seen walls that shorten the route most (`bridgePicks`), one or two (within `bridgeCap`), priced by the rules
    - towers that cover the route (`towerPicks`)
    - a bridge plus a tower charge
    - within the caps; none in round 1 or 8
    - rough ground counts as a lane the defender can't wall: a bridge that opens onto it is valued as one that can't be walled off, and the note says so
  - Coins spent must pay for themselves: they are scored at cost × breach × later rounds that matter, capped by how long the keep would last at this pace. So it spends against strong defenses and late in the match, and not when the army already walks through.
  - A bridge also keeps paying in those later rounds, for a share (`BRIDGE_HOLD`) of what it added this wave: a small share when a wall or two at its ends would take it away again (`bridgeBlock` finds one), a bigger one when it can't be walled off.
  - Its note says which wall it bridged and how much shorter the route got, or that a new bridge didn't pay for itself.
  - Round 1 is a random opening from `AI_OPENERS`.
- **Defender** (`thinkDefend`): every maze (`AI_MAZES`: 3, 4 or 5 serpentine columns, towers in the cells covering the most route), tower mix (`AI_MIXES`) and spending style (`AI_SPEND`), against the last army scaled to the attacker's coins now. Then the best few against a panel of armies that could beat them (`threatsFor`).
  - It keeps its maze unless another is clearly better (15% margin).
  - **Terrain:** each maze family can sit a column left or right (`MAZE_KEYS`: `four-1`, `three+1`, …). `pickMazes` takes, per family, the shift that forces the longest route on this map with its holes walled off (`mazeInfo`, cached per map and bridge set), so rock in a column serves as a free wall and columns step around rough ground. Rough ground in a column is a hole like a bridge, handled by the same build modes. The note says when it shifted and how many rocks it uses.
  - **Bridges:** nothing can be built on one, so a bridge in a maze's columns leaves a hole. Every maze is tried as it is (towers placed along the route the bridges open, `aiSlots` with the bridges) and, where walls help, with the bridges walled off at one end (`blockBridges`, 5 coins a wall). Its finalists also come with a tower beside each bridge the route crosses (`killCells`, a kill zone). A maze whose columns miss the bridges is a relocation, and new walls can't be bridged for a round. The tests decide which; the note says what it did ("I moved my maze…", "I walled off one end…", "I put a tower beside…", "I built around…"), and `brainPlan` returns it as `info.response` for the sims.
  - **Guard towers (Normal and Hard):** a bridge misses if its wall has become a tower, so each finalist also comes in a guarded version, with a tower on the wall the computer would bridge itself in the attacker's place (`bridgePicks` on `seenGrid`). Its tests decide whether that pays. Hard's extra test lays a bridge on the best wall still standing. The note says when it did this.
  - Upgrades always go to the weakest tower, so no single tower carries the defense.
- **Levels** (`SOLO_LEVELS`):
  - Easy: 3 random ideas from the lighter armies, or 3 tower mixes on its current maze (built around the bridges or walling them off, never relocating), no foresight; picks at random among its top 3; at most one bridge or charge a wave.
  - Normal: everything, averaged with the likely counters; takes the second best 10% of the time.
  - Hard: everything, weighing the worst counter too; the defender also tests the last army with a bridge on its best wall; never blunders. No coin bonus at any level.
- **Variety:** a per-match seeded stream (`SOLO.rng`; tests set `SOLO.seed`).
- **Notes:** after each wave the summary shows "The computer's thinking", which says what it saw, how many plans it tried and what it chose. A note says "What held best" or "got the most through" only when it really played its best plan.

**Timing:** `soloStartRound` starts the thinking. `pumpThink` runs it in slices of about 12 ms between frames, with a 3 s cap (`THINK_MS`) on looking for better plans.
- If the player presses Ready first, `soloReady` shows the `#ov-wait` card ("Keep planning" unlocks).
- The plan uses the online plan format (`{dFree, ts, g}` or `{aFree, a, c}`). `soloBeginWave` applies it with the online decoders.
- So nothing the computer does shows while the player plans, and its plan can't depend on the player's.
- `online()` stays false in solo, so online determinism is untouched. A snapshot restores the player's own phase, and the computer thinks again.
- **Replay and thinking:** both swap `S`. A test wave can run while a replay is open: `trial` restores whatever `S` was, and `endRound` checks `QUIET` before `replay`, so a test wave never ends the replay. `soloBeginWave` closes an open replay before the computer's wave starts.

**Measured on v9 (one-wall charges; match.py, 2 seeds; bots, not humans):**
- **As defender**, attacker wins out of 34 across the 17 sim strategies:
  - `basic` bot 34, `counter` bot 18, Normal 12, Hard 10. Easy measured 31 on v8 (wall blast 1); not re-run.
  - Runner rush, maxed tanks, mini-tanks, regen bruisers and slow fat regen still beat every defender, the computer at Hard included.
  - Guard towers: against attackers that charge walls, Normal and Hard put a tower on the likely target in 1–5 rounds of every match.
- **Sim strategies with charges** (attacker bot now picks walls with `wallPicks`), against the `counter` bot:
  - "counter + wall charges" 0/2 (keep left 28). It was 2/2 with the old 5-cell blast, and 0/3 with one-wall charges and the old naive picks.
  - "counter + both charges" and "alternate + both charges" now win 2/2 in round 7 (v8: 0/2 and 1/2).
- **As attacker**, it wins every match against both bots:
  - Against the `counter` bot: Easy takes the keep in round 7 (about 4 charges a match), Normal and Hard in round 4 (1–2 charges).
  - Against the computer's own Normal and Hard defenders: Normal and Hard attackers win every match by round 5–6 (v8: 4–5; the one-wall charge and guard towers buy the defender about a round). Easy wins half.
  - Read with the balance notes below: played well, the attacker side still looks favoured.

**Measured on v10 (bridges at 50 + 20 × n, one a wave; match.py, 3 seeds; bots, not humans), against v9 on `main` with the same bots and seeds:**
- Strategies without bridges or wall charges play out identically on both builds (the tie-break only acts on bridges).
- Attacker wins over the same strategies (the 17 sim strategies plus the computer's three levels), v9 → v10: `counter` bot 36/60 → 39/60, Normal 25/60 → 23/60, Hard 23/60 → 22/60, `basic` 51/51 both. Mean keep left barely moves (122 → 121, 254 → 239, 254 → 242).
- The bridge strategies against the computer defenders leave less keep than v9's wall charges did (e.g. "alternate + bridges & towers" vs Normal: keep 417 → 114), but none wins there; against the `counter` bot "counter + bridges" now wins 3/3 (v9 wall charges 0/3, keep 36).
- **Always vs never bridge** (every strategy forced to lay a bridge whenever one shortens the route, `--opts '{"charges": "bridges", "chargeShare": 1}'`, against the same strategies that never do):
  - Against the `counter` bot, which walls bridges off but never moves its maze: never 21/42 wins (mean keep 172), always 13/42 (mean keep 37). Bridging every wave grinds the keep down for weak armies (swarm keep 736 → 110) but costs strong ones the win (maxed tanks 3/3 → 0/3).
  - Against Normal and Hard, which also relocate: never 17/42 and 16/42, always 1/42 and 2/42.
  - So neither dominates. The price decides it: at 50 + 15 × n bridging every wave beat the `counter` bot 48/54 (89%, against 56% never), at 50 + 20 it is 30%, at 55 + 20 28%, at 60 + 25 and 70 + 20 0%. Cap 2 changes nothing: after the best bridge the route is nearly direct and a second rarely saves two steps.
- How the computer defender answered bridges, per round with a bridge on the map (Normal and Hard, all runs): walled one off 49, maze already clear of them 26, moved its maze 18, built around 3, kill zone 0.
- The computer attacker lays 0.3–1 bridges a match against the computer defenders and 1–4 against the `counter` bot. Normal and Hard still win 3/3 against every defender; Easy wins 0/3 against the computer's Normal and Hard (v9 1/3). With bridges switched off (`bridgeCap: 0`) Easy takes 1/3 again and Normal and Hard reach higher breaches (62–68% vs 52–55%), partly because the defender then stops guarding walls. `BRIDGE_HOLD` 0.35/0.1 played better than 0.7/0.25 (Hard against the `counter` bot: breach 75% vs 55%).

**Measured on v11 (terrain at 5% + 5%; `terrain.py`, each match played with and without terrain on the same seed; bots, not humans):**
- Against the `counter` bot (fixed maze, never shifts), all 18 sim strategies on 40 maps: attacker wins 53% → 66% with terrain, mean keep left 135 → 116. Rough ground in its fixed columns hands weak armies shortcuts (brutes + runners 0 → 20 of 40 maps, ghosts 0 → 14, counter-picks 4 → 24), while rock slows the strongest (runner rush and maxed tanks 38 → 31). Per map the attacker won 22–100%; 6 of 40 maps moved 35+ points, all toward the attacker.
- Against the computer's Normal defender, which shifts its maze to the map, 10 strategies on 20 maps: attacker wins 30% → 23%, keep left 298 → 318. Runner rush and maxed tanks drop from 20/20 to 10/20; regen bruisers still win every map. No map flagged (the biggest swing +30 points, map 4).
- The computer attacker barely notices: Normal and Hard win every match on 12 maps either way (against the `counter` bot and against Normal); Easy wins a little more (11 vs 10 of 12, 5 vs 3 of 12). No map flagged.
- So terrain rewards the side that reads the map: a defender who keeps a fixed maze gets punished, one who adapts gets free walls.

**Roadmap the user chose (hybrid: principles for how it plays, templates for who it is):**
- **Phase B, the smart brain:** done in v8 (above).
- **Phase C, the campaign:** two tracks of about 6 missions (Hold the Keep, Break the Siege).
  - Each mission is data: a commander personality (army ideas, mazes and mixes it favours, foresight, blunders), an opening, rule tweaks (`RULES` overrides restored afterwards), limits such as no charges, and a lesson. Missions never script tower positions per wave.
  - All missions open, nothing saved (no localStorage).
- **Never:** the computer never peeks at the player's current plan, at any difficulty.

## The game as it stands (v10, bridges branch)

- **Modes:** pass-and-play on one device, online on two, or versus the computer on either side. The rules are identical in all three. Since v6 the rule changes are the one-wall charge (v7) and then bridges replacing wall charges (v10).

- **Terrain** (v11): every match gets its own map from a seed (`startMap`; online, from the match code and epoch, so both devices agree; a rematch gets a new one).
  - **Rough ground** (`roughShare = 0.05`, 9 tiles): units cross it like open ground; nothing can be built on it, and it can't be bridged (it's already open).
  - **Rock** (`rockShare = 0.05`, 9 tiles): blocks units like a wall the defender gets for free; can't be removed, built on or bridged. The attacker sees it from round 1, but it doesn't unlock charges.
  - Placement: the board is split into 3×3 zones and each gets the mean share of each kind, give or take one (0–2 tiles at 5%), in clusters of 1–3 tiles that never touch another cluster. The entry, the keep and the cells around them stay clear.
  - Validation: a route must exist, and the computer's mazes must still force at least `MAP_ROOM` (80%) of the route they force on an empty board. Otherwise it rerolls (`MAP_TRIES` 12), then halves the tiles, then plays without terrain. Over 1,000 seeds: 82% pass first time, none needed the fallback, and the worst map keeps 82% of the maze route.
- **Board and route:** 16×11 grid, entry at the left middle, keep at the right middle. Building may never close the route. Units follow the cheapest route: each cell costs 10, plus `RULES.danger = 5` for every working tower that can hit it. So units steer around tower range when the detour is short, and walls are what force them through fire.
- **Rounds:** 8. Each round the defender builds while the attacker plans, in secret. The wave then plays out with everything revealed.
- **Hidden information:**
  - The attacker sees the defense as it stood after the last wave (`seenGrid`).
  - The defender sees the last army sent (`seenArmy`).
  - Bridges and charges only work on things the attacker saw. Rebuilding on the same cell doesn't make something "new" (`seenAs`), which closed a loophole.
  - Bridges already on the map are public.
- **Economy:** both start with 300 coins. The keep has 1000 points; the attacker wins at 0, the defender by surviving 8 rounds. Each round adds a 200-coin pot.
  - Army strength X is the cost of the units sent. Through-strength Y is cost × health fraction left, for each unit that reaches the keep. Breach = Y/X, and the keep loses Y.
  - Defender's pot share = 30% + 40% × (breach ÷ 50%), clamped to 30–70%. If no army is sent, the split is 50/50.
  - Everything is fully refundable: towers at cost plus fee, walls 5 (a bridged wall is refunded automatically), units at cost. Exceptions: laid bridges and spent charges are lost, and offline towers are locked.
- **Towers:** one tower type, tuned with sliders.
  - Price: 40 × range multiplier (by square) × damage multiplier (^1.15) × splash × frost 1.35 × poison 1.45 × chain 1.5, plus a build fee of 10 × towers owned. Fire rate is free.
  - Presets: Basic, Cannon (splash), Sniper, Frost. Offline towers still block their cell and can't be removed or retuned.
- **Walls:** 5 coins each.
- **Units:** up to 4 permanent designs. Units that die come back next wave.
  - Price: 15 × health/150 × speed/1.3 × armor × dodge × regen × resist.
  - **Big-unit surcharge:** above `RULES.bigUnit = 60` coins, price = 60 × (raw ÷ 60)^1.5. A fully maxed unit costs about 1,060 instead of 407.
  - Health: 50–900 HP (raised 2.5× in v5). Speed: 0.7–2.8 cells/s. Armor blocks 3/6/10 per hit, but at least 20% of each hit lands. Dodge: 20/35/50% of direct shots; splash can't be dodged.
  - **Regeneration:** 1/2/3% of max health per second. It only heals after `regenDelay = 3` s without a direct hit (poison ticks don't count), and at most `regenCap = 10`% × level of max health per wave.
  - Resist: 60% less splash, 60% less poison, or 60% weaker frost.
- **Wave timeline:** each design is a track and each unit a dot on a 20 s timeline. Spacing between dots is time between spawns. It decides bunching versus spreading.
- **Bridges** (replaced wall charges in v10; planned in the attacker's step 3, Sabotage):
  - Placed on a wall the attacker saw, hidden like charges (so never on rock or rough ground). When the wave starts the bridge goes down: the wall's 5 coins go back to the defender and the cell is open ground for the rest of the match.
  - Drawn as a square deck with no direction (v11); neighbouring bridges join into one deck, with rails only on the outer edges (`drawBridgeShape`).
  - Nobody can build on a bridge. Taking the wall down first changes nothing: the bridge lands on the empty cell. Only a tower built on that cell by then stops it ("BRIDGE MISSED"; the tower is new), and then the bridge's coins are lost, like a spent charge.
  - Units treat it as any open cell; of two equally cheap routes they take the one over the bridge (the `FK` tie-break). Towers next to it cover it. The defender may wall off either end, as long as a route stays open.
  - Price `bridgeBase + bridgeFee × bridges on the map` = 50 + 20 × n (50, 70, 90, …); bridges planned this round count, in the order planned. At most `bridgeCap = 1` per wave. None in the first wave (nothing seen) or the final wave. There is no move penalty or rebuild fee for the defender: the bet is that bridges eat map space, so free rebuilding gets harder late in the match.
- **Tower charge** (25/55/90 coins): knocks a tower offline for 1/2/3 waves. The defender sees that it's offline, never for how long.
  - At most half the seen towers, rounded up, can be offline in a wave, including ones still offline from earlier charges.
  - No charges in the first wave (nothing seen yet) or the final wave.

## Balance: history, current state, open questions

**History, so you don't undo a fix by accident:**

- **v1:** pass-and-play prototype with walls, towers and explosive charges.
- **v2:** one currency and the breach-split pot. One customisable tower type. A permanent army with a unit designer. Stacked upgrades cost more than separate ones (multiplicative pricing).
- **v3:** the user found towers dominated.
  - Tower charges now knock towers offline. Players felt 40 coins was too much for one wave, so they're 25/55/90.
  - The wave timeline designer was added, and unit prices were lowered.
  - Tower build fees rise with each tower owned, so walls matter by mid-game.
- **v4:**
  - Units steer around tower range. Previously, equal-length routes hugged towers, and towers on open ground were as good as mazes.
  - Wall charge 30 → 40.
  - Cap on offline towers added.
- **v5:**
  - The user reported attackers could never win without knocking out every tower. Full-match simulations agreed: 0% attacker wins against a defender that retunes its towers. The cause was that tower damage potential dwarfed unit health, and a maze multiplies every tower.
  - Unit health ×2.5 at the same prices.
  - No charges in the final wave, at the user's request. Their reasoning: coins spent on charges in wave 7 aren't in the army for wave 8.
  - The rebuild-on-the-same-cell loophole closed.
  - 1×/5×/10× wave speed added.
- **v6:**
  - The user reported attackers always win with charges, and that one unit with maxed health, speed and armor couldn't be stopped. Simulations confirmed both.
  - Wall charge 40 → 60.
  - Big-unit surcharge added.
  - The design scan then found regeneration was the worst offender. A unit healing 6% per second fully recovered between towers, and about two-thirds of high-health regen designs beat every defense. Regen was reworked to the rules above.
- **v7:** two builds made in parallel from v6, both labelled v7, merged in v9:
  - **Single-player:** versus the computer (Easy and Normal, either side), using the sim bots. No rule changes.
  - **One-wall charges:** at the user's request a wall charge breaks one wall, not the wall and its neighbours (`wallBlast` 1 → 0). Price unchanged at 60.
    - Same-budget test on the bot maze (`wallCharge` at its best wall vs more units): one wall opens the same shortcut as the old blast, because units pass a 1-cell gap single file. A 60-coin wall charge still adds 60–150 keep damage against 4–6 towers, more than a 25-coin tower charge on the best tower. Swarms gain little from either.
    - Full matches: "counter + wall charges" went from 3/3 attacker wins to 0/3, but only because the bot charged the wall right beside a tower, and a 1-cell hole leaves the route no room to dodge it. A human picks better walls. (v9 fixed the bot; see below.)
    - What really changes: double-thick walls now need two charges, so thickening key walls (5 coins a cell) counters wall charges. So does turning the wall into a tower before the wave: the charge then misses.
  - Sliders show what the next step costs, in red when unaffordable.
  - Replay of the last wave, from the round summary, the end screen and both sides' Ready step.
- **v8:** the computer thinks: propose, test, pick (see "Single-player"). Hard added, charges at every level, the computer's notes after each wave. No rule changes.
- **v9:** merged the two v7 builds. The computer and the sim bots now plan for one-wall charges (see "Single-player" and `ai.js`), and the computer's defender can put a tower on the wall it expects you to charge. No new rule changes.
- **v10 (bridges, test branch `bridges`):** the user found wall charges made the game one-trick (attackers lose without them, win with them) and asked for a persistent, shared map feature instead. Bridges replace wall charges; tower charges stay (rules under "The game as it stands").
  - Decisions in the build: the bridge goes down at the start of the wave it was planned for; the wall under it is refunded automatically; removing the wall first doesn't stop it; a tower on the cell makes it miss and its coins are lost (consistent with "new defenses get one round"); the price counts bridges planned this round in order; no move penalty for the defender.
  - Price tuned with the sims from the spec's 50 + 15 × n to 50 + 20 × n: at 15, bridging every wave beat the blocking bot 89% of the time (see "Measured on v10").
  - `PROTO` 2 and protocol-named rooms keep it apart from v9 matches.
- **v11 (bridges branch):** at the user's request, bridges are drawn as direction-free square decks that join with their neighbours, and every match gets random terrain: 5% rough ground and 5% rock, spread evenly, validated, the same on both online devices (rules under "The game as it stands"). The computer's mazes shift a column to use rock and dodge rough ground. `PROTO` 3.

**Where it stands (measured on v6 with the tools below; since then only wall charges changed, see v7 and the single-player measurements):**

- Against the defender bot that retunes towers, roughly half the attacker strategies win. These include runner rush, mid-size armored units, regen bruisers, and wall or tower charges. Single-type swarms, ghosts, mixed armies and counter-picking lose. Against a defender bot that never retunes, the attacker wins everything.
- The full v6 design scan ran 256 design-and-wave combinations, each against four defenses of about 750 coins. In 34 of them (13%) even the best defense let more than 30% through, and in 10 (4%) more than half. All the strongest are high-health designs (900 HP marked as 9):

  | Design (slider indexes) | Unit cost | Best defense lets through |
  |---|---|---|
  | hp9 speed4 dodge3 regen3, one giant unit | 707 | 64% |
  | hp9 speed0 armor3 dodge3 regen3, one giant unit | 623 | 61% |
  | hp6 speed4 regen3, 8 units bunched | 86 | 56% |
  | hp9 speed4, 4 units bunched | 151 | 56% |
  | hp6 speed7, 8 units bunched | 94 | 55% |
  | hp9 speed0, 15 units spread | 48 | 52% |

  These are the main suspects if playtests say the attacker is too strong. Single giant units still hold up despite the surcharge, now through dodge and regen rather than armor and speed. The next levers are:
  - the top of the health slider (the 2.5× health boost helped the biggest units most)
  - a steeper surcharge
  - dodge or regen pricing on high-health units

  Re-run `scan.py` after changes; results go to `tools/.build/`, which isn't committed.
- The user's last stance: a small attacker nerf was warranted, delivered as v6. v7 added the one-wall charge on their request. They asked whether wall and tower charges should cost the same; the answer given was no (see v7 above), leaving the wall charge at 60 until playtests show whether players start thickening walls.

**Known open issues and ideas (not done):**

- **The pot rewards losing waves.** The attacker gets 70% when a wave fails, so sandbagging and saving up is paid for. It was flagged to the user and not changed. One option is to base the comeback share on the keep instead of the last wave.
- **The sim's defender bot is crude.** It only counters by rule: splash against cheap or dodging armies, slow heavy shots against armor. It has no answer to regen or high-health bunches. The game's own computer defender (`--defenders game:hard`) is stronger and makes a better baseline, though regen bruisers and high-health designs still beat it.
- **The sim attacker bot's wall charges were naive** (fixed in v9). It charged a wall beside the middle of each column, next to a tower, which with one-wall charges badly undersold them. v9 gave it the game's wall picks; v10's bots lay bridges with the game's `bridgePicks`.
- **Terrain (v11) is untested by humans.** Open questions: is 5% + 5% the right amount, do players read the map (the sims say a defender who doesn't adapt to it loses more), and should rough ground slow units or stay plain open ground.
- **Bridges (v10, test branch) are untested by humans.** Open questions for playtests: do defenders relocate or only wall bridges off (the sims say that choice decides whether bridging every wave pays), is 50 + 20 × n right, and does the kill-zone option ever matter (the computer tests it but never picked it in the sims).
- **Possible features, not built:**
  - Tower targeting modes and a decoy unit trait (postponed by the user).
  - Single-player phase C (campaign). Phases A (v7) and B (v8, the thinking computer) are done.
  - Waking the Render server as soon as the page opens rather than on Connect.
  - From the info screen's "Future directions": Elo per role, matchmaking, more traits each with a counter, real-time charge detonation, and cosmetic-only monetisation.

## Tools (in `tools/`)

The tools load the real `index.html` in headless Chromium through Playwright, so they always test the current rules. Nothing in the shipped game changes. They write a modified copy (with internals exposed and the AI players attached) into `tools/.build/`, which is gitignored.

**Setup (once per machine):**
```
pip install -r tools/requirements.txt && python -m playwright install chromium
npm install                      # repo root: ws, for server.js and the relay tests
(cd tools/tests && npm install)  # peer + peerjs, only for the online test suite
```

**Simulators (`tools/sim/`):**

- `match.py`: full 8-round games between the defender bot (`counter` or `basic`, or the game's own computer defender `game:easy|normal|hard`) and 18 attacker strategies (swarm, rush, maxed tanks, regen bruisers, bridges, tower charges and more; `--attackers computer` runs the game's own computer attacker instead). Prints attacker wins, keep left, breach, the round the keep fell, bridges laid and towers knocked out per match, and how the defender dealt with the bridges on the map, counted per round: `relocate` (moved its maze off them), `clear` (its maze already misses them), `block` (walled off an end), `kill` (tower beside one), `around` (left the hole and built around it). `--rules '{...}'` overrides any `RULES` key or slider table, `--opts '{...}'` merges into every attacker (e.g. `{"charges": "bridges", "chargeShare": 1}` makes every strategy bridge whenever it can), and `--log` prints round-by-round. For example:
  `python tools/sim/match.py --defenders counter --rules '{"bridgeBase": 70, "bridgeFee": 20}'`
  `python tools/sim/match.py --attackers computer --rules '{"bridgeCap": 0}'` (the computer attacker without bridges)
  - The four bridge strategies (`counter + bridges`, `counter + tower charges`, `counter + bridges & towers`, `alternate + bridges & towers`) take the slots of v9's wall-charge strategies with the same armies and budgets, so v9 and v10 runs line up. `always bridge` is `counter-picks` that lays a bridge whenever one shortens the route.
  - The `counter` bot walls off the ends of bridges and rough ground that cut its maze (the game's `blockBridges`) but never moves its maze; `basic` leaves them open. Both skip rock (it's already a wall) and never build on rough ground. The game's defenders also relocate and shift their mazes.
- `scan.py`: the exploit search. It sends every unit design on a grid, with all coins in that design, bunched and spread, against four defenses of equal cost, and records the breach against the best of them. Split it across CPUs with `--part 0/2` and `--part 1/2`, then run `--summary <file>`.
- `terrain.py`: the same matches with and without terrain on many maps (one map per seed), with per-map win rates and flagged maps drawn as text; `--maps 1000` prints only the generator's stats; `--out`/`--summary` split runs across processes. `match.py` games also get a map per seed now (none with `--rules '{"roughShare": 0, "rockShare": 0}'`).
- `wave.py`: one wave against a fixed maze, for quick questions like "do 4 heavy towers stop one maxed unit?"
- `ai.js`: the bots. Add strategies to `ARMIES`/`DESIGNS`, or pass `--opts '{"armySpec": [[{"hp":6,"speed":4}, 1, 0, 0.15]]}'`. The option `{game: 'normal'}` on either side plays the game's own computer instead (`brainPlan`, exposed only in the tools' copy). The old bots stay as fixed reference opponents.
- Knobs in `tools/common.py` (`dmgScale`, `spdScale`, `hpScale`, `armorFloor`) scale things without editing the game. Use them to explore, then make the real change in `RULES` or the slider tables.

**How to use the results:** always run the current rules and the variant with the same bots and seeds, and compare them. The absolute numbers say more about the bots than about human play. Check both sides: a nerf should hit the dominant strategy without moving the others.

**Test suites (`tools/tests/`; run after any change):**

- The fixed scenarios in the local, online and solo suites click known cells, so they set `roughShare` and `rockShare` to 0 through `window.siegeline.rules`; each suite then has its own terrain section.
- `test_local.py`: pass-and-play. Covers terrain (9 rough and 9 rock tiles, gates clear, 0–2 per zone, the route around rock, no wall or tower on rough ground or rock, rock can't be removed or bridged, the attacker sees rock in round 1, a replay keeps the map, a rematch gets a new one, portrait), building, pricing, tuning, bridges (price 50/70/90, one a wave, the wall refund, nothing built on one, a bridge on a removed wall still lands, one on a wall turned tower misses, the tie-break toward the bridge, planning one by touch on a phone), the charge cap, offline towers, the timeline, win and loss, and phone layout.
- `test_online.py`: online play. Covers the lobby, ready gating, hidden plans, identical waves on both devices (also at 10×, with a bridge and a tower charge), desync adoption, rematch with swap, drop and rejoin, both devices building the same map and playing the same wave on it (and a new shared map after a rematch), a `main` build with another `PROTO` never joining (skipped if `origin/main` speaks the same protocol), and peer-to-peer. It uses a stand-in for the claude.ai room (`mockroom.js`) and a local PeerJS server.
- `test_solo.py`: versus computer. Covers:
  - the mode card, and both sides at every level
  - that thinking leaves the live game untouched, and that the plan is identical whatever the player does while it thinks (same seed)
  - that its coins add up, and that it bridges or charges at every level against a strong maze: only what it saw, within the caps, never in round 1 or 8, at most once a wave on Easy
  - that its defense never stands on a bridge, and that its note says what it did about the player's bridge
  - on terrain: whole matches at Normal and Hard with rock in place and nothing on rough ground, and the same map and plan for the same seed
  - the notes every wave (never in pass-and-play), and the wait card with Keep planning
  - matches to the end screen, Rematch, Menu, and phone layout
- `test_relay.py`: `server.js` end to end. Covers server restart mid-match, a 65 s idle stretch, a page hosted elsewhere, and a sleeping server.
- Tests hardcode some current numbers (preset prices, charge prices, bridge prices 50/70/90). Update them when you change rules on purpose.

## Checklist when changing rules or UI

1. Change the number in `RULES` or the slider tables. Don't hardcode it elsewhere.
2. Update the text the player reads:
   - the info overlay: "How to play", "Core mechanics", the counter table and the rules table under "What this demo is"
   - slider hints in `TS`/`US`
   - the charge notes in the attacker panel
3. Bump the version label in the info tagline and the colophon (`prototype vN`).
4. Run the four test suites. For balance changes, run `match.py` before and after, plus `scan.py` if unit pricing or abilities changed.
5. Keep it one self-contained file with no `localStorage`. Check it at phone width.
