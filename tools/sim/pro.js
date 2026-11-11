// Skill-level players for the v28 balance study (tools/sim/pro.py). Loaded after ai.js in the tools' copy of the page.
//
// Defenders
//   pro    the advanced build the user showed (a screenshot of a real match): a compact maze on the left of the board where
//          the route wraps round every tower or passes it twice, and a roster of four: splash + frost, splash + poison,
//          chain + poison, and a short-range tower with the most damage and the fastest fire. It keeps its towers where
//          they are (so it pays no move fee), retunes them in place every round (tuning refunds in full), adds towers on
//          the maze's walls as its coins grow, repairs the maze when a bridge lands, and with sabotage on turns the wall
//          a bridge would hurt most into a tower (a bridge on a tower misses).
//   proA   the same, adapting: it tries several ways of spending its coins and keeps the one that holds best in hidden
//          waves against the army it saw last (scaled to the attacker's coins) and a few likely counters.
//   am     an amateur: keeps the free starter maze, puts towers on random cells beside the route (not on turns, nothing
//          wrapped round them), picks presets at random and spends what's left on random upgrades. Never sells or moves.
//   cpu    the game's own computer defender (brainPlan), Hard by default: serpentine columns, towers spread along them.
// Attackers
//   pro    the advanced attacker: every round it searches unit designs (health, speed, armor, regen, resists), mixes of
//          two or three designs, one design split into groups, the spacing and timing of each group, and sabotage, each
//          played in a hidden wave against the defense it saw last; it starts from last round's best and keeps the
//          army that does the most keep damage there.
//   am     an amateur: random designs, random timing, kept or replaced at random, occasional random sabotage.
//   cpu    the game's own computer attacker (brainPlan), Hard by default.
(() => {
  const I = window.siegeline._i, COLS = 16, ROWS = 11, N = COLS * ROWS, MIDR = 5;
  const ENTRY = MIDR * COLS, EXIT = MIDR * COLS + COLS - 1;
  const at = (c, r) => r * COLS + c, cr = i => [i % COLS, (i / COLS) | 0];
  const mulberry = seed => { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; };
  const top = k => I.TS[k].steps.length - 1;
  const utop = k => I.US[k].steps.length - 1;

  /* ---------------- maps and the pro layout ---------------- */
  // The board in the user's screenshot (v28): its terrain, the maze's walls and the four roster towers.
  const SHOT = {
    rock: [[0, 2], [3, 5], [2, 8], [3, 10], [7, 8], [7, 9], [8, 3], [13, 9], [14, 9]],
    rough: [[3, 3], [5, 4], [0, 10], [1, 10], [8, 0], [13, 2], [11, 7], [12, 7], [10, 9]],
    walls: [[4, 0], [4, 1], [4, 2], [4, 3], [5, 3], [1, 4], [5, 5], [5, 6], [3, 7], [4, 7], [2, 2], [2, 3], [6, 4], [0, 6], [1, 6]],
    roles: [['dps', [2, 1]], ['sf', [2, 5]], ['cp', [3, 8]], ['sp', [1, 9]]],
  };
  const LAYOUTS = {
    // exactly the screenshot
    shot: { map: 'shot', walls: SHOT.walls, roles: SHOT.roles },
    // the same maze on a board with no terrain: the rocks it leans on become walls
    clean: { map: 'none', walls: SHOT.walls.concat([[0, 2], [3, 5], [2, 8], [3, 10], [7, 8], [7, 9]]), roles: SHOT.roles },
  };
  function setMap(S, key, seed) {
    if (key === 'shot') {
      S.terrain = new Uint8Array(N);
      for (const [c, r] of SHOT.rock) S.terrain[at(c, r)] = I.ROCK;
      for (const [c, r] of SHOT.rough) S.terrain[at(c, r)] = I.ROUGH;
      S.mapSeed = 28028;
      for (let i = 0; i < N; i++) if (S.terrain[i] === I.ROCK) { S.grid[i] = { t: 'rock', fresh: false }; S.seenGrid[i] = { t: 'rock', fresh: false }; }
      S.gridVer++; S.seenVer++;
    } else if (key === 'none') { S.terrain = new Uint8Array(N); S.mapSeed = 1; }
    else I.startMap(Math.imul(seed, 2654435761) >>> 0);
  }
  function setRules(rules) {
    for (const k of Object.keys(I.RULES)) if (!(k in window.__baseRules)) delete I.RULES[k]; // sim-only switches from an earlier run
    Object.assign(I.RULES, window.__baseRules, { dmgScale: 1, spdScale: 1, hpScale: 1, armorFloor: 0.2 }, rules);
  }
  function freshState(rules, mapKey, seed) {
    setRules(rules);
    I.S = I.newState(rules.rounds || I.RULES.rounds); const S = I.S;
    S.sabo = rules.sabotage !== false;
    setMap(S, mapKey, seed);
    if (rules.noStarter !== true) I.buildStarter();
    I.recompute();
    return S;
  }

  /* ---------------- shared helpers ---------------- */
  const towersOf = G => { const out = []; G.forEach((g, i) => { if (g && g.t === 'tower') out.push(i); }); return out; };
  const tcount = G => towersOf(G).length;
  const routeOf = (G, br) => I.routeOn(G, br || new Set());
  const coverOf = (i, cfg, route) => { let n = 0; I.coverCells(i, cfg, j => { if (route.has(j)) n++; }); return n; };
  const open = (G, br) => routeOf(G, br).length > 0;
  const mkTower = (S, i, cfg, fee) => ({ t: 'tower', cfg: { ...I.defaultTower(), ...cfg }, fee, off: 0, fresh: !(S.seenGrid[i] && S.seenGrid[i].t === 'tower'), n: ++S.towerSeq, cd: 0, ang: Math.PI, kick: 0, dealt: 0, mfee: 0 });
  const mkWall = (S, i) => ({ t: 'wall', fresh: !(S.seenGrid[i] && S.seenGrid[i].t === 'wall') });
  const armyValue = ds => ds.reduce((v, d) => v + d.count * I.unitCost(d), 0);
  const defWorth = S => Math.round(S.dFree + S.grid.reduce((v, g) => v + (!g || g.t === 'rock' ? 0 : g.t === 'wall' ? I.RULES.wall : I.towerValue(g)), 0));
  const cfgShort = c => `r${c.range}d${c.dps}a${c.accuracy || 0}f${c.rate}${c.splash ? 's' + c.splash : ''}${c.slow ? 'F' : ''}${c.poison ? 'P' : ''}${c.chain ? 'C' : ''}`;
  const unitShort = d => `h${d.hp}s${d.speed}${d.armor ? 'a' + d.armor : ''}${d.regen ? 'g' + d.regen : ''}${d.resist && d.resist !== 'none' ? '+' + d.resist : ''}`;

  /* ---------------- the pro defender ---------------- */
  const ROLE = {
    dps: { base: { range: 0, rate: 0, dps: 2, accuracy: 0 }, keys: ['dps', 'accuracy'] },          // short range, most damage, fastest fire
    sf: { base: { range: 2, rate: 2, dps: 1, splash: 2, slow: true }, keys: ['dps', 'splash', 'range'] },
    cp: { base: { range: 2, rate: 3, dps: 1, chain: true, poison: true }, keys: ['dps', 'range'] },
    sp: { base: { range: 2, rate: 3, dps: 1, splash: 2, poison: true }, keys: ['dps', 'splash', 'range', 'slow'] }, // frost too when it can
    guard: { base: { range: 1, rate: 1, dps: 1 }, keys: ['dps', 'range'] },                         // a tower on a wall a bridge would hurt most
  };
  // what a tower is worth to the pro, roughly: expected damage a second × route cells in its range × its effects
  const FXV = { splash: s => 1 + 1.2 * I.TS.splash.steps[s], chain: 1.6, poison: 1.35, slow: 1.25 };
  function tval(cfg, cover, w = 1, armor = 0) {
    const rate = I.TS.rate.steps[cfg.rate], hit = I.TS.dps.steps[cfg.dps] / rate;
    let m = rate * Math.max(0.2 * hit, hit - armor) * I.shotAcc(cfg) / 100;
    if (cfg.splash) m *= FXV.splash(cfg.splash);
    if (cfg.chain) m *= FXV.chain;
    if (cfg.poison) m *= FXV.poison;
    if (cfg.slow) m *= FXV.slow;
    return m * cover * w;
  }
  const fireScore = (G, br, W) => { const route = new Set(routeOf(G, br)); let v = 0; for (const i of towersOf(G)) v += tval(G[i].cfg, coverOf(i, G[i].cfg, route), 1); return v; };
  // the extra tower slots: the maze's walls ranked by how much route a 2.5-cell tower there would cover
  function extraSlots(S, L) {
    const route = new Set(routeOf(S.grid, S.bridges)), taken = new Set(L.roles.map(([, [c, r]]) => at(c, r)));
    return L.walls.map(([c, r]) => at(c, r)).filter(i => !taken.has(i) && S.grid[i] && S.grid[i].t === 'wall')
      .map(i => [coverOf(i, { range: 2 }, route), i]).filter(x => x[0] >= 6).sort((a, b) => b[0] - a[0]).map(x => x[1]);
  }
  // round 1: sell the starter maze and build the layout's walls
  function layOut(S, L) {
    for (let i = 0; i < N; i++) if (S.grid[i] && S.grid[i].t === 'wall') { S.grid[i] = null; S.dFree += I.RULES.wall; }
    for (const [c, r] of L.walls) { const i = at(c, r); if (!S.grid[i] && !S.terrain[i] && !S.bridges.has(i)) { S.grid[i] = mkWall(S, i); S.dFree -= I.RULES.wall; } }
    for (const [, [c, r]] of L.roles) { const i = at(c, r); if (!S.grid[i] && !S.terrain[i]) { S.grid[i] = mkWall(S, i); S.dFree -= I.RULES.wall; } } // slots wait as walls
    I.recompute();
    if (!S.path) throw new Error('pro layout blocks the route');
  }
  // after a bridge opens the maze: walls (5 each) where they put the most fire back on the route, up to `most`
  function repair(S, most = 6) {
    let base = fireScore(S.grid, S.bridges), added = 0;
    for (let k = 0; k < most && S.dFree >= I.RULES.wall; k++) {
      let best = null;
      for (let i = 0; i < N; i++) {
        if (S.grid[i] || S.terrain[i] === I.ROCK || S.bridges.has(i) || i === ENTRY || i === EXIT || S.terrain[i]) continue;
        S.grid[i] = { t: 'wall' };
        const ok = open(S.grid, S.bridges), v = ok ? fireScore(S.grid, S.bridges) : -1;
        S.grid[i] = null;
        if (v > base * 1.03 && (!best || v > best.v)) best = { i, v };
      }
      if (!best) break;
      S.grid[best.i] = mkWall(S, best.i); S.dFree -= I.RULES.wall; base = best.v; added++;
    }
    I.recompute();
    return added;
  }
  // The pro's spending: start every tower at its role's base tuning, then buy the step (on any tower, or a new tower on
  // the next extra slot) with the most value per coin, until nothing fits. W weights the roles (proA tries several).
  function proTowers(S, L, W, opt) {
    let A = S.dFree;
    const slots = []; // { i, role }
    for (const [role, [c, r]] of L.roles) slots.push({ i: at(c, r), role });
    for (const i of towersOf(S.grid)) if (!slots.some(s => s.i === i)) slots.push({ i, role: (S.grid[i].role || 'dps') });
    // refund every tuning: the plan starts from scratch (a tower's fee stays)
    for (const s of slots) { const g = S.grid[s.i]; if (g && g.t === 'tower') A += I.towerCost(g.cfg); }
    const route = new Set(routeOf(S.grid, S.bridges));
    const plan = [];
    const feeNext = () => I.RULES.towerFee * (tcount(S.grid) + plan.filter(p => p.isNew).length);
    for (const s of slots) {
      const g = S.grid[s.i];
      if (g && g.t === 'rock') continue;
      const cfg = { ...I.defaultTower(), ...ROLE[s.role].base };
      const isNew = !(g && g.t === 'tower');
      const cost = I.towerCost(cfg) + (isNew ? feeNext() : 0);
      if (cost > A) continue; // can't afford this role yet (round 1 on little money)
      A -= cost + (isNew && g && g.t === 'wall' ? -I.RULES.wall : 0);
      plan.push({ i: s.i, role: s.role, cfg, isNew, fee: isNew ? cost - I.towerCost(cfg) : g.fee });
    }
    const extras = extraSlots(S, L).filter(i => !plan.some(p => p.i === i));
    const roleCycle = opt.extraRoles || ['dps', 'sf', 'cp', 'dps', 'sf', 'cp'];
    const arm = opt.armor || 0;
    const val = p => tval(p.cfg, coverOf(p.i, p.cfg, route), W[p.role] || 1, arm);
    // fire rate is free: with armor in the army it goes where each hit beats the armor (opt.rateMode 'armor')
    const fixRate = p => { if (opt.rateMode !== 'armor' || !arm) return; let br = null; for (let r = 0; r <= top('rate'); r++) { const c = { ...p.cfg, rate: r }, v = tval(c, 1, 1, arm); if (!br || v > br.v) br = { r, v }; } p.cfg.rate = br.r; };
    plan.forEach(fixRate);
    for (let guard = 0; guard < 400; guard++) {
      let best = null;
      for (const p of plan) {
        const v0 = val(p), c0 = I.towerCost(p.cfg);
        for (const k of ROLE[p.role].keys) {
          const next = { ...p.cfg };
          if (k === 'slow') { if (next.slow || (opt.slowAfter && A < opt.slowAfter)) continue; next.slow = true; }
          else { if (next[k] >= top(k)) continue; next[k]++; }
          if (k === 'range' && next.range > (opt.maxRange ?? 3)) continue;
          if (k === 'splash' && next.splash > (opt.maxSplash ?? 3)) continue;
          const dc = I.towerCost(next) - c0; if (dc > A || dc <= 0) continue;
          const r = (tval(next, coverOf(p.i, next, route), W[p.role] || 1, arm) - v0) / dc;
          if (r > 0 && (!best || r > best.r)) best = { r, p, next, dc };
        }
      }
      const nx = extras[0];
      if (nx != null && plan.length < (opt.maxTowers || 8)) { // a new tower on the best extra slot
        const role = roleCycle[(plan.length - 4 + roleCycle.length) % roleCycle.length] || 'dps';
        const cfg = { ...I.defaultTower(), ...ROLE[role].base }, fee = feeNext(), dc = I.towerCost(cfg) + fee - I.RULES.wall;
        const r = tval(cfg, coverOf(nx, cfg, route), W[role] || 1, arm) / dc;
        if (dc <= A && (!best || r > best.r * (opt.extraBias || 1))) best = { r, add: { i: nx, role, cfg, isNew: true, fee }, dc };
      }
      if (!best) break;
      if (best.add) { plan.push(best.add); fixRate(best.add); extras.shift(); } else best.p.cfg = best.next;
      A -= best.dc;
    }
    return { plan, left: A };
  }
  function applyTowers(S, plan, left) {
    for (const p of plan) {
      const g = S.grid[p.i];
      if (g && g.t === 'tower') { g.cfg = { ...I.defaultTower(), ...p.cfg }; g.role = p.role; }
      else { S.grid[p.i] = mkTower(S, p.i, p.cfg, p.fee); S.grid[p.i].role = p.role; }
    }
    S.dFree = left;
    I.recompute();
  }
  // With sabotage on, the seen wall whose bridge would take the most fire off the route becomes a tower (a bridge on a
  // tower misses), if its bridge would cost more than a quarter of the fire.
  function guardWalls(S, L, opt) {
    if (S.sabo === false || S.round < 2 || S.round >= S.rounds || opt.noGuard) return [];
    const ok = I.bridgeSpots(S.seenGrid, S.bridges), base = fireScore(S.grid, S.bridges), out = [];
    const cand = [];
    for (let i = 0; i < N; i++) {
      if (!ok(i)) continue;
      if (!S.grid[i] || S.grid[i].t !== 'wall') continue;
      const br = new Set(S.bridges); br.add(i);
      const G = S.grid.slice(); G[i] = null;
      cand.push([base - fireScore(G, br), i]);
    }
    cand.sort((a, b) => b[0] - a[0]);
    const have = towersOf(S.grid).filter(i => S.grid[i].role === 'guard').length; // at most opt.guards (2) guard towers in all
    for (const [drop, i] of cand.slice(0, Math.max(0, (opt.guards ?? 2) - have))) {
      if (drop < base * 0.25) break;
      out.push(i);
    }
    return out;
  }
  function proDefend(S, opt) {
    const L = LAYOUTS[opt.layout || 'shot'];
    if (S.round === 1 && !S.__laid) { layOut(S, L); S.__laid = true; }
    const fixed = S.bridges.size && S.__bridgesSeen !== S.bridges.size ? repair(S) : 0;
    S.__bridgesSeen = S.bridges.size;
    const guards = guardWalls(S, L, opt);
    const Lg = guards.length ? { ...L, roles: L.roles.concat(guards.filter(i => !L.roles.some(([, [c, r]]) => at(c, r) === i)).map(i => ['guard', cr(i)])) } : L;
    const W = opt.W || { dps: 1.5, sf: 1, cp: 1, sp: 0.9, guard: 0.6 };
    const { plan, left } = proTowers(S, Lg, W, opt);
    applyTowers(S, plan, left);
    if (!S.path) throw new Error('pro defender blocked the route');
    return { repaired: fixed, guards: guards.length, towers: plan.map(p => p.role + ':' + cfgShort(p.cfg)).join(' ') };
  }
  // proA: several weightings, each tried in hidden waves against the last army seen (scaled to the attacker's coins now)
  // and a few counters; the one that lets the least keep damage through (mean of the panel) is built.
  const PANEL = [
    [{ hp: 0, speed: 4 }, 1, 0, 0.1],               // a bunched swarm
    [{ hp: 6, speed: 4, regen: 3 }, 1, 0, 0.15],    // regen bruisers
    [{ hp: 7, speed: 3, armor: 3 }, 1, 0, 0.15],    // armored tanks
    [{ hp: 3, speed: 6 }, 1, 0, 0.4],               // fast, spread
  ];
  // the army's armor, weighted by what each design cost
  const armorOf = ds => { let v = 0, a = 0; for (const d of ds || []) if (d.count) { const c = d.count * I.unitCost(d); v += c; a += c * I.US.armor.steps[d.armor || 0]; } return v ? a / v : 0; };
  function proDefendAdaptive(S, opt) {
    const L = LAYOUTS[opt.layout || 'shot'];
    if (S.round === 1 && !S.__laid) { layOut(S, L); S.__laid = true; }
    const fixed = S.bridges.size && S.__bridgesSeen !== S.bridges.size ? repair(S) : 0;
    S.__bridgesSeen = S.bridges.size;
    const guards = guardWalls(S, L, opt);
    const Lg = guards.length ? { ...L, roles: L.roles.concat(guards.filter(i => !L.roles.some(([, [c, r]]) => at(c, r) === i)).map(i => ['guard', cr(i)])) } : L;
    const Ws = [
      { dps: 1.5, sf: 1, cp: 1, sp: 0.9, guard: 0.6 },
      { dps: 2.5, sf: 0.8, cp: 0.8, sp: 0.7, guard: 0.6 },
      { dps: 1, sf: 1.6, cp: 1, sp: 1.3, guard: 0.6 },
      { dps: 1, sf: 1, cp: 1.8, sp: 0.8, guard: 0.6 },
    ];
    const aw = S.aFree + armyValue(S.designs);
    const armies = []; // [designs, weight]
    const scaled = ds => { const sv = armyValue(ds), k = sv ? aw / sv : 1; return ds.filter(d => d.count).map(d => ({ ...d, count: Math.max(1, Math.floor(d.count * k)), tl: { ...d.tl, pos: null } })); };
    if (S.seenArmy && S.seenArmy.some(d => d.count)) armies.push([scaled(S.seenArmy), 1]);
    // the army it expects: the best answer to the defense the attacker saw (level-2 thinking), unless opt.noPredict
    if (!opt.noPredict && S.round > 1) {
      const pr = searchArmy(S.seenGrid, aw, { bridges: [...S.bridges], sabo: false, round: S.round, rounds: S.rounds, rnd: mulberry(S.round * 77), effort: 1, seeds: [5151 + S.round] });
      armies.push([buildArmy(pr.best.spec, aw).ds, 1.5]);
    }
    for (const [u, , s, e] of PANEL.slice(0, opt.panel ?? 3)) { const d = I.makeDesign('Runner', 'P', I.COLORS[0]); Object.assign(d, { armor: 0, regen: 0, resist: 'none' }, u); d.count = Math.floor(aw / I.unitCost(d)); d.tl = { s, e, pos: null }; armies.push([[d], 0.5]); }
    const arm = Math.max(...armies.slice(0, 2).map(([ds]) => armorOf(ds)), 0);
    let best = null;
    const snapG = S.grid.map(g => (g && g.t === 'tower' ? { ...g, cfg: { ...g.cfg } } : g)), snapF = S.dFree, snapSeq = S.towerSeq;
    const cands = [];
    for (let wi = 0; wi < Ws.length; wi++) for (const rateMode of ['base', 'armor']) for (const maxSplash of [2, 3]) cands.push({ wi, rateMode, maxSplash });
    for (const c of cands) {
      S.grid = snapG.map(g => (g && g.t === 'tower' ? { ...g, cfg: { ...g.cfg } } : g)); S.dFree = snapF; S.towerSeq = snapSeq;
      const { plan, left } = proTowers(S, Lg, Ws[c.wi], { ...opt, rateMode: c.rateMode, maxSplash: c.maxSplash, armor: c.rateMode === 'armor' ? Math.max(arm, 3) : 0 });
      const G = S.grid.slice();
      for (const p of plan) G[p.i] = { t: 'tower', cfg: { ...I.defaultTower(), ...p.cfg }, fee: p.fee, off: 0, n: 900 + plan.indexOf(p), fresh: false, cd: 0, ang: Math.PI, kick: 0, dealt: 0 };
      let y = 0, wsum = 0, worst = 0;
      for (const [ds, w] of armies) { const r = I.trial(G, ds, [], 7000 + S.round, [...S.bridges]); y += r.Y * w; wsum += w; worst = Math.max(worst, r.Y); }
      const score = y / wsum + 0.25 * worst;
      if (!best || score < best.score) best = { score, c, plan, left };
    }
    S.grid = snapG; S.dFree = snapF; S.towerSeq = snapSeq;
    applyTowers(S, best.plan, best.left);
    if (!S.path) throw new Error('proA blocked the route');
    return { repaired: fixed, guards: guards.length, w: `${best.c.wi}${best.c.rateMode[0]}${best.c.maxSplash}`, towers: best.plan.map(p => p.role + ':' + cfgShort(p.cfg)).join(' ') };
  }

  /* ---------------- the amateur defender ---------------- */
  const PRESETS = [['Basic', {}, 0.4], ['Cannon', { rate: 4, splash: 2 }, 0.25], ['Sniper', { range: 5, rate: 5 }, 0.2], ['Frost', { range: 1, dps: 1, rate: 2, slow: true }, 0.15]];
  function pickW(list, rnd) { let x = rnd() * list.reduce((v, l) => v + l[2], 0); for (const l of list) { x -= l[2]; if (x <= 0) return l; } return list[list.length - 1]; }
  function amDefend(S, opt, rnd) {
    let budget = Math.floor(S.dFree * (0.75 + 0.25 * rnd()));
    const route = routeOf(S.grid, S.bridges), onRoute = new Set(route);
    const spots = [];
    for (let i = 0; i < N; i++) {
      if (S.grid[i] || S.terrain[i] || S.bridges.has(i) || onRoute.has(i)) continue;
      const [c, r] = cr(i);
      if ([[1, 0], [-1, 0], [0, 1], [0, -1]].some(([dx, dy]) => onRoute.has(at(c + dx, r + dy)) && c + dx >= 0 && c + dx < COLS)) spots.push(i);
    }
    let made = 0, ups = 0;
    for (let k = 0; k < 40 && budget > 0; k++) {
      const tw = towersOf(S.grid);
      if (tw.length < (opt.minTowers || 3) || rnd() < 0.4) {
        if (!spots.length) continue;
        let pick = Math.floor(rnd() * spots.length);
        if (opt.hint && rnd() < opt.hint) { const rs = new Set(route); let bv = -1; spots.forEach((j, k) => { const v = coverOf(j, { range: 2 }, rs); if (v > bv) { bv = v; pick = k; } }); }
        const i = spots.splice(pick, 1)[0];
        const [, cfg] = pickW(PRESETS, rnd), fee = I.RULES.towerFee * tw.length, c = { ...I.defaultTower(), ...cfg };
        const cost = I.towerCost(c) + fee;
        if (cost > budget) continue;
        S.grid[i] = mkTower(S, i, c, fee);
        if (!open(S.grid, S.bridges)) { S.grid[i] = null; S.towerSeq--; continue; }
        budget -= cost; S.dFree -= cost; made++;
      } else if (tw.length) {
        const g = S.grid[tw[Math.floor(rnd() * tw.length)]], c0 = I.towerCost(g.cfg), next = { ...g.cfg };
        const x = rnd();
        if (x < 0.12) { const fx = ['slow', 'poison', 'chain'][Math.floor(rnd() * 3)]; if (next[fx]) continue; next[fx] = true; if (fx === 'chain') next.splash = 0; }
        else { const key = ['dps', 'dps', 'dps', 'range', 'accuracy', 'splash'][Math.floor(rnd() * 6)]; if (next[key] >= top(key)) continue; next[key]++; if (key === 'splash') next.chain = false; }
        const dc = I.towerCost(next) - c0;
        if (dc > budget || dc <= 0) continue;
        g.cfg = next; budget -= dc; S.dFree -= dc; ups++;
      }
    }
    I.recompute();
    return { made, ups, towers: towersOf(S.grid).map(i => cfgShort(S.grid[i].cfg)).join(' ') };
  }

  /* ---------------- the game's own computer ---------------- */
  function cpuDefend(S, opt, rnd, seed) {
    const r = I.brainPlan('def', opt.level || 'hard', seed), p = r.plan;
    S.grid = I.decodeGrid(p.g); S.dFree = p.dFree; S.towerSeq = p.ts; if (p.mt != null) S.totals.moveTries = p.mt; S.mvFee = p.mf || 0; I.recompute();
    return { towers: towersOf(S.grid).map(i => cfgShort(S.grid[i].cfg)).join(' ') };
  }
  function cpuAttack(S, opt, rnd, seed) {
    const p = I.brainPlan('atk', opt.level || 'hard', seed).plan;
    S.designs = I.decodeArmy(p.a); S.aFree = p.aFree; S.charges = I.decodeCharges(p.c);
    return { army: S.designs.filter(d => d.count).map(d => `${unitShort(d)}x${d.count}`).join(' ') };
  }

  /* ---------------- armies ---------------- */
  // spec: [{ u: { hp, speed, armor, regen, resist }, w: share of the coins, s, e: release window (0..1 of the 20 s) }]
  function buildArmy(spec, B) {
    const ds = []; let left = B;
    spec.forEach((g, k) => {
      const d = I.makeDesign('Runner', 'G' + k, I.COLORS[k % I.COLORS.length]);
      Object.assign(d, { armor: 0, regen: 0, resist: 'none' }, g.u);
      if (I.RULES.resMax != null && d.resist !== 'none') { const l = d.resist.split('+').slice(0, I.RULES.resMax); d.resist = l.length ? l.join('+') : 'none'; } // sim-only cap on resists a design
      d.tl = { s: g.s, e: g.e, pos: null };
      d.count = Math.max(0, Math.floor(B * g.w / I.unitCost(d)));
      left -= d.count * I.unitCost(d); ds.push(d);
    });
    // leftovers go on whichever group they buy most of
    for (let more = true; more;) {
      more = false;
      const d = ds.filter(x => I.unitCost(x) <= left).sort((a, b) => I.unitCost(a) - I.unitCost(b))[0];
      if (d && d.count > 0) { d.count++; left -= I.unitCost(d); more = true; }
    }
    return { ds: ds.filter(d => d.count > 0), left };
  }
  const specKey = spec => JSON.stringify(spec.map(g => [g.u.hp, g.u.speed, g.u.armor || 0, g.u.regen || 0, g.u.resist || 'none', Math.round(g.w * 100), Math.round(g.s * 100), Math.round(g.e * 100)]));

  /* ---------------- the amateur attacker ---------------- */
  function amAttack(S, opt, rnd) {
    let B = S.aFree + armyValue(S.designs);
    S.charges = new Map();
    // occasional random sabotage
    if (S.sabo !== false && S.round > 1 && S.round < S.rounds && rnd() < (opt.saboRate ?? 0.3)) {
      const tw = towersOf(S.seenGrid);
      const tries = { bridgeTries: S.totals.bridgeTries || 0, koTries: S.totals.koTries || 0 };
      if (tw.length && rnd() < 0.6) {
        const i = tw[Math.floor(rnd() * tw.length)], c = I.towerChargeCost(I.sabC(S.seenGrid[i]), tries.koTries);
        if (c < B * 0.3) { S.charges = I.sapPlan(S.seenGrid, S.bridges, [[i, 'tower']], 0.1, tries); B -= c; }
      } else {
        const pred = I.bridgeSpots(S.seenGrid, S.bridges), ok = []; for (let i = 0; i < N; i++) if (pred(i)) ok.push(i);
        if (ok.length) { const i = ok[Math.floor(rnd() * ok.length)], ch = priceBridges(S.seenGrid, S.bridges, I.sapPlan(S.seenGrid, S.bridges, [[i, 'bridge']], 0.1, tries)), c = [...ch.values()][0].cost; if (c < B * 0.3) { S.charges = ch; B -= c; } }
      }
    }
    if (!S.__amSpec || rnd() < 0.4) {
      const k = 1 + Math.floor(rnd() * 3), spec = [];
      for (let j = 0; j < k; j++) {
        const u = { hp: Math.floor(rnd() * 9), speed: Math.floor(rnd() * 8), armor: rnd() < 0.4 ? 1 + Math.floor(rnd() * 3) : 0, regen: rnd() < 0.3 ? 1 + Math.floor(rnd() * 3) : 0, resist: 'none' };
        if (rnd() < 0.1) u.resist = ['splash', 'poison', 'frost', 'shock'][Math.floor(rnd() * 4)];
        const s = rnd() * 0.3;
        spec.push({ u, w: 0.2 + rnd(), s, e: Math.min(1, s + 0.05 + rnd() * 0.6) });
      }
      const tw = spec.reduce((v, g) => v + g.w, 0); spec.forEach(g => { g.w /= tw; });
      S.__amSpec = spec;
    }
    const { ds, left } = buildArmy(S.__amSpec, B);
    S.designs = ds; S.aFree = left;
    return { army: ds.map(d => `${unitShort(d)}x${d.count}`).join(' ') };
  }

  // sim-only: a bridge also costs bridgePerCell for every route cell it would save, on the route as the attacker sees it
  function priceBridges(G, br, ch) {
    if (!I.RULES.bridgePerCell) return ch;
    const base = routeOf(G, br).length;
    for (const [cell, c] of ch) if (c.kind === 'bridge') {
      const G2 = G.slice(); G2[cell] = null; const b2 = new Set(br); b2.add(cell);
      c.cost += Math.round(I.RULES.bridgePerCell * Math.max(0, base - routeOf(G2, b2).length));
    }
    return ch;
  }
  /* ---------------- the advanced attacker ---------------- */
  const ARCH = [
    { hp: 0, speed: 4 }, { hp: 0, speed: 6 }, { hp: 1, speed: 4, armor: 1 }, { hp: 2, speed: 6 }, { hp: 2, speed: 5 },
    { hp: 3, speed: 3, armor: 2 }, { hp: 5, speed: 5, armor: 2 }, { hp: 6, speed: 4, regen: 3 }, { hp: 6, speed: 1, armor: 1 },
    { hp: 7, speed: 3, armor: 3 }, { hp: 9, speed: 4 }, { hp: 9, speed: 0, regen: 3 }, { hp: 4, speed: 2, armor: 3, regen: 2 },
    { hp: 8, speed: 2, armor: 2, regen: 3 }, { hp: 5, speed: 7 }, { hp: 3, speed: 5, regen: 2 }, { hp: 6, speed: 3, armor: 2, regen: 3 },
    { hp: 4, speed: 4, armor: 1, regen: 2 },
  ].map(u => ({ armor: 0, regen: 0, resist: 'none', ...u }));
  const RES_FOR = { splash: 'splash', chain: 'shock', poison: 'poison', slow: 'frost' };
  function threatsOf(G, br) {
    const route = new Set(routeOf(G, br)), t = { val: 0, splash: 0, chain: 0, poison: 0, slow: 0, heavy: 0 };
    for (const i of towersOf(G)) {
      const g = G[i], cov = coverOf(i, g.cfg, route); if (!cov) continue;
      const v = I.towerCost(g.cfg) * cov; t.val += v;
      for (const k of ['splash', 'chain', 'poison', 'slow']) if (g.cfg[k]) t[k] += v;
      if (I.TS.dps.steps[g.cfg.dps] / I.TS.rate.steps[g.cfg.rate] >= 25) t.heavy += v;
    }
    for (const k of ['splash', 'chain', 'poison', 'slow', 'heavy']) t[k] = t.val ? t[k] / t.val : 0;
    return t;
  }
  const withRes = (u, list) => ({ ...u, resist: list.length ? ['splash', 'poison', 'frost', 'shock'].filter(k => list.includes(k)).join('+') : 'none' });
  // a reference defense for round 1, when nothing is seen yet: four default towers in the bots' 4-column maze
  function refGrid(S) {
    const G = S.seenGrid.map(g => (g ? { ...g } : null)), cols = [3, 6, 9, 12];
    cols.forEach((c, k) => { const gap = k % 2 ? 10 : 0; for (let r = 0; r < ROWS; r++) if (r !== gap && !G[at(c, r)]) G[at(c, r)] = { t: 'wall', fresh: false }; });
    [[3, 5], [6, 5], [9, 5], [12, 5]].forEach(([c, r], k) => { G[at(c, r)] = { t: 'tower', cfg: I.defaultTower(), fee: 10 * k, off: 0, n: k + 1, fresh: false, cd: 0, ang: Math.PI, kick: 0, dealt: 0 }; });
    return G;
  }
  // The search, used by the pro attacker each round and by the single-wave studies. G: the defense as seen; B: coins;
  // ctx: { bridges, sabo, round, rounds, tries, warm (last best spec), rnd, effort (1 normal, 2+ wider), seeds }
  function searchArmy(G, B, ctx) {
    const br = ctx.bridges || [], seeds = ctx.seeds || [4242 + (ctx.round || 0)], rnd = ctx.rnd || Math.random, effort = ctx.effort || 1;
    const cache = new Map();
    let trials = 0;
    const evalSpec = (spec, charges = null, sabCost = 0, seedList = [seeds[0]]) => {
      const key = specKey(spec) + (charges ? JSON.stringify([...charges.keys()]) + (charges.size ? [...charges.values()][0].t : '') : '') + seedList.join(',');
      if (cache.has(key)) return cache.get(key);
      const { ds } = buildArmy(spec, B - sabCost);
      let Y = 0, X = 0, br0 = 0, leaks = 0, sapOk = 0;
      if (ds.length) for (const sd of seedList) { const r = I.trial(G, ds, charges ? [...charges] : [], sd, br); Y += r.Y; X += r.X; leaks += r.leaks; sapOk += r.sapOk; trials++; }
      const out = { Y: Y / seedList.length, X: X / seedList.length, leaks: leaks / seedList.length, sapOk, spec, charges, sabCost };
      cache.set(key, out);
      return out;
    };
    const thr = threatsOf(G, new Set(br));
    const resNeed = Object.entries(RES_FOR).filter(([k]) => thr[k] >= 0.3).map(([, r]) => r);
    const T0 = [[0, 0.06], [0, 0.4]];
    const results = [];
    const push = r => { results.push(r); return r; };
    // A: archetypes, random designs and last round's best, bunched and spread
    const pool = ARCH.slice();
    for (let k = 0; k < 14 * effort; k++) pool.push({ hp: Math.floor(rnd() * 10), speed: Math.floor(rnd() * 8), armor: rnd() < 0.5 ? Math.floor(rnd() * 4) : 0, regen: rnd() < 0.4 ? Math.floor(rnd() * 4) : 0, resist: 'none' });
    if (resNeed.length) for (const u of ARCH.slice(0, 10)) pool.push(withRes(u, resNeed));
    for (const u of pool) for (const [s, e] of T0) push(evalSpec([{ u, w: 1, s, e }]));
    if (ctx.warm) push(evalSpec(ctx.warm));
    const bestOf = () => results.reduce((a, b) => (b.Y > a.Y ? b : a));
    // B: hill-climb the best single designs (sliders ±1, resists)
    const singles = results.filter(r => r.spec.length === 1).sort((a, b) => b.Y - a.Y);
    const seeds2 = []; const seen = new Set();
    for (const r of singles) { const k = unitShort(r.spec[0].u); if (!seen.has(k)) { seen.add(k); seeds2.push(r); } if (seeds2.length >= 3) break; }
    const climbed = [];
    for (const r0 of seeds2) {
      let cur = r0;
      for (let pass = 0; pass < 3 + effort; pass++) {
        let improved = false;
        const g = cur.spec[0];
        const nbrs = [];
        for (const k of ['hp', 'speed', 'armor', 'regen']) for (const dlt of [-1, 1]) {
          const v = (g.u[k] || 0) + dlt; if (v < 0 || v > utop(k)) continue;
          nbrs.push({ ...g, u: { ...g.u, [k]: v } });
        }
        for (const rk of ['splash', 'poison', 'frost', 'shock']) {
          const l = (g.u.resist || 'none') === 'none' ? [] : g.u.resist.split('+');
          nbrs.push({ ...g, u: withRes(g.u, l.includes(rk) ? l.filter(x => x !== rk) : l.concat(rk)) });
        }
        for (const [s, e] of [[0, 0.02], [0, 0.15], [0, 0.25], [0, 0.6], [0, 1]]) nbrs.push({ ...g, s, e });
        for (const n of nbrs) { const r = push(evalSpec([n])); if (r.Y > cur.Y) { cur = r; improved = true; } }
        if (!improved) break;
      }
      climbed.push(cur);
    }
    // C: mixes of the best two or three designs, a cheap screen, and one design split into two groups
    climbed.sort((a, b) => b.Y - a.Y);
    const A0 = climbed[0].spec[0], B0 = climbed[1] ? climbed[1].spec[0] : null, C0 = climbed[2] ? climbed[2].spec[0] : null;
    const scr = { hp: 0, speed: 5, armor: 0, regen: 0, resist: 'none' };
    const mixes = [];
    if (B0) for (const w of [0.5, 0.7, 0.3]) {
      mixes.push([{ ...A0, w }, { ...B0, w: 1 - w }]); // both in their own windows
      mixes.push([{ ...A0, w, s: 0, e: 0.15 }, { ...B0, w: 1 - w, s: 0.2, e: 0.4 }]);
      mixes.push([{ ...B0, w: 1 - w, s: 0, e: 0.15 }, { ...A0, w, s: 0.2, e: 0.4 }]);
    }
    if (B0 && C0) mixes.push([{ ...A0, w: 0.4 }, { ...B0, w: 0.3 }, { ...C0, w: 0.3 }]);
    for (const w of [0.15, 0.3]) {
      mixes.push([{ u: scr, w, s: 0, e: 0.15 }, { ...A0, w: 1 - w, s: 0.1, e: Math.max(0.2, A0.e) }]); // a screen in front
      mixes.push([{ ...A0, w: 1 - w }, { u: scr, w, s: Math.min(0.9, A0.e + 0.05), e: Math.min(1, A0.e + 0.25) }]); // cheap ones behind
    }
    for (const [g1, g2] of [[[0, 0.08], [0.3, 0.38]], [[0, 0.1], [0.5, 0.6]], [[0, 0.05], [0.15, 0.2]]]) mixes.push([{ ...A0, w: 0.5, s: g1[0], e: g1[1] }, { ...A0, w: 0.5, s: g2[0], e: g2[1] }]); // split into two groups
    mixes.push([{ ...A0, w: 0.34, s: 0, e: 0.06 }, { ...A0, w: 0.33, s: 0.25, e: 0.31 }, { ...A0, w: 0.33, s: 0.5, e: 0.56 }]); // three pulses
    for (const m of mixes) push(evalSpec(m));
    // D: timing nudges on the best army so far (every group earlier, later, tighter, looser)
    let best = bestOf();
    for (let pass = 0; pass < 2; pass++) {
      const b = best.spec, vars = [];
      b.forEach((g, k) => {
        for (const d of [-0.1, 0.1]) vars.push(b.map((x, j) => (j === k ? { ...x, s: Math.max(0, x.s + d), e: Math.min(1, Math.max(Math.max(0, x.s + d) + 0.01, x.e + d)) } : x)));
        for (const f of [0.5, 2]) vars.push(b.map((x, j) => (j === k ? { ...x, e: Math.min(1, x.s + Math.max(0.01, (x.e - x.s) * f)) } : x)));
      });
      if (b.length > 1) for (const dw of [-0.1, 0.1]) vars.push(b.map((x, j) => ({ ...x, w: Math.max(0.05, x.w + (j === 0 ? dw : -dw / (b.length - 1))) })));
      let imp = false;
      for (const v of vars) { const r = push(evalSpec(v)); if (r.Y > best.Y) { best = r; imp = true; } }
      if (!imp) break;
    }
    // E: sabotage on the best army (rounds 2 to the one before last)
    if (ctx.sabo !== false && (ctx.round || 1) > 1 && (ctx.round || 1) < (ctx.rounds || 8)) {
      const tries = ctx.tries || { bridgeTries: 0, koTries: 0 }, bset = new Set(br);
      const picks = I.towerPicks(G, 3, bset), kos = picks.length ? I.capFit(G, picks) : [];
      const bw = I.bridgePicks(G, I.bridgeSpots(G, bset), 1, bset);
      const lists = [];
      if (kos.length) { lists.push(kos.slice(0, 1).map(i => [i, 'tower'])); if (kos.length > 1) lists.push(kos.map(i => [i, 'tower'])); }
      if (bw.length) { lists.push([[bw[0], 'bridge']]); if (kos.length) lists.push([[bw[0], 'bridge'], [kos[0], 'tower']]); }
      const base = best;
      for (const list of lists) for (const t of [0.05, 0.3, 0.6]) {
        const tt = Math.min(1, (base.spec[0].s || 0) + t * Math.max(0.05, base.spec[0].e - base.spec[0].s));
        const ch = priceBridges(G, bset, I.sapPlan(G, bset, list, tt, tries)), cost = [...ch.values()].reduce((v, c) => v + c.cost, 0);
        if (cost >= B * 0.5) continue;
        const r = push(evalSpec(base.spec, ch, cost));
        // sabotage is spent for good, so it has to add more keep damage than its coins would have as units (about breach × cost)
        if (r.Y - cost * (base.Y / Math.max(1, base.X)) > best.Y) best = r;
      }
    }
    // F: the finalists on more seeds
    if (seeds.length > 1) {
      const fin = results.slice().sort((a, b) => b.Y - a.Y).filter((r, k, arr) => arr.findIndex(x => specKey(x.spec) === specKey(r.spec) && x.charges === r.charges) === k).slice(0, 4);
      let fb = null;
      for (const r of fin.concat(best === fin[0] ? [] : [best])) { const rr = evalSpec(r.spec, r.charges, r.sabCost, seeds); if (!fb || rr.Y - r.sabCost * 0 > fb.Y) fb = rr; }
      best = fb;
    }
    return { best, trials, top: results.slice().sort((a, b) => b.Y - a.Y).slice(0, 8) };
  }
  function proAttack(S, opt, rnd) {
    const B = S.aFree + armyValue(S.designs);
    const G = S.round === 1 && !towersOf(S.seenGrid).length ? refGrid(S) : S.seenGrid;
    const res = searchArmy(G, B, { bridges: [...S.bridges], sabo: S.sabo && !opt.noSabo, round: S.round, rounds: S.rounds, tries: { bridgeTries: S.totals.bridgeTries || 0, koTries: S.totals.koTries || 0 }, warm: S.__proBest, rnd, effort: opt.effort || 1, seeds: opt.seeds || [4242 + S.round, 9191 + S.round] });
    const b = res.best;
    const { ds, left } = buildArmy(b.spec, B - b.sabCost);
    S.designs = ds; S.aFree = left; S.charges = b.charges ? new Map(b.charges) : new Map();
    S.__proBest = b.spec;
    return { army: ds.map(d => `${unitShort(d)}x${d.count}@${Math.round(d.tl.s * 20)}-${Math.round(d.tl.e * 20)}s`).join(' '), sab: S.charges.size ? [...S.charges.values()].map(c => c.kind).join('+') : '', trials: res.trials, predY: Math.round(b.Y) };
  }

  // The banker: a token army (one cheap unit) until round opt.from, saving its coins for interest (15% of what's left
  // when a wave starts, at most 150 a wave) and the bigger pot share a failed wave pays, then the advanced attacker.
  function bankAttack(S, opt, rnd) {
    if (S.round < (opt.from || 5)) {
      const B = S.aFree + armyValue(S.designs);
      const d = I.makeDesign('Swarm', 'Token', I.COLORS[2]); Object.assign(d, { hp: 0, speed: 0, armor: 0, regen: 0, resist: 'none' }); d.count = 1; d.tl = { s: 0, e: 0.1, pos: null };
      S.designs = [d]; S.aFree = B - I.unitCost(d); S.charges = new Map();
      return { army: 'token', banked: S.aFree };
    }
    return proAttack(S, opt, rnd);
  }
  const DEF = { pro: proDefend, proA: proDefendAdaptive, am: amDefend, cpu: cpuDefend };
  const ATK = { pro: proAttack, am: amAttack, cpu: cpuAttack, bank: bankAttack };

  // One full match. dOpt.kind: pro | proA | am | cpu; aOpt.kind: pro | am | cpu. rules: RULES overrides, plus
  // { sabotage: false } and { map: 'shot' | 'none' | 'random' } (the pro's layout follows the map: shot → shot, else clean).
  window.proMatch = (dOpt, aOpt, seed, rules = {}) => {
    const map = rules.map || 'shot';
    const S = freshState(rules, map, seed);
    if (dOpt.kind === 'pro' || dOpt.kind === 'proA') dOpt = { layout: map === 'shot' ? 'shot' : 'clean', ...dOpt };
    if ((dOpt.kind === 'pro' || dOpt.kind === 'proA') && map === 'random') throw new Error('the pro layout needs map shot or none');
    const rd = mulberry(seed * 9973 + 11), ra = mulberry(seed * 7919 + 23);
    const log = [];
    for (;;) {
      const t0 = performance.now();
      const dInfo = DEF[dOpt.kind](S, dOpt, rd, seed * 7919 + S.round);
      const t1 = performance.now();
      const aInfo = ATK[aOpt.kind](S, aOpt, ra, seed * 104729 + S.round);
      const t2 = performance.now();
      const dw = defWorth(S), aw = S.aFree + armyValue(S.designs) + [...S.charges.values()].reduce((v, c) => v + c.cost, 0);
      I.startWave(seed * 101 + S.round);
      window.siegeline.advance(900);
      const W = S.wave, row = { r: S.round, dWorth: dw, aWorth: aw, X: W.x, sappers: W.sappers, sapOk: W.sapOk, sapLost: W.sapLost, bridges: W.bridges, d: dInfo, a: aInfo, ms: [Math.round(t1 - t0), Math.round(t2 - t1)] };
      row.dealt = {}; // damage dealt this wave by each tower's role (the pro's), or by its tuning
      for (const i of towersOf(S.grid)) { const g = S.grid[i], k = g.role || cfgShort(g.cfg); row.dealt[k] = Math.round((row.dealt[k] || 0) + (g.dealt || 0)); }
      if (S.over && S.winner === 'attacker') { log.push({ ...row, Y: Math.round(W.y), keep: 0 }); return { winner: 'attacker', round: S.round, keep: 0, keepMax: S.keepMax, log }; }
      const L = S.last;
      log.push({ ...row, Y: Math.round(L.Y), breach: Math.round(L.breach * 100), keep: Math.round(S.keep), dGain: L.dTot, aGain: L.aTot, dInt: L.dInt, aInt: L.aInt });
      if (S.over) return { winner: S.winner, round: S.round, keep: Math.round(S.keep), keepMax: S.keepMax, log };
      S.round++;
    }
  };

  /* ---------------- single-wave studies ---------------- */
  // The pro's (or the amateur's) defense at a given worth on a fresh board, as round `round` would see it.
  window.proDefense = (kind, worth, rules = {}, opt = {}, seed = 1) => {
    const map = rules.map || 'shot';
    const S = freshState(rules, map, seed);
    S.round = opt.round || 2;
    const L = LAYOUTS[map === 'shot' ? 'shot' : 'clean'];
    if (kind === 'pro') { S.dFree = 0; layOut(S, L); S.dFree = worth - (defWorth(S) - S.dFree); const r = proTowers(S, L, opt.W || { dps: 1.5, sf: 1, cp: 1, sp: 0.9 }, opt); applyTowers(S, r.plan, r.left); }
    else if (kind === 'am') { S.dFree = worth - defWorth(S); amDefend(S, { minTowers: 3 }, mulberry(seed * 31 + 7)); }
    else throw new Error('unknown defense ' + kind);
    S.seenGrid = I.cloneGrid(S.grid); S.seenVer++;
    return { worth: defWorth(S), left: S.dFree, towers: towersOf(S.grid).map(i => [cr(i), cfgShort(S.grid[i].cfg), I.towerCost(S.grid[i].cfg)]), route: I.pathLen(S.path), grid: S.grid.map(g => (g ? (g.t === 'tower' ? { t: 'tower', cfg: { ...g.cfg } } : { t: g.t }) : null)) };
  };
  // The best army the search finds against a defense grid (from proDefense) for B coins; plain: one design only.
  window.bestArmy = (grid, B, rules = {}, opt = {}) => {
    const map = rules.map || 'shot';
    const S = freshState(rules, map, 1);
    S.grid = grid.map((g, i) => (g ? (g.t === 'tower' ? { t: 'tower', cfg: { ...I.defaultTower(), ...g.cfg }, fee: 0, off: 0, n: i + 1, fresh: false, cd: 0, ang: Math.PI, kick: 0, dealt: 0 } : { t: g.t, fresh: false }) : null));
    S.seenGrid = I.cloneGrid(S.grid); S.round = opt.round || 3;
    const res = searchArmy(S.seenGrid, B, { bridges: [], sabo: opt.sabo === true && S.sabo, round: S.round, rounds: 8, tries: { bridgeTries: 0, koTries: 0 }, rnd: mulberry(opt.seed || 5), effort: opt.effort || 2, seeds: opt.seeds || [4242, 9191, 1234] });
    const fmt = r => ({ Y: Math.round(r.Y), breach: r.X ? Math.round(r.Y / r.X * 100) : 0, army: r.spec.map(g => `${unitShort(g.u)} ${Math.round(g.w * 100)}% @${Math.round(g.s * 20)}-${Math.round(g.e * 20)}s`).join(' + '), sab: r.charges ? [...r.charges.values()].map(c => c.kind).join('+') : '' });
    return { best: fmt(res.best), trials: res.trials, top: res.top.map(fmt) };
  };
  // An amateur's army against a defense grid: n random armies for B coins, their mean keep damage and breach.
  window.amArmies = (grid, B, rules = {}, n = 20, seed = 3) => {
    const map = rules.map || 'shot';
    const S = freshState(rules, map, 1);
    S.grid = grid.map((g, i) => (g ? (g.t === 'tower' ? { t: 'tower', cfg: { ...I.defaultTower(), ...g.cfg }, fee: 0, off: 0, n: i + 1, fresh: false, cd: 0, ang: Math.PI, kick: 0, dealt: 0 } : { t: g.t, fresh: false }) : null));
    S.seenGrid = I.cloneGrid(S.grid); S.round = 3;
    const rnd = mulberry(seed); let Y = 0, X = 0;
    for (let k = 0; k < n; k++) {
      S.__amSpec = null; S.designs = []; S.aFree = B; S.charges = new Map();
      amAttack(S, { saboRate: 0 }, rnd);
      const r = I.trial(S.grid, S.designs, [], 4242 + k, []);
      Y += r.Y; X += r.X;
    }
    return { Y: Math.round(Y / n), breach: X ? Math.round(Y / X * 100) : 0 };
  };
  // A zero-sum table for the matrix-game study: the pro's candidate defenses at worth D (role weightings × fire-rate plans ×
  // splash caps) against armies for B coins (every defense's best answers from the search, plus archetypes). Returns keep
  // damage Y[d][a]; tools/sim/pro.py solves it for both sides' best mixed strategies.
  window.matrixGame = (D, B, rules = {}, opt = {}) => {
    const map = rules.map || 'shot';
    const S = freshState(rules, map, 1);
    S.round = opt.round || 3;
    const L = LAYOUTS[map === 'shot' ? 'shot' : 'clean'];
    S.dFree = 0; layOut(S, L); S.dFree = D - (defWorth(S) - S.dFree);
    const Ws = [
      { dps: 1.5, sf: 1, cp: 1, sp: 0.9 }, { dps: 2.5, sf: 0.8, cp: 0.8, sp: 0.7 },
      { dps: 1, sf: 1.6, cp: 1, sp: 1.3 }, { dps: 1, sf: 1, cp: 1.8, sp: 0.8 },
    ];
    const snapG = S.grid.slice(), snapF = S.dFree, snapSeq = S.towerSeq, defs = [];
    for (let wi = 0; wi < Ws.length; wi++) for (const [rm, arm] of [['base', 0], ['armor', 6], ['armor', 10]]) for (const ms of [2, 3]) {
      S.grid = snapG.slice(); S.dFree = snapF; S.towerSeq = snapSeq;
      const { plan, left } = proTowers(S, L, Ws[wi], { rateMode: rm, armor: arm, maxSplash: ms, ...(opt.dopt || {}) });
      const G = S.grid.slice();
      for (const p of plan) G[p.i] = { t: 'tower', cfg: { ...I.defaultTower(), ...p.cfg }, fee: p.fee, off: 0, n: 900 + plan.indexOf(p), fresh: false, cd: 0, ang: Math.PI, kick: 0, dealt: 0 };
      const name = `W${wi}${rm === 'base' ? 'b' : 'a' + arm}s${ms}`, key = plan.map(p => p.i + cfgShort(p.cfg)).join('|');
      if (!defs.some(d => d.key === key)) defs.push({ name, key, G, towers: plan.map(p => p.role + ':' + cfgShort(p.cfg)).join(' '), left });
    }
    S.grid = snapG; S.dFree = snapF;
    // armies: each defense's best answers, plus the archetypes bunched
    const armies = new Map();
    const add = spec => { const k = specKey(spec); if (!armies.has(k)) armies.set(k, spec); };
    for (const u of ARCH) add([{ u, w: 1, s: 0, e: 0.1 }]);
    defs.forEach((d, k) => {
      const r = searchArmy(d.G, B, { bridges: [], sabo: false, round: S.round, rounds: 8, rnd: mulberry(97 * k + 5), effort: opt.effort || 1, seeds: [4242] });
      add(r.best.spec);
      for (const t of r.top.slice(0, opt.topK ?? 3)) add(t.spec);
    });
    const specs = [...armies.values()], seeds = opt.seeds || [31337, 27182];
    const Y = defs.map(d => specs.map(spec => { const { ds } = buildArmy(spec, B); let y = 0; for (const sd of seeds) y += I.trial(d.G, ds, [], sd, []).Y; return Math.round(y / seeds.length); }));
    const fmtA = spec => spec.map(g => `${unitShort(g.u)} ${Math.round(g.w * 100)}% @${Math.round(g.s * 20)}-${Math.round(g.e * 20)}s`).join(' + ');
    return { defs: defs.map(d => ({ name: d.name, towers: d.towers, left: d.left })), armies: specs.map(fmtA), Y, X: specs.map(spec => armyValue(buildArmy(spec, B).ds)) };
  };
  window.proLayoutInfo = (map = 'shot') => {
    const S = freshState({ noStarter: true }, map, 1);
    const L = LAYOUTS[map === 'shot' ? 'shot' : 'clean'];
    S.dFree = 1000; layOut(S, L);
    const route = routeOf(S.grid, S.bridges);
    return { route: route.map(cr), len: I.pathLen(S.path), extras: extraSlots(S, L).map(cr), cover: L.roles.map(([role, [c, r]]) => [role, coverOf(at(c, r), { ...ROLE[role].base }, new Set(route))]) };
  };
})();
