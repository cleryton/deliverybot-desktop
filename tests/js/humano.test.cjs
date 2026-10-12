const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../../web/static/humano.js'), 'utf8');

function painel(admin = false) {
  const handlers = {}, calls = [];
  const form = {elements: {telefone: {value: ''}}, addEventListener() {}};
  const elements = {
    '#human-form': form, '#human-list': {}, '#human-chat': {},
    '#human-refresh': {addEventListener(event, callback) {handlers[event] = callback;}}
  };
  const state = {lista: [], mensagens: []};
  const context = vm.createContext({
    isAdmin: admin, $: selector => elements[selector],
    document: {addEventListener() {}},
    api: async route => {calls.push(route); return route === 'humano' ? state.lista : state.mensagens;},
    escapeHTML: value => String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;'),
    run: async (button, fn) => fn(), toast() {}, confirm: () => false,
  });
  vm.runInContext(source, context);
  return {context, handlers, calls, state, elements, form};
}

test('atualizar renova lista e conversa selecionada com telefone codificado', async () => {
  const p = painel();
  p.form.elements.telefone.value = '+55 11';
  p.state.mensagens = [{direcao: 'ENTRADA', conteudo: '<texto literal> novo'}];
  await p.handlers.click({target: {}});
  assert.deepEqual(p.calls.slice(-2), ['humano', 'humano?telefone=%2B55%2011']);
  assert.equal(p.elements['#human-chat'].textContent, 'Cliente: <texto literal> novo');
});

test('atualizar sem seleção não consulta conversa inexistente', async () => {
  const p = painel();
  await p.handlers.click({target: {}});
  assert.ok(p.calls.every(route => route === 'humano'));
});

test('pendência automática orienta conferência e escapa dados do contato', async () => {
  const p = painel();
  p.state.lista = [{nome: '<cliente>', telefone: '55119999', estado: 'ASSUMIDO', envios_para_conferir: 2}];
  await p.context.humanos();
  const html = p.elements['#human-list'].innerHTML;
  assert.match(html, /2 envio\(s\) automático\(s\) para conferir/);
  assert.match(html, /Você pode responder manualmente/);
  assert.ok(html.includes('&lt;cliente>') && !html.includes('<cliente>'));
  assert.ok(!html.includes('Revisar e liberar IA'));
});

test('sem pendências não mostra advertência e revisão da IA continua só para administrador', async () => {
  for (const admin of [false, true]) {
    const p = painel(admin);
    p.state.lista = [{nome: 'Cliente', telefone: '55119999', estado: 'ASSUMIDO', envios_para_conferir: 0, bloqueio_ia: 'REGRAS', motivo_bloqueio: '<motivo>'}];
    await p.context.humanos();
    const html = p.elements['#human-list'].innerHTML;
    assert.ok(!html.includes('envio(s) automático(s)'));
    assert.equal(html.includes('Revisar e liberar IA'), admin);
    assert.ok(html.includes('&lt;motivo>'));
  }
});
