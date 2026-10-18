// Computer players for balance testing. Loaded after the game in tools/.build/sim.html, which exposes the game's
// internals as window.siegeline._i (see tools/common.py). Defines window.runMatch(defenderOpts, attackerOpts, seed, rules).
//
// Both players are simple rule-based bots, not strong players. Compare rule variants against each other with the
// same bots; don't read the absolute win rates as how humans will do.
(() => {
  const I = window.siegeline._i, COLS = 16, ROWS = 11, N = COLS * ROWS;
  const at = (c, r) => r * COLS + c;
  // Lets a run patch slider tables (e.g. { armor: { steps: [0, 2, 4, 7] } }) and restores them before the next run.
  const US0 = JSON.parse(JSON.stringify(Object.fromEntries(Object.entries(I.US).map(([k, v]) => [k, { steps: v.steps, m: v.m }]))));
  const resetUS = () => { for (const [k, v] of Object.entries(US0)) { I.US[k].steps.splice(0, Infinity, ...v.steps); if (v.m) I.US[k].m.splice(0, Infinity, ...v.m); } };

  /* ---------------- defender ----------------
     Sells everything each round (removal refunds in full, walls 5) and rebuilds from its whole worth: a
     serpentine maze of 4 wall columns with towers set into the columns so each covers two lanes, then more
     towers and damage upgrades. Locked (offline) towers stay put.
     style 'counter': retunes towers against the last army it saw (splash on half the towers vs cheap or
                      dodging units, slow heavy shots vs armor). This is the "competent defender" baseline.
     style 'basic':   never retunes (default towers + damage upgrades). A weak defender. */
  const WCOLS = [3, 6, 9, 12];
  const SLOTS = [[3, 5], [6, 5], [9, 5], [12, 5], [3, 8], [6, 2], [9, 8], [12, 2], [3, 2], [6, 8], [9, 2], [12, 8]];
  const colCells = k => { const c = WCOLS[k], gap = k % 2 ? 10 : 0, out = []; for (let r = 0; r < ROWS; r++) if (r !== gap) out.push(at(c, r)); return out; };
  function towerCfgFor(army, k, style) {
    const cfg = I.defaultTower();
    if (style !== 'counter' || !army) return cfg;
    let val = 0, cheap = 0, armor = 0, dodge = 0;
    for (const d of army) { const v = d.count * I.unitCost(d); val += v; if (d.hp <= 2) cheap += v; if (d.armor) armor += v; if (d.dodge) dodge += v; }
    if (!val) return cfg;
    if ((cheap + dodge) / val > 0.45 && k % 2 === 0) { cfg.splash = 2; cfg.rate = 4; }
    else if (armor / val > 0.3) cfg.rate = 5;
    return cfg;
  }
  function upgradeStep(S, getW, spend, towers, force) {
    // raise the weakest tower's damage one step if that buys more damage per coin than another tower
    let best = null;
    for (let i = 0; i < N; i++) {
      const g = S.grid[i]; if (!g || g.t !== 'tower' || g.off > 0 || g.cfg.dps >= I.TS.dps.steps.length - 1) continue;
      if (!best || g.cfg.dps < best.cfg.dps) best = g;
    }
    if (!best) return false;
    const next = { ...best.cfg, dps: best.cfg.dps + 1 };
    const delta = I.towerCost(next) - I.towerCost(best.cfg);
    if (delta > getW()) return false;
    if (!force) {
      const gain = (I.TS.dps.steps[next.dps] - I.TS.dps.steps[best.cfg.dps]) / delta;
      if (gain < 18 * 1.5 / (I.RULES.towerBase + I.RULES.towerFee * towers())) return false;
    }
    best.cfg = next; spend(delta); return true;
  }
  function defend(S, opt) {
    let worth = S.dFree;
    for (let i = 0; i < N; i++) {
      const g = S.grid[i]; if (!g) continue;
      if (g.t === 'tower' && g.off > 0) continue;
      worth += g.t === 'wall' ? I.RULES.wall : I.towerValue(g); S.grid[i] = null;
    }
    // same rule as the game: rebuilding on a cell the attacker saw doesn't make it "new"
    const seen = (i, t) => !!(S.seenGrid[i] && S.seenGrid[i].t === t);
    const towers = () => S.grid.reduce((n, g) => n + (g && g.t === 'tower' ? 1 : 0), 0);
    const addWall = i => { if (S.grid[i] || worth < I.RULES.wall) return; S.grid[i] = { t: 'wall', fresh: !seen(i, 'wall') }; worth -= I.RULES.wall; };
    const addTower = (i, cfg) => {
      if (S.grid[i] && S.grid[i].t === 'tower') return true; // a locked offline tower already sits here
      const fee = I.RULES.towerFee * towers(), cost = I.towerCost(cfg) + fee;
      if (worth < cost) return false;
      if (S.grid[i]) { worth += I.RULES.wall; S.grid[i] = null; } // the tower replaces a wall in its column
      S.grid[i] = { t: 'tower', cfg, fee, off: 0, fresh: !seen(i, 'tower'), n: ++S.towerSeq, cd: 0, ang: Math.PI, kick: 0, dealt: 0 };
      worth -= cost; return true;
    };
    const cols = opt.maxCols == null ? 4 : opt.maxCols;
    const plan = [];
    for (let k = 0; k < 4; k++) { if (k < cols) plan.push(['col', k]); plan.push(['tower', k]); }
    for (let k = 4; k < SLOTS.length; k++) plan.push(['tower', k]);
    let placed = 0;
    for (const [kind, k] of plan) {
      if (kind === 'col') {
        const cells = colCells(k);
        if (worth < cells.length * I.RULES.wall) break;
        cells.forEach(addWall);
      } else {
        if (placed >= 4) while (upgradeStep(S, () => worth, v => { worth -= v; }, towers)) { /* upgrade first */ }
        const [c, r] = SLOTS[k];
        if (!addTower(at(c, r), towerCfgFor(S.seenArmy, k, opt.style))) break;
        placed++;
      }
    }
    while (upgradeStep(S, () => worth, v => { worth -= v; }, towers, true)) { /* spend the rest */ }
    S.dFree = worth;
    I.recompute();
    if (!S.path) throw new Error('defender blocked the path');
  }

  /* ---------------- attacker ----------------
     Also re-buys its whole army from its worth every round (units refund in full).
     opt.army: a strategy name below, or opt.armySpec = [[stats or preset name, share, start, end], ...]
       stats are slider indexes, e.g. { hp: 6, speed: 4, regen: 3 }; start/end are the wave-timeline window (0..1).
     opt.charges: 'walls' | 'towers' | 'both' (with opt.chargeShare = share of worth spent on charges)
     opt.cap: respect the "half the seen towers offline per wave" cap; opt.noLastCharges: none in the final wave. */
  const DESIGNS = {
    Tank: { hp: 9, speed: 7, armor: 3 },          // everything maxed
    MiniTank: { hp: 5, speed: 5, armor: 2 },
    BigTank: { hp: 7, speed: 6, armor: 3 },
    RegenBruiser: { hp: 6, speed: 4, regen: 3 },
    FatRegen: { hp: 9, speed: 0, regen: 3 },
  };
  const ARMIES = {
    swarm: [['Swarm', 1, 0, 0.12]],
    rush: [['Runner', 1, 0, 0.3]],
    brute: [['Brute', 0.5, 0, 0.15], ['Runner', 0.5, 0.12, 0.25]],
    ghost: [['Ghost', 1, 0, 0.3]],
    mixed: [['Brute', 0.35, 0, 0.15], ['Swarm', 0.35, 0.05, 0.2], ['Runner', 0.3, 0.12, 0.25]],
    tank: [['Tank', 1, 0, 0.1], ['Runner', 0, 0, 0.3]],
    tankswarm: [['Tank', 0.6, 0, 0.1], ['Swarm', 0.4, 0, 0.12]],
    minitank: [['MiniTank', 1, 0, 0.15], ['Runner', 0, 0, 0.3]],
    bigtank: [['BigTank', 1, 0, 0.15], ['Runner', 0, 0, 0.3]],
    regenbruiser: [['RegenBruiser', 1, 0, 0.15], ['Runner', 0, 0, 0.3]],
    fatregen: [['FatRegen', 1, 0, 1], ['Runner', 0, 0, 0.3]],
  };
  function pickArmy(S, opt) {
    if (opt.armySpec) return 'custom';
    if (opt.army === 'alternate') return S.lastPick = !S.lastPick ? 'swarm' : S.lastPick === 'swarm' ? 'brute' : 'swarm';
    if (opt.army !== 'counter') return opt.army;
    // counter-pick from the towers seen last wave: splash -> tough units, otherwise a swarm
    let n = 0, splash = 0;
    for (const g of S.seenGrid) if (g && g.t === 'tower') { n++; if (g.cfg.splash) splash++; }
    return !n || splash / n < 0.3 ? 'swarm' : 'brute';
  }
  function makeDesign(p, k) {
    const preset = typeof p === 'string' && I.UPRESETS[p] ? p : 'Runner';
    const d = I.makeDesign(preset, typeof p === 'string' ? p : 'Custom', I.COLORS[k % I.COLORS.length]);
    Object.assign(d, typeof p === 'string' ? (DESIGNS[p] || {}) : p);
    return d;
  }
  function attack(S, opt) {
    let worth = S.aFree;
    for (const d of S.designs) worth += d.count * I.unitCost(d);
    S.charges = new Map();
    const budget = Math.floor(worth * (opt.chargeShare || 0));
    let spent = 0;
    if (budget > 0 && !(S.round >= I.RULES.rounds && opt.noLastCharges)) {
      const tw = [];
      S.seenGrid.forEach((g, i) => { if (g && g.t === 'tower') tw.push([I.towerValue(g), i, g]); });
      tw.sort((a, b) => b[0] - a[0]);
      const cap = opt.cap ? Math.ceil(tw.length / 2) : tw.length;
      let off = tw.filter(([, , g]) => g.off > 0).length;
      if (opt.charges === 'towers' || opt.charges === 'both') {
        for (const [, i, g] of tw) { // knock out the most valuable towers for one wave
          if (g.off > 0) continue;
          const c = I.RULES.towerCharge[0];
          if (off >= cap || spent + c > budget * (opt.charges === 'both' ? 0.6 : 1)) break;
          S.charges.set(i, { kind: 'tower', waves: 1, cost: c }); spent += c; off++;
        }
      }
      if (opt.charges === 'walls' || opt.charges === 'both') {
        for (let c = 0; c < COLS; c++) { // one hole per wall column, beside its middle, to cut the maze short
          let walls = 0; for (let r = 0; r < ROWS; r++) { const g = S.seenGrid[at(c, r)]; if (g && g.t === 'wall') walls++; }
          if (walls < 7) continue;
          for (const r of [4, 6, 3, 7]) {
            const g = S.seenGrid[at(c, r)];
            if (!g || g.t !== 'wall') continue;
            if (spent + I.RULES.wallCharge <= budget) { S.charges.set(at(c, r), { kind: 'wall', waves: 0, cost: I.RULES.wallCharge }); spent += I.RULES.wallCharge; }
            break;
          }
        }
      }
    }
    worth -= spent;
    const key = pickArmy(S, opt);
    const spec = key === 'custom' ? opt.armySpec : ARMIES[key];
    if (!spec) throw new Error('unknown army ' + key);
    S.designs = spec.map(([p, , s, e], k) => { const d = makeDesign(p, k); d.tl = { s, e, pos: null }; return d; });
    let left = worth;
    S.designs.forEach((d, k) => { d.count = Math.floor(worth * spec[k][1] / I.unitCost(d)); left -= d.count * I.unitCost(d); });
    const last = S.designs[S.designs.length - 1]; // spend leftovers on the last design so coins aren't wasted
    if (last && spec.length > 1) { const extra = Math.floor(left / I.unitCost(last)); last.count += extra; left -= extra * I.unitCost(last); }
    S.aFree = left;
    return key;
  }

  // One full match. rules: overrides for RULES (and the knobs in tools/common.py), plus optional US patches:
  //   { wallCharge: 80, hpScale: 0.8, US: { armor: { steps: [0, 2, 4, 7] } } }
  window.runMatch = (dOpt, aOpt, seed, rules = {}) => {
    resetUS();
    const { US, ...plain } = rules;
    Object.assign(I.RULES, window.__baseRules, { dmgScale: 1, spdScale: 1, hpScale: 1, armorFloor: 0.2 }, plain);
    if (US) for (const [k, v] of Object.entries(US)) { if (v.steps) I.US[k].steps.splice(0, Infinity, ...v.steps); if (v.m) I.US[k].m.splice(0, Infinity, ...v.m); }
    I.S = I.newState(); const S = I.S;
    I.recompute();
    const log = [];
    for (;;) {
      defend(S, dOpt);
      const army = attack(S, aOpt);
      I.startWave(seed * 101 + S.round);
      window.siegeline.advance(900);
      if (S.over && S.winner === 'attacker') { log.push({ r: S.round, army, X: S.wave.x, Y: Math.round(S.wave.y), keep: 0 }); return { winner: 'attacker', round: S.round, keep: 0, log }; }
      const L = S.last;
      log.push({ r: S.round, army, X: L.X, Y: Math.round(L.Y), breach: Math.round(L.breach * 100), keep: Math.round(S.keep),
        defWorth: Math.round(S.dFree + S.grid.reduce((v, g) => v + (g ? (g.t === 'wall' ? I.RULES.wall : I.towerValue(g)) : 0), 0)),
        atkWorth: S.aFree + S.designs.reduce((v, d) => v + d.count * I.unitCost(d), 0), charges: L.charges, jammed: L.jammed, wallsBlown: L.walls });
      if (S.over) return { winner: S.winner, round: S.round, keep: Math.round(S.keep), log };
      S.round++;
    }
  };

  // One wave on a fixed defense, for quick what-ifs. towers: list of tower cfg patches placed in the maze slots;
  // army: [[stats or preset, count, start, end], ...]. Returns breach and costs.
  window.runWave = (towers, army, rules = {}, cols = 4, seed = 7) => {
    resetUS();
    const { US, ...plain } = rules;
    Object.assign(I.RULES, window.__baseRules, { dmgScale: 1, spdScale: 1, hpScale: 1, armorFloor: 0.2 }, plain);
    if (US) for (const [k, v] of Object.entries(US)) { if (v.steps) I.US[k].steps.splice(0, Infinity, ...v.steps); if (v.m) I.US[k].m.splice(0, Infinity, ...v.m); }
    I.S = I.newState(); const S = I.S;
    let cost = 0, fee = 0;
    for (let k = 0; k < cols; k++) for (const i of colCells(k)) { S.grid[i] = { t: 'wall', fresh: false }; cost += I.RULES.wall; }
    towers.forEach((cfg, k) => {
      const [c, r] = SLOTS[k], i = at(c, r);
      if (S.grid[i]) cost -= I.RULES.wall;
      const g = { t: 'tower', cfg: { ...I.defaultTower(), ...cfg }, fee, off: 0, fresh: false, n: k + 1, cd: 0, ang: Math.PI, kick: 0, dealt: 0 };
      S.grid[i] = g; cost += I.towerCost(g.cfg) + fee; fee += I.RULES.towerFee;
    });
    I.recompute();
    if (!S.path) throw new Error('blocked');
    S.designs = army.map(([p, n, s, e], k) => { const d = makeDesign(p, k); d.count = n; d.tl = { s, e, pos: null }; return d; });
    const X = S.designs.reduce((v, d) => v + d.count * I.unitCost(d), 0);
    S.keep = 1e9; I.startWave(seed); window.siegeline.advance(900);
    return { defenseCost: cost, armyCost: X, unitCosts: S.designs.map(d => I.unitCost(d)), breach: Math.round(S.last.breach * 100), keepDamage: Math.round(S.last.Y), route: I.pathLen(S.path) };
  };
})();
