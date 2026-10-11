/* Partida opcional: não lê dados do pedido, cookies, conversas ou identificadores. */
(function () {
  'use strict';
  const core = window.DeliveryPong;
  if (!core) return;
  document.querySelectorAll('[data-pong]').forEach(function (root) {
    const canvas = root.querySelector('canvas'), ctx = canvas.getContext('2d');
    if (!ctx) return;
    const start = root.querySelector('[data-start]'), pause = root.querySelector('[data-pause]');
    const restart = root.querySelector('[data-restart]'), mode = root.querySelector('[data-mode]');
    const status = root.querySelector('[data-status]'), score = root.querySelector('[data-score]');
    const disclosure = root.closest('details');
    let game = core.createGame(mode.value), frame = 0, last = 0, target = null, direction = 0, pointer = null;
    const keys = new Set();

    function draw() {
      const scale = Math.min(window.devicePixelRatio || 1, 2);
      if (canvas.width !== game.width * scale) { canvas.width = game.width * scale; canvas.height = game.height * scale; }
      ctx.setTransform(scale, 0, 0, scale, 0, 0);
      ctx.fillStyle = '#102d29'; ctx.fillRect(0, 0, game.width, game.height);
      ctx.strokeStyle = '#385b53'; ctx.lineWidth = 2; ctx.setLineDash([7, 10]);
      ctx.beginPath(); ctx.moveTo(game.width / 2, 18); ctx.lineTo(game.width / 2, game.height - 18); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = '#73e0bb'; ctx.fillRect(24, game.playerY - game.paddle / 2, 14, game.paddle);
      ctx.fillStyle = '#f5d897'; ctx.fillRect(game.width - 38, game.aiY - game.paddle / 2, 14, game.paddle);
      ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(game.ball.x, game.ball.y, game.radius, 0, Math.PI * 2); ctx.fill();
      if (!game.running || game.wait > 0) {
        ctx.fillStyle = 'rgba(16,45,41,.8)'; ctx.fillRect(112, 164, 416, 72);
        ctx.fillStyle = '#fff'; ctx.font = '600 22px system-ui'; ctx.textAlign = 'center';
        ctx.fillText(game.winner ? (game.winner === 'voce' ? 'Você venceu! 🏓' : 'Boa partida! Vamos de novo?') : game.running ? 'Prepare a raquete…' : 'Sua raquete é a verde', game.width / 2, 207);
      }
    }
    function update() {
      score.textContent = game.playerScore + ' × ' + game.aiScore;
      score.setAttribute('aria-label', 'Placar: você ' + game.playerScore + ', computador ' + game.aiScore);
      start.disabled = game.running;
      start.textContent = game.winner ? 'Jogar de novo' : last ? 'Continuar' : 'Jogar';
      pause.disabled = !game.running;
      mode.disabled = game.running;
      if (game.winner) status.textContent = game.winner === 'voce' ? 'Você ganhou! Placar: ' + score.textContent + '.' : 'O computador venceu esta. Placar: ' + score.textContent + '. Que tal outra?';
    }
    function tick(time) {
      frame = 0;
      if (!game.running) return;
      const oldScore = game.playerScore + game.aiScore;
      core.advance(game, last ? (time - last) / 1000 : 0, { target, direction });
      last = time;
      draw();
      if (oldScore !== game.playerScore + game.aiScore) {
        update();
        if (!game.winner) status.textContent = 'Ponto! Você ' + game.playerScore + ', computador ' + game.aiScore + '.';
      }
      if (game.running) frame = requestAnimationFrame(tick);
    }
    function stop(message) {
      if (!game.running) return;
      core.pause(game); cancelAnimationFrame(frame); frame = 0;
      keys.clear(); direction = 0; target = null; pointer = null;
      update(); draw(); status.textContent = message || 'Partida pausada. Toque em Continuar quando quiser.';
    }
    function reset() {
      core.pause(game); cancelAnimationFrame(frame); frame = 0; last = 0;
      keys.clear(); direction = 0; target = null; pointer = null;
      game = core.createGame(mode.value); update(); draw();
      status.textContent = 'Tudo pronto. A primeira pessoa a fazer 5 pontos vence.';
    }
    start.addEventListener('click', function () {
      if (game.winner) reset();
      if (game.running || document.hidden) return;
      core.play(game); last = 0; update(); canvas.focus({ preventScroll: true });
      status.textContent = 'Valendo! Mova a raquete verde. A partida vai até 5 pontos.';
      frame = requestAnimationFrame(tick);
    });
    pause.addEventListener('click', () => stop());
    restart.addEventListener('click', reset);
    mode.addEventListener('change', reset);
    function movePointer(event) {
      if (!game.running) return;
      const rect = canvas.getBoundingClientRect();
      if (rect.height > 0) target = (event.clientY - rect.top) / rect.height * game.height;
      direction = 0;
    }
    canvas.addEventListener('pointerdown', function (event) {
      if (!game.running || pointer !== null) return;
      pointer = event.pointerId; canvas.setPointerCapture(pointer); movePointer(event);
    });
    canvas.addEventListener('pointermove', function (event) {
      if (event.pointerType === 'mouse' || event.pointerId === pointer) movePointer(event);
    });
    const release = event => { if (event.pointerId === pointer) { pointer = null; target = null; } };
    canvas.addEventListener('pointerup', release);
    canvas.addEventListener('pointercancel', release);
    canvas.addEventListener('lostpointercapture', release);
    const keyDirection = key => ['ArrowUp', 'w', 'W'].includes(key) ? -1 : ['ArrowDown', 's', 'S'].includes(key) ? 1 : 0;
    canvas.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { stop(); return; }
      if (!keyDirection(event.key) || !game.running) return;
      event.preventDefault(); keys.add(event.key); target = null;
      direction = [...keys].reduce((sum, key) => sum + keyDirection(key), 0);
    });
    canvas.addEventListener('keyup', function (event) {
      if (!keyDirection(event.key)) return;
      event.preventDefault(); keys.delete(event.key);
      direction = [...keys].reduce((sum, key) => sum + keyDirection(key), 0);
    });
    canvas.addEventListener('blur', () => { keys.clear(); direction = 0; });
    root.querySelectorAll('[data-direction]').forEach(function (button) {
      const press = event => { if (!game.running) return; event.preventDefault(); target = null; direction = Number(button.dataset.direction); };
      button.addEventListener('pointerdown', function (event) { press(event); button.setPointerCapture(event.pointerId); });
      ['pointerup', 'pointercancel', 'lostpointercapture', 'blur'].forEach(type => button.addEventListener(type, () => { direction = 0; }));
      button.addEventListener('keydown', function (event) { if (event.key === ' ' || event.key === 'Enter') press(event); });
      button.addEventListener('keyup', () => { direction = 0; });
    });
    document.addEventListener('visibilitychange', () => { if (document.hidden) stop('Partida pausada enquanto você estava em outra aba. Toque em Continuar.'); });
    window.addEventListener('blur', () => stop());
    window.addEventListener('pagehide', () => stop());
    if (disclosure) disclosure.addEventListener('toggle', () => { if (!disclosure.open) stop(); });
    root.hidden = false; update(); draw();
  });
})();
