/* Física independente da tela e do pedido; sem armazenamento ou rede. */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.DeliveryPong = factory();
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const WIDTH = 640, HEIGHT = 400, PADDLE = 82, RADIUS = 7, LEFT = 38, RIGHT = WIDTH - 38;
  const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

  function serve(game, direction) {
    const angle = (game.random() - 0.5) * 0.8;
    game.ball = { x: WIDTH / 2, y: HEIGHT / 2, vx: direction * 300 * Math.cos(angle), vy: 300 * Math.sin(angle) };
    game.wait = 0.8;
    game.aiOffset = (game.random() - 0.5) * 100;
  }
  function createGame(mode, random) {
    const game = { width: WIDTH, height: HEIGHT, paddle: PADDLE, radius: RADIUS,
      playerY: HEIGHT / 2, aiY: HEIGHT / 2, playerScore: 0, aiScore: 0,
      targetScore: 5, running: false, winner: '', mode: mode === 'normal' ? 'normal' : 'leve', random: random || Math.random };
    serve(game, 1);
    return game;
  }
  function play(game) { if (!game.winner) game.running = true; }
  function pause(game) { game.running = false; }
  function point(game, player) {
    if (player) game.playerScore += 1;
    else game.aiScore += 1;
    if (game.playerScore >= game.targetScore || game.aiScore >= game.targetScore) {
      game.winner = player ? 'voce' : 'computador';
      game.running = false;
    } else serve(game, player ? -1 : 1);
  }
  function move(y, target, distance) {
    return clamp(y + clamp(target - y, -distance, distance), PADDLE / 2, HEIGHT - PADDLE / 2);
  }
  function bounce(game, paddleY, direction) {
    const ball = game.ball;
    const angle = clamp((ball.y - paddleY) / (PADDLE / 2), -1, 1) * 1.02;
    const speed = Math.min(620, Math.hypot(ball.vx, ball.vy) * 1.07);
    ball.vx = direction * speed * Math.cos(angle);
    ball.vy = speed * Math.sin(angle);
    ball.x = direction > 0 ? LEFT + RADIUS : RIGHT - RADIUS;
  }
  function advance(game, elapsed, input) {
    if (!game.running || game.winner || !Number.isFinite(elapsed) || elapsed <= 0) return;
    input = input || {};
    // Passos pequenos evitam atravessar a raquete; travamentos não avançam a partida inteira.
    let remaining = Math.min(elapsed, 0.05);
    while (remaining > 0.000001 && game.running) {
      const dt = Math.min(remaining, 1 / 120);
      remaining -= dt;
      const target = Number.isFinite(input.target) ? input.target : game.playerY + clamp(Number(input.direction) || 0, -1, 1) * 560 * dt;
      game.playerY = move(game.playerY, target, 560 * dt);
      const ball = game.ball;
      const aim = ball.vx > 0 ? ball.y + game.aiOffset : HEIGHT / 2;
      game.aiY = move(game.aiY, aim, (game.mode === 'normal' ? 265 : 185) * dt);
      if (game.wait > 0) { game.wait = Math.max(0, game.wait - dt); continue; }
      const previousX = ball.x;
      ball.x += ball.vx * dt;
      ball.y += ball.vy * dt;
      if (ball.y < RADIUS) { ball.y = 2 * RADIUS - ball.y; ball.vy = Math.abs(ball.vy); }
      if (ball.y > HEIGHT - RADIUS) { ball.y = 2 * (HEIGHT - RADIUS) - ball.y; ball.vy = -Math.abs(ball.vy); }
      if (ball.vx < 0 && previousX >= LEFT + RADIUS && ball.x <= LEFT + RADIUS && Math.abs(ball.y - game.playerY) <= PADDLE / 2 + RADIUS) bounce(game, game.playerY, 1);
      else if (ball.vx > 0 && previousX <= RIGHT - RADIUS && ball.x >= RIGHT - RADIUS && Math.abs(ball.y - game.aiY) <= PADDLE / 2 + RADIUS) bounce(game, game.aiY, -1);
      if (ball.x < -RADIUS) point(game, false);
      else if (ball.x > WIDTH + RADIUS) point(game, true);
    }
  }
  return { createGame, play, pause, advance };
});
