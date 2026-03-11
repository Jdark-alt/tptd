const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const path_module = require('path');

const app = express();
app.use(cors());
app.use(express.static(path_module.join(__dirname, 'public')));

const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });

const rooms = {};

// ─── Game Config (mirrors client) ───────────────────────────────────────────

const enemyTypes = {
    basic:  { cost: 20,  hp: 100,  speed: 1.5, color: '#4ade80', size: 12, reward: 5   },
    fast:   { cost: 30,  hp: 60,   speed: 3.0, color: '#fbbf24', size: 10, reward: 7.5 },
    tanky:  { cost: 40,  hp: 250,  speed: 0.8, color: '#f87171', size: 16, reward: 10  }
};

const towerTypes = {
    basic:  { cost: 50,  damage: 20, range: 100, fireRate: 1000, color: '#60a5fa', upgradeCost: 40, damageIncrease: 10 },
    poison: { cost: 75,  damage: 10, poisonDamage: 5, range: 90,  fireRate: 1500, color: '#a78bfa', upgradeCost: 60, damageIncrease: 5  },
    aoe:    { cost: 100, damage: 15, range: 80,  aoeRadius: 60, fireRate: 2000, color: '#fb923c', upgradeCost: 80, damageIncrease: 8  }
};

const PATH = [
    { x: 0,   y: 200 },
    { x: 200, y: 200 },
    { x: 200, y: 400 },
    { x: 400, y: 400 },
    { x: 400, y: 100 },
    { x: 600, y: 100 },
    { x: 600, y: 500 },
    { x: 800, y: 500 }
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function distanceToSegment(px, py, x1, y1, x2, y2) {
    const A = px - x1, B = py - y1, C = x2 - x1, D = y2 - y1;
    const dot = A * C + B * D;
    const lenSq = C * C + D * D;
    const param = lenSq !== 0 ? dot / lenSq : -1;
    let xx, yy;
    if (param < 0)      { xx = x1; yy = y1; }
    else if (param > 1) { xx = x2; yy = y2; }
    else                { xx = x1 + param * C; yy = y1 + param * D; }
    return Math.sqrt((px - xx) ** 2 + (py - yy) ** 2);
}

function isOnPath(x, y, buffer) {
    for (let i = 0; i < PATH.length - 1; i++) {
        if (distanceToSegment(x, y, PATH[i].x, PATH[i].y, PATH[i + 1].x, PATH[i + 1].y) < buffer) return true;
    }
    return false;
}

function createGameState() {
    return {
        phase: 'lobby',
        wave: 1,
        maxWaves: 10,
        enemiesThrough: 0,
        maxEnemiesThrough: 15,
        attackerGold: 200,
        defenderGold: 350,
        towers: [],
        enemies: [],
        projectiles: [],
        enemyQueue: [],
        waveStarted: false,
        attackerReady: false,
        defenderReady: false,
        spawnIndex: 0,
        lastSpawnTime: 0,
    };
}

// ─── Game Loop ────────────────────────────────────────────────────────────────

function runGameTick(room) {
    const gs = room.gameState;
    const now = Date.now();

    // Spawn enemies
    if (gs.spawnIndex < gs.enemyQueue.length && now - gs.lastSpawnTime > 800) {
        const type = gs.enemyQueue[gs.spawnIndex];
        const cfg = enemyTypes[type];
        // BUG FIX: was gameState.currentWave (undefined) → now gs.wave
        const scaledHp = Math.round(cfg.hp * Math.pow(1.05, gs.wave - 1));
        gs.enemies.push({
            id: gs.spawnIndex,
            type, color: cfg.color, size: cfg.size,
            hp: scaledHp, maxHp: scaledHp,
            speed: cfg.speed, reward: cfg.reward,
            pathIndex: 0, progress: 0,
            x: PATH[0].x, y: PATH[0].y,
            poisoned: false, poisonDamage: 0, poisonTimer: 0
        });
        gs.spawnIndex++;
        gs.lastSpawnTime = now;
    }

    // Update enemies
    for (let i = gs.enemies.length - 1; i >= 0; i--) {
        const e = gs.enemies[i];

        if (e.poisoned) {
            e.poisonTimer++;
            if (e.poisonTimer >= 60) { e.hp -= e.poisonDamage; e.poisonTimer = 0; }
        }

        if (e.hp <= 0) {
            gs.defenderGold += e.reward;
            gs.enemies.splice(i, 1);
            continue;
        }

        if (e.pathIndex < PATH.length - 1) {
            const cur  = PATH[e.pathIndex];
            const next = PATH[e.pathIndex + 1];
            const dist = Math.sqrt((next.x - cur.x) ** 2 + (next.y - cur.y) ** 2);
            e.progress += e.speed / dist;
            if (e.progress >= 1) { e.progress = 0; e.pathIndex++; }
            e.x = cur.x + (next.x - cur.x) * e.progress;
            e.y = cur.y + (next.y - cur.y) * e.progress;
        } else {
            gs.enemiesThrough++;
            gs.enemies.splice(i, 1);
            if (gs.enemiesThrough >= gs.maxEnemiesThrough) {
                endGame(room, false);
                return;
            }
        }
    }

    // Update towers
    gs.towers.forEach(tower => {
        if (now - tower.lastFire < tower.fireRate) return;

        let target = null, minDist = Infinity;
        gs.enemies.forEach(e => {
            const d = Math.sqrt((e.x - tower.x) ** 2 + (e.y - tower.y) ** 2);
            if (d <= tower.range && d < minDist) { minDist = d; target = e; }
        });

        if (!target) return;
        tower.lastFire = now;

        if (tower.type === 'aoe') {
            gs.enemies.forEach(e => {
                if (Math.sqrt((e.x - target.x) ** 2 + (e.y - target.y) ** 2) <= tower.aoeRadius)
                    e.hp -= tower.damage;
            });
            gs.projectiles.push({ x: target.x, y: target.y, radius: 0, maxRadius: tower.aoeRadius, color: tower.color, alpha: 1, type: 'aoe' });
        } else {
            target.hp -= tower.damage;
            if (tower.type === 'poison') { target.poisoned = true; target.poisonDamage = tower.poisonDamage; }
            gs.projectiles.push({ x: tower.x, y: tower.y, targetX: target.x, targetY: target.y, color: tower.color, progress: 0, type: 'bullet' });
        }
    });

    // Update projectiles
    for (let i = gs.projectiles.length - 1; i >= 0; i--) {
        const p = gs.projectiles[i];
        if (p.type === 'aoe') { p.radius += 3; p.alpha -= 0.05; if (p.alpha <= 0) gs.projectiles.splice(i, 1); }
        else                  { p.progress += 0.15; if (p.progress >= 1) gs.projectiles.splice(i, 1); }
    }

    // Broadcast state to both clients
    io.to(room.code).emit('tick', gs);

    // Wave complete?
    if (gs.spawnIndex >= gs.enemyQueue.length && gs.enemies.length === 0) {
        endWave(room);
    }
}

function endWave(room) {
    clearInterval(room.gameInterval);
    room.gameInterval = null;
    const gs = room.gameState;

    gs.waveStarted = false;
    gs.wave++;
    gs.defenderGold += 10;

    if (gs.wave > gs.maxWaves) { endGame(room, true); return; }

    gs.attackerGold = Math.floor(gs.attackerGold + (gs.wave * 1.25) * 175);
    gs.phase = 'attacker';
    gs.attackerReady = false;
    gs.defenderReady = false;
    gs.enemies = [];
    gs.projectiles = [];
    gs.enemyQueue = [];
    gs.spawnIndex = 0;

    io.to(room.code).emit('phaseChange', { phase: 'attacker', gameState: gs });
}

function endGame(room, defenderWon) {
    if (room.gameInterval) { clearInterval(room.gameInterval); room.gameInterval = null; }
    room.gameState.phase = 'gameover';
    io.to(room.code).emit('gameOver', { defenderWon, wave: room.gameState.wave, enemiesThrough: room.gameState.enemiesThrough, maxEnemiesThrough: room.gameState.maxEnemiesThrough, maxWaves: room.gameState.maxWaves });
}

// ─── Socket Events ────────────────────────────────────────────────────────────

io.on('connection', socket => {
    console.log('Connected:', socket.id);

    socket.on('joinRoom', ({ roomCode, role }) => {
        if (!rooms[roomCode]) {
            rooms[roomCode] = { code: roomCode, attacker: null, defender: null, gameState: createGameState(), gameInterval: null };
        }
        const room = rooms[roomCode];

        if (role === 'attacker' && room.attacker && room.attacker !== socket.id) {
            return socket.emit('joinError', 'Attacker slot is already taken in this room.');
        }
        if (role === 'defender' && room.defender && room.defender !== socket.id) {
            return socket.emit('joinError', 'Defender slot is already taken in this room.');
        }

        socket.join(roomCode);
        socket.roomCode = roomCode;
        socket.role = role;

        if (role === 'attacker') room.attacker = socket.id;
        else room.defender = socket.id;

        socket.to(roomCode).emit('opponentJoined', { role });

        if (room.attacker && room.defender) {
            room.gameState.phase = 'attacker';
            io.to(roomCode).emit('gameStart', { gameState: room.gameState });
        } else {
            socket.emit('waitingForOpponent', { role });
        }
    });

    socket.on('confirmEnemies', ({ counts }) => {
        const room = rooms[socket.roomCode];
        if (!room || socket.role !== 'attacker') return;
        const gs = room.gameState;

        const queue = [];
        for (const type in counts) for (let i = 0; i < counts[type]; i++) queue.push(type);
        queue.sort(() => Math.random() - 0.5);
        gs.enemyQueue = queue;
        gs.phase = 'defender';

        io.to(socket.roomCode).emit('phaseChange', { phase: 'defender', gameState: gs });
    });

    socket.on('placeTower', ({ x, y, type }) => {
        const room = rooms[socket.roomCode];
        if (!room || socket.role !== 'defender') return;
        const gs = room.gameState;
        const cost = towerTypes[type]?.cost;
        if (!cost || gs.defenderGold < cost || isOnPath(x, y, 40)) return;

        gs.towers.push({
            x, y, type, level: 1,
            damage: towerTypes[type].damage,
            range: towerTypes[type].range,
            fireRate: towerTypes[type].fireRate,
            lastFire: 0,
            poisonDamage: towerTypes[type].poisonDamage || 0,
            aoeRadius: towerTypes[type].aoeRadius || 0,
            color: towerTypes[type].color
        });
        gs.defenderGold -= cost;
        io.to(socket.roomCode).emit('tick', gs);
    });

    socket.on('upgradeTower', ({ index }) => {
        const room = rooms[socket.roomCode];
        if (!room || socket.role !== 'defender') return;
        const gs = room.gameState;
        const tower = gs.towers[index];
        if (!tower) return;
        const cost = Math.floor(towerTypes[tower.type].upgradeCost * Math.pow(1.5, tower.level - 1));
        if (gs.defenderGold < cost) return;
        gs.defenderGold -= cost;
        tower.level++;
        tower.damage += towerTypes[tower.type].damageIncrease;
        tower.range += 5;
        if (tower.poisonDamage) tower.poisonDamage += 2;
        if (tower.aoeRadius) tower.aoeRadius += 5;
        io.to(socket.roomCode).emit('tick', gs);
    });

    socket.on('sellTower', ({ index }) => {
        const room = rooms[socket.roomCode];
        if (!room || socket.role !== 'defender') return;
        const gs = room.gameState;
        const tower = gs.towers[index];
        if (!tower) return;
        gs.defenderGold += Math.floor(towerTypes[tower.type].cost * 0.7 * tower.level);
        gs.towers.splice(index, 1);
        io.to(socket.roomCode).emit('tick', gs);
    });

    socket.on('playerReady', () => {
        const room = rooms[socket.roomCode];
        if (!room) return;
        const gs = room.gameState;

        if (socket.role === 'attacker') gs.attackerReady = true;
        if (socket.role === 'defender') gs.defenderReady = true;

        io.to(socket.roomCode).emit('readyStatus', { attackerReady: gs.attackerReady, defenderReady: gs.defenderReady });

        if (gs.attackerReady && gs.defenderReady) {
            gs.phase = 'wave';
            gs.waveStarted = true;
            gs.spawnIndex = 0;
            gs.lastSpawnTime = Date.now();
            io.to(socket.roomCode).emit('waveStart', { gameState: gs });
            room.gameInterval = setInterval(() => runGameTick(room), 33); // ~30fps
        }
    });

    socket.on('disconnect', () => {
        if (socket.roomCode) {
            socket.to(socket.roomCode).emit('opponentDisconnected');
            const room = rooms[socket.roomCode];
            if (room) {
                if (socket.role === 'attacker') room.attacker = null;
                if (socket.role === 'defender') room.defender = null;
                if (!room.attacker && !room.defender) {
                    if (room.gameInterval) clearInterval(room.gameInterval);
                    delete rooms[socket.roomCode];
                }
            }
        }
        console.log('Disconnected:', socket.id);
    });
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => console.log(`🎮 Tower Defense server running on port ${PORT}`));
