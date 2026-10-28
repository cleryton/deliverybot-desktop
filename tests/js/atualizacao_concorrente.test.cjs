const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ux = require('../../web/static/experiencia.js');
const esperar = () => new Promise(resolve => setImmediate(resolve));
function pendencia() {
  let resolver, rejeitar;
  const promessa = new Promise((resolve, reject) => { resolver = resolve; rejeitar = reject; });
  return {promessa, resolver, rejeitar};
}
function publicacao(overrides = {}) {
  return {estado: 'DESLIGADO', mensagem: 'Desligado', disponivel: true, ativo: false,
    url: '', porta: 5051, porta_configurada: 5051, modo_configurado: 'RAPIDO',
    automatico: false, dominio: '', token_configurado: false, ...overrides};
}
function atualizacao(overrides = {}) {
  return {atual: '2.47.0', automatica: false, tarefa: null,
    release: {nova: true, versao: '2.47.1', mensagem: 'Disponível'},
    download: {assinatura_confiavel: true, caminho: ''}, ...overrides};
}
function ambiente(arquivo, responder, pagina) {
  const elementos = new Map(), chamadas = [], intervalos = [], acoes = [], erros = [];
  function $(seletor) {
    if (!elementos.has(seletor)) {
      const atributos = new Map(), classes = new Set();
      elementos.set(seletor, {
        tagName: 'BUTTON', value: '', checked: false, disabled: false, hidden: false,
        textContent: '', innerHTML: '', elements: {}, eventos: {}, dataset: {},
        addEventListener(tipo, fn) { this.eventos[tipo] = fn; },
        setAttribute(nome, valor) { atributos.set(nome, String(valor)); },
        getAttribute(nome) { return atributos.get(nome) ?? null; },
        removeAttribute(nome) { atributos.delete(nome); },
        classList: {add: nome => classes.add(nome), remove: nome => classes.delete(nome)},
        focus() {}, select() {}, reset() {}
      });
    }
    return elementos.get(seletor);
  }
  const documento = {visibilityState: 'visible', addEventListener() {}};
  const contexto = vm.createContext({$, DeliveryUX: ux, isAdmin: true, state: {page: pagina},
    document: documento, window: {}, confirm: () => true,
    api: (rota, metodo = 'GET', dados) => {
      chamadas.push({rota, metodo, dados});
      if (rota === 'operadores' || rota === 'operadores/auditoria') return Promise.resolve([]);
      return Promise.resolve(responder(rota, metodo, dados));
    },
    run: (botao, acao) => {
      const tarefa = ux.ocupado(botao, acao).catch(erro => erros.push(erro.message));
      acoes.push(tarefa); return tarefa;
    },
    toast() {}, escapeHTML: String, date: String,
    setInterval(fn, ms) { intervalos.push({fn, ms}); },
    fetch() { assert.fail('Este ensaio não acessa serviços reais.'); }
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../../web/static', arquivo), 'utf8'), contexto);
  function disparar(seletor, tipo, extras = {}) {
    const alvo = $(seletor);
    alvo.eventos[tipo]({target: alvo, currentTarget: alvo, preventDefault() {}, ...extras});
    return acoes.at(-1);
  }
  return {$, chamadas, intervalos, erros, documento, disparar};
}

test('leituras simultâneas compartilham transporte sem guardar resultado depois de concluir', async () => {
  let quantidade = 0;
  const primeira = pendencia(), exibidos = [];
  const consulta = ux.consultaAtual(() => { quantidade++; return primeira.promessa; }, r => exibidos.push(r));
  const a = consulta.consultar(), b = consulta.consultar();
  assert.equal(a, b); await esperar(); assert.equal(quantidade, 1);
  primeira.resolver('primeira'); await a;
  await consulta.consultar(); assert.equal(quantidade, 2);
  assert.deepEqual(exibidos, ['primeira', 'primeira']);
});

test('invalidar descarta aplicação antiga sem soltar a trava da nova leitura pendente', async () => {
  const antiga = pendencia(), nova = pendencia(), exibidos = [];
  let quantidade = 0;
  const consulta = ux.consultaAtual(() => (++quantidade === 1 ? antiga : nova).promessa, r => exibidos.push(r));
  const a = consulta.consultar(); await esperar(); consulta.invalidar();
  const b = consulta.consultar(); await esperar(); antiga.resolver('antiga'); await a;
  assert.equal(consulta.consultar(), b); assert.equal(quantidade, 2);
  nova.resolver('nova'); await b; assert.deepEqual(exibidos, ['nova']);
});

test('erro de leitura libera a próxima consulta sem tentativa automática', async () => {
  let quantidade = 0;
  const consulta = ux.consultaAtual(() => { quantidade++; throw new Error('Falha fictícia'); }, () => {});
  await assert.rejects(consulta.consultar(), /Falha fictícia/);
  assert.equal(quantidade, 1);
  await assert.rejects(consulta.consultar(), /Falha fictícia/); assert.equal(quantidade, 2);
});

test('falha antiga invalidada não alerta depois de uma consulta atual bem-sucedida', async () => {
  const antiga = pendencia(), exibidos = []; let quantidade = 0;
  const consulta = ux.consultaAtual(() => ++quantidade === 1 ? antiga.promessa : 'atual', r => exibidos.push(r));
  const primeira = consulta.consultar(); await esperar(); consulta.invalidar();
  await consulta.consultar(); antiga.rejeitar(new Error('Falha antiga fictícia'));
  assert.equal(await primeira, undefined); assert.deepEqual(exibidos, ['atual']);
});

test('polls lentos da publicação fazem um único GET e não consultam em aba oculta', async () => {
  const leitura = pendencia();
  const a = ambiente('publicacao.js', () => leitura.promessa, 'publicacao');
  await esperar(); for (let i = 0; i < 10; i++) a.intervalos[0].fn();
  await esperar(); assert.equal(a.chamadas.length, 1);
  leitura.resolver(publicacao()); await esperar();
  a.documento.visibilityState = 'hidden'; a.intervalos[0].fn(); await esperar();
  assert.equal(a.chamadas.length, 1);
});

test('estado da publicação anterior ao POST não sobrescreve a leitura nova', async () => {
  const antiga = pendencia(), escrita = pendencia(), nova = pendencia();
  let leituras = 0;
  const a = ambiente('publicacao.js', (_, metodo) => metodo === 'POST' ? escrita.promessa :
    (++leituras === 1 ? antiga : nova).promessa, 'publicacao');
  await esperar();
  const acao = a.disparar('#public-stop', 'click'); await esperar();
  for (let i = 0; i < 5; i++) a.intervalos[0].fn();
  await esperar(); assert.equal(leituras, 1);
  escrita.resolver({}); await esperar(); assert.equal(leituras, 2);
  nova.resolver(publicacao({mensagem: 'Parada confirmada'})); await acao;
  antiga.resolver(publicacao({ativo: true, estado: 'ONLINE', mensagem: 'Estado antigo'})); await esperar();
  assert.equal(a.$('#public-status').textContent, 'Parada confirmada');
  assert.equal(a.$('#public-stop').disabled, true); assert.deepEqual(a.erros, []);
});

test('publicação mantém campos e token digitados enquanto o PUT está em andamento', async () => {
  const escrita = pendencia(); let estado = publicacao();
  const a = ambiente('publicacao.js', (_, metodo) => metodo === 'PUT' ? escrita.promessa : estado, 'publicacao');
  await esperar();
  a.$('#public-token').value = 'token-ficticio-enviado'; a.$('#public-domain').value = 'https://antes.example';
  a.disparar('#public-form', 'input');
  const acao = a.disparar('#public-form', 'submit', {submitter: a.$('#public-save')}); await esperar();
  a.$('#public-token').value = 'novo-token-ficticio'; a.$('#public-domain').value = 'https://depois.example';
  a.disparar('#public-form', 'input');
  estado = publicacao({dominio: 'https://antes.example', token_configurado: true}); escrita.resolver({}); await acao;
  assert.equal(a.$('#public-token').value, 'novo-token-ficticio');
  assert.equal(a.$('#public-domain').value, 'https://depois.example');
  assert.equal(a.chamadas.filter(c => c.metodo === 'PUT').length, 1);
});

test('primeira leitura da publicação também preserva digitação iniciada antes da resposta', async () => {
  const leitura = pendencia(); const a = ambiente('publicacao.js', () => leitura.promessa, 'publicacao');
  a.$('#public-domain').value = 'https://digitado.example'; a.disparar('#public-form', 'input');
  leitura.resolver(publicacao({dominio: 'https://salvo.example'})); await esperar();
  assert.equal(a.$('#public-domain').value, 'https://digitado.example');
});

test('falha de escrita da publicação consulta o estado sem repetir o PUT e conserva o erro original', async () => {
  const a = ambiente('publicacao.js', (_, metodo) => {
    if (metodo === 'PUT') throw new Error('Falha fictícia no envio');
    return publicacao();
  }, 'publicacao'); await esperar();
  a.$('#public-domain').value = 'https://digitado.example'; a.disparar('#public-form', 'input');
  await a.disparar('#public-form', 'submit', {submitter: a.$('#public-save')});
  assert.equal(a.chamadas.filter(c => c.metodo === 'PUT').length, 1);
  assert.equal(a.chamadas.filter(c => c.metodo === 'GET').length, 2);
  assert.deepEqual(a.erros, ['Falha fictícia no envio']);
  assert.equal(a.$('#public-domain').value, 'https://digitado.example');
});

test('polls de atualizações compartilham leitura lenta e param em aba oculta', async () => {
  const leitura = pendencia(); const a = ambiente('administracao.js', () => leitura.promessa, 'atualizacoes');
  await esperar(); for (let i = 0; i < 10; i++) a.intervalos[0].fn(); await esperar();
  assert.equal(a.chamadas.filter(c => c.rota === 'atualizacoes').length, 1);
  leitura.resolver(atualizacao()); await esperar();
  a.documento.visibilityState = 'hidden'; a.intervalos[0].fn(); await esperar();
  assert.equal(a.chamadas.filter(c => c.rota === 'atualizacoes').length, 1);
});

test('checkbox de atualização não regride com GET iniciado antes de salvar preferência', async () => {
  const antiga = pendencia(), escrita = pendencia(), nova = pendencia(); let leituras = 0;
  const a = ambiente('administracao.js', (_, metodo) => metodo === 'PUT' ? escrita.promessa :
    (++leituras === 1 ? antiga : nova).promessa, 'atualizacoes'); await esperar();
  a.$('#update-auto').checked = true;
  const acao = a.disparar('#update-auto', 'change'); await esperar();
  assert.equal(a.$('#update-auto').disabled, true);
  a.intervalos[0].fn(); await esperar(); assert.equal(leituras, 1);
  escrita.resolver({}); await esperar(); nova.resolver(atualizacao({automatica: true})); await acao;
  antiga.resolver(atualizacao({automatica: false})); await esperar();
  assert.equal(a.$('#update-auto').checked, true);
  assert.equal(a.$('#update-auto').disabled, false);
});

test('atualizações impedem operações concorrentes diferentes e não apagam uma nova senha', async () => {
  const escrita = pendencia(); let pendente = false;
  const a = ambiente('administracao.js', (_, metodo) => {
    if (metodo === 'POST') { pendente = true; return escrita.promessa; }
    return atualizacao({tarefa: pendente ? {estado: 'EXECUTANDO', mensagem: 'Preparando'} : null});
  }, 'atualizacoes'); await esperar();
  const campo = a.$('#update-form').elements.senha = {value: 'senha-ficticia-enviada'};
  const acao = a.disparar('#update-form', 'submit', {submitter: a.$('#update-download')}); await esperar();
  await a.disparar('#update-check', 'click'); campo.value = 'nova-senha-ficticia';
  escrita.resolver({}); await acao;
  assert.equal(a.chamadas.filter(c => c.metodo === 'POST').length, 1);
  assert.equal(campo.value, 'nova-senha-ficticia');
  assert.equal(a.$('#update-download').disabled, true);
  assert.match(a.erros[0], /Aguarde/);
});
