"""Preparação automática isolada, sem conta, DNS, túnel ou WhatsApp reais."""
from unittest.mock import Mock

import pytest

from src import config, conexoes, preferencias, publicacao
from src.db import init_db


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticio.db'))
    for chave in preferencias.CAMPOS | {'MODO_TESTE'}:
        monkeypatch.setattr(config, chave, getattr(config, chave))
    config.WHATSAPP_PROVIDER = 'TESTE'
    config.MODO_TESTE = True
    config.TUNEL_AUTOMATICO = 'NAO'
    config.TUNEL_MODO = 'RAPIDO'
    config.TUNEL_URL = config.TUNEL_TOKEN = ''
    monkeypatch.setattr(publicacao, '_gerente', None)
    monkeypatch.setattr(conexoes, '_jobs', {})
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'desktop-ficticio')
    cliente = app.test_client()
    cliente.get('/gestao?acesso=desktop-ficticio')
    with cliente.session_transaction() as sessao:
        cabecalho = {'X-CSRF-Token': sessao['csrf']}
    return app, cliente, cabecalho


@pytest.mark.parametrize('provedor,funcao', [('LOCAL', 'iniciar_whatsapp_local'), ('WAHA', 'conectar_whatsapp')])
def test_salvar_provedor_prepara_https_e_whatsapp_sem_segundo_clique(ambiente, monkeypatch, provedor, funcao):
    _, cliente, cabecalho = ambiente
    iniciar = Mock(return_value={'estado': 'EXECUTANDO'})
    monkeypatch.setattr(conexoes, 'iniciar_tarefa', iniciar)
    monkeypatch.setattr(conexoes.whatsapp_local, 'encerrar', Mock())
    resposta = cliente.put('/gestao/api/configuracoes', json={'WHATSAPP_PROVIDER': provedor}, headers=cabecalho)
    assert resposta.status_code == 200
    assert resposta.json['preparacao_whatsapp']['estado'] == 'EXECUTANDO'
    iniciar.assert_called_once_with('whatsapp', getattr(conexoes, funcao))
    # Repetir a mesma configuração ou mudar a loja não reinicia a sessão.
    iniciar.reset_mock()
    cliente.put('/gestao/api/configuracoes', json={'WHATSAPP_PROVIDER': provedor, 'NOME_RESTAURANTE': 'Loja fictícia'}, headers=cabecalho)
    iniciar.assert_not_called()


def test_corrigir_servidor_waha_reconfigura_mas_sem_desktop_nao_lanca_servico(ambiente, monkeypatch):
    app, cliente, cabecalho = ambiente
    config.WHATSAPP_PROVIDER = 'WAHA'
    config.WAHA_URL = 'https://antigo.example'
    iniciar = Mock(return_value={'estado': 'EXECUTANDO'})
    monkeypatch.setattr(conexoes, 'iniciar_tarefa', iniciar)
    monkeypatch.setattr(conexoes.whatsapp_local, 'encerrar', Mock())
    assert cliente.put('/gestao/api/configuracoes', json={'WAHA_URL': 'https://novo.example'}, headers=cabecalho).status_code == 200
    iniciar.assert_called_once_with('whatsapp', conexoes.conectar_whatsapp)
    iniciar.reset_mock()
    monkeypatch.setattr('src.gestao._local', lambda: False)
    monkeypatch.setattr('src.gestao.autorizado', lambda: True)
    assert cliente.put('/gestao/api/configuracoes', json={'WAHA_URL': 'https://outro.example'}, headers=cabecalho).status_code == 200
    iniciar.assert_not_called()


def test_configuracao_em_preparacao_nao_muda_provedor(ambiente, monkeypatch):
    _, cliente, cabecalho = ambiente
    monkeypatch.setattr(conexoes, '_jobs', {'whatsapp': {'estado': 'EXECUTANDO'}})
    resposta = cliente.put('/gestao/api/configuracoes', json={'WHATSAPP_PROVIDER': 'LOCAL'}, headers=cabecalho)
    assert resposta.status_code == 400
    assert config.WHATSAPP_PROVIDER == 'TESTE'


@pytest.mark.parametrize('falhar', [False, True])
def test_https_antes_do_servico_integrado_e_uma_unica_inicializacao(ambiente, monkeypatch, falhar):
    eventos = []
    def preparar(progresso):
        eventos.append('https')
        if falhar:
            raise ValueError('DNS indisponível fictício')
    monkeypatch.setattr(publicacao, 'preparar_para_whatsapp', preparar)
    monkeypatch.setattr(conexoes.whatsapp_local, 'iniciar', lambda _: eventos.append('servico'))
    monkeypatch.setattr(conexoes, '_waha', Mock(side_effect=[None, {}]))
    if falhar:
        with pytest.raises(ValueError, match='DNS'):
            conexoes.iniciar_whatsapp_local(Mock())
        assert eventos == ['https']
        assert config.WHATSAPP_PROVIDER == 'TESTE'
        conexoes._waha.assert_not_called()
    else:
        conexoes.iniciar_whatsapp_local(Mock())
        assert eventos == ['https', 'servico']
        assert conexoes._waha.call_args.args[2]['start'] is True


@pytest.mark.parametrize('estado', ['DESLIGADO', 'INICIANDO', 'RECONECTANDO', 'ERRO', 'ONLINE'])
def test_qr_so_disponivel_com_https_pronto(ambiente, monkeypatch, estado):
    app, cliente, _ = ambiente
    gerente = publicacao.Publicacao(app)
    gerente.ativo = True
    gerente._status(estado, 'Estado fictício', 'https://ficticio.trycloudflare.com' if estado == 'ONLINE' else '')
    monkeypatch.setattr(publicacao, '_gerente', gerente)
    qr = Mock(return_value={'imagem': 'png-ficticio'})
    monkeypatch.setattr(conexoes, 'qr_whatsapp', qr)
    resposta = cliente.get('/gestao/api/conexoes/qr')
    assert resposta.status_code == (200 if estado == 'ONLINE' else 400)
    assert qr.call_count == (1 if estado == 'ONLINE' else 0)


def test_qr_antigo_oculto_durante_configuracao_e_status_expoe_preparacao(ambiente, monkeypatch):
    _, cliente, _ = ambiente
    monkeypatch.setattr(conexoes, '_jobs', {'whatsapp': {'estado': 'EXECUTANDO'}})
    qr = Mock()
    monkeypatch.setattr(conexoes, 'qr_whatsapp', qr)
    assert cliente.get('/gestao/api/conexoes/qr').status_code == 400
    qr.assert_not_called()
    monkeypatch.setattr(conexoes, 'status_whatsapp', lambda: {'estado': 'SCAN_QR_CODE'})
    monkeypatch.setattr(conexoes, 'status_ollama', lambda: {})
    assert cliente.get('/gestao/api/conexoes').json['pagina_publica']['estado'] == 'DESLIGADO'
