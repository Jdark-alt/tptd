/* v31 item 3: three families of abstract unit shapes, eight each (one per speed step, 0.7 to 2.8 cells/s), for the
   user to pick from before one is wired into the game. Shape is speed only; size is health (the game's unitRadius);
   colour is the army colour. Every shape faces +x and has a clear front. Motion cues come from the speed step, so the
   change between steps is gradual: a trail that lengthens, hover height (the shadow's offset), a pulse that quickens.
   Armour, regeneration and resists are drawn the same way on every shape and size: steel brackets on a ring round the
   unit (the front, then the sides, then all round), a pulsing green cross at its heart, motes circling it.
   Loaded into tools/art/sheet.py's page only; nothing here is in the game. */
(() => {
  const TAU = Math.PI * 2;
  const hex = h => { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
  const mix = (h, to, k) => { const a = hex(h), b = hex(to); return '#' + a.map((v, i) => Math.round(v + (b[i] - v) * k).toString(16).padStart(2, '0')).join(''); };
  const lit = (h, k) => mix(h, '#ffffff', k), dark = (h, k) => mix(h, '#000000', k), rgb = h => hex(h).join(',');
  function glow(c, x, y, r, rgbS, a) {
    if (r <= 0 || a <= 0) return;
    const g = c.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, `rgba(${rgbS},${a})`); g.addColorStop(0.35, `rgba(${rgbS},${a * 0.45})`); g.addColorStop(1, `rgba(${rgbS},0)`);
    c.save(); c.globalCompositeOperation = 'lighter'; c.fillStyle = g; c.fillRect(x - r, y - r, 2 * r, 2 * r); c.restore();
  }
  const poly = (c, P) => { c.moveTo(P[0][0], P[0][1]); for (let k = 1; k < P.length; k++) c.lineTo(P[k][0], P[k][1]); c.closePath(); };
  const sc = (P, R, dx = 0, dy = 0, s = 1) => P.map(([x, y]) => [(x * s + dx) * R, (y * s + dy) * R]);
  const F = s => s / 7; // 0 at the slowest step, 1 at the fastest
  // A streak of light behind the unit (additive): from x0 back to x0 - L, w wide, fading out.
  function streak(c, x0, y, L, w, col, a) {
    if (L <= 0) return;
    const g = c.createLinearGradient(x0, 0, x0 - L, 0); g.addColorStop(0, `rgba(${rgb(col)},${a})`); g.addColorStop(1, `rgba(${rgb(col)},0)`);
    c.save(); c.globalCompositeOperation = 'lighter'; c.fillStyle = g;
    c.beginPath(); c.moveTo(x0, y - w / 2); c.lineTo(x0 - L, y - w * 0.1); c.lineTo(x0 - L, y + w * 0.1); c.lineTo(x0, y + w / 2); c.closePath(); c.fill(); c.restore();
  }
  // a solid piece: lit from the top left (the turned sprite would bake this per heading), a luminous rim
  function piece(c, R, col, path, px, rim = 1) {
    c.beginPath(); path(); const g = c.createLinearGradient(-R, -R, R, R); g.addColorStop(0, lit(col, 0.32)); g.addColorStop(0.55, col); g.addColorStop(1, dark(col, 0.5));
    c.fillStyle = g; c.fill(); c.lineWidth = Math.max(px * 1.1, R * 0.055) * rim; c.strokeStyle = lit(col, 0.6); c.lineJoin = 'round'; c.stroke();
  }
  const ink = (c, R, col, px) => { c.lineWidth = Math.max(px * 0.9, R * 0.035); c.strokeStyle = dark(col, 0.62); };

  /* ---------- A. Sharpening: a solid slab when slow, stretching to a needle when fast ---------- */
  const SH = [
    R => sc([[0.82, -0.95], [0.95, -0.82], [0.95, 0.82], [0.82, 0.95], [-0.86, 0.95], [-0.98, 0.83], [-0.98, -0.83], [-0.86, -0.95]], R), // monolith
    R => [0, 1, 2, 3, 4, 5].map(k => [Math.cos(k * TAU / 6) * 1.1 * R, Math.sin(k * TAU / 6) * 1.0 * R]), // hexagon, a corner forward
    null, // orb
    null, // teardrop
    R => sc([[1.25, 0], [-0.62, -1.0], [-0.22, 0], [-0.62, 1.0]], R), // chevron
    R => sc([[1.5, 0], [-0.72, -0.64], [-0.44, 0], [-0.72, 0.64]], R), // dart
    null, // split blade
    R => sc([[1.9, 0], [-0.9, -0.26], [-0.72, 0], [-0.9, 0.26]], R), // needle
  ];
  const tear = (c, R) => { c.moveTo(1.35 * R, 0); c.arc(-0.18 * R, 0, 0.82 * R, 0.62, TAU - 0.62); c.closePath(); };
  const blades = R => [sc([[1.6, -0.06], [-0.85, -0.66], [-0.58, -0.16]], R), sc([[1.6, 0.06], [-0.85, 0.66], [-0.58, 0.16]], R)];
  function shPath(c, s, R) {
    if (s === 2) c.arc(0, 0, 0.98 * R, 0, TAU);
    else if (s === 3) tear(c, R);
    else if (s === 6) for (const P of blades(R)) poly(c, P);
    else poly(c, SH[s](R));
  }
  function sharpen(c, s, R, col, t, px) {
    const f = F(s);
    // motion: a fading afterimage for the middle steps, a comet tail for the fastest
    if (s >= 3) streak(c, -0.4 * R, 0, R * (0.6 + 4.2 * f * f), R * (1.3 - 0.8 * f), col, 0.22 + 0.25 * f);
    if (s === 7) streak(c, -0.7 * R, 0, R * 5.5, R * 0.34, '#fff4e0', 0.6);
    piece(c, R, col, () => shPath(c, s, R), px);
    ink(c, R, col, px); c.beginPath();
    if (s === 0) { for (const y of [-0.42, 0, 0.42]) { c.moveTo(-0.78 * R, y * R); c.lineTo(0.55 * R, y * R); } c.stroke();
      const p = 0.55 + 0.45 * Math.sin(t * 1.2); c.fillStyle = `rgba(255,248,230,${0.6 + 0.4 * p})`; c.fillRect(0.7 * R, -0.66 * R, 0.13 * R, 1.32 * R); glow(c, 0.76 * R, 0, R * 0.9, '255,230,190', 0.25 * p); }
    else if (s === 1) { const P = [0, 1, 2, 3, 4, 5].map(k => [Math.cos(k * TAU / 6) * 0.58 * R, Math.sin(k * TAU / 6) * 0.53 * R]); poly(c, P); c.stroke(); dot(c, 0.86 * R, 0, R * 0.13, t, 1.6); }
    else if (s === 2) { c.arc(0, 0, 0.6 * R, 0, TAU); c.stroke(); c.beginPath(); c.arc(0, 0, 0.8 * R, -0.5, 0.5); c.lineWidth = R * 0.14; c.strokeStyle = 'rgba(255,248,230,0.9)'; c.stroke(); glow(c, 0.8 * R, 0, R * 0.7, '255,230,190', 0.3); }
    else if (s === 3) { c.moveTo(1.05 * R, 0); c.lineTo(-0.5 * R, 0); c.stroke(); dot(c, 1.02 * R, 0, R * 0.12, t, 2.4); }
    else if (s === 4 || s === 5) { c.moveTo((s === 4 ? 1.0 : 1.25) * R, 0); c.lineTo((s === 4 ? -0.15 : -0.36) * R, 0); c.stroke(); dot(c, (s === 4 ? 0.95 : 1.2) * R, 0, R * 0.11, t, 3.2); }
    else if (s === 6) { c.moveTo(1.45 * R, 0); c.lineTo(-0.85 * R, 0); c.lineWidth = R * 0.08; c.strokeStyle = 'rgba(255,248,230,0.85)'; c.stroke(); glow(c, 0.4 * R, 0, R * 1.2, rgb(col), 0.35); }
    else { dot(c, 1.6 * R, 0, R * 0.1, t, 6); }
  }
  // a front light: blinking a little faster the faster the unit
  function dot(c, x, y, r, t, hz) { const p = 0.6 + 0.4 * Math.sin(t * hz * 2); c.beginPath(); c.arc(x, y, r, 0, TAU); c.fillStyle = `rgba(255,250,235,${0.7 + 0.3 * p})`; c.fill(); glow(c, x, y, r * 4, '255,236,200', 0.3 * p); }

  /* ---------- B. Fragmenting: one dense whole when slow; speed pulls it into more shards in tight formation ---------- */
  const kite = (x, y, k, slim = 0.45) => [[x + k, y], [x - 0.5 * k, y - slim * k], [x - 0.22 * k, y], [x - 0.5 * k, y + slim * k]];
  const FR = [
    () => [[[0.8, -0.95], [0.95, -0.8], [0.95, 0.8], [0.8, 0.95], [-0.95, 0.95], [-0.95, -0.95]]], // one block
    () => [[[0.82, -0.95], [0.95, -0.82], [0.95, -0.05], [-0.95, -0.05], [-0.95, -0.95]], [[0.95, 0.05], [0.95, 0.82], [0.82, 0.95], [-0.95, 0.95], [-0.95, 0.05]]], // cracked in two
    () => [[[1.1, 0], [0.3, -0.85], [0.3, 0.85]], [[0.18, -0.95], [-0.95, -0.95], [-0.95, -0.08], [0.18, -0.08]], [[0.18, 0.08], [-0.95, 0.08], [-0.95, 0.95], [0.18, 0.95]]], // a wedge and two plates
    () => [kite(0.55, 0, 0.75, 0.55), kite(-0.3, -0.62, 0.7, 0.5), kite(-0.3, 0.62, 0.7, 0.5), kite(-0.95, 0, 0.6, 0.5)],
    () => [kite(0.8, 0, 0.62), kite(0.1, -0.56, 0.6), kite(0.1, 0.56, 0.6), kite(-0.6, -1.02, 0.55), kite(-0.6, 1.02, 0.55)],
    () => [kite(0.98, 0, 0.55, 0.4), kite(0.38, -0.44, 0.52, 0.4), kite(0.38, 0.44, 0.52, 0.4), kite(-0.24, -0.86, 0.5, 0.4), kite(-0.24, 0.86, 0.5, 0.4), kite(-0.78, 0, 0.5, 0.4)],
    () => [kite(1.2, 0, 0.5, 0.32), kite(0.6, -0.33, 0.47, 0.32), kite(0.6, 0.33, 0.47, 0.32), kite(0, -0.66, 0.45, 0.32), kite(0, 0.66, 0.45, 0.32), kite(-0.62, -0.98, 0.43, 0.32), kite(-0.62, 0.98, 0.43, 0.32)],
    () => [kite(1.42, 0, 0.5, 0.2), kite(0.86, -0.25, 0.46, 0.2), kite(0.86, 0.25, 0.46, 0.2), kite(0.3, -0.5, 0.44, 0.2), kite(0.3, 0.5, 0.44, 0.2), kite(-0.26, -0.75, 0.42, 0.2), kite(-0.26, 0.75, 0.42, 0.2), kite(-0.82, -1.0, 0.4, 0.2), kite(-0.82, 1.0, 0.4, 0.2)],
  ];
  function frPath(c, s, R) { for (const P of FR[s]()) poly(c, sc(P, R)); }
  function fragment(c, s, R, col, t, px) {
    const f = F(s), parts = FR[s]();
    // each shard trails its own short streak once the body has broken up
    if (s >= 3) for (const P of parts) streak(c, (P[3][0] + 0.1) * R, P[0][1] * R, R * (0.4 + 2.2 * f), R * 0.32 * (1.2 - f * 0.6), col, 0.16 + 0.2 * f);
    // the field that holds it together: hairlines from the heart to every shard, fainter as it pulls apart
    if (s >= 2) { c.beginPath(); for (const P of parts) { c.moveTo(-0.15 * R, 0); c.lineTo(P[0][0] * R * 0.85, P[0][1] * R); } c.lineWidth = Math.max(px * 0.8, R * 0.025); c.strokeStyle = `rgba(${rgb(lit(col, 0.5))},${0.35 - 0.2 * f})`; c.stroke(); }
    for (const P of parts) piece(c, R, col, () => poly(c, sc(P, R)), px, s >= 5 ? 0.8 : 1);
    if (s <= 1) { // the whole: a seam of light down its front
      const p = 0.55 + 0.45 * Math.sin(t * 1.4);
      c.fillStyle = `rgba(255,248,230,${0.55 + 0.45 * p})`; c.fillRect(0.74 * R, -0.62 * R, 0.12 * R, 1.24 * R); glow(c, 0.8 * R, 0, R * 0.9, '255,230,190', 0.25 * p);
      ink(c, R, col, px); c.beginPath(); c.moveTo(-0.7 * R, -0.5 * R); c.lineTo(0.5 * R, -0.5 * R); c.moveTo(-0.7 * R, 0.5 * R); c.lineTo(0.5 * R, 0.5 * R); c.stroke();
    } else { // the heart, glowing between the pieces
      const p = 0.6 + 0.4 * Math.sin(t * (2 + 5 * f));
      c.beginPath(); c.arc(-0.15 * R, 0, R * 0.13, 0, TAU); c.fillStyle = `rgba(255,248,230,${0.6 + 0.4 * p})`; c.fill(); glow(c, -0.15 * R, 0, R * 0.8, rgb(col), 0.35 * p);
      dot(c, parts[0][0][0] * R - 0.05 * R, 0, R * 0.08, t, 2 + 4 * f);
    }
  }

  /* ---------- C. Energy: heavy rings and stacked plates when slow, a bright core trailing light when fast ---------- */
  function enPath(c, s, R) { const r = [1, 0.95, 0.9, 0.9, 0.95, 0.75, 0.55, 0.42][s] * R; c.arc(0, 0, r, 0, TAU); }
  function energy(c, s, R, col, t, px) {
    const f = F(s), pulse = 0.55 + 0.45 * Math.sin(t * (0.9 + 7 * f * f)), C = rgb(col), hot = '#fff6e6';
    const ring = (r, w, a0 = 0, a1 = TAU, alpha = 1, colr = col) => { c.beginPath(); c.arc(0, 0, r, a0, a1); c.lineWidth = w; c.strokeStyle = colr; c.globalAlpha = alpha; c.stroke(); c.globalAlpha = 1; };
    const core = (r, a) => { const g = c.createRadialGradient(-r * 0.25, -r * 0.25, r * 0.05, 0, 0, r); g.addColorStop(0, hot); g.addColorStop(0.45, lit(col, 0.45)); g.addColorStop(1, dark(col, 0.2)); c.beginPath(); c.arc(0, 0, r, 0, TAU); c.fillStyle = g; c.fill(); glow(c, 0, 0, r * 3.2, C, a); };
    if (s <= 2) { // stacked plates: thick rings, each a little up and left of the one under it, a slow pulse
      const n = 3 - s, rs = [[0.95, 0.66, 0.38], [0.92, 0.55], [0.86]][s];
      c.beginPath(); c.arc(0.04 * R, 0.05 * R, 1.02 * R, 0, TAU); c.fillStyle = dark(col, 0.72); c.fill();
      rs.forEach((r, k) => { c.save(); c.translate(-0.03 * R * k, -0.03 * R * k); ring(r * R, R * (0.2 - 0.03 * s), 0, TAU, 1, dark(col, 0.25 - 0.05 * k)); ring(r * R, R * 0.05, Math.PI * 1.05, Math.PI * 1.6, 0.9, lit(col, 0.45)); c.restore(); });
      core(R * [0.16, 0.24, 0.34][s], 0.15 + 0.25 * pulse);
      ring(rs[0] * R, R * 0.17, -0.5, 0.5, 0.85 + 0.15 * pulse, hot); // the front: a lit arc and a light beyond it
      c.beginPath(); c.arc((rs[0] + 0.3) * R, 0, R * 0.1, 0, TAU); c.fillStyle = hot; c.fill();
      glow(c, rs[0] * R, 0, R * 0.9, '255,236,210', 0.3 * pulse);
      void n;
    } else if (s === 3) { // a core in a ring open at the back
      ring(0.88 * R, R * 0.14, -2.35, 2.35, 1, col); ring(0.88 * R, R * 0.05, -2.35, -1.3, 0.9, lit(col, 0.5));
      core(R * 0.42, 0.3 + 0.2 * pulse); ring(0.88 * R, R * 0.1, -0.35, 0.35, 0.9, hot);
    } else { // a bright core trailing light, a shield of light before it
      const cr = [0, 0, 0, 0, 0.42, 0.36, 0.32, 0.28][s] * R;
      streak(c, -cr * 0.4, 0, R * [0, 0, 0, 0, 1.4, 2.4, 3.6, 5.2][s], cr * 2.1, col, 0.55);
      streak(c, -cr * 0.4, 0, R * [0, 0, 0, 0, 0.9, 1.6, 2.6, 4.2][s], cr * 0.9, '#fff2dc', 0.6);
      if (s >= 6) for (const y of [-0.45, 0.45]) streak(c, -cr * 0.2, y * R, R * (s === 6 ? 2.0 : 2.8), cr * 0.35, col, 0.4);
      if (s === 5) for (const sg of [-1, 1]) ring(0.78 * R, R * 0.09, sg * 0.9, sg * 1.9, 0.9, lit(col, 0.2));
      ring(cr * 1.75, R * 0.1, -1.0, 1.0, 0.95, lit(col, 0.35)); // the shield before it
      core(cr, 0.45 + 0.25 * pulse);
      if (s >= 6) { const rnd = k => (Math.sin(k * 91.7 + t * 3) * 43758.5) % 1; for (let k = 0; k < (s === 6 ? 5 : 8); k++) { const x = -cr - Math.abs(rnd(k)) * R * (s === 6 ? 2.2 : 3.4), y = (rnd(k + 9)) * R * 0.5; c.beginPath(); c.arc(x, y, R * 0.045, 0, TAU); c.fillStyle = `rgba(255,240,215,${0.4 + 0.4 * Math.abs(rnd(k + 3))})`; c.fill(); } }
    }
  }

  /* ---------- D. Combined (round 2, the user: "for slower units, take inspiration from energy; for mid-speed units,
     from sharpening; for high-speed units, a fragmented style … sophisticated, sharp, a trail behind them … the health
     difference has to do justice in the size … not boxy"): one family whose every member has the same glowing core
     and luminous rim, wrapped in heavy stacked plates when slow (each slow step its own outline: three lobes, an orb
     behind a crescent shield, a pointed lens), a sleek hull at mid speed (a teardrop, a broad arrowhead, a swept dart),
     and blades split apart by lines of light when fast, trailing jet streaks. The fast shapes are as wide as the slow
     ones and longer, so a 900 HP fast unit is the biggest thing on the board. ---------- */
  const CB_DART = [[1.55, 0], [0.2, -0.32], [-0.55, -0.98], [-0.38, -0.32], [-0.78, -0.2], [-0.78, 0.2], [-0.38, 0.32], [-0.55, 0.98], [0.2, 0.32]];
  const CB_SPLIT = [[[1.75, 0], [0.15, -0.21], [-0.82, -0.12], [-0.82, 0.12], [0.15, 0.21]],
    [[0.95, -0.34], [-0.38, -1.06], [-0.8, -0.96], [-0.12, -0.33]], [[0.95, 0.34], [-0.38, 1.06], [-0.8, 0.96], [-0.12, 0.33]]];
  const CB_TALON = [[[1.95, 0], [0.32, -0.17], [-0.92, -0.1], [-0.92, 0.1], [0.32, 0.17]],
    [[1.1, -0.29], [-0.2, -0.6], [-0.68, -0.54], [0.06, -0.25]], [[1.1, 0.29], [-0.2, 0.6], [-0.68, 0.54], [0.06, 0.25]],
    [[0.38, -0.7], [-0.72, -1.1], [-1.02, -0.97], [-0.46, -0.66]], [[0.38, 0.7], [-0.72, 1.1], [-1.02, 0.97], [-0.46, 0.66]]];
  const TRI = [0, 2.094, -2.094];
  const lens = (c, R, k = 1, dx = 0, dy = 0) => { c.moveTo((1.15 * k + dx) * R, dy * R); c.quadraticCurveTo((0.1 * k + dx) * R, (-1.72 * k + dy) * R, (-1.0 * k + dx) * R, dy * R); c.quadraticCurveTo((0.1 * k + dx) * R, (1.72 * k + dy) * R, (1.15 * k + dx) * R, dy * R); c.closePath(); };
  const crescent = (c, R) => { c.arc(0, 0, 1.0 * R, -1.95, 1.95); c.arc(0.16 * R, 0, 0.78 * R, 1.75, -1.75, true); c.closePath(); };
  function cbPath(c, s, R) {
    if (s === 0) { for (const a of TRI) { c.moveTo(Math.cos(a) * 0.42 * R + 0.6 * R, Math.sin(a) * 0.42 * R); c.arc(Math.cos(a) * 0.42 * R, Math.sin(a) * 0.42 * R, 0.6 * R, 0, TAU); } c.moveTo(0.5 * R, 0); c.arc(0, 0, 0.5 * R, 0, TAU); }
    else if (s === 1) { c.moveTo(0.6 * R, 0); c.arc(-0.12 * R, 0, 0.72 * R, 0, TAU); crescent(c, R); }
    else if (s === 2) lens(c, R);
    else if (s === 3) tear(c, R);
    else if (s === 4) poly(c, sc([[1.3, 0], [-0.62, -1.02], [-0.26, 0], [-0.62, 1.02]], R));
    else if (s === 5) poly(c, sc(CB_DART, R));
    else for (const P of s === 6 ? CB_SPLIT : CB_TALON) poly(c, sc(P, R));
  }
  // the heart every member shares: a warm core, pulsing slowly when slow and quickly when fast
  function cbCore(c, x, r, col, t, f) {
    const p = 0.6 + 0.4 * Math.sin(t * (0.9 + 7 * f * f)), g = c.createRadialGradient(x - r * 0.25, -r * 0.25, r * 0.05, x, 0, r);
    g.addColorStop(0, '#fff7ea'); g.addColorStop(0.5, lit(col, 0.45)); g.addColorStop(1, dark(col, 0.15));
    c.beginPath(); c.arc(x, 0, r, 0, TAU); c.fillStyle = g; c.fill(); glow(c, x, 0, r * (2.6 + p), rgb(col), 0.28 + 0.22 * p);
    return p;
  }
  // a lit seam: a line of light along a hull or between blades
  const seam = (c, pts, w, a) => { c.save(); c.globalCompositeOperation = 'lighter'; c.beginPath(); c.moveTo(pts[0][0], pts[0][1]); for (const q of pts.slice(1)) c.lineTo(q[0], q[1]); c.lineWidth = w; c.lineCap = 'round'; c.strokeStyle = `rgba(255,236,205,${a})`; c.stroke(); c.restore(); };
  function combined(c, s, R, col, t, px) {
    const f = F(s), hot = '#fff6e6';
    if (s === 0) { // three heavy lobes stacked round the core; the forward one lit
      for (const a of [TRI[1], TRI[2], TRI[0]]) {
        const x = Math.cos(a) * 0.42 * R, y = Math.sin(a) * 0.42 * R;
        piece(c, R, col, () => c.arc(x, y, 0.6 * R, 0, TAU), px);
        ink(c, R, col, px); c.beginPath(); c.arc(x - 0.04 * R, y - 0.04 * R, 0.38 * R, 0, TAU); c.stroke();
      }
      piece(c, R, dark(col, 0.35), () => c.arc(0, 0, 0.5 * R, 0, TAU), px, 0.8);
      const p = cbCore(c, 0, 0.3 * R, col, t, f);
      c.beginPath(); c.arc(0.42 * R, 0, 0.6 * R, -0.55, 0.55); c.lineWidth = R * 0.13; c.strokeStyle = hot; c.globalAlpha = 0.75 + 0.25 * p; c.stroke(); c.globalAlpha = 1;
      glow(c, 1.0 * R, 0, R * 0.8, '255,236,210', 0.22 * p);
    } else if (s === 1) { // an orb behind a crescent shield
      piece(c, R, dark(col, 0.2), () => c.arc(-0.12 * R, 0, 0.72 * R, 0, TAU), px);
      ink(c, R, col, px); c.beginPath(); c.arc(-0.16 * R, -0.04 * R, 0.5 * R, 0, TAU); c.stroke();
      const p = cbCore(c, -0.12 * R, 0.32 * R, col, t, f);
      piece(c, R, col, () => crescent(c, R), px);
      c.beginPath(); c.arc(0, 0, 0.93 * R, -0.6, 0.6); c.lineWidth = R * 0.1; c.strokeStyle = hot; c.globalAlpha = 0.7 + 0.3 * p; c.stroke(); c.globalAlpha = 1;
      ink(c, R, col, px); c.beginPath(); for (const a of [-1.2, 1.2]) { c.moveTo(Math.cos(a) * 0.82 * R, Math.sin(a) * 0.82 * R); c.lineTo(Math.cos(a) * 0.98 * R, Math.sin(a) * 0.98 * R); } c.stroke();
    } else if (s === 2) { // a pointed lens, two plates stacked
      piece(c, R, col, () => lens(c, R), px);
      piece(c, R, dark(col, 0.25), () => lens(c, R, 0.62, -0.06, -0.03), px, 0.8);
      cbCore(c, -0.05 * R, 0.27 * R, col, t, f);
      seam(c, [[0.3 * R, 0], [1.05 * R, 0]], R * 0.07, 0.8);
      ink(c, R, col, px); c.beginPath(); for (const sg of [-1, 1]) { c.moveTo(-0.55 * R, sg * 0.45 * R); c.lineTo(-0.15 * R, sg * 0.62 * R); } c.stroke();
    } else if (s === 3) { // a teardrop with a lit seam to its point
      streak(c, -0.85 * R, 0, R * 1.2, R * 1.2, col, 0.2);
      piece(c, R, col, () => tear(c, R), px);
      ink(c, R, col, px); c.beginPath(); c.moveTo(1.0 * R, 0); c.arc(-0.18 * R, 0, 0.55 * R, 0.72, TAU - 0.72); c.closePath(); c.stroke();
      cbCore(c, -0.2 * R, 0.25 * R, col, t, f);
      seam(c, [[0.1 * R, 0], [1.25 * R, 0]], R * 0.07, 0.85);
    } else if (s === 4) { // a broad arrowhead: lit spine, two engines
      for (const sg of [-1, 1]) streak(c, -0.3 * R, sg * 0.32 * R, R * 1.8, R * 0.32, col, 0.35);
      piece(c, R, col, () => poly(c, sc([[1.3, 0], [-0.62, -1.02], [-0.26, 0], [-0.62, 1.02]], R)), px);
      ink(c, R, col, px); c.beginPath(); poly(c, sc([[0.8, 0], [-0.3, -0.58], [-0.08, 0], [-0.3, 0.58]], R)); c.stroke();
      cbCore(c, 0.12 * R, 0.22 * R, col, t, f);
      seam(c, [[0.3 * R, 0], [1.15 * R, 0]], R * 0.06, 0.9);
    } else if (s === 5) { // a swept dart: panel lines, twin engines, a longer trail
      for (const sg of [-1, 1]) streak(c, -0.72 * R, sg * 0.16 * R, R * 2.6, R * 0.3, col, 0.45);
      streak(c, -0.72 * R, 0, R * 1.8, R * 0.18, '#fff2dc', 0.5);
      piece(c, R, col, () => poly(c, sc(CB_DART, R)), px);
      ink(c, R, col, px); c.beginPath(); for (const sg of [-1, 1]) { c.moveTo(0.2 * R, sg * 0.32 * R); c.lineTo(-0.38 * R, sg * 0.32 * R); c.moveTo(-0.1 * R, sg * 0.42 * R); c.lineTo(-0.48 * R, sg * 0.8 * R); } c.stroke();
      cbCore(c, 0.05 * R, 0.2 * R, col, t, f);
      seam(c, [[0.35 * R, 0], [1.4 * R, 0]], R * 0.055, 0.9);
    } else { // fast: blades split apart by lines of light, each trailing a jet streak
      const B = s === 6 ? CB_SPLIT : CB_TALON, L = s === 6 ? 3.2 : 4.4;
      for (const P of B) { const tail = P.reduce((m, q) => (q[0] < m[0] ? q : m), P[0]), w = Math.max(...P.map(q => Math.abs(q[1]))) - Math.min(...P.map(q => Math.abs(q[1]))); streak(c, tail[0] * R, (P[0][1] + tail[1]) / 2 * R, R * L * (P === B[0] ? 1 : 0.8), R * Math.max(0.2, w * 0.7), col, 0.42); }
      streak(c, -0.9 * R, 0, R * L * 1.1, R * 0.16, '#fff2dc', 0.6);
      for (const P of B) piece(c, R, col, () => poly(c, sc(P, R)), px, 0.9);
      // the lines of light between the blades, and hairlines from the heart to each
      seam(c, [[1.55 * R, 0], [-0.7 * R, 0]], R * 0.045, 0.85);
      for (const P of B.slice(1)) seam(c, [[P[0][0] * R, P[0][1] * R], [P[3][0] * R, P[3][1] * R]], R * 0.05, 0.75);
      c.beginPath(); for (const P of B.slice(1)) { c.moveTo(0.05 * R, 0); c.lineTo(P[3][0] * R, P[3][1] * R); } c.lineWidth = Math.max(px * 0.8, R * 0.02); c.strokeStyle = `rgba(${rgb(lit(col, 0.5))},0.45)`; c.stroke();
      ink(c, R, col, px); c.beginPath(); for (const P of B) { const m = [(P[0][0] + P[2][0]) / 2, (P[0][1] + P[2][1]) / 2]; c.moveTo(P[0][0] * R * 0.9 + m[0] * R * 0.1, P[0][1] * R); c.lineTo(m[0] * R, m[1] * R); } c.stroke();
      cbCore(c, 0.05 * R, 0.19 * R, col, t, f);
      glow(c, (s === 6 ? 1.75 : 1.95) * R, 0, R * 0.7, '255,240,220', 0.35);
    }
  }
  // Resists as a shield: a glowing plate in each resist's colour, orbiting the unit outside its armour.
  function shieldPlates(c, res, R, t, px) {
    const n = res.length; if (!n) return;
    const r = R * 1.5 + 0.05, w = Math.max(R * 0.18, 0.045), span = Math.min(1.5, TAU / n - 0.32);
    res.forEach((k, j) => {
      const a = t * 0.55 + j * TAU / n, a0 = a - span / 2, a1 = a + span / 2, d = span * 0.16, colH = RES_COL[k];
      c.beginPath(); c.moveTo(Math.cos(a0) * (r + w / 2), Math.sin(a0) * (r + w / 2)); c.arc(0, 0, r + w, a0 + d, a1 - d);
      c.lineTo(Math.cos(a1) * (r + w / 2), Math.sin(a1) * (r + w / 2)); c.arc(0, 0, r, a1 - d, a0 + d, true); c.closePath();
      const g = c.createRadialGradient(0, 0, r - w, 0, 0, r + w * 1.4); g.addColorStop(0, `rgba(${rgb(colH)},0.15)`); g.addColorStop(0.6, `rgba(${rgb(colH)},0.95)`); g.addColorStop(1, lit(colH, 0.5));
      c.fillStyle = g; c.fill(); c.lineWidth = Math.max(px * 0.8, 0.008); c.strokeStyle = 'rgba(5,8,12,0.8)'; c.stroke();
      c.beginPath(); c.arc(0, 0, r + w * 0.82, a0 + d * 1.6, a1 - d * 1.6); c.lineWidth = Math.max(px, w * 0.18); c.strokeStyle = 'rgba(255,255,255,0.75)'; c.stroke();
      glow(c, Math.cos(a) * (r + w / 2), Math.sin(a) * (r + w / 2), w * 4.5, rgb(colH), 0.5);
    });
  }

  /* ---------- shared: the silhouette, hover, armour, regeneration, resists, status ---------- */
  const FAM = {
    sharpen: { name: 'Sharpening', draw: sharpen, path: shPath, words: ['Monolith', 'Hexagon', 'Orb', 'Teardrop', 'Chevron', 'Dart', 'Split blade', 'Needle'] },
    fragment: { name: 'Fragmenting', draw: fragment, path: frPath, words: ['Block', 'Cracked', 'Wedge', 'Four shards', 'Five', 'Six', 'Seven', 'Flock'] },
    energy: { name: 'Energy', draw: energy, path: enPath, words: ['Three plates', 'Two plates', 'One plate', 'Open ring', 'Shielded core', 'Winged core', 'Comet', 'Spark'] },
    combined: { name: 'Combined', draw: combined, path: cbPath, words: ['Bastion', 'Shieldbearer', 'Lens', 'Teardrop', 'Arrowhead', 'Dart', 'Splitwing', 'Talon'] },
  };
  const RES_COL = { splash: '#ffd27a', poison: '#8fe388', frost: '#bff3ff', shock: '#a98bff' };
  // u: { fam, s (speed step), R, col, ang, armor, regen, res: [...], slow, poison, flash }
  function drawUnit(c, u, t, px) {
    const fam = FAM[u.fam], f = F(u.s), R = u.R;
    c.save(); c.translate(u.x, u.y);
    // the shadow: the silhouette, further below the faster the unit (it hovers higher)
    c.save(); c.translate(0.03 + 0.09 * f, 0.04 + 0.11 * f); c.rotate(u.ang); c.beginPath(); fam.path(c, u.s, R); c.fillStyle = `rgba(0,0,0,${0.5 - 0.15 * f})`; c.fill(); c.restore();
    const bob = Math.sin(t * (2 + 6 * f) + u.x * 3) * 0.012 * f; c.translate(0, -bob);
    c.save(); c.rotate(u.ang);
    fam.draw(c, u.s, R, u.col, t, px);
    if (u.slow || u.poison || u.flash) { c.beginPath(); fam.path(c, u.s, R); c.fillStyle = u.flash ? 'rgba(255,255,255,0.8)' : u.slow ? 'rgba(200,245,255,0.5)' : 'rgba(143,227,136,0.38)'; c.fill(); }
    c.restore();
    const rr = R * 1.32 + 0.035, aw = Math.max(px * 1.6, R * 0.1);
    if (u.armor) { // steel brackets on a ring: the front, then the sides too, then all round
      const segs = [[-0.6, 0.6]]; if (u.armor >= 2) segs.push([1.2, 1.94], [-1.94, -1.2]); if (u.armor >= 3) segs.push([Math.PI - 0.6, Math.PI + 0.6]);
      for (const [a0, a1] of segs) for (const [w, col] of [[aw + px * 1.6, 'rgba(6,8,10,0.9)'], [aw, '#c6d0d8']]) { c.beginPath(); c.arc(0, 0, rr, u.ang + a0, u.ang + a1); c.lineWidth = w; c.strokeStyle = col; c.lineCap = 'butt'; c.stroke(); }
      if (u.armor >= 3) for (let k = 0; k < 4; k++) { const a = u.ang + k * Math.PI / 2 + Math.PI / 4; c.beginPath(); c.arc(Math.cos(a) * rr, Math.sin(a) * rr, aw * 0.45, 0, TAU); c.fillStyle = '#8d99a5'; c.fill(); }
    }
    if (u.regen) { // a pulsing green cross at the heart
      const p = 0.7 + 0.3 * Math.sin(t * 5), k = Math.max(R * 0.32, 0.05) * p, w = k * 0.36;
      glow(c, 0, 0, k * 3, '150,255,180', 0.45 * p);
      c.fillStyle = '#04110a'; c.fillRect(-k - px, -w / 2 - px, 2 * k + 2 * px, w + 2 * px); c.fillRect(-w / 2 - px, -k - px, w + 2 * px, 2 * k + 2 * px);
      c.fillStyle = '#c8ffd9'; c.fillRect(-k, -w / 2, 2 * k, w); c.fillRect(-w / 2, -k, w, 2 * k);
    }
    if (u.fam === 'combined') shieldPlates(c, u.res || [], R, t, px);
    else (u.res || []).forEach((k, j, L) => { const a = t * 2.2 + j * TAU / L.length, r2 = rr + 0.02; c.beginPath(); c.arc(Math.cos(a) * r2, Math.sin(a) * r2, Math.max(0.03, R * 0.14), 0, TAU); c.fillStyle = RES_COL[k]; c.fill(); c.lineWidth = 0.012; c.strokeStyle = 'rgba(7,9,12,0.85)'; c.stroke(); });
    if (u.slow) { c.strokeStyle = 'rgba(220,250,255,0.9)'; c.lineWidth = 0.02; c.beginPath(); for (let j = 0; j < 3; j++) { const a = j * 2.1 + 0.4, r1 = R * 1.05, r2 = R * 1.4; c.moveTo(Math.cos(a) * r1, Math.sin(a) * r1); c.lineTo(Math.cos(a + 0.12) * r2, Math.sin(a + 0.12) * r2); c.lineTo(Math.cos(a + 0.25) * r1, Math.sin(a + 0.25) * r1); } c.stroke(); }
    if (u.poison) for (let j = 0; j < 3; j++) { const ph = (t * 0.9 + j / 3) % 1; c.beginPath(); c.arc((j - 1) * R * 0.5, -ph * 0.4, 0.025 + 0.02 * (1 - ph), 0, TAU); c.fillStyle = `rgba(143,227,136,${0.75 * (1 - ph)})`; c.fill(); }
    c.restore();
  }
  window.UNIT_FAM = { FAM, drawUnit, glow, rgb };
})();
