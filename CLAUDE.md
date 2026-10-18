# Siegeline: notes for Claude Code

Siegeline (working title) is an asymmetric 1v1 tower defense played in the browser. One player defends the keep with walls and towers. The other attacks with an army they design and choreograph. The game started in a long claude.ai chat and moves here now. This file carries over what that chat learned: how the game works, why the rules are what they are, where balance stands, and how to test changes. **Current build: v8.**

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

## How index.html is organised

Search for these names; the file is long.

- **Rules:** `RULES` (all tunable numbers), `TS` (tower sliders), `US` (unit sliders), `RESIST`, `TPRESETS`/`UPRESETS`, `towerCost`, `unitCost`/`unitRaw`.
- **Pathing:** `flow` (Dijkstra cost field from the exit), `dangerField`, `nextStep`, `tracePath`, `recompute`, `routeOpenWithout` (connectivity check for "path must stay open").
- **Defender actions:** `canBuild`, `tryBuild`, `removeAt`, `setTowerCfg`, `seenAs`.
- **Attacker actions:** `setDesign`, `changeCount`, `plantWall`, `plantTower`, `canChargeTower`, `towerCap`, `offlineNext`, `chargeStatus`.
- **Wave simulation:** `startWave` (UI) and `prepWave` (setup), `buildSpawns`, `makeUnit`, `waveStep`, `moveUnit`, `updateTowers`, `strike`, `damage`, `leak`, `detonate`, `endRound`.
- **Flow and UI:** `setPhase`, `startRound`, `defenderReady`, `attackerReady`, `nextRound`, `renderDef`, `renderAtk`, `renderWave`, the overlays (`#ov-info`, `#ov-mode`, `#ov-wait`, `#ov-hand`, `#ov-sum`, `#ov-end`), and `frame` (main loop with the 1×/5×/10× wave speed).
- **Online:** `NET`, `netState`, `lockIn`, `unlock`, `netCheck`, `beginOnlineWave`, `netAfterWave`, `adoptResult`, `encodeGrid`/`decodeGrid`, `encodeArmy`/`decodeArmy`, `decodeCharges`. Transports: `roomLink` (claude.ai), `relayLink` (server.js), `peerLink` (PeerJS), chosen in `connect()` in that order.
- **Versus computer:** `SOLO`, `SOLO_LEVELS`, `soloKnows`, `thinkAttack`, `thinkDefend`, `trial` (hidden test waves, `QUIET`), `aiArmy`/`AI_ARMIES`, `buildDefense`/`AI_MAZES`/`AI_MIXES`, `wallPicks`, `towerPicks`, `retuneAgainst`, `threatsFor`, the notes (`attackNote`, `defendNote`), and the flow (`soloStartRound`, `pumpThink`, `soloReady`, `soloBeginWave`, `brainPlan` for the sims). See "Single-player" below.
- **Handle:** `window.siegeline` is a small handle for the console and tests: `state`, `net`, `solo`, `rules`, `cellToClient`, `advance(sec)`. The tools inject extra internals into their own copy only.

### Determinism (do not break)

Online play sends only plans. Both devices then run the same wave and must get bit-identical results. Inside the wave simulation:

- Use `srand()`, never `Math.random`. It's seeded per match, epoch and round. `Math.random` is fine for visual effects only.
- Use `hyp()` (sqrt), never `Math.hypot`. No trig either; `atan2`/`cos`/`sin` are only for drawing angles.
- Step in fixed 1/60 s increments (`STEP`). The speed buttons run more steps per frame; they never change the step size.
- Keep path costs integers. Rebuild state on both sides from the encoded plans (`beginOnlineWave` decodes both players' plans, its own included).
- After any change to wave logic, run `tools/tests/test_online.py`. It checks that both devices end identical, including with one device at 10× speed.
- The computer opponent runs waves out of sight (`trial`) with `QUIET` set. Anything new in the wave code that touches the DOM, redraws the terrain or ends the round must be skipped while `QUIET` is true, the way `leak`, `detonate` and `endRound` do it. Effects pushed to `fx`/`floaters` are trimmed by `trial` itself.

### Online protocol (presence-style, absolute state)

Each side publishes `{v, id, role, code, ep, st, rd, lk, go, at, plan, res}`. The same object travels over the claude.ai room, the relay or PeerJS. The flow:

1. A player who presses Ready sets `lk` to the round number.
2. Once both sides are locked, each sets `go` and reveals `plan`. Plans stay private until both commit.
3. The wave starts when both have `go === round`.
4. The defender publishes `res`, and the attacker adopts it if their copy disagrees, so the defender's device is the referee.
5. `ep` is the match epoch. A rematch or a rejoin after a reload bumps it, and the other side follows. A device that reloads mid-match can't resume; the lobby offers to restart.

### Single-player (versus computer)

The mode screen has a third card, **Versus computer**. The player picks a side and a level (Easy, Normal or Hard), and the computer takes the other seat. There are no pass-the-device screens.

**Fair play:** the computer knows only what a human in its seat would.
- As attacker: `seenGrid`.
- As defender: its own grid, `seenArmy`, and the attacker's coins (the HUD shows those to both players).
- `soloKnows` copies that at the start of the round, before the player does anything, and the computer never reads the live state again that round.

**Propose, test, pick:** principles generate candidate plans, each is played out in a hidden copy of the real wave (`trial`), and the best one is played.
- `trial` swaps in a scratch state and runs the real `waveStep` with `QUIET` set, then restores `S`, `srand`, `uid`, the effects and the route field.
- One trial costs about 6–15 ms on a desktop, and 16–22 ms with the CPU throttled 4×. A round's thinking is 50–70 trials at Normal and Hard, about 0.3–0.8 s of wall time.
- **Attacker** (`thinkAttack`):
  - Army ideas (`AI_ARMIES`: swarm, rush, ghost, plated, bruiser, hulk, brutes screening a swarm, runners with ghosts), each bunched and spread, against the seen defense.
  - The best few against that defense retuned to counter them (`retuneAgainst`), then with charge options:
    - wall picks that shorten the seen route most (`wallPicks`)
    - towers that cover the route (`towerPicks`)
    - within the cap; none in round 1 or 8
  - A charge must pay for itself: it is scored at cost × breach × later rounds that matter, capped by how long the keep would last at this pace. So it charges against strong defenses and late in the match, and not when the army already walks through.
  - Round 1 is a random opening from `AI_OPENERS`.
- **Defender** (`thinkDefend`): every maze (`AI_MAZES`: 3, 4 or 5 serpentine columns, towers in the cells covering the most route), tower mix (`AI_MIXES`) and spending style (`AI_SPEND`), against the last army scaled to the attacker's coins now. Then the best few against a panel of armies that could beat them (`threatsFor`).
  - It keeps its maze unless another is clearly better (15% margin), and repairs blown walls.
  - Upgrades always go to the weakest tower, so no single tower carries the defense.
- **Levels** (`SOLO_LEVELS`):
  - Easy: 3 random ideas from the lighter armies, or 3 tower mixes on its current maze, no foresight; picks at random among its top 3; at most one charge a wave.
  - Normal: everything, averaged with the likely counters; takes the second best 10% of the time.
  - Hard: everything, weighing the worst counter too; the defender also tests the last army with a wall charge; never blunders. No coin bonus at any level.
- **Variety:** a per-match seeded stream (`SOLO.rng`; tests set `SOLO.seed`).
- **Notes:** after each wave the summary shows "The computer's thinking", which says what it saw, how many plans it tried and what it chose. A note says "What held best" or "got the most through" only when it really played its best plan.

**Timing:** `soloStartRound` starts the thinking. `pumpThink` runs it in slices of about 12 ms between frames, with a 3 s cap (`THINK_MS`) on looking for better plans.
- If the player presses Ready first, `soloReady` shows the `#ov-wait` card ("Keep planning" unlocks).
- The plan uses the online plan format (`{dFree, ts, g}` or `{aFree, a, c}`). `soloBeginWave` applies it with the online decoders.
- So nothing the computer does shows while the player plans, and its plan can't depend on the player's.
- `online()` stays false in solo, so online determinism is untouched. A snapshot restores the player's own phase, and the computer thinks again.

**Measured (match.py, 2–3 seeds; bots, not humans):**
- **As defender**, attacker wins out of 34 across the 17 sim strategies:
  - `basic` bot 34, Easy 31, `counter` bot 19, Normal 12, Hard 10.
  - Runner rush, maxed tanks, mini-tanks, regen bruisers and slow fat regen still beat every defender, the computer at Hard included.
- **As attacker**, it wins every match against both bots:
  - Against the `counter` bot: Easy takes the keep in round 7 (about 4 charges a match), Normal and Hard in round 4 (2–3 charges).
  - Against the computer's own Normal and Hard defenders: Normal and Hard attackers win every match by round 4–5; Easy wins half.
  - Read with the balance notes below: played well, the attacker side still looks favoured.

**Roadmap the user chose (hybrid: principles for how it plays, templates for who it is):**
- **Phase B, the smart brain:** done in v8 (above).
- **Phase C, the campaign:** two tracks of about 6 missions (Hold the Keep, Break the Siege).
  - Each mission is data: a commander personality (army ideas, mazes and mixes it favours, foresight, blunders), an opening, rule tweaks (`RULES` overrides restored afterwards), limits such as no charges, and a lesson. Missions never script tower positions per wave.
  - All missions open, nothing saved (no localStorage).
- **Never:** the computer never peeks at the player's current plan, at any difficulty.

## The game as it stands (v8)

- **Modes:** pass-and-play on one device, online on two, or versus the computer on either side. The rules are identical in all three; v7 and v8 changed no numbers from v6.

- **Board and route:** 16×11 grid, entry at the left middle, keep at the right middle. Building may never close the route. Units follow the cheapest route: each cell costs 10, plus `RULES.danger = 5` for every working tower that can hit it. So units steer around tower range when the detour is short, and walls are what force them through fire.
- **Rounds:** 8. Each round the defender builds while the attacker plans, in secret. The wave then plays out with everything revealed.
- **Hidden information:**
  - The attacker sees the defense as it stood after the last wave (`seenGrid`).
  - The defender sees the last army sent (`seenArmy`).
  - Charges only work on things the attacker saw. Rebuilding on the same cell doesn't make something "new" (`seenAs`), which closed a loophole.
- **Economy:** both start with 300 coins. The keep has 1000 points; the attacker wins at 0, the defender by surviving 8 rounds. Each round adds a 200-coin pot.
  - Army strength X is the cost of the units sent. Through-strength Y is cost × health fraction left, for each unit that reaches the keep. Breach = Y/X, and the keep loses Y.
  - Defender's pot share = 30% + 40% × (breach ÷ 50%), clamped to 30–70%. If no army is sent, the split is 50/50.
  - Everything is fully refundable: towers at cost plus fee, walls 5, units at cost. Exceptions: blown walls are lost, spent charges are lost, and offline towers are locked.
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
- **Charges:**
  - Wall charge (`wallCharge = 60`): destroys the wall and its four neighbours that the attacker saw. The defender loses those coins.
  - Tower charge (25/55/90 coins): knocks a tower offline for 1/2/3 waves. The defender sees that it's offline, never for how long.
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
- **v7:** single-player versus the computer (Easy and Normal, either side), using the sim bots. No rule changes.
- **v8:** the computer thinks: propose, test, pick (see "Single-player"). Hard added, charges at every level, the computer's notes after each wave. No rule changes.

**Where it stands (v6, measured with the tools below):**

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
- The user's last stance: a small attacker nerf was warranted, delivered as v6. Get their playtest feedback on v6 before the next round of changes.

**Known open issues and ideas (not done):**

- **The pot rewards losing waves.** The attacker gets 70% when a wave fails, so sandbagging and saving up is paid for. It was flagged to the user and not changed. One option is to base the comeback share on the keep instead of the last wave.
- **The sim's defender bot is crude.** It only counters by rule: splash against cheap or dodging armies, slow heavy shots against armor. It has no answer to regen or high-health bunches. The game's own computer defender (`--defenders game:hard`) is stronger and makes a better baseline, though regen bruisers and high-health designs still beat it.
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

- `match.py`: full 8-round games between the defender bot (`counter` or `basic`, or the game's own computer defender `game:easy|normal|hard`) and 17 attacker strategies (swarm, rush, maxed tanks, regen bruisers, charges and more; `--attackers computer` runs the game's own computer attacker instead). Each line also shows charges used per match. Prints attacker wins, keep left, breach and the round the keep fell. `--rules '{...}'` overrides any `RULES` key or slider table, and `--log` prints round-by-round. For example:
  `python tools/sim/match.py --defenders counter --rules '{"wallCharge": 80}'`
- `scan.py`: the exploit search. It sends every unit design on a grid, with all coins in that design, bunched and spread, against four defenses of equal cost, and records the breach against the best of them. Split it across CPUs with `--part 0/2` and `--part 1/2`, then run `--summary <file>`.
- `wave.py`: one wave against a fixed maze, for quick questions like "do 4 heavy towers stop one maxed unit?"
- `ai.js`: the bots. Add strategies to `ARMIES`/`DESIGNS`, or pass `--opts '{"armySpec": [[{"hp":6,"speed":4}, 1, 0, 0.15]]}'`. The option `{game: 'normal'}` on either side plays the game's own computer instead (`brainPlan`, exposed only in the tools' copy). The old bots stay as fixed reference opponents.
- Knobs in `tools/common.py` (`dmgScale`, `spdScale`, `hpScale`, `armorFloor`) scale things without editing the game. Use them to explore, then make the real change in `RULES` or the slider tables.

**How to use the results:** always run the current rules and the variant with the same bots and seeds, and compare them. The absolute numbers say more about the bots than about human play. Check both sides: a nerf should hit the dominant strategy without moving the others.

**Test suites (`tools/tests/`; run after any change):**

- `test_local.py`: pass-and-play. Covers building, pricing, tuning, the charge cap, offline towers, the timeline, win and loss, and phone layout.
- `test_online.py`: online play. Covers the lobby, ready gating, hidden plans, identical waves on both devices (also at 10×), desync adoption, rematch with swap, drop and rejoin, and peer-to-peer. It uses a stand-in for the claude.ai room (`mockroom.js`) and a local PeerJS server.
- `test_solo.py`: versus computer. Covers:
  - the mode card, and both sides at every level
  - that thinking leaves the live game untouched, and that the plan is identical whatever the player does while it thinks (same seed)
  - that its coins add up, and that it charges at every level against a strong maze: only what it saw, within the cap, never in round 1 or 8, at most once a wave on Easy
  - the notes every wave (never in pass-and-play), and the wait card with Keep planning
  - matches to the end screen, Rematch, Menu, and phone layout
- `test_relay.py`: `server.js` end to end. Covers server restart mid-match, a 65 s idle stretch, a page hosted elsewhere, and a sleeping server.
- Tests hardcode some current numbers (preset prices, charge prices). Update them when you change rules on purpose.

## Checklist when changing rules or UI

1. Change the number in `RULES` or the slider tables. Don't hardcode it elsewhere.
2. Update the text the player reads:
   - the info overlay: "How to play", "Core mechanics", the counter table and the rules table under "What this demo is"
   - slider hints in `TS`/`US`
   - the charge notes in the attacker panel
3. Bump the version label in the info tagline and the colophon (`prototype vN`).
4. Run the four test suites. For balance changes, run `match.py` before and after, plus `scan.py` if unit pricing or abilities changed.
5. Keep it one self-contained file with no `localStorage`. Check it at phone width.
