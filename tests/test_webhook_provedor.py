"""Eventos de uma conexão desativada não iniciam atendimento na conexão atual."""
from contextlib import contextmanager
import hashlib
import hmac
import json
import threading
from unittest.mock import Mock

import pytest

from src import config, estoque, pedidos, preferencias, processamento, protecao_ia, seguranca, whatsapp
from src.db import get_conn, init_db


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    for nome in vars(config):
        if nome.isupper():
            monkeypatch.setattr(config, nome, getattr(config, nome))
    for campo, valor in {
        'DATABASE_PATH': str(tmp_path/'webhook-ficticio.db'), 'SEED_CATALOGO': False,
        'MODO_TESTE': False, 'IA_PROVIDER': '', 'WHATSAPP_PROVIDER': 'LOCAL',
        'WAHA_SESSION': 'sessao-ficticia', 'WEBHOOK_SECRET': 'chave-ficticia-do-teste',
    }.items():
        monkeypatch.setattr(config, campo, valor)
    init_db(seed_cardapio=False)
    from src.app import app
    fila = Mock(wraps=processamento.enfileirar)
    lembrar = Mock(wraps=whatsapp._lembrar_chat_id)
    monkeypatch.setattr(processamento, 'enfileirar', fila)
    monkeypatch.setattr(whatsapp, '_lembrar_chat_id', lembrar)
    monkeypatch.setattr(whatsapp, '_chat_id_cache', {})
    monkeypatch.setattr(whatsapp, '_sessao_cache', {})
    return app.test_client(), fila, lembrar


def evento(sessao='sessao-ficticia'):
    return {'event': 'message', 'session': sessao, 'payload': {
        'id': 'evento-ficticio', 'from': '5511999990001@c.us', 'body': 'Olá'}}


@pytest.mark.parametrize('provedor', ['META', 'TESTE'])
@pytest.mark.parametrize('json_valido', [True, False])
def test_webhook_desativado_ignora_sem_ler_corpo_ou_modificar_contatos(cliente, monkeypatch, provedor, json_valido):
    c, fila, lembrar = cliente
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', provedor)
    kwargs = {'json': evento()} if json_valido else {'data': '{', 'content_type': 'application/json'}
    r = c.post('/webhook/waha/chave-ficticia-do-teste', **kwargs)
    assert r.status_code == 200 and r.json == {'status': 'ignorado'}
    fila.assert_not_called()
    lembrar.assert_not_called()


@pytest.mark.parametrize('provedor', ['LOCAL', 'WAHA'])
def test_conexao_ativa_continua_recebendo_a_sessao_configurada(cliente, monkeypatch, provedor):
    c, fila, lembrar = cliente
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', provedor)
    r = c.post('/webhook/waha/chave-ficticia-do-teste', json=evento())
    assert r.status_code == 200 and r.json['status'] == 'recebido'
    assert fila.call_args.args[0]['session'] == 'sessao-ficticia'
    assert fila.call_args.args[1] == 'evento-ficticio'
    assert fila.call_args.kwargs['roteamento_esperado'] == preferencias.roteamento_whatsapp()
    lembrar.assert_called_once()
    assert lembrar.call_args.kwargs['_conn'] is not None


def test_sessao_alheia_e_segredo_incorreto_nao_alimentam_fila(cliente):
    c, fila, lembrar = cliente
    assert c.post('/webhook/waha/chave-ficticia-do-teste', json=evento('outra-sessao')).json == {'status': 'ignorado'}
    assert c.post('/webhook/waha/incorreto', json=evento()).status_code == 404
    fila.assert_not_called()
    lembrar.assert_not_called()


def dados(sessao='sessao-ficticia'):
    return {'telefone': '5511999990001', 'texto': 'Olá', 'nome': 'Pessoa fictícia',
            'chat_id': '5511999990001@c.us', 'session': sessao}


def trocar_para_meta():
    preferencias.salvar({'WHATSAPP_PROVIDER': 'META', 'WHATSAPP_TOKEN': 'token-ficticio',
        'WHATSAPP_PHONE_NUMBER_ID': '111111', 'WHATSAPP_BUSINESS_ACCOUNT_ID': '222222',
        'WHATSAPP_VERIFY_TOKEN': 'verificacao-ficticia', 'WHATSAPP_APP_SECRET': 'app-ficticio',
        'WHATSAPP_META_AMBIENTE': 'TESTE'})


def sem_ingestao():
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM tarefas_bot').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM clientes').fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM mensagens').fetchone()[0] == 0
    assert not whatsapp._chat_id_cache and not whatsapp._sessao_cache


def test_extracao_sem_lembrar_nao_altera_contato_ou_cache(cliente):
    _, _, lembrar = cliente
    assert whatsapp.extrair_mensagem_recebida_waha(evento(), lembrar=False) == dados() | {'nome': 'Cliente'}
    lembrar.assert_not_called()
    sem_ingestao()


def test_rota_capturada_antes_da_troca_nao_e_reclassificada(cliente):
    _, fila, lembrar = cliente
    rota = preferencias.roteamento_whatsapp()
    trocar_para_meta()
    with pytest.raises(processamento._ConexaoAlterada):
        fila(dados(), 'evento-ficticio', roteamento_esperado=rota)
    lembrar.assert_not_called()
    sem_ingestao()


def test_troca_durante_extracao_nao_cria_contato_nem_tarefa_na_meta(cliente, monkeypatch):
    c, _, lembrar = cliente
    original = whatsapp.extrair_mensagem_recebida_waha
    def extrair_apos_troca(payload, **kwargs):
        trocar_para_meta()
        return original(payload, **kwargs)
    monkeypatch.setattr(whatsapp, 'extrair_mensagem_recebida_waha', extrair_apos_troca)
    r = c.post('/webhook/waha/chave-ficticia-do-teste', json=evento())
    assert r.status_code == 500
    lembrar.assert_not_called()
    sem_ingestao()


def test_falha_na_transacao_nao_deixa_contato_ou_cache(cliente, monkeypatch):
    _, fila, lembrar = cliente
    def falhar(*args, **kwargs):
        raise RuntimeError('Falha fictícia para conferir rollback')
    monkeypatch.setattr(protecao_ia, 'avaliar', falhar)
    with pytest.raises(RuntimeError, match='Falha fictícia'):
        fila(dados(), 'evento-ficticio', roteamento_esperado=preferencias.roteamento_whatsapp())
    lembrar.assert_called_once()
    sem_ingestao()


@pytest.mark.parametrize('provedor', ['LOCAL', 'WAHA'])
def test_ingestao_valida_persiste_rota_sem_reaprender_evento_duplicado(cliente, monkeypatch, provedor):
    c, fila, lembrar = cliente
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', provedor)
    r = c.post('/webhook/waha/chave-ficticia-do-teste', json=evento())
    assert r.status_code == 200 and r.json['duplicada'] is False
    repetido = evento()
    repetido['payload']['from'] = '5511999990002@c.us'
    dup = c.post('/webhook/waha/chave-ficticia-do-teste', json=repetido)
    assert dup.status_code == 200 and dup.json['duplicada'] is True
    assert r.json['id'] == dup.json['id']
    lembrar.assert_called_once()
    with get_conn() as conn:
        contatos = [dict(p) for p in conn.execute('SELECT telefone,chat_id,waha_session FROM clientes')]
        assert contatos == [{'telefone': '5511999990001', 'chat_id': '5511999990001@c.us',
                             'waha_session': 'sessao-ficticia'}]
        rota = conn.execute('SELECT rota,origem FROM tarefas_bot').fetchone()
        assert rota['rota'] == processamento._assinatura_roteamento(preferencias.roteamento_whatsapp())
        assert rota['origem'] == provedor + ':sessao-ficticia'
    assert fila.call_count == 2


def contato_com_pedido(provedor='LOCAL'):
    preferencias.salvar({'WHATSAPP_PROVIDER': provedor, 'WAHA_SESSION': 'sessao-ficticia',
                         'WAHA_URL': 'https://waha-ficticio.example'})
    p = estoque.salvar_produto({'nome': 'Item fictício', 'categoria': 'Teste', 'preco': 10, 'estoque': 2})
    pedido = pedidos.criar_pedido('5511999990001', 'Pessoa fictícia',
        [{'produto_id': p['id'], 'quantidade': 1}], 'Pix', forma_entrega='ENTREGA',
        cep='00000000', endereco='Rua fictícia, 123')
    whatsapp._lembrar_chat_id('5511999990001', 'contato-ficticio@lid', 'sessao-ficticia')
    return pedido


@pytest.mark.parametrize('provedor,mudanca', [
    ('LOCAL', {'WAHA_SESSION': 'nova-sessao-ficticia'}),
    ('WAHA', {'WAHA_URL': 'https://outro-waha-ficticio.example'}),
    ('LOCAL', {'WHATSAPP_PROVIDER': 'WAHA'}),
    ('LOCAL', {'WHATSAPP_PROVIDER': 'TESTE'}),
])
def test_troca_de_rota_descarta_so_metadados_da_conexao_anterior(cliente, provedor, mudanca):
    pedido = contato_com_pedido(provedor)
    assert whatsapp._chat_id_cache and whatsapp._sessao_cache
    preferencias.salvar(mudanca)
    with get_conn() as conn:
        contato = dict(conn.execute('SELECT nome,telefone,cep,endereco,chat_id,waha_session FROM clientes').fetchone())
    assert contato == {'nome': 'Pessoa fictícia', 'telefone': '5511999990001', 'cep': '00000000',
                       'endereco': 'Rua fictícia, 123', 'chat_id': None, 'waha_session': None}
    assert pedidos.obter_pedido(pedido['id']) == pedido
    assert not whatsapp._chat_id_cache and not whatsapp._sessao_cache


def test_mesma_rota_e_credencial_rotativa_preservam_metadados(cliente):
    contato_com_pedido('WAHA')
    cache = dict(whatsapp._chat_id_cache), dict(whatsapp._sessao_cache)
    preferencias.salvar({'WAHA_URL': 'https://waha-ficticio.example/'})
    preferencias.salvar({'WAHA_API_KEY': 'credencial-rotativa-ficticia'})
    assert (whatsapp._chat_id_cache, whatsapp._sessao_cache) == cache
    with get_conn() as conn:
        assert tuple(conn.execute('SELECT chat_id,waha_session FROM clientes').fetchone()) == (
            'contato-ficticio@lid', 'sessao-ficticia')


def test_troca_recusada_por_pendencia_nao_apaga_metadados(cliente):
    _, fila, _ = cliente
    fila(dados(), 'evento-ficticio', roteamento_esperado=preferencias.roteamento_whatsapp())
    whatsapp._chat_id_conhecido('5511999990001')
    whatsapp._sessao_conhecida('5511999990001')
    cache = dict(whatsapp._chat_id_cache), dict(whatsapp._sessao_cache)
    with pytest.raises(ValueError, match='pendentes'):
        preferencias.salvar({'WAHA_SESSION': 'nova-sessao-ficticia'})
    assert (whatsapp._chat_id_cache, whatsapp._sessao_cache) == cache
    with get_conn() as conn:
        assert tuple(conn.execute('SELECT chat_id,waha_session FROM clientes').fetchone()) == (
            '5511999990001@c.us', 'sessao-ficticia')


@pytest.mark.parametrize('consultar', ['_chat_id_conhecido', '_sessao_conhecida'])
def test_leitura_iniciada_antes_da_troca_nao_repoe_cache_antigo(cliente, monkeypatch, consultar):
    contato_com_pedido()
    whatsapp._invalidar_rotas()
    get_conn_original = whatsapp.get_conn
    primeira = True
    @contextmanager
    def consulta_lenta():
        with get_conn_original() as conn:
            class Conexao:
                def execute(self, *args):
                    cursor = conn.execute(*args)
                    class Cursor:
                        def fetchone(self):
                            nonlocal primeira
                            resultado = cursor.fetchone()
                            if primeira:
                                primeira = False
                                preferencias.salvar({'WAHA_SESSION': 'nova-sessao-ficticia'})
                            return resultado
                    return Cursor()
            yield Conexao()
    monkeypatch.setattr(whatsapp, 'get_conn', consulta_lenta)
    assert getattr(whatsapp, consultar)('5511999990001') is None
    assert not whatsapp._chat_id_cache and not whatsapp._sessao_cache


def test_falha_de_persistencia_legada_nao_publica_novo_cache(cliente, monkeypatch):
    def falhar(*args):
        raise RuntimeError('Falha fictícia')
    monkeypatch.setattr(whatsapp, '_persistir_chat_id', falhar)
    whatsapp._lembrar_chat_id('5511999990001', 'contato-ficticio@lid', 'sessao-ficticia')
    sem_ingestao()


@pytest.mark.parametrize('provedor', ['WAHA', 'META'])
def test_rota_e_capturada_antes_do_comparador_de_autenticacao(cliente, monkeypatch, provedor):
    c, _, lembrar = cliente
    trocou = False
    if provedor == 'WAHA':
        preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://waha-ficticio.example'})
        original = seguranca.igual
        def validar_e_trocar(a, b):
            nonlocal trocou
            correto = original(a, b)
            if correto and not trocou:
                trocou = True
                preferencias.salvar({'WAHA_URL': 'https://outro-waha-ficticio.example',
                                     'WEBHOOK_SECRET': 'nova-chave-ficticia'})
            return correto
        monkeypatch.setattr(seguranca, 'igual', validar_e_trocar)
        r = c.post('/webhook/waha/chave-ficticia-do-teste', json=evento())
    else:
        trocar_para_meta()
        payload = {'entry': [{'id': '222222', 'changes': [{'value': {
            'metadata': {'phone_number_id': '333333'},
            'messages': [{'from': '5511999990001', 'id': 'evento-ficticio',
                          'type': 'text', 'text': {'body': 'Olá'}}]}}]}]}
        corpo = json.dumps(payload).encode('utf-8')
        assinatura = 'sha256=' + hmac.new(b'app-ficticio', corpo, hashlib.sha256).hexdigest()
        original = hmac.compare_digest
        def validar_e_trocar(a, b):
            nonlocal trocou
            correto = original(a, b)
            if correto and not trocou:
                trocou = True
                preferencias.salvar({'WHATSAPP_PHONE_NUMBER_ID': '333333',
                                     'WHATSAPP_APP_SECRET': 'novo-app-ficticio'})
            return correto
        monkeypatch.setattr(hmac, 'compare_digest', validar_e_trocar)
        r = c.post('/webhook', data=corpo, content_type='application/json',
                   headers={'X-Hub-Signature-256': assinatura})
    assert trocou and r.status_code == 500
    lembrar.assert_not_called()
    sem_ingestao()


def test_webhook_aguarda_aplicacao_completa_sem_autenticar_configuracao_hibrida(cliente, monkeypatch):
    c, _, lembrar = cliente
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://waha-ficticio.example'})
    escrita_parcial, liberar, leitor_iniciado, terminou = (threading.Event() for _ in range(4))
    respostas, erros = [], []
    atribuir = setattr
    def atribuir_com_pausa(alvo, nome, valor):
        atribuir(alvo, nome, valor)
        if alvo is config and nome == 'WAHA_URL' and valor == 'https://outro-waha-ficticio.example':
            escrita_parcial.set()
            if not liberar.wait(5):
                raise RuntimeError('A pausa fictícia não foi encerrada.')
    monkeypatch.setattr(preferencias, 'setattr', atribuir_com_pausa, raising=False)
    def atualizar():
        try:
            preferencias.salvar({'WAHA_URL': 'https://outro-waha-ficticio.example',
                                 'WEBHOOK_SECRET': 'nova-chave-ficticia',
                                 'WHATSAPP_APP_SECRET': 'novo-app-ficticio'})
        except Exception as exc:
            erros.append(exc)
    def receber():
        try:
            leitor_iniciado.set()
            with c.application.test_client() as outro:
                respostas.append(outro.post('/webhook/waha/chave-ficticia-do-teste', json=evento()))
        except Exception as exc:
            erros.append(exc)
        finally:
            terminou.set()
    escritor = threading.Thread(target=atualizar)
    leitor = threading.Thread(target=receber)
    escritor.start()
    try:
        assert escrita_parcial.wait(5)
        leitor.start()
        assert leitor_iniciado.wait(5)
        assert not terminou.wait(0.1)
    finally:
        liberar.set()
        escritor.join(5)
        if leitor.ident is not None:
            leitor.join(5)
    assert not escritor.is_alive() and not leitor.is_alive() and not erros
    assert len(respostas) == 1 and respostas[0].status_code == 404
    assert preferencias.capturar_entrada_whatsapp() == (
        ('WAHA', 'https://outro-waha-ficticio.example', 'sessao-ficticia'),
        'nova-chave-ficticia', 'novo-app-ficticio')
    lembrar.assert_not_called()
    sem_ingestao()
