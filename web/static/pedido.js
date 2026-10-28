/* O catálogo não persiste dados pessoais: somente o formulário envia o pedido. */
(function () {
  'use strict';
  const form = document.getElementById('form-pedido');
  if (!form) return;
  const produtos = Array.from(form.querySelectorAll('.produto'));
  const entrega = document.getElementById('forma_entrega');
  const endereco = document.getElementById('campo-endereco');
  const confirmar = document.getElementById('botao-confirmar');
  const revisar = document.getElementById('botao-revisar');
  const carrinho = document.getElementById('lista-carrinho');
  const feedback = document.getElementById('feedback-pedido');
  const busca = document.getElementById('busca-produtos');
  const limpar = document.getElementById('limpar-busca');
  const validacao = document.getElementById('validacao-pedido');
  const filtros = Array.from(form.querySelectorAll('.categoria-filtro'));
  const reais = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const medida = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 3 });
  const taxaCentavos = Math.max(0, Math.round((Number(form.dataset.taxaEntrega) || 0) * 100));
  let categoriaAtiva = '';
  let enviando = false;
  let feedbackTimer;
  const camposInvalidos = new Set();

  function avisar(texto) {
    clearTimeout(feedbackTimer);
    feedbackTimer = setTimeout(function () { feedback.textContent = texto; }, 180);
  }
  function quantidade(produto) {
    const valor = Number(produto.querySelector('input[type=number]').value);
    return Number.isFinite(valor) && valor > 0 ? valor : 0;
  }
  function sincronizarQuantidade(produto, normalizar) {
    const input = produto.querySelector('input[type=number]');
    const maximo = Math.min(999999, Math.max(0, Number(input.max)));
    let valor = quantidade(produto);
    if (normalizar) {
      // Controles e digitação respeitam estoque e precisão; o servidor confere novamente.
      valor = Math.max(0, Math.min(maximo, valor));
      valor = Number(input.step) === 1 ? Math.floor(valor) : Math.round(valor * 1000) / 1000;
      input.value = String(valor);
    }
    produto.classList.toggle('selecionado', valor > 0);
    produto.querySelector('.menos').disabled = valor <= 0 || enviando;
    produto.querySelector('.mais').disabled = valor >= maximo || enviando;
    return valor;
  }
  function alterarQuantidade(produto, sentido) {
    if (enviando) return;
    const input = produto.querySelector('input[type=number]');
    const passo = Number(produto.querySelector('.stepper').dataset.passo);
    input.value = String(Math.max(0, Math.min(Number(input.max), Math.round((quantidade(produto) + sentido * passo) * 1000) / 1000)));
    sincronizarQuantidade(produto, true);
    atualizarResumo();
    avisar(produto.dataset.nome + ': ' + medida.format(quantidade(produto)) + ' ' + produto.dataset.unidade + '.');
  }
  function controleCarrinho(produto, sentido) {
    const botao = document.createElement('button');
    const acao = sentido > 0 ? 'mais' : 'menos';
    const input = produto.querySelector('input[type=number]');
    botao.type = 'button';
    botao.id = 'carrinho-' + produto.dataset.produtoId + '-' + acao;
    botao.textContent = sentido > 0 ? '+' : '−';
    botao.setAttribute('aria-label', (sentido > 0 ? 'Aumentar' : 'Diminuir') + ' quantidade de ' + produto.dataset.nome + ' no pedido');
    botao.disabled = enviando || (sentido > 0 ? quantidade(produto) >= Number(input.max) : quantidade(produto) <= 0);
    botao.addEventListener('click', function () {
      if (enviando) return;
      alterarQuantidade(produto, sentido);
      // O resumo é reconstruído. Devolve o foco ao controle equivalente, ou
      // ao controle oposto quando atingir o limite, sem pular a página.
      const equivalente = document.getElementById(botao.id);
      const oposto = document.getElementById('carrinho-' + produto.dataset.produtoId + '-' + (sentido > 0 ? 'menos' : 'mais'));
      const destino = equivalente && !equivalente.disabled ? equivalente : oposto && !oposto.disabled ? oposto : document.getElementById('titulo-checkout');
      destino.focus({ preventScroll: true });
    });
    return botao;
  }
  function atualizarResumo() {
    let selecionados = 0;
    let subtotal = 0;
    const fragmento = document.createDocumentFragment();
    produtos.forEach(function (produto) {
      const qtd = sincronizarQuantidade(produto, false);
      if (!qtd) return;
      selecionados += 1;
      // Preço em centavos e quantidade em milésimos evitam erros na soma fracionada.
      const linhaCentavos = Math.floor((Math.round(Number(produto.dataset.preco) * 100) * Math.round(qtd * 1000) + 500) / 1000);
      subtotal += linhaCentavos;
      const linha = document.createElement('li');
      const info = document.createElement('div');
      const nome = document.createElement('span');
      nome.className = 'carrinho-nome';
      nome.textContent = produto.dataset.nome;
      const qtdTexto = document.createElement('span');
      qtdTexto.className = 'carrinho-quantidade';
      qtdTexto.textContent = medida.format(qtd) + ' ' + produto.dataset.unidade;
      const ajuste = document.createElement('div');
      ajuste.className = 'ajuste-carrinho';
      ajuste.setAttribute('role', 'group');
      ajuste.setAttribute('aria-label', 'Quantidade de ' + produto.dataset.nome + ' no pedido');
      ajuste.append(controleCarrinho(produto, -1), qtdTexto, controleCarrinho(produto, 1));
      const remover = document.createElement('button');
      remover.type = 'button';
      remover.className = 'remover-item';
      remover.textContent = 'Remover';
      remover.setAttribute('aria-label', 'Remover ' + produto.dataset.nome + ' do pedido');
      remover.disabled = enviando;
      remover.addEventListener('click', function () {
        produto.querySelector('input[type=number]').value = '0';
        atualizarResumo();
        // A linha sai da lista; direciona o foco para um controle estável.
        document.getElementById('titulo-checkout').focus({ preventScroll: true });
        avisar(produto.dataset.nome + ' removido do pedido.');
      });
      info.append(nome, ajuste, remover);
      const preco = document.createElement('span');
      preco.className = 'carrinho-linha-preco';
      preco.textContent = reais.format(linhaCentavos / 100);
      linha.append(info, preco);
      fragmento.appendChild(linha);
    });
    carrinho.replaceChildren(fragmento);
    const taxa = entrega.value === 'ENTREGA' && selecionados ? taxaCentavos : 0;
    const total = reais.format((subtotal + taxa) / 100);
    document.getElementById('subtotal-produtos').textContent = reais.format(subtotal / 100);
    document.getElementById('label-taxa').textContent = entrega.value === 'ENTREGA' ? 'Taxa de entrega' : 'Retirada na loja';
    document.getElementById('subtotal-entrega').textContent = taxa ? reais.format(taxa / 100) : 'Sem taxa';
    document.getElementById('total-checkout').textContent = total;
    document.getElementById('resumo-total').textContent = total;
    document.getElementById('resumo-itens').textContent = selecionados ? selecionados + (selecionados === 1 ? ' produto selecionado' : ' produtos selecionados') : 'Nenhum produto selecionado';
    document.getElementById('carrinho-vazio').hidden = selecionados > 0;
    document.getElementById('dica-carrinho').hidden = selecionados === 0;
    confirmar.disabled = !selecionados || enviando;
    revisar.disabled = !selecionados || enviando;
    atualizarValidacao();
  }
  function atualizarEntrega() {
    const exigeEndereco = entrega.value === 'ENTREGA';
    endereco.hidden = !exigeEndereco;
    document.getElementById('cep').required = exigeEndereco;
    document.getElementById('numero').required = exigeEndereco;
    endereco.querySelectorAll('input').forEach(function (campo) { campo.disabled = !exigeEndereco; });
    atualizarResumo();
  }
  function textoBusca(texto) {
    return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
  }
  function filtrar() {
    const termos = textoBusca(busca.value).split(/\s+/).filter(Boolean);
    let encontrados = 0;
    form.querySelectorAll('.categoria').forEach(function (secao) {
      let presentes = 0;
      const correspondeCategoria = !categoriaAtiva || secao.dataset.categoria === categoriaAtiva;
      secao.querySelectorAll('.produto').forEach(function (produto) {
        const corresponde = correspondeCategoria && termos.every(function (termo) { return produto.dataset.buscaNormalizada.includes(termo); });
        produto.hidden = !corresponde;
        if (corresponde) presentes += 1;
      });
      secao.hidden = presentes === 0;
      encontrados += presentes;
    });
    limpar.hidden = busca.value.length === 0;
    document.getElementById('busca-vazia').hidden = encontrados > 0;
    const resultado = document.getElementById('resultado-busca');
    resultado.hidden = !termos.length && !categoriaAtiva;
    resultado.textContent = encontrados + (encontrados === 1 ? ' produto encontrado' : ' produtos encontrados');
  }
  function resetarFiltros(focarBusca = true) {
    categoriaAtiva = '';
    busca.value = '';
    filtros.forEach(function (botao, indice) { botao.classList.toggle('ativa', indice === 0); botao.setAttribute('aria-pressed', String(indice === 0)); });
    filtrar();
    if (focarBusca) busca.focus();
  }
  function atualizarValidacao() {
    for (const campo of camposInvalidos) {
      if (campo.validity.valid || campo.disabled) {
        campo.removeAttribute('aria-invalid');
        camposInvalidos.delete(campo);
      }
    }
    validacao.hidden = camposInvalidos.size === 0;
    if (!camposInvalidos.size) { validacao.textContent = ''; return; }
    const campo = camposInvalidos.values().next().value;
    const nome = campo.labels?.[0]?.textContent.trim() || 'Campo do pedido';
    validacao.textContent = nome + ': ' + campo.validationMessage + (camposInvalidos.size > 1 ? ' Confira também os outros campos destacados.' : '');
  }

  produtos.forEach(function (produto) {
    const input = produto.querySelector('input[type=number]');
    produto.dataset.buscaNormalizada = textoBusca(produto.dataset.busca);
    produto.querySelector('.mais').hidden = false;
    produto.querySelector('.menos').hidden = false;
    produto.querySelector('.mais').addEventListener('click', function () { alterarQuantidade(produto, 1); });
    produto.querySelector('.menos').addEventListener('click', function () { alterarQuantidade(produto, -1); });
    input.addEventListener('input', atualizarResumo);
    input.addEventListener('change', function () {
      sincronizarQuantidade(produto, true);
      atualizarResumo();
      avisar(produto.dataset.nome + ': ' + medida.format(quantidade(produto)) + ' ' + produto.dataset.unidade + '.');
    });
    sincronizarQuantidade(produto, true);
  });
  if (busca) {
    form.querySelector('.ferramentas-catalogo').hidden = false;
    busca.addEventListener('input', filtrar);
    limpar.addEventListener('click', function () { busca.value = ''; filtrar(); busca.focus(); });
    document.getElementById('resetar-filtros').addEventListener('click', function () { resetarFiltros(); });
    filtros.forEach(function (botao) {
      botao.addEventListener('click', function () {
        categoriaAtiva = botao.dataset.categoria;
        filtros.forEach(function (outro) { outro.classList.toggle('ativa', outro === botao); outro.setAttribute('aria-pressed', String(outro === botao)); });
        filtrar();
      });
    });
  }
  entrega.addEventListener('change', atualizarEntrega);
  document.getElementById('cep').addEventListener('input', function () {
    const numeros = this.value.replace(/\D/g, '').slice(0, 8);
    this.value = numeros.length > 5 ? numeros.slice(0, 5) + '-' + numeros.slice(5) : numeros;
  });
  const tituloCheckout = document.getElementById('titulo-checkout');
  tituloCheckout.tabIndex = -1;
  revisar.addEventListener('click', function () {
    if (revisar.disabled) return;
    document.getElementById('checkout').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    tituloCheckout.focus({ preventScroll: true });
  });
  form.addEventListener('invalid', function (evento) {
    const campo = evento.target;
    // Um produto com quantidade inválida pode estar escondido pela busca.
    // Revela o campo antes de o navegador tentar focá-lo, sem perder os itens.
    if (campo.closest('.produto')) resetarFiltros(false);
    campo.setAttribute('aria-invalid', 'true');
    camposInvalidos.add(campo);
    atualizarValidacao();
  }, true);
  form.addEventListener('input', atualizarValidacao);
  entrega.addEventListener('change', atualizarValidacao);
  form.addEventListener('submit', function (evento) {
    if (enviando || !produtos.some(function (produto) { return quantidade(produto) > 0; })) { evento.preventDefault(); return; }
    // Campos permanecem habilitados para que o navegador envie todas as quantidades.
    enviando = true;
    confirmar.textContent = 'Enviando seu pedido…';
    form.setAttribute('aria-busy', 'true');
    atualizarResumo();
    avisar('Enviando seu pedido. Aguarde a confirmação.');
  });
  window.addEventListener('pageshow', function (evento) {
    if (!evento.persisted) return;
    enviando = false;
    form.removeAttribute('aria-busy');
    confirmar.textContent = 'Confirmar meu pedido →';
    atualizarEntrega();
  });
  document.getElementById('carrinho').hidden = false;
  document.getElementById('valores-pedido').hidden = false;
  document.getElementById('barra-pedido').hidden = produtos.length === 0;
  document.body.classList.add('js-pronto');
  atualizarEntrega();
  const erro = document.getElementById('erro-pedido');
  if (erro) erro.focus();
})();
