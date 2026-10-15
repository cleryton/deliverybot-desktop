"""Acesso remoto com contas fictícias, sem túnel nem mensagens reais."""
import re
import time
from unittest.mock import Mock

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

from src import acesso_remoto as remoto, config, operadores, publicacao, fila, estoque, pedidos, whatsapp
from src.db import get_conn, init_db
from src.politica_terminal import Limites


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticio.db'))
    monkeypatch.setattr(config, 'MODO_TESTE', True)
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    monkeypatch.setattr(config, 'BASE_URL', 'https://loja-ficticia.example')
    monkeypatch.setattr(publicacao, '_gerente', None)
    monkeypatch.setattr(remoto, '_limites', Limites())
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', Mock())
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'desktop-ficticio')
    local = app.test_client()
    local.get('/gestao?acesso=desktop-ficticio')
    with local.session_transaction() as s:
        headers = {'X-CSRF-Token': s['csrf']}
    def conta(login, perfil):
        r = local.post('/gestao/api/operadores', headers=headers, json={'nome': login, 'login': login, 'senha': 'senha-ficticia-123', 'perfil': perfil})
        assert r.status_code == 200
        return r.json['id']
    admin = conta('patrao', 'ADMIN')
    atendente = conta('atendente', 'ATENDENTE')
    caixa = conta('caixa', 'CAIXA')
    publico = Client(publicacao.PaginaPublica(app, publicacao.endereco), Response)
    return app, local, headers, publico, admin, atendente, caixa


def convite(a, **extra):
    d = {'operador_id': a[5], 'minutos': 60, 'permissao': 'CONSULTA', **extra}
    r = a[1].post('/gestao/api/remoto', headers=a[2], json=d)
    assert r.status_code == 201, r.json
    return r.json


def csrf(c):
    r = c.get('/remoto', base_url=config.BASE_URL)
    assert r.status_code == 200
    return re.search(r'name="csrf-token" content="([^"]+)"', r.text)[1]


def entrar(a, acesso=None, cliente=None, **extra):
    acesso = acesso or convite(a)
    c = cliente or a[3]
    h = {'X-CSRF-Token': csrf(c), 'Origin': config.BASE_URL}
    r = c.post('/remoto/api/entrar', base_url=config.BASE_URL, headers=h,
               json={'convite': acesso['link'].split('#')[1], 'login': 'atendente', 'senha': 'senha-ficticia-123', **extra})
    return c, r, {'X-CSRF-Token': r.json.get('csrf', h['X-CSRF-Token']), 'Origin': config.BASE_URL}


def pedido():
    p = estoque.salvar_produto({'nome': 'Produto fictício', 'categoria': 'Teste', 'preco': 15, 'estoque': 3, 'custo': 4})
    return pedidos.criar_pedido(telefone='5511999999999', nome_cliente='Pessoa fictícia', endereco='Endereço privado', itens=[{'produto_id': p['id'], 'quantidade': 1}], forma_entrega='RETIRADA BALCAO', forma_pagamento='Dinheiro')


def test_convite_guarda_so_hash_e_listagem_nao_expoe_segredos(ambiente):
    a = ambiente; r = convite(a); segredo = r['link'].split('#')[1]
    with get_conn() as c:
        registro = dict(c.execute('SELECT * FROM acessos_remotos').fetchone())
    assert registro['convite_hash'] == remoto._hash(segredo)
    assert segredo not in str(registro)
    s = a[1].get('/gestao/api/remoto').json
    assert segredo not in str(s) and 'convite_hash' not in str(s) and 'sessao_hash' not in str(s)


@pytest.mark.parametrize('campo,valor', [('minutos', True), ('minutos', 0), ('minutos', 10080), ('operador_id', True), ('permissao', 'ADMIN')])
def test_dados_invalidos_nao_abrem_acesso(ambiente, campo, valor):
    a = ambiente
    d = {'operador_id': a[5], 'minutos': 60, 'permissao': 'CONSULTA', campo: valor}
    assert a[1].post('/gestao/api/remoto', headers=a[2], json=d).status_code == 400


def test_nao_cria_convite_sem_https_ou_para_caixa(ambiente, monkeypatch):
    a = ambiente
    assert a[1].post('/gestao/api/remoto', headers=a[2], json={'operador_id': a[6], 'minutos': 60, 'permissao': 'CONSULTA'}).status_code == 400
    monkeypatch.setattr(config, 'BASE_URL', 'http://localhost:5000')
    assert a[1].post('/gestao/api/remoto', headers=a[2], json={'operador_id': a[5], 'minutos': 60, 'permissao': 'CONSULTA'}).status_code == 400


def test_link_so_aceita_conta_vinculada_e_uma_unica_entrada(ambiente):
    a = ambiente; invite = convite(a)
    _, r, _ = entrar(a, invite, login='patrao')
    assert r.status_code == 401
    _, r, _ = entrar(a, invite, senha='incorreta-senha')
    assert r.status_code == 401
    c, r, h = entrar(a, invite)
    assert r.status_code == 200
    assert 'Secure;' in r.headers['Set-Cookie'] and 'HttpOnly;' in r.headers['Set-Cookie']
    assert c.get('/remoto/api/estado', base_url=config.BASE_URL).status_code == 200
    outro = Client(publicacao.PaginaPublica(a[0], publicacao.endereco), Response)
    assert entrar(a, invite, cliente=outro)[1].status_code == 401


def test_sem_convite_nao_herda_desktop_nem_conta_admin(ambiente):
    a = ambiente
    # Mesmo uma sessão administrativa válida não autoriza o gateway remoto.
    cookie = a[1].get_cookie('session').value
    c = Client(publicacao.PaginaPublica(a[0], publicacao.endereco), Response, use_cookies=False)
    h = {'Cookie': 'session=' + cookie, 'Host': 'localhost', 'X-Forwarded-For': '127.0.0.1'}
    assert c.get('/remoto/api/estado', headers=h).status_code == 401
    assert a[1].get('/remoto', headers={'X-Deliverybot-Remote-Gateway': 'true'}).status_code == 404


def test_dados_remotos_minimizados_e_gestao_interna_bloqueada(ambiente):
    a = ambiente; pedido()
    c, r, _ = entrar(a)
    assert r.status_code == 200
    s = c.get('/remoto/api/estado', base_url=config.BASE_URL).json
    assert len(s['pedidos']) == 1 and len(s['produtos']) == 1
    assert not any(chave in str(s) for chave in ('cliente_telefone', 'endereco', 'senha_hash', 'custo', 'WHATSAPP_TOKEN'))
    for path in ['/gestao', '/gestao/api/remoto', '/gestao/api/configuracoes', '/gestao/api/backup', '/terminal/estado', '/cozinha', '/static/acesso_remoto_admin.js', '/static/gestao.js']:
        assert c.get(path, base_url=config.BASE_URL).status_code == 404


@pytest.mark.parametrize('sql', [
    'UPDATE acessos_remotos SET ativo=0', 'UPDATE acessos_remotos SET expira_em=1',
    'UPDATE acessos_remotos SET ultimo=1', 'UPDATE operadores SET ativo=0',
    "UPDATE operadores SET versao='nova'", "UPDATE operadores SET perfil='CAIXA'",
])
def test_revogacao_expiracao_e_troca_de_conta_invalidam_cookie(ambiente, sql):
    c, r, h = entrar(ambiente)
    assert r.status_code == 200
    with get_conn() as conn: conn.execute(sql)
    assert c.get('/remoto/api/estado', base_url=config.BASE_URL).status_code == 401


def test_sair_revoga_cookie_copiado_e_todos_revoga_convites(ambiente):
    a = ambiente
    c, _, h = entrar(a)
    cookie = c.get_cookie('session', domain='loja-ficticia.example').value
    assert c.post('/remoto/api/sair', base_url=config.BASE_URL, headers=h, json={}).status_code == 200
    outro = Client(publicacao.PaginaPublica(a[0], publicacao.endereco), Response, use_cookies=False)
    assert outro.get('/remoto/api/estado', headers={'Cookie': 'session=' + cookie}).status_code == 401
    invite = convite(a)
    assert a[1].delete('/gestao/api/remoto', headers=a[2], json={'confirmar': True}).status_code == 200
    assert entrar(a, invite)[1].status_code == 401


def test_csrf_obrigatorio_em_login_e_alteracoes_e_admin(ambiente):
    a = ambiente; invite = convite(a)
    assert a[3].post('/remoto/api/entrar', base_url=config.BASE_URL, json={}).status_code == 403
    c, _, h = entrar(a, invite)
    for origem in ['https://invasor.example', 'null']:
        assert c.post('/remoto/api/sair', base_url=config.BASE_URL, headers={**h, 'Origin': origem}, json={}).status_code == 403
    assert a[1].post('/gestao/api/remoto', json={}).status_code == 403
    assert a[1].delete('/gestao/api/remoto', headers=a[2], json={}).status_code == 400


def test_consulta_nao_avanca_e_operacao_usa_status_esperado(ambiente):
    a = ambiente; p = pedido(); pid = p['id']
    c, _, h = entrar(a)
    path = f'/remoto/api/pedidos/{pid}/avancar'
    assert c.post(path, base_url=config.BASE_URL, headers=h, json={'confirmar': True, 'status': 'AGUARDANDO'}).status_code == 403
    c, _, h = entrar(a, convite(a, permissao='PEDIDOS'))
    data = {'confirmar': True, 'status': 'AGUARDANDO'}
    assert c.post(path, base_url=config.BASE_URL, headers=h, json=data).status_code == 200
    assert c.post(path, base_url=config.BASE_URL, headers=h, json=data).status_code == 400
    assert pedidos.obter_pedido(pid)['status'] == 'EM_PREPARO'
    whatsapp.enviar_mensagem.assert_called_once()
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM auditoria_operadores WHERE acao='REMOTO_AVANCAR'").fetchone()[0] == 1


def test_revogacao_antes_da_transacao_impede_pedido_e_aviso(ambiente, monkeypatch):
    a = ambiente; p = pedido(); c, _, h = entrar(a, convite(a, permissao='PEDIDOS'))
    original = fila.avancar_status
    def revogar_primeiro(*args, **kw):
        with get_conn() as conn: conn.execute('UPDATE acessos_remotos SET ativo=0')
        return original(*args, **kw)
    monkeypatch.setattr(fila, 'avancar_status', revogar_primeiro)
    assert c.post(f"/remoto/api/pedidos/{p['id']}/avancar", base_url=config.BASE_URL, headers=h, json={'confirmar': True, 'status': 'AGUARDANDO'}).status_code == 401
    assert pedidos.obter_pedido(p['id'])['status'] == 'RECEBIDO'
    whatsapp.enviar_mensagem.assert_not_called()


def test_limite_de_login_nao_confia_em_ip_forjado(ambiente):
    a = ambiente; invite = convite(a)
    for _ in range(10):
        assert entrar(a, invite, senha='senha-errada-123')[1].status_code == 401
    assert entrar(a, invite)[1].status_code == 429


def test_gerencia_exige_admin_local_e_nao_so_senha_cozinha(ambiente, monkeypatch):
    a = ambiente
    with a[1].session_transaction() as s:
        with get_conn() as c: v = c.execute('SELECT versao FROM operadores WHERE id=?', (a[5],)).fetchone()[0]
        s['operador_id'] = a[5]; s['operador_versao'] = v
    assert a[1].get('/gestao/api/remoto').status_code == 403
    monkeypatch.setitem(a[0].config, 'DESKTOP_TOKEN', None)
    assert a[1].get('/gestao/api/remoto').status_code in {401, 403}


def test_reinicio_e_convite_expirado_ficam_fechados(ambiente):
    a = ambiente; invite = convite(a)
    with get_conn() as conn: conn.execute('UPDATE acessos_remotos SET expira_em=1')
    assert entrar(a, invite)[1].status_code == 401
    invite = convite(a)
    remoto.encerrar_ao_iniciar()
    assert entrar(a, invite)[1].status_code == 401


def test_numero_de_convites_e_tamanho_de_requisicao_limitados(ambiente):
    a = ambiente
    with get_conn() as c:
        versao = c.execute('SELECT versao FROM operadores WHERE id=?', (a[5],)).fetchone()[0]
        for n in range(20):
            c.execute('INSERT INTO acessos_remotos(operador_id,conta_versao,convite_hash,permissao,expira_em) VALUES(?,?,?,?,?)', (a[5], versao, str(n), 'CONSULTA', time.time() + 60))
    assert a[1].post('/gestao/api/remoto', headers=a[2], json={'operador_id': a[5], 'minutos': 60, 'permissao': 'CONSULTA'}).status_code == 400
    token = csrf(a[3])
    assert a[3].post('/remoto/api/entrar', base_url=config.BASE_URL, headers={'X-CSRF-Token': token}, json={'convite': 'x' * 5000}).status_code == 413


def test_troca_de_senha_durante_login_impede_consumir_convite(ambiente, monkeypatch):
    a = ambiente; invite = convite(a)
    original = remoto.check_password_hash
    def trocar(hash_, senha):
        with get_conn() as c: c.execute("UPDATE operadores SET versao='trocada' WHERE id=?", (a[5],))
        return original(hash_, senha)
    monkeypatch.setattr(remoto, 'check_password_hash', trocar)
    assert entrar(a, invite)[1].status_code == 401


def test_avanco_invalido_nao_executa_e_revogar_um_preserva_outros(ambiente):
    a = ambiente; primeiro = convite(a); segundo = convite(a)
    assert a[1].delete('/gestao/api/remoto/' + str(primeiro['id']), headers=a[2], json={'confirmar': True}).status_code == 200
    assert entrar(a, primeiro)[1].status_code == 401
    c, r, h = entrar(a, segundo)
    assert r.status_code == 200
    for d in [[], {'status': []}, {'status': 'AGUARDANDO', 'confirmar': 'sim'}]:
        assert c.post('/remoto/api/pedidos/999/avancar', base_url=config.BASE_URL, headers=h, json=d).status_code == 400


def test_autorizacao_do_responsavel_revalidada_dentro_da_transacao(ambiente, monkeypatch):
    a = ambiente; original = remoto.criar
    def criar_apos_revogacao(d):
        with get_conn() as c: c.execute("UPDATE operadores SET perfil='ATENDENTE' WHERE id=?", (a[4],))
        return original(d)
    monkeypatch.setattr(remoto, 'criar', criar_apos_revogacao)
    assert a[1].post('/gestao/api/remoto', headers=a[2], json={'operador_id':a[5], 'minutos':60, 'permissao':'PEDIDOS'}).status_code == 400
    with get_conn() as c:
        assert c.execute('SELECT COUNT(*) FROM acessos_remotos').fetchone()[0] == 0
