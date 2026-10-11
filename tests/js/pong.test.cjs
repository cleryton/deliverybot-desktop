'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../../web/static/pong-core.js');
const game = mode => core.createGame(mode, () => 0.5);

test('só começa por ação do jogador e pausa sem alterar a partida', () => {
  const g = game(); const before = { ...g.ball };
  core.advance(g, 0.04, { direction: 1 }); assert.deepEqual(g.ball, before);
  core.play(g); g.wait = 0; core.advance(g, 0.04); assert.ok(g.ball.x > before.x);
  core.pause(g); const paused = { ...g.ball }; const y = g.playerY;
  core.advance(g, 0.04, { direction: 1 }); assert.deepEqual(g.ball, paused); assert.equal(g.playerY, y);
});
test('toque e teclado respeitam os limites da mesa', () => {
  const g = game(); core.play(g);
  for (let i = 0; i < 100; i++) core.advance(g, 0.04, { target: -10000 });
  assert.equal(g.playerY, g.paddle / 2);
  for (let i = 0; i < 100; i++) core.advance(g, 0.04, { direction: 1 });
  assert.equal(g.playerY, g.height - g.paddle / 2);
});
test('rebate as duas paredes sem pontuar', () => {
  const g = game(); core.play(g); g.wait = 0;
  g.ball = { x: 300, y: 8, vx: 100, vy: -300 }; core.advance(g, 0.04);
  assert.ok(g.ball.vy > 0); assert.ok(g.ball.y >= g.radius);
  g.ball = { x: 300, y: 392, vx: 100, vy: 300 }; core.advance(g, 0.04);
  assert.ok(g.ball.vy < 0); assert.ok(g.ball.y <= g.height - g.radius);
  assert.equal(g.playerScore + g.aiScore, 0);
});
test('raquetes devolvem a bola, aumentam o ritmo e mudam o ângulo', () => {
  const g = game(); core.play(g); g.wait = 0;
  g.ball = { x: 50, y: g.playerY + 20, vx: -300, vy: 0 }; core.advance(g, 0.02);
  assert.ok(g.ball.vx > 0); assert.ok(g.ball.vy > 0); assert.ok(Math.hypot(g.ball.vx, g.ball.vy) > 300);
  g.ball = { x: 590, y: g.aiY, vx: 300, vy: 0 }; core.advance(g, 0.04);
  assert.ok(g.ball.vx < 0);
});
test('bola rápida não atravessa raquete nem ultrapassa o limite de velocidade', () => {
  const g = game(); core.play(g); g.wait = 0;
  g.ball = { x: 70, y: g.playerY, vx: -2000, vy: 0 }; core.advance(g, 0.04);
  assert.ok(g.ball.vx > 0); assert.ok(Math.hypot(g.ball.vx, g.ball.vy) <= 620);
  assert.equal(g.aiScore, 0);
});
test('bola perdida concede um ponto e prepara um novo saque', () => {
  const g = game(); core.play(g); g.wait = 0;
  g.ball = { x: -8, y: 30, vx: -300, vy: 0 }; core.advance(g, 0.01);
  assert.equal(g.aiScore, 1); assert.equal(g.playerScore, 0); assert.ok(g.wait > 0);
  g.wait = 0; g.ball = { x: 648, y: 30, vx: 300, vy: 0 }; core.advance(g, 0.01);
  assert.equal(g.playerScore, 1); assert.equal(g.aiScore, 1);
});
test('vence em cinco pontos, para a partida e não pontua novamente', () => {
  for (const player of [true, false]) {
    const g = game(); core.play(g); g.wait = 0;
    if (player) g.playerScore = 4; else g.aiScore = 4;
    g.ball = { x: player ? 648 : -8, y: 30, vx: player ? 300 : -300, vy: 0 };
    core.advance(g, 0.04); assert.equal(g.winner, player ? 'voce' : 'computador'); assert.equal(g.running, false);
    const score = g.playerScore + g.aiScore; core.play(g); core.advance(g, 0.04);
    assert.equal(g.playerScore + g.aiScore, score); assert.equal(g.running, false);
  }
});
test('nova partida limpa o placar; dificuldades têm velocidades distintas', () => {
  const easy = game('leve'), normal = game('normal');
  core.play(easy); core.play(normal); easy.ball.y = normal.ball.y = 350;
  core.advance(easy, 0.04); core.advance(normal, 0.04);
  assert.ok(normal.aiY > easy.aiY); const fresh = game();
  assert.equal(fresh.playerScore + fresh.aiScore, 0); assert.equal(fresh.winner, ''); assert.equal(fresh.running, false);
});
test('entradas inválidas e suspensão longa não corrompem a física', () => {
  const g = game(); core.play(g); g.wait = 0; const before = { ...g.ball };
  for (const dt of [NaN, Infinity, -1, 0]) core.advance(g, dt, { target: NaN });
  assert.deepEqual(g.ball, before);
  core.advance(g, 60, { target: Infinity, direction: NaN });
  assert.ok(g.ball.x - before.x <= 15.01); assert.ok(Number.isFinite(g.playerY));
});
