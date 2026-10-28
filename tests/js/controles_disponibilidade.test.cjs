const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ux = require('../../web/static/experiencia.js');

// Executa os módulos reais com o mesmo wrapper ocupado do painel. Nenhum
// transporte, serviço, sessão ou arquivo de uso real participa destes ensaios.
function ambiente(arquivo, responder) {
  const elementos = new Map(), chamadas = [], pendentes = [], avisos = [];
  function $(seletor) {
    if (!elementos.has(seletor)) {
      const atributos = new Map(), classes = new Set();
      elementos.set(seletor, {
        tagName: 'BUTTON', value: '', textContent: '', innerHTML: '', checked: false,
        hidden: false, disabled: false, eventos: {}, elements: {}, dataset: {},
        addEventListener(tipo, fn) { this.eventos[tipo] = fn; },
        setAttribute(nome, valor) { atributos.set(nome, String(valor)); },
        getAttribute(nome) { return atributos.get(nome) ?? null; },
        removeAttribute(nome) { atributos.delete(nome); },
        classList: {add: nome => classes.add(nome), remove: nome => classes.delete(nome)},
        focus() {}, select() {}, closest() { return null; }, reset() {}
      });
    }
    return elementos.get(seletor);
  }
  const contexto = vm.createContext({
    $, DeliveryUX: ux, isAdmin: true, state: {page: 'inicio'},
    document: {visibilityState: 'visible', addEventListener() {}}, window: {},
    api: async (rota, metodo = 'GET', dados) => {
      chamadas.push({rota, metodo, dados});
      return responder(rota, metodo, dados);
    },
    run: (botao, acao) => {
      const tarefa = ux.ocupado(botao, acao);
      pendentes.push(tarefa);
      return tarefa;
    },
    toast: (mensagem, erro) => avisos.push({mensagem, erro}),
    escapeHTML: valor => String(valor), date: String, confirm: () => true,
    setInterval() {},
    fetch() { assert.fail('O teste não pode fazer requisições reais.'); }
  });
  const codigo = fs.readFileSync(path.join(__dirname, '../../web/static', arquivo), 'utf8');
  vm.runInContext(codigo, contexto);
  async function concluir() {
    await new Promise(resolve => setImmediate(resolve));
    while (pendentes.length) await Promise.all(pendentes.splice(0));
  }
  async function disparar(seletor, evento, extras = {}) {
    const alvo = $(seletor);
    alvo.eventos[evento]({target: alvo, currentTarget: alvo, preventDefault() {}, ...extras});
    await concluir();
  }
  return {$, chamadas, avisos, concluir, disparar};
}

test('iniciar página mantém o botão indisponível depois do wrapper enquanto o túnel inicia', async () => {
  const estado = {estado: 'DESLIGADO', mensagem: 'Desligado', disponivel: true,
    ativo: false, url: '', porta: 5051, porta_configurada: 5051,
    modo_configurado: 'RAPIDO', automatico: false, dominio: '', token_configurado: false};
  const a = ambiente('publicacao.js', (rota, metodo, dados) => {
    assert.equal(rota, 'pagina-publica');
    if (metodo === 'POST') {
      assert.equal(dados.acao, 'iniciar');
      Object.assign(estado, {estado: 'INICIANDO', ativo: true, mensagem: 'Iniciando em segundo plano'});
    }
    return structuredClone(estado);
  });
  await a.concluir();
  const iniciar = a.$('#public-start');
  assert.equal(iniciar.disabled, false);
  await a.disparar('#public-start', 'click');
  assert.equal(a.$('#public-state').textContent, 'Iniciando…');
  assert.equal(iniciar.getAttribute('aria-busy'), null);
  assert.equal(iniciar.disabled, true);
  assert.equal(a.$('#public-stop').disabled, false);
  assert.equal(a.$('#public-test').disabled, true);
  // Mesmo um disparo sintético repetido passa pelo bloqueio real do wrapper.
  await a.disparar('#public-start', 'click');
  assert.equal(a.chamadas.filter(c => c.metodo === 'POST').length, 1);
  assert.match(a.avisos[0].mensagem, /iniciando em segundo plano/);
});

test('download em execução continua indisponível após finalizar e não aceita segundo POST', async () => {
  const atualizacao = {atual: '2.46.0', automatica: false, tarefa: null,
    release: {nova: true, versao: '2.47.0', mensagem: 'Disponível'},
    download: {assinatura_confiavel: true, caminho: ''}};
  const a = ambiente('administracao.js', (rota, metodo, dados) => {
    if (rota === 'operadores' || rota === 'operadores/auditoria') return [];
    assert.equal(rota, 'atualizacoes');
    if (metodo === 'POST') {
      assert.equal(dados.acao, 'baixar');
      assert.equal(dados.senha, 'senha-ficticia-do-teste');
      atualizacao.tarefa = {estado: 'EXECUTANDO', mensagem: 'Preparando atualização'};
    }
    return structuredClone(atualizacao);
  });
  await a.concluir();
  const baixar = a.$('#update-download'), formulario = a.$('#update-form');
  formulario.elements.senha = {value: 'senha-ficticia-do-teste'};
  assert.equal(baixar.disabled, false);
  await a.disparar('#update-form', 'submit', {submitter: baixar});
  assert.equal(baixar.getAttribute('aria-busy'), null);
  assert.equal(baixar.disabled, true);
  assert.equal(a.$('#update-install').disabled, true);
  assert.equal(formulario.elements.senha.value, '');
  assert.equal(a.$('#update-status').textContent, 'Preparando atualização');
  await a.disparar('#update-form', 'submit', {submitter: baixar});
  assert.equal(a.chamadas.filter(c => c.metodo === 'POST').length, 1);
});
