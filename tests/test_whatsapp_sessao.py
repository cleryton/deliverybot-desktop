"""Notificações diretas também usam a conexão ativa, sem transportes reais."""
from unittest.mock import Mock

import pytest

from src import config, whatsapp, whatsapp_documentos


@pytest.fixture
def transporte(monkeypatch):
    monkeypatch.setattr(config, 'MODO_TESTE', False)
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'WAHA')
    monkeypatch.setattr(config, 'WAHA_URL', 'https://whatsapp-ficticio.example')
    monkeypatch.setattr(config, 'WAHA_SESSION', 'sessao-ativa')
    monkeypatch.setattr(config, 'WAHA_API_KEY', 'chave-ficticia')
    monkeypatch.setattr(whatsapp, '_chat_id_conhecido', lambda _: '5511999990174@c.us')
    antiga = Mock(side_effect=AssertionError('Cadastro não autoriza outra conta de envio'))
    monkeypatch.setattr(whatsapp, '_sessao_conhecida', antiga)
    resposta = Mock(status_code=200, content=b'{}')
    resposta.json.return_value = {'id': 'envio-ficticio'}
    enviar = Mock(return_value=resposta)
    monkeypatch.setattr(whatsapp._http, 'post', enviar)
    return enviar, antiga


@pytest.mark.parametrize('formato', ['TEXTO', 'PDF'])
def test_notificacao_sem_sessao_nao_herda_conta_antiga_do_contato(transporte, formato):
    enviar, antiga = transporte
    if formato == 'TEXTO':
        whatsapp._enviar_via_waha('5511999990174', 'Confirmação fictícia')
    else:
        whatsapp_documentos.enviar('5511999990174', b'%PDF-1.4\n%%EOF', 'Catálogo fictício')
    assert enviar.call_args.kwargs['json']['session'] == 'sessao-ativa'
    antiga.assert_not_called()


@pytest.mark.parametrize('formato', ['TEXTO', 'PDF'])
def test_sessao_alheia_explicita_nao_chega_ao_transporte(transporte, formato):
    enviar, _ = transporte
    with pytest.raises(ValueError, match='conexão ativa'):
        if formato == 'TEXTO':
            whatsapp._enviar_via_waha('5511999990174', 'Confirmação fictícia', session='outra-conta')
        else:
            whatsapp_documentos.enviar('5511999990174', b'%PDF-1.4\n%%EOF', 'Catálogo fictício', session='outra-conta')
    enviar.assert_not_called()


def test_evento_de_sessao_alheia_nao_altera_rota_do_cliente(transporte, monkeypatch):
    lembrar = Mock(side_effect=AssertionError('Evento alheio não altera o cadastro'))
    monkeypatch.setattr(whatsapp, '_lembrar_chat_id', lembrar)
    evento = {'event': 'message', 'session': 'outra-conta',
              'payload': {'from': '5511999990174@c.us', 'body': 'Texto fictício'}}
    assert whatsapp.extrair_mensagem_recebida_waha(evento) is None
    lembrar.assert_not_called()
