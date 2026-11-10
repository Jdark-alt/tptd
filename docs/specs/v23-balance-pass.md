# v23: Tower pricing, sabotage economy, interest

Built on v22.2 (`PROTO` 13). Seven changes, all balance. No new UI screens.

**Why:** a skilled defender can stop almost any army with three maxed, minimum-range towers in a maze that walks the route past each tower several times (playtest: wave 8, keep 889/1000, 0 of 30 through, attacker on Auto-army). Two causes:

1. Range is priced by its square and every multiplier multiplies the rest, so range 1.5 (×0.36) takes 64% off the whole tower. A 75 dps, 100% accuracy chain tower costs ~178 at range 1.5 and ~495 at range 2.5.
2. Damage is barely superlinear (`^1.15`), so stacking it on one tower is nearly as efficient as spreading it.

On the attacker side, the cheap front tower kills sappers before they land, and the attacker gets nothing back when the defender reshuffles the layout their plan was built against.

**Design rules to keep** (from the user): every change must be two-sided; simple rules, no special cases; don't change the game for new players whose default towers (range 2.5, damage 18) stay at 40 coins.

---

## 1. Range priced linearly

`TS.range.mult`: `(steps[i] / 2.5) ^ rangePow` with new `RULES.rangePow: 1` (was effectively 2).

- Range 1.5 → ×0.6 (was ×0.36). Range 5 → ×2 (was ×4). Default 2.5 → ×1 (unchanged).
- Low range stays cheaper and stays a real choice; it just stops discounting the rest of the tower so heavily.
- Update the Range slider hint ("Priced by its square…") to say range is priced in proportion to its reach.

## 2. Damage exponent 1.15 → 1.4

`TS.dps.mult`: `(steps[i] / 18) ^ dpsPow` with new `RULES.dpsPow: 1.4`.

- 75 dps → ×7.4 (was ×5.2). 18 dps → ×1 (unchanged).
- With 1 and 2, the playtest tower (75 dps, 100% accuracy, chain, range 1.5) costs about 425 instead of 178.

Fire rate stays free (Damage is already total damage per second; fire rate only splits it into shots). The build fee (+10 per tower owned) stays as it is.

## 3. Sappers get armour

`RULES.sapper`: add `armor: 1` (the armor slider's step 1: blocks 3 per hit). Use it where sappers are made (currently `armor: 0` hardcoded in the sapper design, ~line 2977); read it from `RULES.sapper` so the sims can vary it.

- Counters the cheap, low-damage front tower that screens sappers.
- Update the sapper notes/cards in the attacker panel and the rules table.
- Keep the v22 check: sappers should land roughly 44–65% of the time in the sims. If armour pushes them well above that, report it; don't retune silently.

## 4. Move fee goes to the attacker

Today the move/remove fee on a seen tower (`moveFeeOf`, `removeFee`, `relocFees`) is paid into nothing. Change: **the fees the defender has paid this round (net of fees refunded by moving a tower back onto its seen cell) are credited to the attacker.**

- Settle at `endRound`, alongside the pot gains, so the coins appear in the attacker's next planning phase. Nothing changes during planning, so Undo and moving back stay exact.
- Applies to the human defender (drags, removals, swaps) and the computer defender (`relocFees`, `SOLO.fees`).
- Keep the existing fee schedule for this build (10% of slider price, +5 points per relocation, capped at 40%). The sims test a flat 10% variant (see Testing).
- Online: both devices must credit the same amount. Derive it from state both sides already share (the seen grid and the grid at lock-in), and extend `test_online.py`'s seen-tower drag check to confirm the attacker's coins match on both devices.
- Show it in the wave summary as its own line for the attacker ("Defender moved towers: +N").

## 5. A killed sapper pays the defender

When a sapper is shot down (state `go` → `lost`, the "SAPPER DOWN" path), the defender gets `RULES.sapKillShare` (start at `0.5`) of that sabotage's cost.

- Settle at `endRound` (record the amount on `S.wave` during the wave; read each sapper's cost from `S.charges` before it's cleared).
- Only `lost` pays. A sapper that **missed** because its target moved, or reached the keep, pays no one (that's item 6).
- Show it in the wave summary as its own line for the defender ("Sappers shot down: +N").

## 6. A fizzled sabotage pays no one

When the target was moved or removed and the sapper misses, its cost stays spent, as today. This is a rule to **keep**, not a change: make sure item 5's payout doesn't apply to it, and say so in the sabotage notes ("If the tower has moved, the knock-out misses and its coins are spent").

Why: the defender already paid the attacker the move fee (item 4). Paying the defender back here would loop money both ways over one event.

## 7. Interest for both sides

At `endRound`, each side earns `floor(RULES.interestRate × min(leftover, RULES.interestCap))`, where leftover is the coins that side had free when the wave started (record at `prepWave`).

- `interestRate: 0.15`, `interestCap: 150` (roughly one side's share of a round's pot, which grows from 200 to 320 across the match). Both in `RULES`.
- Added before the next planning phase, like the pot. The summary shows it per side ("Interest: +N").
- Every round, both sides. It doesn't matter after the last wave since the match ends.
- The bots don't need to learn to bank in this build. Note in the findings how much interest each side ended up earning.

---

## Player-facing text

Per the checklist in CLAUDE.md:

- Info overlay: "How to play", "Core mechanics", the counter table, the rules table, and the tower cost callout (`40 × range × damage × …`, now with range linear and damage `^1.4`).
- Slider hints: Range, Damage.
- Sabotage notes and cards: sapper armour, the shot-down payout, the missed-on-moved rule.
- Move fee text: it now goes to the attacker.
- Version: v23 in the tagline and colophon. Bump `PROTO` to 14, since the rules change what both devices compute.

## Testing

Run the four test suites. Update tests that hardcode tower or preset prices (they will change with 1 and 2).

Then the sims, **one change at a time against the v22.2 baseline**, same bots and seeds, so each effect is visible on its own:

1. **The playtest build.** Add a `concentrated` defense to `scan.py`'s `DEFENSES`: three towers at range step 0, damage step 8, accuracy step 3, one with chain, one with splash, one with poison, in a maze that passes each several times. Run it with sabotage off against the strongest attacker strategies, at baseline and with 1 + 2. Report the leak share. The goal is that an optimised army leaks a meaningful share without sabotage.
2. **New-player defense.** The `basic` defender in `match.py`, baseline vs 1 + 2. Its result should barely move.
3. **Snipers.** With range linear, check long-range builds (range step 7) don't become the new best defense.
4. **Sapper armour** (3): land rate against `counter`, against the 44–65% band.
5. **Move fee to attacker** (4): attacker wins and economy with the computer defender at Hard (which moves towers). Also run the flat 10% variant (`moveFeeRise: 0`).
6. **Kill payout** (5): `sapKillShare` 0.5 vs 1.0. Watch whether the cheap front tower gets stronger.
7. **Interest** (7): `interestRate` 0.10 vs 0.15, `interestCap` 100 vs 150 vs 200.
8. **All together:** `match.py` with every pairing, compared with `compare.py` against baseline.

Write the results to `docs/research/` with what was run, what it showed, and what you'd change. Don't retune numbers past what this spec sets; the user decides from the data.

## Out of scope (later)

Tower target priority, formations, special tiles, zone effects, pricier wall sappers.
