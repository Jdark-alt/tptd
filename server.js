// Siegeline relay server.
// Serves the game (index.html) and passes each player's state to the other players in the same match.
// The game itself runs in the players' browsers; this server only forwards messages and keeps no game data,
// so a restart mid-match is harmless: both pages reconnect and resend their state.
const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const PORT = process.env.PORT || 10000;
const PAGE = path.join(__dirname, 'index.html');
const MAX_PER_ROOM = 6;

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  if (url === '/health') {
    // Pages hosted elsewhere (GitHub Pages) call this to wake the server, so allow any origin.
    res.writeHead(200, { 'content-type': 'text/plain', 'cache-control': 'no-store', 'access-control-allow-origin': '*' });
    res.end('ok');
    return;
  }
  if (url === '/' || url === '/index.html') {
    fs.readFile(PAGE, 'utf8', (err, html) => {
      if (err) { res.writeHead(500, { 'content-type': 'text/plain' }); res.end('index.html is missing next to server.js'); return; }
      // Served from here, the page uses this same server as its relay.
      html = html.replace('<head>', '<head><script>window.SIEGE_RELAY = "same-origin";</script>');
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-cache' });
      res.end(html);
    });
    return;
  }
  res.writeHead(404, { 'content-type': 'text/plain' });
  res.end('Not found');
});

const wss = new WebSocketServer({ server, path: '/relay', maxPayload: 64 * 1024 });
const rooms = new Map(); // room name -> Map(player id -> { ws, state })
const send = (ws, msg) => { if (ws.readyState === 1) ws.send(JSON.stringify(msg)); };

wss.on('connection', ws => {
  let room = null, id = null;
  ws.alive = true;
  ws.on('pong', () => { ws.alive = true; });
  ws.on('message', data => {
    ws.alive = true;
    let m;
    try { m = JSON.parse(data); } catch (_) { return; }
    if (!m || typeof m !== 'object') return;
    if (m.t === 'hb') { send(ws, { t: 'hb' }); return; }
    if (m.t === 'join' && !room && typeof m.room === 'string' && typeof m.id === 'string') {
      const name = m.room.slice(0, 48), who = m.id.slice(0, 32);
      let r = rooms.get(name);
      if (!r) rooms.set(name, r = new Map());
      if (r.size >= MAX_PER_ROOM && !r.has(who)) { send(ws, { t: 'full' }); ws.close(); return; }
      const old = r.get(who);
      if (old && old.ws !== ws) { try { old.ws.terminate(); } catch (_) { /* already gone */ } }
      room = name; id = who;
      r.set(id, { ws, state: null });
      const others = [];
      for (const [k, v] of r) if (k !== id && v.state) others.push({ id: k, state: v.state });
      send(ws, { t: 'peers', peers: others });
      return;
    }
    if (m.t === 'state' && room) {
      const r = rooms.get(room), me = r && r.get(id);
      if (!me || me.ws !== ws) return;
      me.state = m.state;
      for (const [k, v] of r) if (k !== id) send(v.ws, { t: 'state', id, state: m.state });
    }
  });
  ws.on('close', () => {
    if (!room) return;
    const r = rooms.get(room), me = r && r.get(id);
    if (!me || me.ws !== ws) return;
    r.delete(id);
    for (const [, v] of r) send(v.ws, { t: 'left', id });
    if (!r.size) rooms.delete(room);
  });
});

// Ping every connection; drop the ones that stopped answering so the other player sees them leave.
setInterval(() => {
  for (const ws of wss.clients) {
    if (!ws.alive) { ws.terminate(); continue; }
    ws.alive = false;
    try { ws.ping(); } catch (_) { /* closing */ }
  }
}, 20000);

server.listen(PORT, () => console.log(`Siegeline server listening on ${PORT}`));
