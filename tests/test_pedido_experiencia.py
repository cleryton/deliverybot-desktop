"""Recuperação acessível de erros no checkout, sem persistir rascunhos pessoais."""
import re
from html.parser import HTMLParser
from unittest.mock import Mock

import pytest

from src import config, estoque, publicacao, viacep, whatsapp
from src.db import get_conn, init_db
from src.links import gerar_link_pedido, obter_link

BASE = 'https://checkout-ficticio.example'


class Campos(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.ids = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids[attrs['id']] = attrs


def csrf(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html)[1]


@pytest.fixture
def loja(tmp_path, monkeypatch):
    for campo, valor in {
        'DATABASE_PATH': str(tmp_path / 'experiencia-ficticia.db'),
        'MODO_TESTE': False, 'SEED_CATALOGO': False,
        'WHATSAPP_PROVIDER': 'TESTE', 'IA_PROVIDER': '',
        'BASE_URL': BASE, 'FORMAS_PAGAMENTO': 'Pix,Dinheiro',
    }.items():
        monkeypatch.setattr(config, campo, valor)
    monkeypatch.setattr(publicacao, '_gerente', None)
    envio = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', envio)
    init_db(seed_cardapio=False)
    from src.app import app
    produtos = [estoque.salvar_produto({'nome': nome, 'categoria': 'Teste',
                                      'preco': 12, 'estoque': 10})
                for nome in ('Lanche fictício', 'Suco fictício')]
    cliente = app.test_client()
    url = '/m/' + gerar_link_pedido('5500000000003').rsplit('/', 1)[-1]
    pagina = cliente.get(url, base_url=BASE)
    dados = {'csrf_token': csrf(pagina.text), 'nome': 'Pessoa fictícia',
             'forma_pagamento': 'Pix', 'forma_entrega': 'ENTREGA',
             'cep': '00000-000', 'numero': '123', 'complemento': 'Bloco fictício',
             'qtd_' + str(produtos[0]['id']): '5', 'qtd_' + str(produtos[1]['id']): '2'}
    monkeypatch.setattr(viacep, 'validar_area_entrega', lambda cep: (True, '', {}))
    monkeypatch.setattr(viacep, 'endereco_formatado', lambda dados: 'Rua fictícia')
    return cliente, produtos, url, dados, envio


def sem_compra(loja):
    cliente, _, url, _, envio = loja
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0] == 0
    assert not obter_link(url.rsplit('/', 1)[-1])['usado']
    envio.assert_not_called()
    with cliente.session_transaction(base_url=BASE) as sessao:
        assert 'Pessoa fictícia' not in str(dict(sessao))
        assert 'Bloco fictício' not in str(dict(sessao))


@pytest.mark.parametrize('campo', ['cep', 'numero'])
def test_erro_de_endereco_aponta_correcao_e_conserva_dados_e_selecao(loja, monkeypatch, campo):
    cliente, produtos, url, dados, _ = loja
    if campo == 'cep':
        monkeypatch.setattr(viacep, 'validar_area_entrega', lambda cep: (False, 'CEP fora da área de entrega.', {}))
    else:
        dados['numero'] = ''
    resposta = cliente.post(url, base_url=BASE, data=dados)
    assert resposta.status_code == 400
    campos = Campos(resposta.text).ids
    assert campos['erro-pedido']['data-campo-erro'] == campo
    assert f'href="#{campo}"' in resposta.text
    for nome in ('nome', 'cep', 'numero', 'complemento'):
        assert campos[nome]['value'] == dados[nome]
    for produto in produtos:
        assert campos['qtd-' + str(produto['id'])]['value'] == dados['qtd_' + str(produto['id'])]
    assert '<option value="Pix" selected>' in resposta.text
    assert '<option value="ENTREGA" selected>' in resposta.text
    sem_compra(loja)


def test_estoque_mudou_mostra_limite_sem_reescrever_escolha_e_permite_corrigir(loja):
    cliente, produtos, url, dados, _ = loja
    pid = produtos[0]['id']
    with get_conn() as conn:
        conn.execute('UPDATE produtos SET estoque=1 WHERE id=?', (pid,))
    resposta = cliente.post(url, base_url=BASE, data=dados)
    assert resposta.status_code == 400
    campos = Campos(resposta.text).ids
    assert campos['qtd-' + str(pid)]['value'] == '5'
    assert float(campos['qtd-' + str(pid)]['max']) == 1
    assert campos['erro-pedido']['data-campo-erro'] == 'qtd-' + str(pid)
    sem_compra(loja)
    dados.update({'csrf_token': csrf(resposta.text), 'qtd_' + str(pid): '1', 'preco': '0.01'})
    assert cliente.post(url, base_url=BASE, data=dados).status_code == 303
    with get_conn() as conn:
        assert conn.execute('SELECT total_itens FROM pedidos').fetchone()[0] == 36
    assert cliente.post(url, base_url=BASE, data=dados).status_code == 410


def test_item_que_saiu_do_catalogo_e_avisado_sem_perder_outros_itens(loja):
    cliente, produtos, url, dados, _ = loja
    with get_conn() as conn:
        conn.execute('UPDATE produtos SET ativo=0 WHERE id=?', (produtos[0]['id'],))
    resposta = cliente.post(url, base_url=BASE, data=dados)
    assert resposta.status_code == 400
    assert '1 item ficou indisponível e saiu da seleção' in resposta.text
    campos = Campos(resposta.text).ids
    assert 'qtd-' + str(produtos[0]['id']) not in campos
    assert campos['qtd-' + str(produtos[1]['id'])]['value'] == '2'
    assert campos['nome']['value'] == 'Pessoa fictícia'
    sem_compra(loja)


def test_nome_longo_volta_ao_formulario_escapado_em_vez_de_pagina_vazia(loja):
    cliente, _, url, dados, _ = loja
    dados['nome'] = '<script>alert(1)</script>' + 'a' * 160
    resposta = cliente.post(url, base_url=BASE, data=dados)
    assert resposta.status_code == 400
    campos = Campos(resposta.text).ids
    assert campos['erro-pedido']['data-campo-erro'] == 'nome'
    assert campos['nome']['value'] == dados['nome'][:160]
    assert '<script>alert(1)</script>' not in resposta.text
    sem_compra(loja)
