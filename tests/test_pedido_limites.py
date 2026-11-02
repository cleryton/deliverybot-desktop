"""Confirmações limitadas antes de consultas externas e alterações de estoque."""
import re
from unittest.mock import Mock

import pytest

from src import config, estoque, publicacao, viacep, whatsapp
from src.db import get_conn, init_db
from src.links import gerar_link_pedido, obter_link

BASE = 'https://comercio-ficticio.example'


@pytest.fixture
def loja(tmp_path, monkeypatch):
    for campo, valor in {
        'DATABASE_PATH': str(tmp_path/'limites-ficticios.db'), 'SEED_CATALOGO': False,
        'MODO_TESTE': False, 'IA_PROVIDER': '', 'WHATSAPP_PROVIDER': 'TESTE',
        'BASE_URL': BASE, 'FORMAS_PAGAMENTO': 'Pix,Dinheiro',
    }.items():
        monkeypatch.setattr(config, campo, valor)
    monkeypatch.setattr(publicacao, '_gerente', None)
    envio = Mock()
    cep = Mock(return_value=(False, 'CEP fictício inválido.', None))
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', envio)
    monkeypatch.setattr(viacep, 'validar_area_entrega', cep)
    init_db(seed_cardapio=False)
    from src.app import app
    produto = estoque.salvar_produto({'nome': 'Item fictício', 'categoria': 'Teste', 'preco': 12, 'estoque': 10})
    caminho = '/m/' + gerar_link_pedido('5500000000001').rsplit('/', 1)[-1]
    cliente = app.test_client()
    html = cliente.get(caminho, base_url=BASE).text
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', html)[1]
    dados = {'csrf_token': csrf, 'nome': 'Pessoa fictícia', 'forma_entrega': 'ENTREGA',
             'forma_pagamento': 'Pix', 'cep': '00000000', 'qtd_'+str(produto['id']): '1'}
    return cliente, caminho, dados, cep, envio


def test_repeticoes_do_link_sao_barradas_antes_de_consultar_cep(loja):
    c, caminho, dados, cep, envio = loja
    for _ in range(8):
        assert c.post(caminho, base_url=BASE, data=dados).status_code == 400
    for _ in range(3):
        resposta = c.post(caminho, base_url=BASE, data=dados)
        assert resposta.status_code == 429 and resposta.headers['Retry-After'] == '60'
        assert 'no-store' in resposta.headers['Cache-Control']
    assert cep.call_count == 8
    envio.assert_not_called()
    assert not obter_link(caminho.rsplit('/', 1)[-1])['usado']
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0] == 0
        assert conn.execute('SELECT estoque FROM produtos').fetchone()[0] == 10


def test_pausa_expira_sem_consumir_link_e_outro_cliente_continua(loja, monkeypatch):
    from src import politica_terminal
    from src.protecao_pedido import ProtecaoConfirmacao
    from src import protecao_pedido
    monkeypatch.setattr(protecao_pedido, 'protecao', ProtecaoConfirmacao())
    c, caminho, dados, cep, envio = loja
    for _ in range(8):
        assert c.post(caminho, base_url=BASE, data=dados).status_code == 400
    assert c.post(caminho, base_url=BASE, data=dados).status_code == 429
    outro = '/m/' + gerar_link_pedido('5500000000002').rsplit('/', 1)[-1]
    pagina = c.get(outro, base_url=BASE)
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', pagina.text)[1]
    assert c.post(outro, base_url=BASE, data={**dados, 'csrf_token': csrf}).status_code == 400
    agora = politica_terminal.time.monotonic()
    monkeypatch.setattr(politica_terminal.time, 'monotonic', lambda: agora+61)
    assert c.post(caminho, base_url=BASE, data=dados).status_code == 400
    assert cep.call_count == 10 and not obter_link(caminho.rsplit('/', 1)[-1])['usado']
    envio.assert_not_called()


def test_ocupacao_nao_consulta_cep_e_libera_vaga_apos_falha(loja, monkeypatch):
    from src import protecao_pedido
    protecao = protecao_pedido.ProtecaoConfirmacao()
    monkeypatch.setattr(protecao_pedido, 'protecao', protecao)
    c, caminho, dados, cep, _ = loja
    with protecao.reservar('primeira-operacao-ficticia'), protecao.reservar('segunda-operacao-ficticia'):
        r = c.post(caminho, base_url=BASE, data=dados)
        assert r.status_code == 429 and r.headers['Retry-After'] == '15'
        cep.assert_not_called()
    cep.side_effect = RuntimeError('falha-ficticia-na-consulta')
    assert c.post(caminho, base_url=BASE, data=dados).status_code == 500
    cep.side_effect = None
    # Se a exceção retivesse a vaga, a segunda reserva abaixo falharia.
    with protecao.reservar('nova-primeira-ficticia'), protecao.reservar('nova-segunda-ficticia'):
        pass
    assert c.post(caminho, base_url=BASE, data=dados).status_code == 400
    assert not obter_link(caminho.rsplit('/', 1)[-1])['usado']


def test_cota_global_limita_links_distintos_e_nao_guarda_tokens(loja, monkeypatch):
    from src import protecao_pedido
    protecao = protecao_pedido.ProtecaoConfirmacao()
    monkeypatch.setattr(protecao_pedido, 'protecao', protecao)
    c, caminho, dados, cep, envio = loja
    for indice in range(60):
        with protecao.reservar('token-ficticio-'+str(indice)):
            pass
    r = c.post(caminho, base_url=BASE, data=dados)
    assert r.status_code == 429 and r.headers['Retry-After'] == '60'
    cep.assert_not_called()
    envio.assert_not_called()
    assert 'token-ficticio' not in str(protecao.limites.itens)
    assert config.DATABASE_PATH not in str(protecao.limites.itens)
