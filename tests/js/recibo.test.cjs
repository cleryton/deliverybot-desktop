'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const code = fs.readFileSync(require('node:path').join(__dirname, '../../web/static/recibo.js'), 'utf8');

test('impressão somente por ação do cliente, sem envio de rede', () => {
  let impressoes = 0;
  const eventos = {};
  const botao = {hidden: true, addEventListener: (nome, fn) => { eventos[nome] = fn; }};
  vm.runInNewContext(code, {document: {getElementById: () => botao}, window: {print: () => { impressoes++; }}});
  assert.equal(botao.hidden, false);
  assert.equal(impressoes, 0);
  eventos.click();
  assert.equal(impressoes, 1);
});

test('não oferece controle sem impressão disponível e aceita página sem recibo', () => {
  const botao = {hidden: true, addEventListener: () => assert.fail('Não registrar impressão indisponível')};
  vm.runInNewContext(code, {document: {getElementById: () => botao}, window: {}});
  assert.equal(botao.hidden, true);
  vm.runInNewContext(code, {document: {getElementById: () => null}, window: {print: () => assert.fail()}});
});
