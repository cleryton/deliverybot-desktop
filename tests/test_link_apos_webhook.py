"""Mensagens da Meta simuladas: link após reconexão sem envio real."""
from unittest.mock import Mock

import pytest

from src import bot, config, ia, processamento, publicacao, whatsapp
from src.db import get_conn, init_db


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'teste.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    monkeypatch.setattr(config, 'MODO_TESTE', False)
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'META')
    monkeypatch.setattr(config, 'IA_PROVIDER', '')
    monkeypatch.setattr(publicacao, '_gerente', None)
    monkeypatch.setattr(config, 'BASE_URL', '')
    monkeypatch.setattr(processamento, '_servico_pronto', lambda: True)
    processamento._parar.clear()
    init_db()


def tarefa(texto):
    return processamento.enfileirar({'telefone': '5547999990000', 'texto': texto}, 'evento-ficticio')['id']


@pytest.mark.parametrize('texto', ['quero o link', 'gostaria de um link', 'preciso de link', 'pode me enviar o link?', 'quero o link para pedir'])
def test_pedido_explicito_de_link_dispensa_ia(monkeypatch, texto):
    monkeypatch.setattr(config, 'BASE_URL', 'https://loja.example')
    modelo = Mock(side_effect=AssertionError('Não chamar IA'))
    monkeypatch.setattr(ia, 'responder', modelo)
    resposta = bot._resposta_rapida('5547999990000', texto)
    assert 'https://loja.example/m/' in resposta
    modelo.assert_not_called()


@pytest.mark.parametrize('texto', ['não quero o link', 'quero o link de pagamento', 'preciso de link de rastreamento', 'quero o link da privacidade'])
def test_outros_assuntos_nao_autorizam_link_de_compra(texto):
    assert not ia.intencao_pedido(texto)


@pytest.mark.parametrize('persistido', [False, True])
@pytest.mark.parametrize('texto', ['quero o link', '2'])
@pytest.mark.parametrize('provedor', ['LOCAL', 'META'])
def test_aguarda_https_e_envia_link_uma_vez_apos_reconexao(monkeypatch, persistido, texto, provedor):
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', provedor)
    ident = tarefa(texto)
    if persistido:
        with get_conn() as conn:
            conn.execute('UPDATE tarefas_bot SET resposta=? WHERE id=?', (ia.PEDIDO_INDISPONIVEL, ident))
    enviar = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', enviar)
    assert processamento.processar_proxima() is False
    enviar.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado FROM tarefas_bot WHERE id=?', (ident,)).fetchone()[0] == 'PENDENTE'
        assert conn.execute('SELECT count(*) FROM links_pedido').fetchone()[0] == 0
    monkeypatch.setattr(config, 'BASE_URL', 'https://nova-loja.example')
    assert processamento.processar_proxima() is True
    assert processamento.processar_proxima() is False
    enviar.assert_called_once()
    resposta = enviar.call_args.args[1]
    assert 'https://nova-loja.example/m/' in resposta
    assert ia.PEDIDO_INDISPONIVEL not in resposta and 'localhost' not in resposta
    with get_conn() as conn:
        link = conn.execute('SELECT telefone,usado FROM links_pedido').fetchone()
        assert tuple(link) == ('5547999990000', 0)
        assert conn.execute('SELECT count(*) FROM links_pedido').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM pedidos').fetchone()[0] == 0


@pytest.mark.parametrize('provedor', ['LOCAL', 'META'])
def test_https_indisponivel_nao_bloqueia_outro_cliente_e_preserva_ordem(monkeypatch, provedor):
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', provedor)
    primeira = tarefa('2')
    enviar = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', enviar)
    assert processamento.processar_proxima() is False
    seguinte = processamento.enfileirar({'telefone': '5547999990000', 'texto': '3'}, 'seguinte')['id']
    outra = processamento.enfileirar({'telefone': '5547999990001', 'texto': '3'}, 'outra')['id']
    assert processamento.processar_proxima() is True
    assert enviar.call_args.args[0] == '5547999990001'
    with get_conn() as conn:
        estados = dict(conn.execute('SELECT id,estado FROM tarefas_bot'))
    assert estados == {primeira: 'PENDENTE', seguinte: 'PENDENTE', outra: 'CONCLUIDA'}
    assert processamento.situacao()['aguardando_https'] == 1
    monkeypatch.setattr(config, 'BASE_URL', 'https://loja.example')
    assert processamento.processar_proxima() is True
    assert '/m/' in enviar.call_args.args[1]
    assert processamento.processar_proxima() is True
    assert '/m/' not in enviar.call_args.args[1]
    assert processamento.situacao()['aguardando_https'] == 0


def test_https_restabelecido_retoma_a_ordem_original(monkeypatch):
    tarefa('2')
    enviar = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', enviar)
    assert processamento.processar_proxima() is False
    processamento.enfileirar({'telefone': '5547999990001', 'texto': '3'}, 'outra')
    monkeypatch.setattr(config, 'BASE_URL', 'https://loja.example')
    assert processamento.processar_proxima() is True
    assert enviar.call_args.args[0] == '5547999990000'


def test_contagem_https_nao_inclui_envios_incertos(monkeypatch):
    ident = tarefa('2')
    assert processamento.processar_proxima() is False
    assert processamento.situacao()['aguardando_https'] == 1
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='VERIFICAR' WHERE id=?", (ident,))
    assert processamento.situacao()['aguardando_https'] == 0
