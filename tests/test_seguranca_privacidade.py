"""Testes com dados fictícios, sem serviços, contas ou mensagens reais."""
import os
import sqlite3
from contextlib import closing
from unittest.mock import Mock

import pytest
from werkzeug.security import generate_password_hash

from src import config, preferencias, pedidos, estoque, processamento, privacidade, seguranca, backups, ia
from src.db import get_conn, init_db
from src.links import gerar_link_pedido

TELEFONE = "5511999990000"
SENHA = "uma-senha-de-backup-forte"


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "loja.db"))
    monkeypatch.setattr(config, "SEED_CATALOGO", False)
    for chave in preferencias.CAMPOS | {"MODO_TESTE", "ADMIN_PERMITIR_REMOTO", "COZINHA_AUTH_MODO", "COZINHA_USUARIO", "COZINHA_SENHA_HASH"}:
        monkeypatch.setattr(config, chave, getattr(config, chave))
    config.FORMAS_PAGAMENTO = "Pix,Dinheiro"
    config.MODO_TESTE = True
    config.WHATSAPP_PROVIDER = "TESTE"
    config.LGPD_MENSAGENS_DIAS = 30
    config.LGPD_IA_EXTERNA = "NAO"
    config.ADMIN_PERMITIR_REMOTO = False
    config.COZINHA_AUTH_MODO = "SENHA"
    config.COZINHA_USUARIO = "operador"
    config.COZINHA_SENHA_HASH = generate_password_hash("senha-de-operador")
    seguranca._tentativas.clear()
    init_db()


@pytest.fixture
def cliente(monkeypatch):
    from src.app import app
    monkeypatch.setitem(app.config, "DESKTOP_TOKEN", "token-teste-local")
    c = app.test_client()
    c.get("/gestao?acesso=token-teste-local", follow_redirects=True)
    with c.session_transaction() as sessao:
        token = sessao["csrf"]
    return c, {"X-CSRF-Token": token}


def compra():
    p = estoque.salvar_produto({"nome": "Caderno", "categoria": "Papelaria", "preco": 10, "estoque": 5})
    return pedidos.criar_pedido(TELEFONE, "Ana Fictícia", [{"produto_id": p["id"], "quantidade": 1}], "Pix", cep="01000-000", endereco="Rua Fictícia, 123")


def titular(**campos):
    return {"telefone": TELEFONE, "identidade_confirmada": True, **campos}


def test_administracao_recusa_rede_e_dns_rebinding(cliente):
    c, _ = cliente
    for caminho in ("/gestao/api/privacidade", "/gestao/api/pedidos"):
        assert c.get(caminho, environ_overrides={"REMOTE_ADDR": "192.168.1.9"}).status_code == 401
        assert c.get(caminho, headers={"Host": "ataque.example"}).status_code == 401
    assert c.get("/cozinha", environ_overrides={"REMOTE_ADDR": "192.168.1.9"}).status_code == 403


def test_csrf_na_cozinha_e_origem_cruzada(cliente):
    c, headers = cliente
    pedido = compra()
    auth = ("operador", "senha-de-operador")
    assert c.get("/cozinha", auth=auth).status_code == 200
    assert c.post(f'/cozinha/avancar/{pedido["id"]}', auth=auth).status_code == 403
    assert c.post(f'/cozinha/avancar/{pedido["id"]}', auth=auth, headers={**headers, "Origin": "https://ataque.example"}).status_code == 403
    assert c.post(f'/cozinha/avancar/{pedido["id"]}', auth=auth, headers=headers).status_code == 302
    assert c.post('/gestao/api/privacidade/exportar', headers={**headers,"Sec-Fetch-Site":"cross-site"}, json=titular()).status_code == 403


def test_limite_de_tentativas_senha(cliente, monkeypatch):
    c, _ = cliente
    for _ in range(10):
        assert c.get("/cozinha", auth=("operador", "errada")).status_code == 401
    assert c.get("/cozinha", auth=("operador", "senha-de-operador")).status_code == 429
    instante = seguranca.time.monotonic()
    monkeypatch.setattr(seguranca.time, "monotonic", lambda: instante + 301)
    assert c.get("/cozinha", auth=("operador", "senha-de-operador")).status_code == 200


def test_headers_e_scripts_sem_recurso_externo(cliente):
    c, _ = cliente
    r = c.get('/privacidade')
    assert r.headers['Cache-Control'] == 'no-store'
    assert r.headers['Referrer-Policy'] == 'no-referrer'
    assert "frame-ancestors 'none'" in r.headers['Content-Security-Policy']
    assert "script-src 'self' 'nonce-" in r.headers['Content-Security-Policy']
    html = c.get('/cozinha', auth=('operador','senha-de-operador')).get_data(as_text=True)
    assert 'fonts.googleapis.com' not in html and '<script nonce=' in html


def test_formulario_publico_protege_pedido_e_nao_vaza_dados(cliente):
    c, headers = cliente
    p = estoque.salvar_produto({"nome": "Caneta", "categoria": "Papelaria", "preco": 5, "estoque": 1})
    url = gerar_link_pedido(TELEFONE).replace(config.BASE_URL, '')
    pagina = c.get(url)
    assert b'aviso de privacidade' in pagina.data and b'csrf_token' in pagina.data
    corpo = {'nome':'Ana', 'forma_pagamento':'Pix',f'qtd_{p["id"]}':'1'}
    assert c.post(url, data=corpo).status_code == 403
    assert c.post(url, data={**corpo,'csrf_token':headers['X-CSRF-Token']}).status_code == 303
    assert c.get(url).status_code == 410


def test_credencial_protegida_e_migracao_sem_perda():
    preferencias.salvar({'WAHA_API_KEY':'chave-ficticia-privada'})
    with get_conn() as conn:
        armazenado = conn.execute("SELECT valor FROM configuracoes WHERE chave='WAHA_API_KEY'").fetchone()[0]
        if os.name == 'nt':
            assert armazenado.startswith('dpapi:v1:') and 'chave-ficticia' not in armazenado
        conn.execute("UPDATE configuracoes SET valor='antiga-ficticia' WHERE chave='WAHA_API_KEY'")
    preferencias.carregar()
    assert config.WAHA_API_KEY == 'antiga-ficticia'
    with get_conn() as conn:
        assert seguranca.revelar_segredo(conn.execute("SELECT valor FROM configuracoes WHERE chave='WAHA_API_KEY'").fetchone()[0]) == 'antiga-ficticia'


def test_backup_portavel_sem_credenciais_e_sem_texto_claro(tmp_path):
    compra()
    marcador = 'Cliente fictício Ana — identificação privada no backup'
    preferencias.salvar({'ANTHROPIC_API_KEY':'segredo-ficticio','NOME_RESTAURANTE':'Loja de teste'})
    legado = 'credencial-legada-ficticia-' * 250
    with get_conn() as origem:
        origem.execute('UPDATE clientes SET nome=? WHERE telefone=?', (marcador, TELEFONE))
        origem.execute("INSERT OR REPLACE INTO configuracoes(chave,valor) VALUES('WAHA_API_KEY',?)", (legado,))
    caminho = backups.criar(SENHA)
    bruto = __import__('pathlib').Path(caminho).read_bytes()
    # Ciphertext aleatório pode conter três bytes como b'Ana'; verifica o dado completo.
    assert marcador.encode() not in bruto and TELEFONE.encode() not in bruto and b'SQLite format' not in bruto
    decifrado = backups.abrir_arquivo(caminho, SENHA)
    assert b'credencial-legada-ficticia-' not in decifrado
    with closing(sqlite3.connect(':memory:')) as conn:
        conn.deserialize(decifrado)
        assert conn.execute('SELECT nome FROM clientes').fetchone()[0] == marcador
        assert not conn.execute("SELECT 1 FROM configuracoes WHERE chave='ANTHROPIC_API_KEY'").fetchone()
    with pytest.raises(ValueError, match='Senha incorreta'):
        backups.decifrar(bruto, SENHA+'errada')
    with pytest.raises(ValueError, match='alterado'):
        backups.decifrar(bruto[:-1]+bytes([bruto[-1]^1]), SENHA)


def test_backup_exige_senha_forte(cliente):
    c, headers = cliente
    for senha in (None, '123', 123456789012):
        assert c.post('/gestao/api/backup',json={'senha':senha},headers=headers).status_code == 400


def test_exportacao_restrita_sem_tokens_e_auditoria_sem_telefone(cliente):
    c, headers = cliente
    compra()
    link = gerar_link_pedido(TELEFONE)
    pedidos.registrar_mensagem(TELEFONE,'SAIDA',link)
    assert c.post('/gestao/api/privacidade/exportar',json={'telefone':TELEFONE},headers=headers).status_code == 400
    r = c.post('/gestao/api/privacidade/exportar',json=titular(),headers=headers)
    assert r.status_code == 200 and r.json['cliente']['nome'] == 'Ana Fictícia'
    assert link.rsplit('/',1)[-1] not in r.get_data(as_text=True)
    assert 'WEBHOOK_SECRET' not in r.get_data(as_text=True)
    with get_conn() as conn:
        assert TELEFONE not in str([dict(x) for x in conn.execute('SELECT * FROM auditoria_privacidade')])


def test_correcao_validada_e_remocao_preserva_venda(cliente):
    c, headers = cliente
    pedido = compra()
    r = c.post('/gestao/api/privacidade/corrigir',json=titular(nome='Nome corrigido',cep='',endereco=''),headers=headers)
    assert r.status_code == 200
    assert pedidos.obter_pedido(pedido['id'])['cliente_nome'] == 'Nome corrigido'
    dados = titular(confirmar_remocao=True)
    assert c.post('/gestao/api/privacidade/remover',json=dados,headers=headers).status_code == 400
    pedidos.cancelar_pedido(pedido['id'])
    pedidos.registrar_mensagem(TELEFONE,'ENTRADA','texto privado')
    gerar_link_pedido(TELEFONE)
    assert c.post('/gestao/api/privacidade/remover',json=dados,headers=headers).status_code == 200
    p = pedidos.obter_pedido(pedido['id'])
    assert p['total_pedido'] == pedido['total_pedido'] and p['itens'] == pedido['itens']
    assert p['cliente_nome'] == 'Cliente sem identificação' and TELEFONE != p['cliente_telefone']
    with get_conn() as conn:
        for tabela in ('mensagens','links_pedido','tarefas_bot','sessoes_bot'):
            assert not conn.execute(f'SELECT 1 FROM {tabela} WHERE telefone=?',(TELEFONE,)).fetchone()
    assert estoque.listar_produtos()[0]['estoque'] == 5


def test_remocao_bloqueada_durante_envio():
    tarefa = processamento.enfileirar({'telefone':TELEFONE,'texto':'oi'})
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='ENVIANDO' WHERE id=?",(tarefa['id'],))
    with pytest.raises(ValueError, match='processamento'):
        privacidade.remover_identificacao(titular(confirmar_remocao=True))


def test_limpeza_preserva_pendentes_e_deduplicacao():
    pedidos.registrar_mensagem(TELEFONE,'ENTRADA','antiga')
    outro = '5511888880000'
    pedidos.registrar_mensagem(outro,'ENTRADA','pendente')
    chave = TELEFONE+'@lid:mensagem-ficticia'
    tarefa = processamento.enfileirar({'telefone':TELEFONE,'texto':'concluida'},chave)
    processamento.enfileirar({'telefone':outro,'texto':'pendente'},'pendente')
    with get_conn() as conn:
        conn.execute("UPDATE mensagens SET criado_em=datetime('now','-60 days')")
        conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA', atualizado_em=datetime('now','-60 days') WHERE id=?",(tarefa['id'],))
    assert privacidade.limpar_historico()['mensagens'] == 1
    with get_conn() as conn:
        r = conn.execute('SELECT * FROM tarefas_bot WHERE id=?',(tarefa['id'],)).fetchone()
        assert r['telefone'] == '' and r['texto'] == '' and TELEFONE not in r['chave']
        assert conn.execute('SELECT conteudo FROM mensagens').fetchone()[0] == 'pendente'
    assert processamento.enfileirar({'telefone':TELEFONE,'texto':'duplicada'},chave)['duplicada']


def test_ia_minimiza_cadastro_email_telefone_documento_e_link():
    compra()
    conteudo = f'Ana Fictícia, Rua Fictícia, 123; CEP 01000-000, {TELEFONE}, teste@example.com, 123.456.789-00, https://loja.example/m/tokenprivado'
    filtrado = privacidade.reduzir_para_ia(TELEFONE, conteudo)
    for item in ('Ana Fictícia','Rua Fictícia','01000-000',TELEFONE,'teste@example.com','123.456.789-00','tokenprivado'):
        assert item not in filtrado


@pytest.mark.parametrize('provedor,url',[('ANTHROPIC','http://localhost:11434'),('OLLAMA','https://ia.example')])
def test_ia_externa_desativada_por_padrao(monkeypatch, provedor, url):
    config.IA_PROVIDER = provedor
    config.OLLAMA_URL = url
    remoto = Mock(side_effect=AssertionError('não deve transmitir'))
    monkeypatch.setattr(ia,'_responder_anthropic',remoto)
    monkeypatch.setattr(ia,'_responder_ollama',remoto)
    with pytest.raises(ia.IAIndisponivel, match='externa desativado'):
        ia.responder(TELEFONE,'oi')
    remoto.assert_not_called()


def test_log_filtra_credenciais_e_nao_exibe_corpo_em_modo_teste(capsys, caplog):
    from src import whatsapp
    whatsapp.enviar_mensagem(TELEFONE,'texto privado')
    assert 'texto privado' not in capsys.readouterr().out
    dados = seguranca.reduzir_dados(f'https://x.example/m/segredo {TELEFONE} https://x.example/webhook/waha/chave ?acesso=token')
    assert not any(x in dados for x in ('segredo',TELEFONE,'/chave','token'))


def test_protecao_da_pasta_preserva_arquivos(tmp_path):
    pasta = tmp_path / 'dados'
    pasta.mkdir()
    (pasta/'arquivo.txt').write_text('preservado')
    seguranca.proteger_pasta(pasta)
    assert (pasta/'arquivo.txt').read_text() == 'preservado'


def test_aviso_no_primeiro_atendimento_e_comando_sem_ia(monkeypatch):
    from src import bot
    original = bot._processar
    resposta = Mock(return_value='Olá!')
    monkeypatch.setattr(bot, '_processar', resposta)
    assert '/privacidade' in bot.processar_mensagem(TELEFONE,'oi')
    assert '/privacidade' not in bot.processar_mensagem(TELEFONE,'oi de novo')
    monkeypatch.setattr(bot, '_processar', original)
    externo = Mock(side_effect=AssertionError('O comando de privacidade não deve chamar IA'))
    monkeypatch.setattr(ia, 'responder', externo)
    assert '/privacidade' in bot.processar_mensagem(TELEFONE,'PRIVACIDADE')
    externo.assert_not_called()


def test_ia_nao_transmite_link_real_para_provedor(monkeypatch):
    from types import SimpleNamespace
    config.IA_PROVIDER = 'ANTHROPIC'
    config.LGPD_IA_EXTERNA = 'SIM'
    config.ANTHROPIC_API_KEY = 'chave-ficticia'
    blocotool = SimpleNamespace(type='tool_use',name='gerar_link_pedido',id='ferramenta-ficticia')
    resposta1 = SimpleNamespace(stop_reason='tool_use',content=[blocotool])
    resposta2 = SimpleNamespace(stop_reason='end_turn',content=[SimpleNamespace(type='text',text='Compre: [LINK_PEDIDO_1]')])
    api = Mock(side_effect=[resposta1,resposta2])
    monkeypatch.setattr(ia, 'anthropic', SimpleNamespace(Anthropic=lambda **_:SimpleNamespace(messages=SimpleNamespace(create=api))))
    resultado = ia.responder(TELEFONE,'quero comprar')
    token = resultado.rsplit('/',1)[-1]
    assert '/m/' in resultado and len(token) >= 40
    assert token not in str(api.call_args_list)
    assert '[LINK_PEDIDO_1]' in str(api.call_args_list)


def test_https_para_provedor_externo_e_cookie_seguro(cliente):
    with pytest.raises(ValueError,match='HTTPS'):
        seguranca.transporte_seguro('http://servidor.example')
    seguranca.transporte_seguro('http://127.0.0.1:3000')
    seguranca.transporte_seguro('https://servidor.example')
    c, _ = cliente
    resposta = c.get('/gestao?acesso=token-teste-local', base_url='https://localhost')
    assert 'Secure' in resposta.headers['Set-Cookie']


def test_backup_recusa_estruturas_nao_previstas(tmp_path):
    from desktop import validar_backup
    arquivo = tmp_path/'invalido.db'
    with closing(sqlite3.connect(arquivo)) as conn:
        conn.executescript('CREATE TABLE dados(id); CREATE VIEW estranha AS SELECT * FROM dados;')
    with pytest.raises(ValueError,match='estruturas'):
        validar_backup(arquivo)
