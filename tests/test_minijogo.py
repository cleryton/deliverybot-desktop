"""Página pública e confirmação isoladas, com envio WhatsApp simulado."""
import re
from unittest.mock import Mock

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

from src import config, publicacao
from src.db import get_conn, init_db


@pytest.fixture
def publico(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path/'ficticio.db'))
    monkeypatch.setattr(config, 'MODO_TESTE', True)
    monkeypatch.setattr(config, 'BASE_URL', 'https://loja-ficticia.example')
    monkeypatch.setattr(publicacao, '_gerente', None)
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'token-ficticio')
    return Client(publicacao.PaginaPublica(app, lambda: config.BASE_URL), Response)


def test_jogo_independente_publico_sem_dados_do_cliente_ou_cookie(publico):
    resposta = publico.get('/jogar')
    assert resposta.status_code == 200
    assert 'data-pong' in resposta.text and '<canvas' in resposta.text
    assert '5 pontos' in resposta.text and 'data-pause' in resposta.text
    assert not resposta.headers.get('Set-Cookie')
    assert '/m/' not in resposta.text and 'csrf_token' not in resposta.text
    assert "script-src 'self'" in resposta.headers['Content-Security-Policy']
    assert 'https://' not in resposta.text
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM clientes').fetchone()[0] == 0


@pytest.mark.parametrize('asset', ['pong.css','pong-core.js','pong.js','recibo.js'])
def test_recursos_do_jogo_passam_pelo_tunel_sem_liberar_painel(publico, asset):
    assert publico.get('/static/'+asset).status_code == 200
    assert publico.get('/static/gestao.js').status_code == 404
    assert publico.get('/gestao/api/produtos').status_code == 404


def test_confirmacao_oferece_jogo_sem_reabrir_link_usado(publico, monkeypatch):
    from src import estoque, whatsapp
    from src.links import gerar_link_pedido
    envio = Mock(); monkeypatch.setattr(whatsapp, 'enviar_mensagem', envio)
    produto = estoque.salvar_produto({'nome':'Lanche fictício','preco':10,'estoque':2,'categoria':'Teste'})
    caminho = '/m/'+gerar_link_pedido('5511999990028').rsplit('/',1)[-1]
    pagina = publico.get(caminho)
    assert 'data-pong' not in pagina.text  # O jogo aparece após salvar a compra.
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', pagina.text)[1]
    resposta = publico.post(caminho, data={'csrf_token':csrf,'nome':'Pessoa fictícia','forma_pagamento':'Dinheiro',
                                          'forma_entrega':'RETIRADA BALCAO','qtd_'+str(produto['id']):'1'},
                            headers={'Origin':config.BASE_URL}, follow_redirects=True)
    assert resposta.status_code == 200
    assert 'Seu pedido foi recebido!' in resposta.text and 'data-pong' in resposta.text
    assert 'href="/jogar"' in resposta.text and 'noreferrer' in resposta.text
    assert publico.get(caminho).status_code == 410
    assert publico.get('/jogar').status_code == 200
    assert estoque.listar_produtos()[0]['estoque'] == 1
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0] == 1
    assert publico.post(caminho, data={'csrf_token':csrf}).status_code == 410


def test_jogo_nao_disponibiliza_operacoes_post_ou_apis(publico):
    assert publico.post('/jogar').status_code == 404
    assert publico.get('/jogar/status').status_code == 404
    assert publico.get('/static/pong/../gestao.js').status_code == 404
