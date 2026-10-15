"""Configurações individuais fictícias, sem acessar Meta ou enviar mensagens."""
import json
from unittest.mock import Mock
import pytest
import requests

from src import config, preferencias, meta_configuracao as setup
from src.db import get_conn, init_db

APP, WABA, NUM = '123456789001', '123456789002', '123456789003'


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticio.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    for k in preferencias.CAMPOS | {'MODO_TESTE', 'WHATSAPP_API_URL'}:
        monkeypatch.setattr(config, k, getattr(config, k))
    preferencias.aplicar({'WHATSAPP_PROVIDER': 'TESTE', 'WHATSAPP_APP_ID': '',
        'WHATSAPP_PHONE_NUMBER_ID': '', 'WHATSAPP_BUSINESS_ACCOUNT_ID': '',
        'WHATSAPP_TOKEN': 'token-de-outra-pessoa', 'WHATSAPP_APP_SECRET': 'segredo-de-outra-pessoa', 'IA_PROVIDER': ''})
    init_db()
    monkeypatch.setattr(setup.publicacao, 'preparar_para_whatsapp', Mock(return_value='https://loja.example'))
    monkeypatch.setattr(setup.publicacao, 'endereco', lambda: 'https://loja.example')


def dados(**extra):
    return {'WHATSAPP_APP_ID': APP, 'WHATSAPP_BUSINESS_ACCOUNT_ID': WABA,
        'WHATSAPP_TOKEN': 'meu-token-ficticio', 'WHATSAPP_APP_SECRET': 'meu-segredo-ficticio',
        'WHATSAPP_PHONE_NUMBER_ID': NUM, 'WHATSAPP_META_AMBIENTE': 'TESTE',
        'numero_anterior': '', 'confirmar': True, 'configurar_webhook': False, **extra}


def graph(monkeypatch, **alteracoes):
    descricao = {'is_valid': True, 'app_id': APP, 'type': 'SYSTEM_USER', 'expires_at': 0,
        'data_access_expires_at': 0, 'scopes': ['whatsapp_business_messaging', 'whatsapp_business_management'], **alteracoes}
    chamada = Mock(side_effect=[{'data': descricao}, {'data': [{'id': NUM, 'display_phone_number': 'Número fictício', 'verified_name': 'Loja'}]}])
    monkeypatch.setattr(setup, '_consulta', chamada)
    return chamada


def test_consulta_usa_credenciais_explicitamente_e_nunca_retoma_token_de_outra_pessoa(monkeypatch):
    consulta = graph(monkeypatch)
    r = setup.consultar(dados())
    assert r['numeros'][0]['id'] == NUM and r['expira_em'] == 0
    assert consulta.call_args_list[0].args[1] == APP + '|meu-segredo-ficticio'
    assert consulta.call_args_list[1].args[1] == 'meu-token-ficticio'
    assert 'meu-token' not in json.dumps(r) and 'meu-segredo' not in json.dumps(r)


@pytest.mark.parametrize('campo', ['WHATSAPP_APP_ID', 'WHATSAPP_BUSINESS_ACCOUNT_ID', 'WHATSAPP_TOKEN', 'WHATSAPP_APP_SECRET'])
def test_credencial_ausente_nao_herda_configuracao_anterior(campo, monkeypatch):
    chamada = graph(monkeypatch)
    d = dados(); d.pop(campo)
    with pytest.raises(ValueError): setup.consultar(d)
    chamada.assert_not_called()


@pytest.mark.parametrize('alteracoes', [{'is_valid': False}, {'app_id': '999999999'}, {'expires_at': 1},
    {'data_access_expires_at': 1}, {'scopes': ['whatsapp_business_messaging']}, {'scopes': [{}]}, {'expires_at': True}])
def test_token_expirado_app_diferente_e_permissoes_invalidas_nao_conectam(alteracoes, monkeypatch):
    graph(monkeypatch, **alteracoes)
    with pytest.raises(ValueError): setup.conectar(dados())
    assert config.WHATSAPP_PROVIDER == 'TESTE'


def test_salva_conta_individual_chave_automatica_e_segredos_protegidos_sem_enviar(monkeypatch):
    graph(monkeypatch)
    post = Mock(); monkeypatch.setattr(setup._http, 'post', post)
    r = setup.conectar(dados())
    assert r['salvo'] and not r['webhook_configurado']
    assert config.WHATSAPP_APP_ID == APP and config.WHATSAPP_PHONE_NUMBER_ID == NUM
    assert config.WHATSAPP_TOKEN == 'meu-token-ficticio' and len(config.WHATSAPP_VERIFY_TOKEN) >= 32
    with get_conn() as c:
        segredo = c.execute("SELECT valor FROM configuracoes WHERE chave='WHATSAPP_TOKEN'").fetchone()[0]
    assert segredo != config.WHATSAPP_TOKEN and 'meu-token' not in json.dumps(r)
    post.assert_not_called()


def test_numero_fora_da_conta_nao_e_salvo(monkeypatch):
    graph(monkeypatch)
    with pytest.raises(ValueError, match='pertencente'): setup.conectar(dados(WHATSAPP_PHONE_NUMBER_ID='98765432100'))
    assert config.WHATSAPP_PHONE_NUMBER_ID == ''


@pytest.mark.parametrize('extra', [{'confirmar': False}, {'numero_anterior': 'outro'}, {'configurar_webhook': 'true'}, {'WHATSAPP_META_AMBIENTE': 'OUTRO'}])
def test_confirmacao_e_tipos_sao_obrigatorios(extra, monkeypatch):
    consulta = graph(monkeypatch)
    with pytest.raises(ValueError): setup.conectar(dados(**extra))
    consulta.assert_not_called()


def test_mensagem_que_chega_durante_consulta_impede_troca(monkeypatch):
    consulta = graph(monkeypatch)
    def durante(d):
        with get_conn() as c:
            c.execute("INSERT INTO tarefas_bot(origem,chave,telefone,texto,estado) VALUES('TESTE','ficticia','5511999990000','oi','PENDENTE')")
        return {'numeros': [{'id': NUM}]}
    monkeypatch.setattr(setup, 'consultar', durante)
    with pytest.raises(ValueError, match='pendentes'): setup.conectar(dados())
    assert config.WHATSAPP_PROVIDER == 'TESTE'


def test_conta_alterada_durante_consulta_nao_e_sobrescrita(monkeypatch):
    def durante(d):
        preferencias.salvar({'WHATSAPP_APP_ID': '987654321000'})
        return {'numeros': [{'id': NUM}]}
    monkeypatch.setattr(setup, 'consultar', durante)
    with pytest.raises(ValueError, match='alterada durante'): setup.conectar(dados())
    assert config.WHATSAPP_APP_ID == '987654321000'


def test_webhook_usa_somente_graph_https_e_so_post_de_assinaturas(monkeypatch):
    graph(monkeypatch)
    post = Mock(return_value=Mock(status_code=200, json=Mock(return_value={'success': True})))
    monkeypatch.setattr(setup._http, 'post', post)
    r = setup.conectar(dados(configurar_webhook=True))
    assert r['webhook_configurado'] and post.call_count == 2
    urls = [ch.args[0] for ch in post.call_args_list]
    assert urls == [f'https://graph.facebook.com/v25.0/{APP}/subscriptions', f'https://graph.facebook.com/v25.0/{WABA}/subscribed_apps']
    assert post.call_args_list[0].kwargs['data']['callback_url'] == 'https://loja.example/webhook'
    assert all(ch.kwargs['allow_redirects'] is False for ch in post.call_args_list)
    assert all('/messages' not in u for u in urls)


def test_erro_de_webhook_preserva_configuracao_e_nao_afirma_que_esta_conectado(monkeypatch):
    graph(monkeypatch)
    post = Mock(side_effect=requests.Timeout('meu-segredo-ficticio'))
    monkeypatch.setattr(setup._http, 'post', post)
    r = setup.conectar(dados(configurar_webhook=True))
    assert r['salvo'] and not r['webhook_configurado']
    assert 'meu-segredo' not in json.dumps(r)
    assert config.WHATSAPP_PROVIDER == 'META'


def test_localhost_nunca_e_enviado_como_callback(monkeypatch):
    graph(monkeypatch)
    monkeypatch.setattr(setup.publicacao, 'endereco', lambda: 'http://localhost:5000')
    post = Mock(); monkeypatch.setattr(setup._http, 'post', post)
    with pytest.raises(ValueError): setup.conectar(dados(configurar_webhook=True))
    post.assert_not_called()
    assert config.WHATSAPP_PROVIDER == 'TESTE'


def test_novas_rotas_exigem_administrador_e_csrf(monkeypatch):
    from src.app import app
    from src import operadores
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'teste-local')
    cliente = app.test_client()
    for rota in ('numeros', 'conectar', 'webhook'):
        assert cliente.post('/gestao/api/meta/' + rota, json={}).status_code == 401
    cliente.get('/gestao?acesso=teste-local', follow_redirects=True)
    with cliente.session_transaction() as s: csrf = s['csrf']
    for rota in ('numeros', 'conectar', 'webhook'):
        assert cliente.post('/gestao/api/meta/' + rota, json={}).status_code == 403
    monkeypatch.setattr(operadores, 'admin', lambda: False)
    monkeypatch.setattr(operadores, 'existem', lambda: True)
    monkeypatch.setattr(operadores, 'usuario', lambda dados=None: {'id': 7, 'perfil': 'CAIXA'})
    for rota in ('numeros', 'conectar', 'webhook'):
        assert cliente.post('/gestao/api/meta/' + rota, json={}, headers={'X-CSRF-Token': csrf}).status_code == 403


def test_falha_apos_salvar_informa_sucesso_parcial_e_permite_recuperacao(monkeypatch):
    graph(monkeypatch)
    monkeypatch.setattr(setup, 'configurar_webhook', Mock(side_effect=ValueError('falha fictícia')))
    r = setup.conectar(dados(configurar_webhook=True))
    assert r['salvo'] and not r['webhook_configurado']
    assert 'foi salva' in r['aviso'] and config.WHATSAPP_PHONE_NUMBER_ID == NUM


def test_troca_de_conta_durante_webhook_nao_mistura_tokens(monkeypatch):
    graph(monkeypatch)
    setup.conectar(dados())
    def mudanca(*args, **kwargs):
        preferencias.aplicar({'WHATSAPP_TOKEN': 'token-de-outra-conta'})
        return True
    post = Mock(side_effect=mudanca)
    monkeypatch.setattr(setup, '_post', post)
    r = setup.configurar_webhook()
    assert not r['webhook_configurado'] and post.call_count == 1


def test_escritas_simultaneas_na_meta_sao_recusadas(monkeypatch):
    import threading
    pronto, liberar = threading.Event(), threading.Event()
    def segurar():
        with setup._lock:
            pronto.set()
            liberar.wait(5)
    thread = threading.Thread(target=segurar)
    thread.start()
    assert pronto.wait(3)
    try:
        with pytest.raises(ValueError, match='andamento'): setup.conectar(dados())
    finally:
        liberar.set(); thread.join(3)


def test_tokens_em_urls_de_diagnostico_sao_ocultados():
    from src.seguranca import reduzir_dados
    mensagem = 'GET /debug_token?input_token=meu-token-ficticio&access_token=outro-token&client_secret=segredo-ficticio&appsecret_proof=prova-ficticia HTTP/1.1'
    r = reduzir_dados(mensagem)
    assert all(s not in r for s in ('meu-token-ficticio', 'outro-token', 'segredo-ficticio', 'prova-ficticia'))
    assert r.count('[privado]') == 4
