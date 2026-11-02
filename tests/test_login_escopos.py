"""Autenticações independentes e CSRF por operação, somente dados fictícios."""
import hmac

import pytest
from flask import Flask, session
from werkzeug.datastructures import MultiDict
from werkzeug.security import generate_password_hash

from src import config, seguranca
from src.db import init_db


@pytest.fixture
def login_base(tmp_path, monkeypatch):
    for nome in vars(config):
        if nome.isupper():
            monkeypatch.setattr(config, nome, getattr(config, nome))
    config.DATABASE_PATH = str(tmp_path / 'login-ficticio.db')
    config.SEED_CATALOGO = False
    config.MODO_TESTE = True
    config.WHATSAPP_PROVIDER = 'TESTE'
    config.IA_PROVIDER = ''
    config.COZINHA_AUTH_MODO = 'SENHA'
    config.COZINHA_USUARIO = 'cozinha.ficticia'
    config.COZINHA_SENHA_HASH = generate_password_hash('senha-base-ficticia-123')
    config.ADMIN_PERMITIR_REMOTO = False
    monkeypatch.setattr(seguranca, '_tentativas', {})
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', None)
    c = app.test_client()
    auth = ('cozinha.ficticia', 'senha-base-ficticia-123')
    assert c.get('/gestao', auth=auth).status_code == 200
    with c.session_transaction() as s:
        token = s['csrf']
    assert c.post('/gestao/api/operadores', auth=auth, headers={'X-CSRF-Token': token}, json={
        'nome': 'Responsável fictício', 'login': 'admin.ficticio',
        'senha': 'senha-operador-ficticia-123', 'perfil': 'ADMIN'}).status_code == 200
    assert c.post('/gestao/sair', auth=auth, headers={'X-CSRF-Token': token}).status_code == 302
    return c, auth, token


def test_basic_valido_nao_reinicia_limite_do_operador(login_base, monkeypatch):
    c, auth, token = login_base
    dados = {'login': 'admin.ficticio', 'senha': 'senha-incorreta-ficticia', 'csrf_token': token}
    for _ in range(10):
        assert c.post('/gestao/login', auth=auth, data=dados).status_code == 401
    # Uma leitura autenticada da cozinha não libera a outra barreira de senha.
    assert c.get('/cozinha', auth=auth).status_code == 200
    assert c.post('/gestao/login', auth=auth, data=dados).status_code == 429
    assert c.post('/gestao/login', auth=auth, data={
        **dados, 'senha': 'senha-operador-ficticia-123'}).status_code == 429
    instante = seguranca.time.monotonic()
    monkeypatch.setattr(seguranca.time, 'monotonic', lambda: instante + 301)
    assert c.post('/gestao/login', auth=auth, data={
        **dados, 'senha': 'senha-operador-ficticia-123'}).status_code == 302


def test_sucesso_so_limpa_as_tentativas_do_mesmo_ambito(monkeypatch):
    monkeypatch.setattr(seguranca, '_tentativas', {})
    app = Flask(__name__)
    with app.test_request_context('/', environ_base={'REMOTE_ADDR': '127.0.0.1'}):
        for _ in range(10):
            seguranca.registrar_login(False)
            seguranca.registrar_login(False, ambito='operador')
        assert seguranca.login_bloqueado() and seguranca.login_bloqueado(ambito='operador')
        seguranca.registrar_login(True, ambito='operador')
        assert seguranca.login_bloqueado() and not seguranca.login_bloqueado(ambito='operador')
        seguranca.registrar_login(False, ambito='operador')
        seguranca.registrar_login(True)
        assert not seguranca.login_bloqueado()
        for _ in range(9):
            seguranca.registrar_login(False, ambito='operador')
        assert seguranca.login_bloqueado(ambito='operador')
        assert not seguranca.login_bloqueado()


@pytest.fixture
def app_csrf():
    app = Flask(__name__)
    app.secret_key = 'chave-ficticia-para-testar-csrf'
    return app


def test_csrf_escopado_nao_aceita_global_nem_outro_pedido(app_csrf):
    with app_csrf.test_request_context('/', method='POST'):
        global_ = seguranca.csrf()
        primeiro = seguranca.csrf('pedido:primeiro-ficticio')
        segundo = seguranca.csrf('pedido:segundo-ficticio')
        segredo = dict(session)
        assert len({global_, primeiro, segundo}) == 3
        assert segredo == {'csrf': global_}
    for escopo, recebido, esperado in [
        (None, global_, True), ('pedido:primeiro-ficticio', primeiro, True),
        ('pedido:primeiro-ficticio', segundo, False), ('pedido:primeiro-ficticio', global_, False),
        (None, primeiro, False), ('pedido:segundo-ficticio', segundo, True),
    ]:
        with app_csrf.test_request_context('/', method='POST', data={'csrf_token': recebido}):
            session.update(segredo)
            assert seguranca.csrf_valido(escopo=escopo) is esperado
            assert dict(session) == segredo


def test_csrf_escopado_nao_cria_segredo_ao_validar(app_csrf):
    with app_csrf.test_request_context('/', method='POST', data={'csrf_token': 'inexistente'}):
        assert not seguranca.csrf_valido(escopo='pedido:ficticio')
        assert not session


@pytest.mark.parametrize('chave', ['chave-servidor-ficticia', b'chave-servidor-ficticia'])
def test_csrf_escopado_depende_do_segredo_do_servidor_e_da_sessao(app_csrf, chave):
    app_csrf.secret_key = chave
    escopo = 'pedido:ficticio'
    with app_csrf.test_request_context('/'):
        raiz_publica = seguranca.csrf()
        token = seguranca.csrf(escopo)
        segredo = dict(session)
    # Conhecer o token global não permite assinar outro contexto.
    forjado = hmac.new(raiz_publica.encode(), escopo.encode(), 'sha256').hexdigest()
    with app_csrf.test_request_context('/', method='POST', headers={'X-CSRF-Token': forjado}):
        session.update(segredo)
        assert not seguranca.csrf_valido(escopo=escopo)
    with app_csrf.test_request_context('/', method='POST', headers={'X-CSRF-Token': token}):
        session['csrf'] = 'outra-sessao-ficticia'
        assert not seguranca.csrf_valido(escopo=escopo)
    app_csrf.secret_key = b'outra-chave-servidor-ficticia'
    with app_csrf.test_request_context('/', method='POST', headers={'X-CSRF-Token': token}):
        session.update(segredo)
        assert not seguranca.csrf_valido(escopo=escopo)


@pytest.mark.parametrize('cabecalhos', [
    {'Origin': 'https://invasor.example'}, {'Origin': 'null'}, {'Sec-Fetch-Site': 'cross-site'},
])
def test_csrf_escopado_mantem_recusa_de_origem(app_csrf, cabecalhos):
    with app_csrf.test_request_context('/'):
        token = seguranca.csrf('pedido:ficticio')
        segredo = dict(session)
    with app_csrf.test_request_context('/', method='POST', headers=cabecalhos, data={'csrf_token': token}):
        session.update(segredo)
        assert not seguranca.csrf_valido(escopo='pedido:ficticio')


def test_csrf_escopado_mantem_recusa_de_parametros_repetidos(app_csrf):
    with app_csrf.test_request_context('/'):
        token = seguranca.csrf('pedido:ficticio')
        segredo = dict(session)
    dados = MultiDict([('csrf_token', token), ('nome', 'Pessoa fictícia'), ('nome', 'Outra fictícia')])
    with app_csrf.test_request_context('/', method='POST', data=dados):
        session.update(segredo)
        assert not seguranca.csrf_valido(escopo='pedido:ficticio')
