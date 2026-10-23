"""Credenciais salvas não comprovam conexão nem entrega de mensagens."""
import json
from unittest.mock import Mock

import pytest

from src import config, diagnosticos


@pytest.mark.parametrize('segredo', ['', 'segredo-ficticio'])
def test_meta_configurada_nao_e_conexao_comprovada(monkeypatch, segredo):
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'META')
    monkeypatch.setattr(config, 'WHATSAPP_TOKEN', 'token-ficticio')
    monkeypatch.setattr(config, 'WHATSAPP_PHONE_NUMBER_ID', '12345')
    monkeypatch.setattr(config, 'WHATSAPP_APP_SECRET', segredo)
    monkeypatch.setattr(config, 'IA_PROVIDER', '')
    conn = Mock()
    monkeypatch.setattr(diagnosticos, 'get_conn', Mock(return_value=MockContext(conn)))
    monkeypatch.setattr(diagnosticos.publicacao, 'situacao', lambda: {})
    monkeypatch.setattr(diagnosticos.processamento, 'situacao', lambda: {})
    monkeypatch.setattr(diagnosticos.processamento, 'ativo', lambda: False)
    monkeypatch.setattr(diagnosticos.rotinas, 'situacao', lambda: {})
    # A verificação da Meta neste relatório é local, sem chamadas à conta real.
    rede = Mock(side_effect=AssertionError('Não consultar serviços externos'))
    monkeypatch.setattr(diagnosticos.conexoes, 'http', rede)
    relatorio = diagnosticos.coletar()
    wa = relatorio['servicos']['whatsapp']
    assert wa['conectado'] is False
    assert wa['servico'] is bool(segredo)
    assert wa['estado'] == ('META_CONFIGURADA' if segredo else 'META_PENDENTE')
    assert 'token-ficticio' not in json.dumps(relatorio)
    assert 'segredo-ficticio' not in json.dumps(relatorio)
    rede.assert_not_called()


class MockContext:
    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        return self.conn

    def __exit__(self, *args):
        return False
