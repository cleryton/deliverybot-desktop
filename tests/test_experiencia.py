"""Controles devem estar na página certa, sem esconder operações diárias."""
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Estrutura(HTMLParser):
    vazios = {'input', 'meta', 'link', 'img', 'br', 'hr', 'source'}

    def __init__(self, texto):
        super().__init__()
        self.pilha = []
        self.elementos = {}
        self.ordem = []
        self.scripts = []
        self.feed(texto)

    def handle_starttag(self, tag, attrs):
        if tag == 'option' and self.pilha and self.pilha[-1][0] == 'option':
            self.pilha.pop()
        atributos = dict(attrs)
        identificador = atributos.get('id')
        if identificador:
            assert identificador not in self.elementos, f'ID repetido: {identificador}'
            self.elementos[identificador] = (atributos, [a.get('id') for _, a in self.pilha])
            self.ordem.append(identificador)
        if tag == 'script':
            self.scripts.append(atributos.get('src', ''))
        if tag not in self.vazios:
            self.pilha.append((tag, atributos))

    def handle_endtag(self, tag):
        if tag in {'select', 'datalist'} and self.pilha and self.pilha[-1][0] == 'option':
            self.pilha.pop()
        assert self.pilha and self.pilha[-1][0] == tag, f'Fechamento fora de ordem: {tag}'
        self.pilha.pop()


def tela():
    return Estrutura((ROOT / 'web/templates/gestao.html').read_text(encoding='utf-8'))


def test_pedidos_filtros_e_atualizacao_na_mesma_pagina():
    s = tela()
    for identificador in ('order-list', 'order-search', 'order-filter', 'order-count', 'order-sync'):
        assert 'page-pedidos' in s.elementos[identificador][1]
        assert 'catalog-tools' not in s.elementos[identificador][1]


def test_catalogo_prioriza_busca_e_produtos_sem_ocultar_as_ferramentas():
    s = tela()
    for identificador in ('search', 'filter', 'product-list', 'products-clear'):
        assert 'page-produtos' in s.elementos[identificador][1]
        assert 'catalog-tools' not in s.elementos[identificador][1]
    assert s.ordem.index('product-list') < s.ordem.index('catalog-tools')
    for identificador in ('document-file', 'catalog-pdf-download', 'catalog-preview', 'catalog-import'):
        assert 'catalog-tools' in s.elementos[identificador][1]
    assert 'data-admin-only' in s.elementos['catalog-tools'][0]


def test_interface_carrega_dependencia_antes_do_painel_e_tem_estado_acessivel():
    s = tela()
    assert next(i for i, src in enumerate(s.scripts) if 'experiencia.js' in src) < next(i for i, src in enumerate(s.scripts) if 'gestao.js' in src)
    assert s.elementos['sync-status'][0]['role'] == 'status'
    assert s.elementos['product-save-status'][0]['aria-live'] == 'polite'
    assert s.elementos['menu-toggle'][0]['aria-controls'] == 'app-menu'
