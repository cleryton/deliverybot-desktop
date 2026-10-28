const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const codigo = fs.readFileSync(path.join(__dirname, '../../web/static/administracao.js'), 'utf8');
const esperar = () => new Promise(resolve => setImmediate(resolve));
function ambiente(admin = false) {
  const elementos = new Map(), chamadas = [], intervalos = [], erros = [], navegacoes = [];
  const $ = seletor => {
    if (!elementos.has(seletor)) elementos.set(seletor, {
      value: '', checked: false, textContent: '', innerHTML: '', disabled: false,
      content: 'csrf-ficticio', eventos: {}, elements: {}, resets: 0,
      addEventListener(nome, fn) { this.eventos[nome] = fn; },
      reset() { this.resets++; }, showModal() { this.aberto = true; }
    });
    return elementos.get(seletor);
  };
  const respostas = {
    operadores: [{id: 1, nome: '<img onerror=alert(1)>', login: 'teste', perfil: 'ADMIN', ativo: 1}],
    'operadores/auditoria': [{operador: '<operador>', acao: '<alteracao>', objeto: '<conta>', criado_em: '2026-01-01'}],
    atualizacoes: {atual: '1.0.0', automatica: false, tarefa: null,
      release: {nova: true, versao: '1.0.1', mensagem: 'Disponível'},
      download: {assinatura_confiavel: false, caminho: ''}}
  };
  const c = vm.createContext({$, isAdmin: admin, state: {page: 'inicio'}, DeliveryUX: require('../../web/static/experiencia.js'),
    document: {visibilityState: 'visible'}, window: {}, confirm: () => true,
    location: {reload() { navegacoes.push('reload'); }, assign(url) { navegacoes.push(url); }},
    setInterval(fn, ms) { intervalos.push({fn, ms}); }, date: String,
    escapeHTML: valor => String(valor).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;'),
    FormData: class { constructor(form) { return form.entradas; } },
    toast() {}, run: async (_, fn) => { try { return await fn(); } catch (e) { erros.push(e.message); } },
    api: async (rota, metodo, dados) => { chamadas.push({rota, metodo, dados}); return respostas[rota] || {}; },
    fetch: async (url, opcoes) => { chamadas.push({url, opcoes}); return {ok: true}; }
  });
  vm.runInContext(codigo, c);
  const evento = async (seletor, nome, extras = {}) => {
    const alvo = $(seletor);
    await alvo.eventos[nome]({target: alvo, currentTarget: alvo, submitter: {}, preventDefault() {}, ...extras});
    await esperar();
  };
  return {c, $, chamadas, respostas, erros, intervalos, navegacoes, evento};
}

test('painel não administrativo não inicia consultas de contas nem de atualizações', async () => {
  const a = ambiente(); await esperar();
  assert.equal(a.chamadas.length, 0);
  assert.equal(a.intervalos.length, 0);
});

test('contas e auditoria escapam textos; atualização sem assinatura bloqueia instalação', async () => {
  const a = ambiente(true); await esperar();
  assert.deepEqual(a.chamadas.map(x => x.rota).sort(), ['atualizacoes', 'operadores', 'operadores/auditoria']);
  assert.match(a.$('#operator-list').innerHTML, /&lt;img onerror=alert\(1\)&gt;/);
  assert.ok(!a.$('#operator-audit').innerHTML.includes('<alteracao>'));
  assert.equal(a.$('#update-install').disabled, true);
  assert.equal(a.$('#update-download').disabled, false);
  assert.deepEqual(a.erros, []);
});

test('cadastro de funcionário conserva envio, limpeza do formulário e atualização da lista', async () => {
  const a = ambiente(); a.$('#operator-form').entradas = [['nome', 'Fictício'], ['login', 'teste'], ['perfil', 'CAIXA']];
  await a.evento('#operator-form', 'submit');
  assert.equal(a.chamadas[0].metodo, 'POST');
  assert.equal(a.chamadas[0].dados.perfil, 'CAIXA');
  assert.equal(a.$('#operator-form').resets, 1);
  assert.ok(a.chamadas.some(x => x.rota === 'operadores/auditoria'));
  assert.deepEqual(a.erros, []);
});

test('edição de conta preserva vínculo, perfil e valor booleano de ativação', async () => {
  const a = ambiente(), f = a.$('#operator-edit-form');
  f.elements = {id: {value: ''}, perfil: {value: ''}, ativo: {checked: false}, senha: {value: 'senha-ficticia'}};
  await a.evento('#operator-list', 'click', {target: {closest: () => ({dataset: {operador: '7', perfil: 'CAIXA', ativo: '1'}})}});
  assert.equal(a.$('#operator-edit').aberto, true);
  assert.equal(f.elements.ativo.checked, true);
  f.elements.ativo.checked = false;
  await a.evento('#operator-edit-form', 'submit');
  assert.equal(a.chamadas[0].rota, 'operadores/7');
  assert.equal(a.chamadas[0].dados.ativo, false);
  assert.equal(a.chamadas[0].dados.perfil, 'CAIXA');
  assert.deepEqual(a.navegacoes, ['reload']);
});

test('saída da conta usa POST e CSRF antes de navegar', async () => {
  const a = ambiente(); await a.evento('#operator-logout', 'click');
  assert.equal(a.chamadas[0].url, '/gestao/sair');
  assert.equal(a.chamadas[0].opcoes.method, 'POST');
  assert.equal(a.chamadas[0].opcoes.headers['X-CSRF-Token'], 'csrf-ficticio');
  assert.deepEqual(a.navegacoes, ['/gestao']);
});

test('consulta periódica só acontece com a página de atualizações visível', async () => {
  const a = ambiente(true); await esperar(); a.chamadas.length = 0;
  assert.equal(a.intervalos.length, 1);
  a.intervalos[0].fn(); await esperar(); assert.equal(a.chamadas.length, 0);
  a.c.state.page = 'atualizacoes'; a.c.document.visibilityState = 'hidden';
  a.intervalos[0].fn(); await esperar(); assert.equal(a.chamadas.length, 0);
  a.c.document.visibilityState = 'visible'; a.intervalos[0].fn(); await esperar();
  assert.equal(a.chamadas.length, 1);
  assert.equal(a.chamadas[0].rota, 'atualizacoes');
});

test('download limpa a senha do formulário e tarefa ativa desabilita novas operações', async () => {
  const a = ambiente(), f = a.$('#update-form');
  f.elements.senha = {value: 'senha-ficticia-backup'};
  a.respostas.atualizacoes.tarefa = {estado: 'EXECUTANDO', mensagem: 'Preparando'};
  await a.evento('#update-form', 'submit');
  assert.equal(a.chamadas[0].dados.acao, 'baixar');
  assert.equal(a.chamadas[0].dados.senha, 'senha-ficticia-backup');
  assert.equal(f.elements.senha.value, '');
  assert.equal(a.$('#update-download').disabled, true);
  assert.equal(a.$('#update-install').disabled, true);
});

test('instalação continua exigindo ponte do aplicativo e confirmação explícita', async () => {
  const a = ambiente(); let instalacoes = 0;
  await a.evento('#update-install', 'click');
  assert.match(a.erros[0], /Desktop/);
  a.c.window.pywebview = {api: {instalar_atualizacao: async () => { instalacoes++; }}};
  a.c.confirm = () => false; await a.evento('#update-install', 'click');
  assert.equal(instalacoes, 0);
  a.c.confirm = () => true; await a.evento('#update-install', 'click');
  assert.equal(instalacoes, 1);
});
