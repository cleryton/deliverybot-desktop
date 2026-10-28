/* Navegação local: busca de telas e avisos de edição, sem persistir formulários. */
(function(root, factory) {
  const helpers = factory();
  if (typeof module === 'object' && module.exports) module.exports = helpers;
  else root.DeliveryNav = helpers;
})(typeof globalThis === 'object' ? globalThis : this, function() {
  'use strict';
  function normalizar(texto) {
    return String(texto || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
  }
  function corresponde(titulo, aliases, busca) {
    const alvo = normalizar(titulo + ' ' + (aliases || ''));
    return normalizar(busca).split(/\s+/).filter(Boolean).every(termo => alvo.includes(termo));
  }
  function alteracoes() {
    const revisoes = new Map(), pendentes = new Set();
    return {
      registrar(pagina) { revisoes.set(pagina, (revisoes.get(pagina) || 0) + 1); pendentes.add(pagina); },
      revisao(pagina) { return revisoes.get(pagina) || 0; },
      limpar(pagina) { pendentes.delete(pagina); revisoes.set(pagina, (revisoes.get(pagina) || 0) + 1); },
      tem(pagina) { return pagina === undefined ? pendentes.size > 0 : pendentes.has(pagina); },
      confirmar(pagina, perguntar, acao = 'sair') {
        return !pendentes.has(pagina) || perguntar(`Há alterações não salvas nesta tela. Deseja ${acao} e descartá-las?`);
      }
    };
  }
  function criar({nav, busca, limpar, resultado, administrador}) {
    const botoes = [...nav.querySelectorAll('[data-page]')];
    const grupos = [...nav.querySelectorAll('.nav-group')];
    const permitido = botao => !botao.hidden && (administrador || !botao.closest('[data-admin-only]'));
    const visiveis = () => botoes.filter(botao => permitido(botao) && !botao.classList.contains('nav-filtered'));
    function atualizar() {
      for (const botao of botoes) botao.classList.toggle('nav-filtered',
        !permitido(botao) || !corresponde(botao.textContent, botao.dataset.searchTerms, busca.value));
      for (const grupo of grupos) grupo.classList.toggle('nav-filtered',
        !visiveis().some(botao => grupo.contains(botao)));
      const ativo = !!busca.value;
      limpar.hidden = !ativo;
      resultado.hidden = !ativo;
      const quantidade = visiveis().length;
      resultado.textContent = quantidade ? `${quantidade} ${quantidade === 1 ? 'tela encontrada' : 'telas encontradas'}.` :
        'Nenhuma tela encontrada. Tente outro nome ou limpe a busca.';
    }
    function limparBusca(focar = true) {
      busca.value = ''; atualizar(); if (focar) busca.focus();
    }
    busca.addEventListener('input', atualizar);
    limpar.addEventListener('click', () => limparBusca());
    busca.addEventListener('keydown', evento => {
      if (evento.key === 'Escape' && busca.value) {
        evento.preventDefault(); evento.stopPropagation(); limparBusca();
      } else if (evento.key === 'ArrowDown' || evento.key === 'Enter') {
        const opcoes = visiveis();
        if (!opcoes.length) return;
        evento.preventDefault();
        if (evento.key === 'Enter' && opcoes.length === 1) opcoes[0].click();
        else opcoes[0].focus();
      }
    });
    nav.addEventListener('keydown', evento => {
      const atual = evento.target.closest('[data-page]');
      if (!atual || !['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(evento.key)) return;
      const opcoes = visiveis(), indice = opcoes.indexOf(atual);
      if (indice < 0) return;
      evento.preventDefault();
      const proximo = evento.key === 'Home' ? 0 : evento.key === 'End' ? opcoes.length - 1 :
        (indice + (evento.key === 'ArrowDown' ? 1 : -1) + opcoes.length) % opcoes.length;
      opcoes[proximo].focus();
    });
    atualizar();
    return {atualizar, limparBusca};
  }
  return {corresponde, alteracoes, criar};
});
