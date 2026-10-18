// A stand-in for the claude.ai room capability, built on BroadcastChannel, for local tests.
(() => {
  const me = Math.random().toString(36).slice(2, 10);
  window.__mockLatency = 30;
  function makeRoom(name) {
    const bc = new BroadcastChannel('mockroom-' + name);
    const peers = new Map(); // peer -> presence
    let mine = {}, peerH = [], connH = [], left = false;
    const snap = () => [{ peer: me, by: null, isMe: true, sameTab: true, kind: 'viewer', guest: false, presence: Object.freeze({ ...mine }), updatedAt: Date.now() },
      ...[...peers].map(([peer, presence]) => ({ peer, by: null, isMe: false, sameTab: false, kind: 'viewer', guest: false, presence, updatedAt: Date.now() }))];
    const fire = () => setTimeout(() => { if (!left) { const p = snap(); peerH.forEach(h => h({ peers: p, joined: [], left: [], updated: [] })); } }, 0);
    const post = m => setTimeout(() => { if (!left && !window.__mockOffline) bc.postMessage(m); }, window.__mockLatency);
    bc.onmessage = e => {
      if (window.__mockOffline) return;
      const m = e.data;
      if (m.t === 'hello') { post({ t: 'p', peer: me, presence: mine }); if (!peers.has(m.peer)) { peers.set(m.peer, Object.freeze({})); fire(); } }
      else if (m.t === 'p') { peers.set(m.peer, Object.freeze(JSON.parse(JSON.stringify(m.presence)))); fire(); }
      else if (m.t === 'bye') { peers.delete(m.peer); fire(); }
    };
    addEventListener('pagehide', () => bc.postMessage({ t: 'bye', peer: me }));
    post({ t: 'hello', peer: me });
    return {
      name,
      presence(patch) {
        const merged = { ...mine };
        for (const [k, v] of Object.entries(patch)) { if (v === null) delete merged[k]; else merged[k] = v; }
        const size = new TextEncoder().encode(JSON.stringify(merged)).length;
        window.__maxPresence = Math.max(window.__maxPresence || 0, size);
        if (size > 4096) return Promise.reject({ code: 'invalid_argument', message: 'presence over 4 KiB: ' + size });
        mine = merged; post({ t: 'p', peer: me, presence: mine }); fire();
        return Promise.resolve();
      },
      peers: snap,
      onPeers(h) { peerH.push(h); fire(); return () => { peerH = peerH.filter(x => x !== h); }; },
      onConnection(h) { connH.push(h); setTimeout(() => h(true), 50); return () => { connH = connH.filter(x => x !== h); }; },
      connected: () => true,
      emit: () => Promise.resolve(), on: () => () => {},
      leave() { left = true; bc.postMessage({ t: 'bye', peer: me }); bc.close(); return Promise.resolve(); },
    };
  }
  const rooms = {};
  const room = { join: async name => (rooms[name] ||= makeRoom(name)) };
  window.claude = { use: async n => (n === 'room' ? room : null) };
})();
