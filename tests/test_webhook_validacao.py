"""Entradas Meta inválidas são recusadas sem processar dados ou expor segredos."""
import hashlib
import hmac
import logging
from unittest.mock import Mock

import pytest
from flask import Request

from src import config, meta_custos, processamento, seguranca, whatsapp
from src.db import init_db


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    for nome in vars(config):
        if nome.isupper():
            monkeypatch.setattr(config, nome, getattr(config, nome))
    for nome, valor in {
        'DATABASE_PATH': str(tmp_path/'meta-ficticio.db'), 'SEED_CATALOGO': False,
        'MODO_TESTE': True, 'WHATSAPP_PROVIDER': 'TESTE', 'IA_PROVIDER': '',
        'WHATSAPP_APP_SECRET': 'app-exclusivamente-ficticio',
        'WHATSAPP_VERIFY_TOKEN': 'verificador-exclusivamente-ficticio',
    }.items():
        monkeypatch.setattr(config, nome, valor)
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config, 'PROPAGATE_EXCEPTIONS', False)
    status = Mock()
    extrair = Mock(return_value=None)
    fila = Mock()
    monkeypatch.setattr(meta_custos, 'registrar_status', status)
    monkeypatch.setattr(whatsapp, 'extrair_mensagem_recebida', extrair)
    monkeypatch.setattr(processamento, 'enfileirar', fila)
    return app.test_client(), (status, extrair, fila)


@pytest.mark.parametrize('assinatura', [
    None, '', 'sha256=é', 'sha256='+('g'*64), 'sha1='+('0'*64),
    'sha256='+('0'*63), 'sha256='+('0'*65), 'sha256='+('0'*4096),
], ids=['ausente', 'vazia', 'nao-ascii', 'nao-hexadecimal', 'prefixo', 'curta', 'longa', 'excessiva'])
def test_assinatura_malformada_nao_le_corpo_nem_processa_evento(cliente, monkeypatch, assinatura):
    c, dependencias = cliente
    leitura = Mock(side_effect=AssertionError('Cabeçalho inválido deve ser recusado antes do corpo.'))
    monkeypatch.setattr(Request, 'get_data', leitura)
    headers = {} if assinatura is None else {'X-Hub-Signature-256': assinatura}
    r = c.post('/webhook', data=b'{}', content_type='application/json', headers=headers)
    assert r.status_code == 403
    leitura.assert_not_called()
    for dependencia in dependencias:
        dependencia.assert_not_called()


def test_assinatura_com_formato_correto_mas_incorreta_e_recusada(cliente):
    c, dependencias = cliente
    r = c.post('/webhook', data=b'{}', content_type='application/json',
               headers={'X-Hub-Signature-256': 'sha256='+('0'*64)})
    assert r.status_code == 403
    for dependencia in dependencias:
        dependencia.assert_not_called()


def test_evento_assinado_correto_preserva_contabilidade_e_extracao(cliente):
    c, (status, extrair, fila) = cliente
    corpo = b'{}'
    assinatura = 'sha256='+hmac.new(config.WHATSAPP_APP_SECRET.encode(), corpo, hashlib.sha256).hexdigest()
    r = c.post('/webhook', data=corpo, content_type='application/json',
               headers={'X-Hub-Signature-256': assinatura})
    assert r.status_code == 200 and r.json == {'status': 'ignorado'}
    status.assert_called_once_with({})
    extrair.assert_called_once_with({})
    fila.assert_not_called()


@pytest.mark.parametrize('desafio', [None, '', '  ', 'x'*1025], ids=['ausente', 'vazio', 'espacos', 'excessivo'])
def test_verificacao_exige_desafio_preenchido_e_limitado(cliente, desafio):
    c, dependencias = cliente
    consulta = {'hub.mode': 'subscribe', 'hub.verify_token': config.WHATSAPP_VERIFY_TOKEN}
    if desafio is not None:
        consulta['hub.challenge'] = desafio
    r = c.get('/webhook', query_string=consulta)
    assert r.status_code == 400 and r.mimetype == 'text/plain'
    for dependencia in dependencias:
        dependencia.assert_not_called()


@pytest.mark.parametrize('desafio', ['123456', 'desafio-ficticio', '<b>texto-ficticio</b>', 'x'*1024],
                         ids=['numerico', 'texto', 'html-literal', 'limite'])
def test_verificacao_retorna_somente_texto_literal(cliente, desafio):
    c, _ = cliente
    r = c.get('/webhook', query_string={'hub.mode': 'subscribe',
        'hub.verify_token': config.WHATSAPP_VERIFY_TOKEN, 'hub.challenge': desafio})
    assert r.status_code == 200 and r.mimetype == 'text/plain'
    assert r.text == desafio
    assert r.headers['X-Content-Type-Options'] == 'nosniff'


def test_verificador_incorreto_continua_bloqueado(cliente):
    c, _ = cliente
    r = c.get('/webhook', query_string={'hub.mode': 'subscribe',
        'hub.verify_token': 'incorreto-ficticio', 'hub.challenge': '<b>nao-refletir</b>'})
    assert r.status_code == 403 and '<b>nao-refletir</b>' not in r.text


@pytest.mark.parametrize('nome', [
    'hub.verify_token', 'HUB.VERIFY_TOKEN', 'hub%2Everify_token',
    'hub.verify%5Ftoken', '%68%75%62%2e%76%65%72%69%66%79%5f%74%6f%6b%65%6e',
])
def test_log_oculta_verificador_da_meta_inclusive_nome_codificado(nome):
    url = f'https://loja-ficticia.example/webhook?{nome}=verificador-nao-exibir&hub.challenge=desafio-ficticio'
    registro = logging.LogRecord('teste-ficticio', logging.INFO, __file__, 1, url, (), None)
    assert seguranca.LogPrivado().filter(registro)
    assert 'verificador-nao-exibir' not in registro.getMessage()
    assert '[privado]' in registro.getMessage() and 'desafio-ficticio' in registro.getMessage()
