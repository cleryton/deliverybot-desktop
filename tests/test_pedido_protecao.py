"""Integridade do formulário real, somente com banco e transporte fictícios."""
import re
from unittest.mock import Mock

import pytest
from werkzeug.datastructures import MultiDict

from src import config, estoque, publicacao, whatsapp
from src.db import get_conn, init_db
from src.links import gerar_link_pedido, obter_link

BASE = 'https://comercio-ficticio.example'


@pytest.fixture
def loja(tmp_path, monkeypatch):
    for campo, valor in {
        'DATABASE_PATH': str(tmp_path / 'pedido-ficticio.db'),
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
    produto = estoque.salvar_produto({'nome': 'Item fictício', 'categoria': 'Teste',
                                      'preco': 12, 'estoque': 10})
    caminhos = ['/m/' + gerar_link_pedido(telefone).rsplit('/', 1)[-1]
                for telefone in ('5500000000001', '5500000000002')]
    return app.test_client(), produto, caminhos, envio


def abrir(cliente, caminho):
    resposta = cliente.get(caminho, base_url=BASE)
    assert resposta.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', resposta.text)[1]


def dados(produto, csrf):
    return {'csrf_token': csrf, 'nome': 'Pessoa fictícia', 'forma_pagamento': 'Pix',
            'forma_entrega': 'RETIRADA BALCAO', 'qtd_' + str(produto['id']): '1'}


def sem_compra(caminhos, envio):
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0] == 0
        assert conn.execute('SELECT estoque FROM produtos').fetchone()[0] == 10
    assert all(not obter_link(url.rsplit('/', 1)[-1])['usado'] for url in caminhos)
    envio.assert_not_called()


def test_formulario_de_um_link_nao_confirma_outro_cliente(loja):
    cliente, produto, caminhos, envio = loja
    csrf_a = abrir(cliente, caminhos[0])
    resposta = cliente.post(caminhos[1], base_url=BASE, data=dados(produto, csrf_a))
    assert resposta.status_code == 403
    sem_compra(caminhos, envio)
    assert cliente.get(caminhos[1] + '/comprovante', base_url=BASE).status_code == 410


def test_primeiro_acesso_ao_link_do_whatsapp_confirma_o_proprio_pedido(loja):
    cliente, produto, caminhos, envio = loja
    csrf = abrir(cliente, caminhos[0])
    resposta = cliente.post(caminhos[0], base_url=BASE, data=dados(produto, csrf))
    assert resposta.status_code == 303
    assert cliente.get(resposta.location, base_url=BASE).status_code == 200
    assert obter_link(caminhos[0].rsplit('/', 1)[-1])['usado']
    assert not obter_link(caminhos[1].rsplit('/', 1)[-1])['usado']
    assert envio.call_count == 3


def test_multiplas_abas_preservam_provas_independentes(loja):
    cliente, produto, caminhos, envio = loja
    csrf_a = abrir(cliente, caminhos[0])
    csrf_b = abrir(cliente, caminhos[1])
    assert csrf_a != csrf_b
    for url, csrf in zip(caminhos, (csrf_a, csrf_b)):
        resposta = cliente.post(url, base_url=BASE, data=dados(produto, csrf))
        assert resposta.status_code == 303
        assert cliente.get(resposta.location, base_url=BASE).status_code == 200
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0] == 2
    assert envio.call_count == 6


def test_token_global_de_outros_formularios_nao_autoriza_pedido(loja):
    cliente, produto, caminhos, envio = loja
    abrir(cliente, caminhos[0])
    with cliente.session_transaction(base_url=BASE) as sessao:
        csrf_global = sessao['csrf']
    resposta = cliente.post(caminhos[0], base_url=BASE, data=dados(produto, csrf_global))
    assert resposta.status_code == 403
    sem_compra(caminhos, envio)


def test_prova_do_link_nao_transfere_sessao_para_outro_navegador(loja):
    cliente, produto, caminhos, envio = loja
    csrf = abrir(cliente, caminhos[0])
    outro = cliente.application.test_client()
    abrir(outro, caminhos[0])
    resposta = outro.post(caminhos[0], base_url=BASE, data=dados(produto, csrf))
    assert resposta.status_code == 403
    sem_compra(caminhos, envio)


@pytest.mark.parametrize('origem', [
    {'Origin': 'https://outro-ficticio.example'},
    {'Sec-Fetch-Site': 'cross-site'},
])
def test_prova_do_link_nao_dispensa_validacao_da_origem(loja, origem):
    cliente, produto, caminhos, envio = loja
    csrf = abrir(cliente, caminhos[0])
    resposta = cliente.post(caminhos[0], base_url=BASE,
                            data=dados(produto, csrf), headers=origem)
    assert resposta.status_code == 403
    sem_compra(caminhos, envio)


@pytest.mark.parametrize('campo', ['csrf_token', 'quantidade'])
def test_prova_do_link_nao_aceita_campos_repetidos(loja, campo):
    cliente, produto, caminhos, envio = loja
    csrf = abrir(cliente, caminhos[0])
    repetido = 'csrf_token' if campo == 'csrf_token' else 'qtd_' + str(produto['id'])
    formulario = MultiDict(list(dados(produto, csrf).items()) + [(repetido, 'outro')])
    resposta = cliente.post(caminhos[0], base_url=BASE, data=formulario)
    assert resposta.status_code == 403
    sem_compra(caminhos, envio)
