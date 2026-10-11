"""Regressões do acesso público, com dados fictícios e sem contas WhatsApp."""
import io
import threading
from unittest.mock import Mock

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

from src import config, preferencias, publicacao
from src.db import get_conn, init_db


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'loja.db'))
    for chave in preferencias.CAMPOS | {'MODO_TESTE'}:
        monkeypatch.setattr(config, chave, getattr(config, chave))
    config.WHATSAPP_PROVIDER = 'TESTE'
    config.MODO_TESTE = True
    config.TUNEL_AUTOMATICO = 'NAO'
    config.TUNEL_MODO = 'RAPIDO'
    config.TUNEL_URL = config.TUNEL_TOKEN = ''
    config.BASE_URL = 'http://localhost:5000'
    monkeypatch.setattr(publicacao, '_gerente', None)
    init_db(seed_cardapio=False)


@pytest.fixture
def aplicativo(monkeypatch):
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'token-desktop-ficticio')
    return app


def gerente_online(aplicativo, monkeypatch, url='https://loja-ficticia.trycloudflare.com'):
    g = publicacao.Publicacao(aplicativo)
    g.ativo = True
    g._status('ONLINE', 'Conector fictício.', url)
    monkeypatch.setattr(publicacao, '_gerente', g)
    return g


def painel(aplicativo):
    c = aplicativo.test_client()
    c.get('/gestao?acesso=token-desktop-ficticio')
    with c.session_transaction() as s:
        h = {'X-CSRF-Token': s['csrf']}
    return c, h


def test_gateway_bloqueia_painel_mesmo_com_sessao_e_host_forjados(aplicativo, monkeypatch):
    gerente_online(aplicativo, monkeypatch)
    c, _ = painel(aplicativo)
    publico = Client(publicacao.PaginaPublica(aplicativo, publicacao.endereco), Response, use_cookies=False)
    headers = {'Cookie': 'session=' + c.get_cookie('session').value, 'Host': '127.0.0.1',
               'X-Forwarded-For': '127.0.0.1', 'X-Forwarded-Host': 'localhost', 'X-Forwarded-Proto': 'http'}
    for caminho in ['/gestao?acesso=token-desktop-ficticio', '/gestao/api/configuracoes', '/cozinha', '/testar', '/', '/static/gestao.js', '/static/../templates/gestao.html', '//gestao', '/m/../gestao', '/api/bot/mensagem/segredo']:
        r = publico.get(caminho, headers=headers)
        assert r.status_code == 404, caminho
        assert not r.headers.get('Set-Cookie')
    assert publico.get('/privacidade', headers=headers).status_code == 200
    assert publico.get('/webhook/waha/incorreto', headers=headers).status_code == 404
    assert publico.post('/webhook/waha/incorreto', headers=headers).status_code == 404


def test_compra_https_cookie_seguro_e_csrf(aplicativo, monkeypatch):
    import re
    from src import estoque, whatsapp
    from src.links import gerar_link_pedido
    gerente_online(aplicativo, monkeypatch)
    envio = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', envio)
    produto = estoque.salvar_produto({'nome': 'Produto fictício', 'categoria': 'Teste', 'preco': 10, 'estoque': 2})
    caminho = '/m/' + gerar_link_pedido('5511999990022').rsplit('/', 1)[-1]
    c = Client(publicacao.PaginaPublica(aplicativo, publicacao.endereco), Response)
    r = c.get(caminho, base_url=publicacao.endereco())
    assert r.status_code == 200
    assert 'Secure;' in r.headers['Set-Cookie']
    assert r.headers['Referrer-Policy'] == 'same-origin'
    csrf = re.search(r'name="csrf_token" value="([^"]+)"', r.text)[1]
    dados = {'csrf_token': csrf, 'nome': 'Pessoa fictícia', 'forma_pagamento': 'Dinheiro', 'forma_entrega': 'RETIRADA BALCAO', 'qtd_' + str(produto['id']): '1'}
    assert c.post(caminho, base_url=publicacao.endereco(), data=dados, headers={'Origin': 'https://outro.example'}).status_code == 403
    assert c.post(caminho, base_url=publicacao.endereco(), data=dados, headers={'Origin': 'null'}).status_code == 403
    assert c.post(caminho, base_url=publicacao.endereco(), data=dados, headers={'Origin': publicacao.endereco()}).status_code == 200
    assert estoque.listar_produtos()[0]['estoque'] == 1
    assert c.post(caminho, base_url=publicacao.endereco(), data=dados).status_code == 410


def test_diagnostico_usa_url_da_sessao_e_para_sem_publicar_localhost(aplicativo, monkeypatch):
    g = gerente_online(aplicativo, monkeypatch)
    c, h = painel(aplicativo)
    r = c.post('/gestao/api/preparacao/testar', headers=h).json
    assert r['url'].startswith(publicacao.endereco())
    publico = Client(publicacao.PaginaPublica(aplicativo, publicacao.endereco), Response)
    assert publico.get('/diagnostico/' + r['url'].rsplit('/', 1)[-1]).status_code == 200
    assert c.get('/gestao/api/preparacao').json['abertura_recebida']
    g._status('RECONECTANDO', 'Sem internet')
    assert publicacao.endereco() == ''
    assert publico.get('/privacidade').status_code == 503
    assert config.BASE_URL == 'http://localhost:5000'
    assert c.get('/gestao/api/preparacao').json['endereco_publico'] is False


def test_bot_offline_e_resposta_antiga_recebe_dominio_atual(aplicativo, monkeypatch):
    from src import bot, links
    g = gerente_online(aplicativo, monkeypatch)
    telefone = '5511999990033'
    antigo = bot._resposta_opcao('2', telefone)
    g._status('ONLINE', 'Conectado', 'https://novo-ficticio.trycloudflare.com')
    novo = links.atualizar_resposta(antigo, telefone)
    assert 'novo-ficticio' in novo and 'loja-ficticia' not in novo
    with pytest.raises(ValueError):
        links.atualizar_resposta(antigo, '5511999990044')
    g._status('RECONECTANDO', 'Sem internet')
    assert 'ATENDENTE' in bot._resposta_opcao('2', telefone)
    with pytest.raises(ValueError):
        links.atualizar_resposta(antigo, telefone)
    assert links.atualizar_resposta('Olá, tudo bem?', telefone) == 'Olá, tudo bem?'
    g.ativo = False
    config.MODO_TESTE = False
    assert 'ATENDENTE' in bot._resposta_opcao('2', telefone)


def test_link_expirado_na_fila_gera_outro(aplicativo, monkeypatch):
    from src import bot, links
    gerente_online(aplicativo, monkeypatch)
    telefone = '5511999990033'
    antigo = bot._resposta_opcao('2', telefone)
    with get_conn() as conn:
        conn.execute("UPDATE links_pedido SET expira_em='2000-01-01 00:00:00'")
    assert links.atualizar_resposta(antigo, telefone) != antigo


def test_configuracao_exige_admin_csrf_e_preserva_token_privado(aplicativo, monkeypatch):
    g = publicacao.Publicacao(aplicativo)
    monkeypatch.setattr(publicacao, '_gerente', g)
    c, h = painel(aplicativo)
    assert c.put('/gestao/api/pagina-publica', json={}).status_code == 403
    dados = {'TUNEL_MODO': 'FIXO', 'TUNEL_URL': 'https://pedidos.example', 'TUNEL_TOKEN': 'token-ficticio', 'TUNEL_AUTOMATICO': 'SIM', 'TUNEL_PORTA': 5051}
    r = c.put('/gestao/api/pagina-publica', json=dados, headers=h)
    assert r.status_code == 200 and r.json['token_configurado']
    assert 'token-ficticio' not in r.text
    with get_conn() as conn:
        segredo = conn.execute("SELECT valor FROM configuracoes WHERE chave='TUNEL_TOKEN'").fetchone()[0]
    if __import__('os').name == 'nt':
        assert segredo.startswith('dpapi:v1:')
    assert c.put('/gestao/api/pagina-publica', json={'TUNEL_TOKEN': ''}, headers=h).status_code == 200
    assert config.TUNEL_TOKEN == 'token-ficticio'
    g.ativo = True
    assert c.put('/gestao/api/pagina-publica', json=dados, headers=h).status_code == 400
    assert c.put('/gestao/api/configuracoes', json={'TUNEL_PORTA': 5052}, headers=h).status_code == 400
    g.ativo = False
    admin = {'nome': 'Responsável fictício', 'login': 'admin', 'senha': 'senha-ficticia-123', 'perfil': 'ADMIN'}
    c.post('/gestao/api/operadores', json=admin, headers=h)
    c.post('/gestao/api/operadores', json={**admin, 'login': 'vendas', 'perfil': 'ATENDENTE'}, headers=h)
    c.post('/gestao/sair', headers=h)
    c.post('/gestao/login', data={'login': 'vendas', 'senha': admin['senha'], 'csrf_token': h['X-CSRF-Token']})
    assert c.get('/gestao/api/pagina-publica').status_code == 403
    assert c.post('/gestao/api/pagina-publica', json={'acao': 'iniciar'}, headers=h).status_code == 403


@pytest.mark.parametrize('url', ['http://loja.example', 'https://localhost', 'https://127.0.0.1', 'https://[::1]', 'https://loja.local', 'https://user:senha@loja.example', 'https://loja.example:5000', 'https://loja.example/caminho', 'https://loja..example', 'https://loja.example?q=1'])
def test_dominio_fixo_rejeita_enderecos_invalidos(url):
    with pytest.raises(ValueError):
        publicacao.validar_dominio(url)


def test_comando_sem_token_nos_argumentos_e_sem_configuracao_externa(aplicativo, tmp_path, monkeypatch):
    g = publicacao.Publicacao(aplicativo)
    g._modo, g._token, g._dominio = 'FIXO', 'segredo-ficticio', 'https://pedidos.example'
    monkeypatch.setenv('TUNNEL_LOGLEVEL', 'debug')
    monkeypatch.setenv('TUNNEL_LOGFILE', 'arquivo-externo.log')
    info = {}
    cmd, env = g._comando('cloudflared.exe', tmp_path, info)
    assert 'segredo-ficticio' not in ' '.join(cmd)
    assert env['TUNNEL_TOKEN'] == 'segredo-ficticio'
    assert 'TUNNEL_LOGFILE' not in env and 'TUNNEL_LOGLEVEL' not in env
    assert info['url'] == 'https://pedidos.example'
    assert (tmp_path / 'conector.yml').read_text() == '{}\n'
    g._modo = 'RAPIDO'
    cmd, env = g._comando('cloudflared.exe', tmp_path, {})
    assert '--url' in cmd and 'TUNNEL_TOKEN' not in env


def test_leitor_aceita_somente_dominio_cloudflare_e_metricas_loopback():
    p = Mock(stdout=io.StringIO('https://evil.example\nStarting metrics server on 0.0.0.0:100/metrics\nhttps://loja-ficticia.trycloudflare.com\nStarting metrics server on 127.0.0.1:9999/metrics\n'))
    info = {}
    publicacao.Publicacao._ler(p, info, threading.Lock())
    assert info == {'url': 'https://loja-ficticia.trycloudflare.com', 'metricas': 'http://127.0.0.1:9999/ready'}


def test_backup_portatil_nao_leva_token(tmp_path):
    import sqlite3
    from src import backups
    preferencias.salvar({'TUNEL_TOKEN': 'segredo-ficticio', 'TUNEL_AUTOMATICO': 'SIM'})
    arquivo = backups.criar('senha-ficticia-longa')
    with sqlite3.connect(':memory:') as c:
        c.deserialize(backups.abrir_arquivo(arquivo, 'senha-ficticia-longa'))
        assert not c.execute("SELECT valor FROM configuracoes WHERE chave='TUNEL_TOKEN'").fetchone()
        assert c.execute("SELECT valor FROM configuracoes WHERE chave='TUNEL_AUTOMATICO'").fetchone()[0] == 'NAO'


def test_inicio_automatico_e_parada_idempotente(aplicativo, monkeypatch):
    iniciar = Mock()
    monkeypatch.setattr(publicacao.Publicacao, 'iniciar', iniciar)
    publicacao.preparar(aplicativo)
    iniciar.assert_not_called()
    config.TUNEL_AUTOMATICO = 'SIM'
    g = publicacao.preparar(aplicativo)
    iniciar.assert_called_once()
    g.encerrar()
    g.encerrar()
    assert not g.ativo and g.situacao()['estado'] == 'DESLIGADO'


def test_conector_alterado_nao_e_executado(aplicativo, tmp_path, monkeypatch):
    import json
    import sys
    (tmp_path / 'packaging').mkdir()
    (tmp_path / 'cloudflare/runtime').mkdir(parents=True)
    (tmp_path / 'packaging/cloudflared.json').write_text(json.dumps({'sha256': '0' * 64}))
    (tmp_path / 'cloudflare/runtime/cloudflared.exe').write_bytes(b'arquivo-alterado-ficticio')
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    with pytest.raises(ValueError, match='ausente ou alterado'):
        publicacao.Publicacao(aplicativo)._binario()


def test_token_ausente_nao_impede_abrir_aplicativo(aplicativo):
    config.TUNEL_AUTOMATICO = 'SIM'
    config.TUNEL_MODO = 'FIXO'
    g = publicacao.preparar(aplicativo)
    assert g.situacao()['estado'] == 'ERRO'
    assert 'token' in g.situacao()['mensagem']
    assert publicacao.endereco() == ''
    g.encerrar()


def test_reinicia_conector_que_cai_e_encerra_todos_recursos(aplicativo, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from src import seguranca
    import waitress
    g = publicacao.Publicacao(aplicativo)
    g.ativo = True
    monkeypatch.setattr(g, '_binario', lambda: tmp_path / 'cloudflared.exe')
    monkeypatch.setattr(seguranca, 'proteger_pasta', lambda _: None)
    servidor = Mock()
    monkeypatch.setattr(waitress, 'create_server', lambda *a, **kw: servidor)
    estados = []
    original = g._status
    monkeypatch.setattr(g, '_status', lambda estado, mensagem, url='': (estados.append(estado), original(estado, mensagem, url)))
    processos = []
    def criar_processo(*a, **kw):
        p = Mock()
        p.poll.return_value = 0 if not processos else None
        p.stdout = io.StringIO('https://loja-ficticia.trycloudflare.com\nStarting metrics server on 127.0.0.1:9999/metrics\n')
        processos.append(p)
        return p
    monkeypatch.setattr(publicacao.subprocess, 'Popen', criar_processo)
    # O leitor é síncrono neste teste; nenhuma thread ou rede real é iniciada.
    def thread(target, args=(), **kw):
        return SimpleNamespace(start=lambda: target(*args) if target == g._ler else None, join=lambda **kw: None)
    monkeypatch.setattr(publicacao.threading, 'Thread', thread)
    class Parada:
        stop = False
        leituras = 0
        def is_set(self):
            return self.stop
        def wait(self, segundos):
            if len(processos) > 1 and segundos == 2:
                self.leituras += 1
                if self.leituras > 1:
                    self.stop = True
            return self.stop
    g._stop = Parada()
    http = MagicMock()
    http.__enter__.return_value = http
    http.get.return_value.__enter__.return_value.status_code = 200
    http.get.return_value.__enter__.return_value.iter_content.return_value = [g._verificacao.encode()]
    monkeypatch.setattr(publicacao.requests, 'Session', lambda: http)
    g._executar()
    assert len(processos) == 2
    assert 'RECONECTANDO' in estados and 'ONLINE' in estados
    processos[1].terminate.assert_called_once()
    servidor.close.assert_called_once()
    assert g._processo is None
    assert config.BASE_URL == 'http://localhost:5000'


@pytest.mark.parametrize('base', ['http://loja.example', 'http://localhost:5000', 'https://loja.localhost', 'https://192.168.0.12', 'https://127.1', 'https://loja.lan', 'https://user:senha@loja.example'])
def test_producao_nunca_gera_link_sem_https_publico(base):
    from src import links
    config.MODO_TESTE = False
    config.BASE_URL = base
    assert publicacao.endereco() == ''
    with pytest.raises(links.PaginaIndisponivel):
        links.gerar_link_pedido('5511999990033')
    with get_conn() as banco:
        assert banco.execute('SELECT COUNT(*) FROM links_pedido').fetchone()[0] == 0


@pytest.mark.parametrize('url', ['https://pizzaria-peruzzolo.whatsapp.com','https://WHATSAPP.COM','https://wa.me','https://loja.wa.me'])
def test_whatsapp_nao_pode_ser_dominio_de_pedidos(url):
    with pytest.raises(ValueError, match='WhatsApp não hospeda'):
        publicacao.validar_dominio(url)


@pytest.mark.parametrize('texto', ['Peça: https://pizzaria-peruzzolo.whatsapp.com', 'Peça: pizzaria-peruzzolo.whatsapp.com', 'Abra www.site-inventado.com/pedido'])
def test_transporte_nao_envia_dominios_inventados(aplicativo, monkeypatch, texto):
    from src import whatsapp
    gerente_online(aplicativo,monkeypatch)
    config.MODO_TESTE=False
    config.WHATSAPP_PROVIDER='LOCAL'
    enviar=Mock()
    monkeypatch.setattr(whatsapp,'_enviar_via_waha',enviar)
    with pytest.raises(ValueError):
        whatsapp.enviar_mensagem('5511999990033',texto)
    enviar.assert_not_called()


def test_links_cadastrados_e_humanos_preservados(aplicativo,monkeypatch):
    from src import links
    gerente_online(aplicativo,monkeypatch)
    config.MODO_TESTE=False
    config.ENDERECO_RESTAURANTE='Veja https://maps.example/local?x=1'
    assert links.atualizar_resposta(config.ENDERECO_RESTAURANTE,'5511999990033')==config.ENDERECO_RESTAURANTE
    with pytest.raises(ValueError):
        links.atualizar_resposta('https://maps.example/outro','5511999990033')
    assert links.atualizar_resposta('https://manual.example/orcamento','5511999990033',permitir_externos=True)=='https://manual.example/orcamento'
    with pytest.raises(ValueError):
        links.atualizar_resposta('https://localhost/orcamento','5511999990033',permitir_externos=True)


def test_fila_corrige_resposta_antiga_inventada_sem_chamar_ia(aplicativo,monkeypatch):
    from src import links, processamento, whatsapp, bot
    gerente_online(aplicativo,monkeypatch)
    config.MODO_TESTE=False
    config.WHATSAPP_PROVIDER='LOCAL'
    telefone='5511999990033'
    tarefa=processamento.enfileirar({'telefone':telefone,'texto':'quero fazer um pedido'},'ficticia-dns')
    with get_conn() as c:
        c.execute('UPDATE tarefas_bot SET resposta=? WHERE id=?',('Peça em https://pizzaria-peruzzolo.whatsapp.com',tarefa['id']))
    envio=Mock()
    monkeypatch.setattr(processamento,'_servico_pronto',lambda:True)
    monkeypatch.setattr(whatsapp,'enviar_mensagem',envio)
    monkeypatch.setattr(bot,'processar_mensagem',Mock(side_effect=AssertionError('Não chamar a IA outra vez.')))
    processamento._parar.clear()
    assert processamento.processar_proxima()
    assert envio.call_count==1
    resposta=envio.call_args.args[1]
    assert 'whatsapp.com' not in resposta and 'https://loja-ficticia.trycloudflare.com/m/' in resposta
    token=resposta.split('/m/')[1].split()[0]
    assert links.obter_link(token)['telefone']==telefone


def test_fila_humana_preserva_link_externo_explicito(aplicativo,monkeypatch):
    from src import processamento, whatsapp
    gerente_online(aplicativo,monkeypatch)
    config.MODO_TESTE=False
    config.WHATSAPP_PROVIDER='LOCAL'
    texto='Veja https://manual.example/documento'
    tarefa=processamento.enfileirar({'telefone':'5511999990033','texto':texto},'ficticia-humana')
    with get_conn() as c:
        c.execute("UPDATE tarefas_bot SET origem='HUMANO', resposta=? WHERE id=?",(texto,tarefa['id']))
    envio=Mock()
    monkeypatch.setattr(processamento,'_servico_pronto',lambda:True)
    monkeypatch.setattr(whatsapp,'enviar_mensagem',envio)
    processamento._parar.clear()
    assert processamento.processar_proxima()
    assert envio.call_args.kwargs['permitir_externos'] is True
    assert envio.call_args.args[1]==texto


def test_probe_informa_falha_dns_sem_publicar_endereco(aplicativo):
    import socket
    import requests
    g=publicacao.Publicacao(aplicativo)
    erro=requests.ConnectionError('Falha de acesso')
    erro.__cause__=socket.gaierror(-2,'Domínio fictício inexistente')
    http=Mock()
    http.get.side_effect=erro
    assert not g._verificar_https(http,'https://ficticio.example')
    assert g._diagnostico_https=='DNS' and g.situacao()['url']==''


def test_links_em_frases_naturais_markdown_e_aviso_usam_https_atual(aplicativo, monkeypatch):
    from src import links
    g = gerente_online(aplicativo, monkeypatch)
    config.MODO_TESTE = False
    telefone = '5511999990033'
    link = links.gerar_link_pedido(telefone)
    original = f'Pode escolher com calma: [seu pedido]({link}).\nAviso: https://antigo.trycloudflare.com/privacidade'
    g._status('ONLINE', 'Verificado', 'https://atual.trycloudflare.com')
    atualizado = links.atualizar_resposta(original, telefone)
    assert f'[seu pedido](https://atual.trycloudflare.com/m/{link.rsplit("/", 1)[-1]}).' in atualizado
    assert 'https://atual.trycloudflare.com/privacidade' in atualizado
    assert 'antigo' not in atualizado and 'loja-ficticia' not in atualizado
    # Um token conhecido é corrigido mesmo se veio com localhost de um histórico antigo.
    assert links.atualizar_resposta('Abra: http://localhost:5000/m/' + link.rsplit('/', 1)[-1], telefone).startswith('Abra: https://atual.')


@pytest.mark.parametrize('texto', ['Compre: https://loja.example/m/token-inventado', 'Abra https://192.168.1.2:5000', 'Abra http://loja.example', 'Abra https://loja.localhost', 'Abra localhost:5000', 'Abra http://[::1]:5000', 'Abra 192.168.1.2:5000/m/teste', 'Abra ftp://192.168.1.2/pedidos'])
def test_barreira_final_impede_envio_de_link_invalido(aplicativo, monkeypatch, texto):
    from src import whatsapp
    gerente_online(aplicativo, monkeypatch)
    config.MODO_TESTE = False
    config.WHATSAPP_PROVIDER = 'LOCAL'
    envio = Mock()
    monkeypatch.setattr(whatsapp, '_enviar_via_waha', envio)
    with pytest.raises(ValueError):
        whatsapp.enviar_mensagem('5511999990033', texto)
    envio.assert_not_called()


def test_fila_aguarda_https_e_retoma_com_dominio_atual_sem_repetir_ia(aplicativo, monkeypatch):
    from src import links, processamento, whatsapp, bot
    g = gerente_online(aplicativo, monkeypatch)
    config.MODO_TESTE = False
    config.WHATSAPP_PROVIDER = 'LOCAL'
    telefone = '5511999990033'
    link = links.gerar_link_pedido(telefone)
    tarefa = processamento.enfileirar({'telefone': telefone, 'texto': 'quero comprar'}, 'ficticia-https')
    with get_conn() as banco:
        banco.execute('UPDATE tarefas_bot SET resposta=? WHERE id=?', ('Escolha por aqui: ' + link, tarefa['id']))
    g._status('RECONECTANDO', 'Verificando')
    envio, gerar = Mock(), Mock(side_effect=AssertionError('não chamar a IA novamente'))
    monkeypatch.setattr(processamento, '_servico_pronto', lambda: True)
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', envio)
    monkeypatch.setattr(bot, 'processar_mensagem', gerar)
    processamento._parar.clear()
    assert processamento.processar_proxima() is False
    envio.assert_not_called()
    with get_conn() as banco:
        row = banco.execute('SELECT estado,resposta FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()
        assert row['estado'] == 'PENDENTE' and row['resposta'].endswith(link)
    g._status('ONLINE', 'Verificado', 'https://novo.trycloudflare.com')
    assert processamento.processar_proxima() is True
    envio.assert_called_once()
    gerar.assert_not_called()
    assert 'https://novo.trycloudflare.com/m/' in envio.call_args.args[1]
    with get_conn() as banco:
        assert banco.execute('SELECT estado FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()[0] == 'CONCLUIDA'


def test_probe_https_confere_aplicativo_sem_seguir_redirect(aplicativo):
    from unittest.mock import MagicMock
    g = publicacao.Publicacao(aplicativo)
    http = MagicMock()
    resposta = http.get.return_value.__enter__.return_value
    resposta.status_code = 200
    resposta.iter_content.return_value = [b'outro-aplicativo']
    assert not g._verificar_https(http, 'https://loja.example')
    resposta.iter_content.return_value = [g._verificacao.encode()]
    assert g._verificar_https(http, 'https://loja.example')
    assert http.get.call_args.kwargs['allow_redirects'] is False
    assert http.get.call_args.args[0].startswith('https://loja.example/_deliverybot/health/')
    resposta.status_code = 302
    assert not g._verificar_https(http, 'https://loja.example')
    resposta.status_code = 200
    resposta.iter_content.return_value = [b'x' * 128, b'x']
    assert not g._verificar_https(http, 'https://loja.example')


def test_gateway_probe_nao_libera_painel_ou_pedido_antes_de_pronto(aplicativo):
    c = Client(publicacao.PaginaPublica(aplicativo, lambda: '', 'verificacao-ficticia', lambda: False), Response)
    r = c.get('/_deliverybot/health/verificacao-ficticia')
    assert r.status_code == 200 and r.text == 'verificacao-ficticia'
    assert r.headers['Cache-Control'] == 'no-store' and not r.headers.get('Set-Cookie')
    assert c.get('/privacidade').status_code == 503
    assert c.get('/_deliverybot/health/outro').status_code == 503


def test_leitor_rejeita_dominios_com_sufixo_enganoso():
    processo = Mock(stdout=io.StringIO('https://loja.trycloudflare.com.evil.example\nhttps://loja.trycloudflare.com:444\n'))
    info = {}
    publicacao.Publicacao._ler(processo, info, threading.Lock())
    assert not info


def test_encerramento_oculta_url_antes_de_esperar_thread(aplicativo, monkeypatch):
    g = gerente_online(aplicativo, monkeypatch)
    config.MODO_TESTE = False
    def esperar(**kwargs):
        assert publicacao.endereco() == ''
    g._thread = Mock()
    g._thread.join.side_effect = esperar
    g._thread.is_alive.return_value = False
    g.encerrar()
    assert g.situacao()['estado'] == 'DESLIGADO'


def test_monitor_renova_callback_na_troca_de_url_e_retenta_falhas(aplicativo, monkeypatch):
    from src import conexoes
    g = gerente_online(aplicativo, monkeypatch)
    config.MODO_TESTE = False
    config.WHATSAPP_PROVIDER = 'WAHA'
    renovacao = Mock(side_effect=[True, ValueError('Serviço indisponível'), True])
    monkeypatch.setattr(conexoes, 'renovar_webhook_publico', renovacao)
    assert g._atualizar_webhook('https://primeiro.example')
    assert g._atualizar_webhook('https://primeiro.example')
    assert renovacao.call_count == 1
    assert not g._atualizar_webhook('https://novo.example')
    assert not g._atualizar_webhook('https://novo.example')
    assert renovacao.call_count == 2
    g._webhook_apos = 0
    assert g._atualizar_webhook('https://novo.example')
    assert renovacao.call_count == 3
