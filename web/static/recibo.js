/* Imprime apenas a página já confirmada; não envia nem armazena dados. */
(function () {
  'use strict';
  const botao = document.getElementById('imprimir-recibo');
  if (!botao || typeof window.print !== 'function') return;
  botao.hidden = false;
  botao.addEventListener('click', function () { window.print(); });
})();
