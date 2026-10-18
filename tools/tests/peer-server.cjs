// Local PeerJS broker for tools/tests/test_online.py (the real game uses the free public one).
const { PeerServer } = require('peer');
PeerServer({ port: 9000, path: '/myapp', host: '127.0.0.1' }, () => console.log('peer server up'));
