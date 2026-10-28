const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const nav = require('../../web/static/navegacao.js');

// DOM fictício em memória; os eventos e o envio da gestão vêm do script real.
function painel() {
  const elementos = new Map(), eventos = {}, tarefas = [], chamadas = [];
  function elemento(dados = {}) {
    const atributos = new Map();
    const e = {dataset: {}, value: '', textContent: '', innerHTML: '', hidden: false,
      classList: {add() {}, remove() {}, toggle() {}, contains() { return false; }},
      setAttribute(k, v) { atributos.set(k, v); }, getAttribute(k) { return atributos.get(k) ?? null; },
      removeAttribute(k) { atributos.delete(k); }, addEventListener() {},
      querySelectorAll() { return []; }, querySelector() { return null; },
      focus() {}, scrollIntoView() {}, reset() {}, ...dados};
    e.elements = new Proxy({}, {get(o, k) { return o[k] ||= elemento(); }});
    return e;
  }
  const $ = seletor => {
    if (!elementos.has(seletor)) elementos.set(seletor, elemento());
    return elementos.get(seletor);
  };
  const contexto = vm.createContext({
    DeliveryNav: nav, DeliveryUX: {pedidos: itens => itens, texto: String},
    document: {body: {dataset: {admin: 'true'}, classList: elemento().classList},
      querySelector: $, querySelectorAll: () => [], visibilityState: 'visible',
      addEventListener(tipo, fn) { (eventos[tipo] ||= []).push(fn); }},
    window: {addEventListener() {}, scrollTo() {}},
    matchMedia: () => ({matches: false, addEventListener() {}}),
    setInterval() {}, setTimeout() {}, clearTimeout() {},
    confirm: () => true, FormData: class {}, Option: class {}, FileReader: class {},
    fetch: () => assert.fail('Nenhuma requisição real é permitida.')
  });
  vm.runInContext(fs.readFileSync(require.resolve('../../web/static/gestao.js'), 'utf8'), contexto);
  contexto.run = (_, acao) => { const tarefa = acao(); tarefas.push(tarefa); return tarefa; };
  contexto.api = async (rota, metodo, dados) => { chamadas.push({rota, metodo, dados}); return {}; };
  contexto.toast = () => {};
  contexto.reload = async () => {};
  return {contexto, $, chamadas,
    exec: texto => vm.runInContext(texto, contexto),
    async clicar(dataset) {
      const botao = elemento({dataset});
      const alvo = {closest: seletor => seletor === 'button' ? botao : null};
      for (const fn of eventos.click || []) fn({target: alvo});
      await Promise.all(tarefas.splice(0));
    }};
}

for (const status of ['RECEBIDO', 'CONFIRMADO', 'EM_PREPARO', 'PRONTO']) {
  test(`os botões de ${status} enviam o estado da tela que originou a ação`, async () => {
    const a = painel();
    a.exec(`state.orders=[{id:7,status:'${status}',numero_pedido:'#12345678',itens:[],total_pedido:12}];renderOrders()`);
    const html = a.$('#order-list').innerHTML;
    assert.match(html, new RegExp(`data-advance="7" data-status="${status}"`));
    assert.match(html, new RegExp(`data-cancel="7" data-status="${status}"`));
    // Uma atualização no estado em memória não transforma o botão antigo
    // em autorização para avançar mais uma etapa.
    a.exec("state.orders[0].status='PRONTO'");
    await a.clicar({advance: '7', status});
    await a.clicar({cancel: '7', status});
    assert.equal(a.chamadas.length, 2);
    assert.equal(a.chamadas[0].rota, 'pedidos/7/avancar');
    assert.equal(a.chamadas[1].rota, 'pedidos/7/cancelar');
    for (const chamada of a.chamadas) {
      assert.equal(chamada.metodo, 'POST');
      assert.equal(chamada.dados.status, status);
    }
  });
}

test('pedido finalizado não oferece avanço ou cancelamento', () => {
  const a = painel();
  a.exec("state.orders=[{id:7,status:'RETIRADO',numero_pedido:'#12345678',itens:[],total_pedido:12}];renderOrders()");
  assert.doesNotMatch(a.$('#order-list').innerHTML, /data-advance|data-cancel/);
});
