# v34: Economy (Advanced mode)

Built on v33 (`PROTO` 22). Adds the economy: crystal sites, Mines, Prospectors, interest moved into it, and the Bet. The design doc is the user's "Siegeline: Economy mode"; where they differ, this spec wins.

**Why:** both sides should have ways to earn and ways to take from the other side's earnings, all decided by planning rather than luck. Target: a side that plays the economy well ends a match with roughly **20–30% more coins** than one that ignores it. Enough to plan around, not enough to win on its own.

**Design rules to keep** (from the user):

- Simple rules, no special cases. Every number goes in `RULES`.
- Two-sided: each side has a way to earn and a way to take from the other.
- True to role: the defender earns by building, the attacker by sending units.
- Optional: a player can ignore every part.
- Nothing happens mid-wave from player input. Earnings, loot, bounties and bets are tallied during the wave and paid at `endRound`, before the next planning phase.
- Balance from sims. Starting values here are for the sims to test; report, don't retune past the listed variants silently.

This changes the map, prices, the wave and the plan format, so **bump `PROTO` to 23**. Version **v34** in the tagline and colophon.

Suggested order: 1 (modes), 2 (interest), 3 (sites), 4 (Mines), 5 (Prospectors), 6 (Bet), 7 (computer and bots), 8 (tooltips), then the sims.

---

## 1. Modes: Simple and Advanced

The match setting that today picks Sabotage on or off becomes **Mode: Simple / Advanced** (start screen, lobby, rules sheet).

| | Simple | Advanced |
|---|---|---|
| Sabotage | Off | On |
| Economy (sections 2–6) | Off | On |
| Unit health bonus (`noSabHp` 1.15) | Yes | No |
| Move fee | Free | As today |
| Everything from v33 | Yes | Yes |

- **Simple is today's no-sabotage game minus interest** (interest moves into the economy).
- **Internally keep two flags,** `S.sabo` and a new `S.eco`, both set from the mode. The UI only offers the two modes, but the sims must be able to run Sabotage-only and Economy-only to measure each on its own.
- Online: the host's mode applies to both devices, as the sabotage setting does today.

---

## 2. Interest (Advanced only)

Today each side earns 15% of the coins it left unspent when the wave started, at most 150 a wave (`interestRate` 0.15, `interestMax` 150, reached with 1,000 banked).

**The user's direction:** sending no units for 1–2 waves to bank interest is a good attacker strategy and must stay viable. It shouldn't be a guaranteed win. Slow it down a little; don't kill it.

- **Start:** `interestMax` 150 → **100** (reached with about 670 banked). Rate unchanged.
- **Sim variants:** `interestMax` 100, 120, 150; and `interestRate` 0.12 with `interestMax` 150.
- **Read on banking:** in Advanced, each side sees the other's free coins at the start of the round (the coins banked) in the HUD, so a defender can see a big wave coming. If the HUD already shows this, keep it; otherwise add it beside the worths.
- Simple mode: no interest. Remove the interest lines from its summary and rules sheet.

---

## 3. Crystal sites (Advanced only)

- **`RULES.crystalSites` (start 5)** per map, placed from the map seed after terrain, so both online devices build the same sites without sending anything.
- On open, buildable ground (not rock or rough), at least 2 cells from either gate and at least 3 cells (Chebyshev) from each other. If the seed can't place them all, place as many as fit; log it in the sims.
- **Units walk over sites** like open ground. **Only walls can go on a site**: a wall there becomes a Mine (section 4). A tower can't be built on a site ("Crystal site: build a wall here to make a Mine").
- **Auto-maze never builds on crystal sites,** in the starter maze, the button and the computer's maze building. It treats them as cells it can't wall (the route may still pass over them). v33's weak-wall thickening skips them too.
- Sites are public: both sides see them from round 1. Draw them as a distinct crystal tile, readable at 390 px, distinct from rock, rough, open ground and walls.

---

## 4. Mines (defender)

A Mine is a wall on a crystal site. It earns from the route next to it, and that same exposure is where Prospectors rob it.

- **Building:** the Wall tool (or a drawn wall, or a Shape) on a site makes a Mine. Cost: `RULES.wall` + `RULES.mineCost` (start **40**). Walls drawn across a site in a drag include it at the Mine price; the drag's cost line shows it.
- **Exposure:** how many of the Mine's 4 sides (up, down, left, right) are route cells, counted on the route at wave start (`prepWave`). Diagonals don't count.
- **Income:** `RULES.mineIncome` (start **5**) × exposure, so 0–20 a wave. A Mine off the route, or on a second layer of walls, earns nothing.
- **Goes live next wave:** a Mine built this round earns nothing in this round's wave, so the attacker always sees it before it pays. Mark it `fresh`-style and clear it after the wave.
- **During the wave** each live Mine holds its income as a store (`m.store`). Passing units scrape it and Prospectors loot it (section 5). At `endRound` the defender gets what's left, and the summary shows "Mines +N" (and the ledger "Looted −N").
- **Removing a Mine:** in the round it was built, a full refund (wall + 40), like Undo. After that, the wall refund only (`RULES.wall`); the 40 is spent. The site is free to build on again.
- **Sabotage:** a Mine is a wall, so wall sappers can bridge it like any wall. A bridged Mine is gone (the usual wall refund), and the store it holds that wave is still paid to the defender at `endRound`.
- **Where it shows:**
  - With the Wall tool, hovering a site shows "Mine · earns N a wave here" for the current route.
  - Hovering a Mine shows its exposure, income and what was looted last wave.
  - The attacker sees Mines as seen after the last wave, with the same hover info.
  - In a wave, a small gold number floats up when a Prospector loots it.
- **Online:** Mines travel with the grid like walls (a new cell type, or a wall flag, in `encodeGrid`/`decodeGrid`). Income and loot are computed on both devices from the same state.

---

## 5. Prospectors (attacker)

Prospector is a toggle on a unit design, like a resist. Its units earn for every second they're alive and loot Mines they pass. In return they deal half keep damage and pay the defender a bounty when they die.

- **Where:** a Prospector toggle in the design editor, beside the resists, Advanced only. Sappers can't be Prospectors.
- **Price:** × `RULES.prospMult` (start **1.3**), applied like a resist multiplier. Every amount below uses the unit's full price with this included (`unitCost`).
- **Keep damage:** × `RULES.prospKeep` (start **0.5**). The army strength the breach is measured against counts Prospectors at the same 0.5, so breach still means "share of the threat that got through".
- **Trickle:** `RULES.prospTrickle` (start **0.02**) × price for each second the unit is on the board (from release until it dies or reaches the keep), capped at `RULES.prospTrickleCap` (start **0.30**) × price a wave. Paid even if it dies.
- **Loot:** the first time in a wave that a Prospector stands on a route cell beside a Mine (one of the Mine's 4 sides), it takes `RULES.prospLoot` (start **0.20**) × its price from that Mine's store, up to what's left. Once per Prospector per Mine per wave. The loot is the attacker's at once; it doesn't need to reach the keep.
- **Scrape (every other unit):** any unit that isn't a Prospector takes `RULES.mineScrape` (start **0.01**) × its price the first time it passes a Mine's side, under the same rules as loot (once per unit per Mine per wave, up to what's left, the attacker's at once). Sappers count as units here.
  - **Why (the user's call):** towers earn Prospector bounties without the defender doing anything, so any attacker army reaching a Mine chips at it without the attacker doing anything. Both sides now have a passive counter to the other's economy; Prospectors stay the deliberate choice that pays far more.
  - Example: a 600-coin army of ordinary units passing a 15-coin Mine scrapes about 6 of it. A Mine never loses more than it made that wave.
- **Bounty:** a Prospector killed by a tower pays the defender `RULES.prospBounty` (start **0.10**) × its price. One that reaches the keep pays nothing.
- **Units come back each wave,** as all units do, so the price is paid once while trickle and bounty repeat every wave.
- **Rounding:** tally exact amounts on `S.wave`; round each side's totals once at `endRound`.
- **Determinism:** trickle, loot and bounty come from simulation time and positions only, no random rolls, so both devices and replays agree.
- **Where it shows:**
  - The design card shows the toggle, the price change and a line: "Earns 2% of its price a second alive (max 30%), loots Mines it passes, half keep damage."
  - A Prospector marker on the unit, readable on every shape and size (follow v31's indicator rules: shape is speed, size is health).
  - The wave forecast reports the Prospectors' expected trickle and loot.
  - The summary shows "Prospectors +N" for the attacker and "Prospector bounties +N" for the defender.
- **Online:** the toggle travels in `encodeArmy`.

**Break-even** is about 5 seconds alive (2% a second × 5 = the 10% bounty). Include this in the sims' report.

---

## 6. Bet (Advanced, behind its own switch)

Before each wave, each side can secretly bet coins on how much of the army will get through. Behind `RULES.bet` (default on in Advanced) so playtests can switch it off. In the code, name it Bet throughout (`bet`, `betLow`, `betHigh`, `betCap`).

### 6.1 The rule

- **The pick:** Low (breach under `RULES.betLow`, start **0.10**), Medium (in between), or High (`RULES.betHigh`, start **0.40**, or more). An empty army is breach 0, so Low.
- **Stake:** 0 up to 10% (`RULES.betCap`) of the value the side has committed when it presses Ready, and never more than its free coins:
  - **Attacker:** the army and sabotage being sent (army value with the Prospector multiplier, plus charges).
  - **Defender:** towers, walls and Mines on the board, including crowding (`defWorth − dFree`).
  - Deleting and rebuilding doesn't matter; only what stands at Ready counts.
- **Payout:** a right bet gets the stake back plus the same again. A wrong bet loses the stake; it goes to no one. The stake leaves the free coins at lock-in, so it doesn't earn interest.
- **Hidden:** the bet locks with the plan and is revealed in the summary. Online, it travels with the plan, and neither device shows the other's before the wave ends.

### 6.2 The interface: clear at a glance

The Bet panel sits on the Ready/lock card, collapsed to one line by default so it never gets in the way: **"Bet on this wave · optional"**. Tapping it opens the panel. It must fit at 390 px without scrolling the card.

The panel, top to bottom:

1. **One line of explanation:** "Guess how much of the army gets through. Right: win your stake. Wrong: lose it."
2. **Three option buttons,** each with its meaning written on it, not just the label:
   - **Low** · "Under 10% gets through"
   - **Medium** · "10–40% gets through"
   - **High** · "Over 40% gets through"
   The percentages come from `RULES`, never hardcoded in the text.
3. **Stake stepper:** − / amount / +, plus Max. Under it: "Up to N (10% of what you're sending)" for the attacker, "Up to N (10% of your defense)" for the defender. 0 by default; no stake means no bet.
4. **The outcome line,** live as the player changes the pick or stake: "Right: +30 · Wrong: −30".
5. **A hint from the forecast** where one exists, kept neutral: the attacker sees "Your forecast: 22% through"; the defender, after a test run, "Your test: 15% through". No hint when there's no forecast or test.

After lock-in, the Ready card's wait state shows "Your bet: High · 30", and the summary shows the result: "Bet High · right · +30" or "Bet Low · wrong · −20", with the actual breach beside it.

The first time a player opens the panel in a match, it shows a single dismissible line: "Bets are hidden from your opponent until the wave ends."

---

## 7. Computer opponent and sim bots

Without this, solo gets easier and the sims say nothing.

- **Computer defender (all levels):** builds Mines on sites where exposure is 2 or more and it can afford them, and weighs guarding them. It pays crowding, as since v33.
- **Computer attacker:** turns Prospector on for some designs when the defender has Mines, or when it is behind on coins; times them behind tougher groups where it can. It may bank for a wave when its forecast says its army can't break through.
- **Bet:** the computer bets from its own forecast and stakes modestly. It never sees the player's plan or bet (the rule since v8).
- **Sim bots:** add attacker strategies `prospect` (Prospectors on the main designs), `bank` (no units for 2 waves, then everything) and `bank+prospect`; add a defender option `miner` (Mines on every exposed site). Existing strategies run unchanged, with Economy off and on.
- Report thinking time at 4× CPU throttling.

---

## 8. Tooltips: short, plain, numbers from `RULES`

Every new thing gets a tooltip (hover on desktop, hold on touch), following the existing tooltip style. Rules for all of them:

- **Two lines at most:** what it is, then what it does for you or against you. Numbers inline.
- **Live numbers** where the board decides them (exposure, income, loot), filled from the current state. Every rule number comes from `RULES`, never hardcoded.
- **Same wording on both sides** where both see the thing, so players learn one vocabulary. The attacker's version says what's in it for the attacker.

The texts (placeholders in braces):

| Where | Who | Tooltip |
|---|---|---|
| Crystal site (empty) | Both | **Crystal site.** A wall built here becomes a Mine that earns coins each wave. |
| Crystal site, Wall tool hovering | Defender | **Mine here: {cost} coins.** Earns {income} a wave on this route ({sides} sides touch the route). |
| Mine | Defender | **Mine · {income} a wave.** Earns 5 per side touching the route. Units passing those sides scrape it; Prospectors steal more. Last wave: earned {kept}, looted {looted}. |
| Mine, built this round | Defender | **New Mine.** Starts earning next wave. Remove it this round for a full refund. |
| Mine | Attacker | **Mine · holds {income} a wave.** Units walking past it scrape 1% of their price; Prospectors steal 20%. |
| Prospector toggle (design editor) | Attacker | **Prospector.** ×1.3 price, half keep damage. Earns 2% of its price each second alive (up to 30% a wave) and steals from Mines it passes. If shot down, the defender gets 10% of its price. |
| Prospector unit, in a wave or the forecast | Both | **Prospector · earned {trickle}, looted {loot}** this wave. |
| Prospector unit | Defender (planning, seen army) | **Prospector.** Earns the attacker coins while alive and steals from your Mines. Kill it: +{bounty}. |
| Interest line in the HUD or summary | Both | **Interest.** 15% of the coins you didn't spend, up to 100 a wave. |
| Opponent's banked coins (HUD) | Both | **Banked: {n}.** Coins your opponent didn't spend last round. A big bank can mean a big wave coming. |
| Bet panel, collapsed | Both | **Bet.** Optional. Guess how much of the army gets through and stake coins on it. |

Check every tooltip fits on one card at 390 px and doesn't cover the cell it describes.

---

## Sims and report

Against the v33 baseline, same bots and seeds. Run Simple, Sabotage-only, Economy-only and Advanced (both). Write results to `docs/research/v34-sim-results.md`.

1. **Economy's worth:** coins over a match for a side using Mines or Prospectors vs one ignoring them. Target +20–30%.
2. **Win rates:** Advanced vs Sabotage-only, attacker win rate overall and per strategy, against `counter` and `game:hard`.
3. **Banking:** the `bank` strategy's win rate against Hard for each interest variant. Target: viable but not a sure win, roughly 35–55%.
4. **Prospectors:** average trickle + loot vs bounty per Prospector. Target 2–3× the bounty at default timing. Also the flat-cap variant `RULES.prospLootMax` 15 (loot per Prospector capped), to see whether big single units loot too much.
5. **Mines:** average payback in waves (target about 3), and share of Mine income looted and scraped. Scrape variants: `mineScrape` 0.005, 0.01, 0.02.
6. **Snowball:** does a coin lead after wave 3 predict the winner more strongly with Economy on than off?
7. **Bet:** average net coins a match per side, and how often each pick (Low, Medium, High) is made.
8. **Sites:** maps where fewer than 5 sites fit; starter maze route length with sites reserved vs v33.

**Gate:** if Advanced moves the overall attacker win rate by more than 10 points vs Sabotage-only, or any strategy by more than 20, flag it in the CLAUDE.md entry and don't retune other numbers in this build. The user decides from the data.

---

## Tests

1. **Modes:** Simple has no sabotage, no economy, no interest, +15% unit health; Advanced has all of sections 2–6. The lobby shows two modes.
2. **Sites:** 5 sites, identical on both devices for one seed; none on rock, rough or near gates; towers refused on them; Auto-maze never walls them.
3. **Mine exposure and income:** fixed scenarios with 0, 1, 2, 3 and 4 route sides give 0, 5, 10, 15, 20.
4. **Live next wave:** a Mine built this round earns nothing this wave and earns the next.
5. **Removal:** full refund the round it's built; wall refund only after.
6. **Loot:** the doc's worked example (a 15-coin Mine, 50-coin Prospectors: first takes 10, second 5, third 0); a Prospector loots each Mine once per wave; an ordinary unit scrapes 1% of its price once per Mine per wave; scrape and loot together never take more than the Mine holds.
7. **Trickle and bounty:** a Prospector killed at 3 s gives the attacker 3% and the defender 10% of its price; one alive 20 s gives the 30% cap.
8. **Breach:** a Prospector reaching the keep deals half damage and counts half in army strength.
9. **Bridged Mine:** removed with the wall refund; its store still paid.
10. **Interest:** pays 15% up to 100 in Advanced, nothing in Simple.
11. **Bet:** stake cap from committed value (selling the army before Ready lowers it); right bet +stake, wrong −stake; hidden from the other device until the summary.
12. **Online:** both devices agree on coins after a wave with Mines, Prospectors, a looted Mine, a bridged Mine and two bets; replays reproduce it.
13. **Computer:** at Normal, the computer builds at least one Mine or Prospector design in most matches where it can.
14. **Bet panel and tooltips:** the panel opens from its one-line summary, shows the three options with their percentages and the live outcome line, and fits at 390 px; every tooltip in section 8 appears with live numbers that match the board.
15. The four test suites pass, with fixed scenarios switching sites off where they click known cells (`RULES.crystalSites: 0`).

## Docs

- CLAUDE.md: "What v34 changed", the rules as they stand, the sim results, test notes.
- Info overlay: modes, an Economy section (sites, Mines, Prospectors, interest, Bet) with the worked examples, and the rules table.
- Save this spec as `docs/specs/v34-economy.md`.

## Out of scope (later)

Power-ups mode (Relay, Banner), target priority, formations, special tiles, Looters and Outposts (parked), attacker buildings and defender units as full categories.
