"""Consumidor local reservado, com concorrência simulada e nenhuma conta real."""
from concurrent.futures import ThreadPoolExecutor
import threading
import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import bot, config, humano, ia, preferencias, processamento, publicacao, whatsapp
from src.db import get_conn, init_db


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticia.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    for chave in preferencias.CAMPOS | {'MODO_TESTE'}:
        monkeypatch.setattr(config, chave, getattr(config, chave))
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'LOCAL')
    monkeypatch.setattr(config, 'MODO_TESTE', False)
    monkeypatch.setattr(processamento, '_parar', threading.Event())
    monkeypatch.setattr(processamento, '_acordar', threading.Event())
    monkeypatch.setattr(processamento, '_servico_pronto', lambda: True)
    monkeypatch.setattr(publicacao, 'endereco', lambda: '')
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', Mock(return_value={}))
    init_db()


def entrada(texto, indice=0):
    return processamento.enfileirar({'telefone': f'554799990{indice:03}', 'texto': texto}, f'ficticia-{indice}-{texto}')


@pytest.mark.parametrize('texto', ['Oi!', '  BOA   TARDE  ', 'qual o horário?', 'catálogo', 'aceita cartão?', '9', 'ATENDENTE'])
def test_consultas_locais_entram_na_lista_rapida(texto):
    assert processamento._mensagem_rapida(texto)


@pytest.mark.parametrize('texto', ['2', '1?', '１', 'ｈｕｍａｎｏ', 'humano!', 'atendente!', 'sim', 'quero pedir', 'oi e resolva esta conta', 'abre hoje?', 'quero o link', '', 'qual o horário e a entrega?'])
def test_pedido_confirmacao_e_pergunta_composta_nao_entram_na_lista(texto):
    assert not processamento._mensagem_rapida(texto)


@pytest.mark.parametrize('texto', ['Oi!', 'qual o horário?', 'catálogo', 'aceita cartão?', 'onde fica'])
def test_consultas_reservadas_realmente_dispensam_inferencia(monkeypatch, texto):
    monkeypatch.setattr(ia, 'responder', Mock(side_effect=AssertionError('Consulta rápida não deve chamar IA.')))
    assert processamento._mensagem_rapida(texto)
    entrada(texto)
    assert processamento.processar_proxima(somente_rapidas=True)
    ia.responder.assert_not_called()
    assert whatsapp.enviar_mensagem.call_count == 1


def test_reservado_nao_chama_bot_para_consulta_lenta(monkeypatch):
    entrada('Preciso consultar ingredientes de um produto')
    gerar = Mock(side_effect=AssertionError('Consumidor reservado não pode chamar este caminho.'))
    monkeypatch.setattr(bot, 'processar_mensagem', gerar)
    assert not processamento.processar_proxima(somente_rapidas=True)
    gerar.assert_not_called()
    assert processamento.situacao()['pendentes'] == 1


@pytest.mark.parametrize('estado', ['PENDENTE', 'PROCESSANDO', 'ENVIANDO', 'FALHOU', 'VERIFICAR'])
def test_reservado_respeita_entrada_anterior_da_mesma_conversa(monkeypatch, estado):
    anterior = entrada('Preciso consultar ingredientes de um produto')
    entrada('oi')
    with get_conn() as conn:
        conn.execute('UPDATE tarefas_bot SET estado=? WHERE id=?', (estado, anterior['id']))
    gerar = Mock(return_value='Resposta local')
    monkeypatch.setattr(bot, 'processar_mensagem', gerar)
    assert not processamento.processar_proxima(somente_rapidas=True)
    gerar.assert_not_called()
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA' WHERE id=?", (anterior['id'],))
    assert processamento.processar_proxima(somente_rapidas=True)
    assert gerar.call_args.args[1] == 'oi'


def test_duas_inferencias_ocupadas_nao_atrasam_saudacao_de_outra_pessoa(monkeypatch):
    iniciadas = [threading.Event(), threading.Event()]
    liberar = threading.Event()
    concluidas = threading.Event()

    def responder(telefone, texto):
        if texto.startswith('Consulta complexa'):
            iniciadas[int(texto[-1])].set()
            assert liberar.wait(8), 'A simulação deve liberar as inferências.'
            return 'Informação fictícia do produto'
        assert texto == 'oi'
        return 'Boas-vindas à lanchonete fictícia!'

    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    entrada('Consulta complexa 0', 0)
    entrada('Consulta complexa 1', 1)
    with ThreadPoolExecutor(max_workers=3) as executor:
        normais = [executor.submit(processamento.processar_proxima) for _ in range(2)]
        try:
            assert all(evento.wait(8) for evento in iniciadas)
            nova = entrada('oi', 2)
            futuro = executor.submit(processamento.processar_proxima, somente_rapidas=True)
            assert futuro.result(timeout=8)
            assert all(not futuro.done() for futuro in normais)
            assert entrada('oi', 2)['duplicada']
            assert whatsapp.enviar_mensagem.call_count == 1
            with get_conn() as conn:
                assert conn.execute('SELECT estado FROM tarefas_bot WHERE id=?', (nova['id'],)).fetchone()[0] == 'CONCLUIDA'
            concluidas.set()
        finally:
            liberar.set()
        assert all(futuro.result(timeout=8) for futuro in normais)
    assert concluidas.is_set()
    assert whatsapp.enviar_mensagem.call_count == 3


def test_pausa_humana_continua_bloqueando_automacao():
    humano.solicitar('554799990000')
    assert entrada('oi')['estado'] == 'CONCLUIDA'
    assert not processamento.processar_proxima(somente_rapidas=True)
    whatsapp.enviar_mensagem.assert_not_called()


def test_busca_reservada_e_limitada_a_64_candidatas(monkeypatch):
    for indice in range(64):
        entrada('Consulta complexa', indice)
    entrada('oi', 64)
    monkeypatch.setattr(bot, 'processar_mensagem', lambda *args: 'Resposta fictícia')
    assert not processamento.processar_proxima(somente_rapidas=True)
    assert processamento.processar_proxima()
    assert processamento.processar_proxima(somente_rapidas=True)


def test_inicializacao_separa_dois_consumidores_gerais_e_um_local(monkeypatch):
    threads = []
    def criar(**dados):
        thread = Mock()
        thread.dados = dados
        threads.append(thread)
        return thread
    monkeypatch.setattr(processamento, '_threads', [])
    monkeypatch.setattr(processamento.threading, 'Thread', criar)
    processamento.iniciar()
    assert len(threads) == 3
    assert [thread.dados.get('kwargs', {}) for thread in threads] == [{}, {}, {'somente_rapidas': True}]
    assert all(thread.start.call_count == 1 for thread in threads)


def carregar_benchmark(monkeypatch):
    pasta = Path(__file__).resolve().parents[1] / 'packaging'
    monkeypatch.syspath_prepend(str(pasta))
    return runpy.run_path(str(pasta / 'benchmark_respostas.py'))


@pytest.mark.parametrize('pares,espera', [(2, .2), (31, .2), (3, .09), (3, 1.01)])
def test_benchmark_recusa_medicao_fora_dos_limites(monkeypatch, pares, espera):
    benchmark = carregar_benchmark(monkeypatch)
    with pytest.raises(ValueError, match='3 a 30'):
        benchmark['executar'](pares, espera)


def test_benchmark_recusa_backend_carregado_e_preserva_configuracao(monkeypatch):
    benchmark = carregar_benchmark(monkeypatch)
    antes = config.DATABASE_PATH, config.WHATSAPP_PROVIDER, config.MODO_TESTE
    with pytest.raises(ValueError, match='processo separado'):
        benchmark['executar'](3, .2)
    assert (config.DATABASE_PATH, config.WHATSAPP_PROVIDER, config.MODO_TESTE) == antes


@pytest.mark.parametrize('estado', ['PENDENTE', 'PROCESSANDO', 'ENVIANDO', 'FALHOU', 'VERIFICAR'])
@pytest.mark.parametrize('inicial,dados', [
    ('LOCAL', {'WHATSAPP_PROVIDER': 'WAHA'}),
    ('LOCAL', {'WHATSAPP_PROVIDER': 'TESTE'}),
    ('LOCAL', {'WAHA_SESSION': 'outra-loja-ficticia'}),
    ('WAHA', {'WHATSAPP_PROVIDER': 'LOCAL'}),
    ('WAHA', {'WAHA_URL': 'https://novo-ficticio.example'}),
    ('WAHA', {'WAHA_SESSION': 'outra-loja-ficticia'}),
])
def test_troca_de_rota_com_fila_pendente_e_atomica(inicial, dados, estado):
    preferencias.salvar({'WHATSAPP_PROVIDER': inicial, 'WAHA_URL': 'https://antigo-ficticio.example',
                        'WAHA_SESSION': 'default'})
    tarefa = entrada('oi')
    with get_conn() as conn:
        conn.execute('UPDATE tarefas_bot SET estado=? WHERE id=?', (estado, tarefa['id']))
        persistidos = dict(conn.execute('SELECT chave,valor FROM configuracoes').fetchall())
    rota = preferencias.roteamento_whatsapp()
    nome = config.NOME_RESTAURANTE
    with pytest.raises(ValueError, match='mensagens pendentes'):
        preferencias.salvar({**dados, 'NOME_RESTAURANTE': 'Não salvar alteração parcial'})
    assert preferencias.roteamento_whatsapp() == rota
    assert config.NOME_RESTAURANTE == nome
    with get_conn() as conn:
        assert dict(conn.execute('SELECT chave,valor FROM configuracoes').fetchall()) == persistidos


def test_rotacao_de_chaves_e_save_idempotente_recuperam_conexao_com_fila():
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example',
                        'WAHA_SESSION': 'default'})
    entrada('oi')
    rota = preferencias.roteamento_whatsapp()
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example/',
                        'WAHA_SESSION': 'default', 'WAHA_API_KEY': 'chave-ficticia-renovada'})
    assert preferencias.roteamento_whatsapp() == rota
    assert config.WAHA_API_KEY == 'chave-ficticia-renovada'


def test_troca_de_rota_e_permitida_com_tarefas_concluidas():
    tarefa = entrada('oi')
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA' WHERE id=?", (tarefa['id'],))
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_SESSION': 'nova-loja-ficticia'})
    assert config.WHATSAPP_PROVIDER == 'WAHA'
    assert config.WAHA_SESSION == 'nova-loja-ficticia'


def test_tarefa_de_outro_provedor_nao_usa_a_conexao_atual(monkeypatch):
    tarefa = entrada('oi')
    # Simula uma tarefa antiga preservada após uma troca de configuração.
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'WAHA')
    responder = Mock(side_effect=AssertionError('Não interpretar uma tarefa de outra conexão.'))
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert processamento.processar_proxima()
    responder.assert_not_called()
    whatsapp.enviar_mensagem.assert_not_called()
    with get_conn() as conn:
        row = conn.execute('SELECT estado,erro FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()
        assert row['estado'] == 'FALHOU' and 'conexão' in row['erro']
        assert conn.execute('SELECT COUNT(*) FROM mensagens').fetchone()[0] == 0


@pytest.mark.parametrize('campo,valor', [
    ('WHATSAPP_PROVIDER', 'LOCAL'),
    ('WAHA_URL', 'https://outro-ficticio.example'),
    ('WAHA_SESSION', 'outra-sessao-ficticia'),
])
def test_mudanca_inesperada_durante_preparacao_nao_atravessa_o_envio(monkeypatch, campo, valor):
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example',
                        'WAHA_SESSION': 'default'})
    tarefa = entrada('oi')
    def responder(*_):
        monkeypatch.setattr(config, campo, valor)
        return 'Resposta preparada na conexão anterior'
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_not_called()
    with get_conn() as conn:
        row = conn.execute('SELECT estado,erro FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()
        assert row['estado'] == 'FALHOU' and 'conexão' in row['erro']


def test_rota_persistida_alterada_antes_de_aplicar_tambem_bloqueia_envio(monkeypatch):
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example'})
    tarefa = entrada('oi')
    def responder(*_):
        with get_conn() as conn:
            conn.execute("UPDATE configuracoes SET valor='https://outro-ficticio.example' WHERE chave='WAHA_URL'")
        return 'Resposta preparada na conexão anterior'
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()[0] == 'FALHOU'


def test_configuracao_muda_enquanto_reserva_nao_processa_com_snapshot_antigo(monkeypatch):
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example'})
    tarefa = entrada('oi')
    with get_conn() as conn:
        conn.execute("UPDATE configuracoes SET valor='https://outro-ficticio.example' WHERE chave='WAHA_URL'")
    responder = Mock(side_effect=AssertionError('Aguarde a aplicação da configuração persistida.'))
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert not processamento.processar_proxima()
    responder.assert_not_called()
    whatsapp.enviar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()[0] == 'PENDENTE'


def test_rotacao_de_chave_durante_inferencia_nao_descarta_resposta(monkeypatch):
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example'})
    entrada('oi')
    def responder(*_):
        preferencias.salvar({'WAHA_API_KEY': 'chave-ficticia-renovada'})
        return 'Resposta na mesma conexão'
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_called_once()


def test_troca_simultanea_com_inferencia_e_recusada_antes_de_gravar(monkeypatch):
    iniciou, liberar = threading.Event(), threading.Event()
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example'})
    entrada('oi')
    def responder(*_):
        iniciou.set()
        assert liberar.wait(8)
        return 'Resposta na mesma conexão'
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    with ThreadPoolExecutor(max_workers=1) as executor:
        futuro = executor.submit(processamento.processar_proxima)
        try:
            assert iniciou.wait(8)
            with pytest.raises(ValueError, match='mensagens pendentes'):
                preferencias.salvar({'WHATSAPP_PROVIDER': 'LOCAL'})
            assert config.WHATSAPP_PROVIDER == 'WAHA'
        finally:
            liberar.set()
        assert futuro.result(timeout=8)
    whatsapp.enviar_mensagem.assert_called_once()


@pytest.mark.parametrize('dados', [
    {'WAHA_URL': 'https://outro-ficticio.example'},
    {'WAHA_SESSION': 'outra-sessao-ficticia'},
])
def test_evento_na_janela_entre_gravacao_e_aplicacao_nao_e_aceito(monkeypatch, dados):
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example',
                        'WAHA_SESSION': 'default'})
    aplicar = preferencias.aplicar
    def aplicar_depois_de_evento(valores):
        with pytest.raises(processamento._ConexaoAlterada):
            entrada('oi')
        aplicar(valores)
    monkeypatch.setattr(preferencias, 'aplicar', aplicar_depois_de_evento)
    preferencias.salvar(dados)
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM tarefas_bot').fetchone()[0] == 0
    # O evento repetido depois da aplicação recebe o retrato da nova conexão.
    tarefa = entrada('oi')
    with get_conn() as conn:
        assert conn.execute('SELECT rota FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()[0]


@pytest.mark.parametrize('dados', [
    {'WAHA_URL': 'https://outro-ficticio.example'},
    {'WAHA_SESSION': 'outra-sessao-ficticia'},
])
def test_tarefa_preserva_a_rota_original_ao_recuperar_na_mesma_plataforma(monkeypatch, dados):
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example',
                        'WAHA_SESSION': 'default'})
    tarefa = entrada('oi')
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA' WHERE id=?", (tarefa['id'],))
        original = conn.execute('SELECT rota FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()[0]
    preferencias.salvar(dados)
    with get_conn() as conn:
        # Representa uma tarefa antiga restaurada depois de mudar o servidor/sessão.
        conn.execute("UPDATE tarefas_bot SET estado='PENDENTE' WHERE id=?", (tarefa['id'],))
    responder = Mock(side_effect=AssertionError('A rota original não corresponde à conta atual.'))
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert processamento.processar_proxima()
    responder.assert_not_called()
    whatsapp.enviar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado,rota FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()[:] == ('FALHOU', original)
    with pytest.raises(ValueError, match='conexão original'):
        processamento.reenviar(tarefa['id'])


@pytest.mark.parametrize('origem', ['LOCAL:default', 'WAHA:default', 'HUMANO'])
def test_tarefa_legada_sem_rota_e_preservada_para_revisao(monkeypatch, origem):
    with get_conn() as conn:
        ident = conn.execute("INSERT INTO tarefas_bot(origem,chave,telefone,texto,resposta,chat_id,sessao) VALUES(?,?,?,?,?,?,?)",
                             (origem, 'legada-ficticia', '554799990000', 'oi', 'Resposta preservada', '123456789@lid', 'sessao-antiga')).lastrowid
    responder = Mock(side_effect=AssertionError('Legado não autoriza conexão atual.'))
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert processamento.processar_proxima()
    responder.assert_not_called()
    whatsapp.enviar_mensagem.assert_not_called()
    with pytest.raises(ValueError, match='conexão original'):
        processamento.reenviar(ident)
    with get_conn() as conn:
        row = conn.execute('SELECT estado,texto,resposta,chat_id,sessao,rota FROM tarefas_bot WHERE id=?', (ident,)).fetchone()
        assert row[:] == ('FALHOU', 'oi', 'Resposta preservada', '123456789@lid', 'sessao-antiga', '')


def test_deduplicacao_legada_nao_carimba_a_rota_atual():
    tarefa = entrada('oi')
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET rota='', estado='CONCLUIDA' WHERE id=?", (tarefa['id'],))
    repetida = entrada('oi')
    assert repetida['duplicada'] and repetida['id'] == tarefa['id']
    with get_conn() as conn:
        assert conn.execute('SELECT rota FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()[0] == ''
        assert conn.execute('SELECT COUNT(*) FROM tarefas_bot').fetchone()[0] == 1


def test_reenvio_confirmado_na_mesma_rota_preserva_metadados():
    preferencias.salvar({'WAHA_SESSION': 'loja-ficticia'})
    tarefa = processamento.enfileirar({'telefone': '554799990000', 'texto': 'oi',
                                       'chat_id': '123456789@lid', 'session': 'loja-ficticia'}, 'evento-ficticio')
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='VERIFICAR', resposta='Resposta preservada' WHERE id=?", (tarefa['id'],))
        original = dict(conn.execute('SELECT origem,rota,chat_id,sessao,resposta FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone())
    processamento.reenviar(tarefa['id'])
    with get_conn() as conn:
        assert dict(conn.execute('SELECT origem,rota,chat_id,sessao,resposta FROM tarefas_bot WHERE id=?', (tarefa['id'],)).fetchone()) == original
    assert processamento.processar_proxima()
    assert whatsapp.enviar_mensagem.call_args.kwargs['chat_id'] == '123456789@lid'
    assert whatsapp.enviar_mensagem.call_args.kwargs['session'] == 'loja-ficticia'


def test_resposta_humana_tambem_fica_vinculada_a_rota_da_criacao(monkeypatch):
    humano.controlar('554799990000', 'assumir')
    tarefa = humano.responder({'telefone': '554799990000', 'mensagem': 'Resposta humana fictícia', 'confirmar_envio': True})
    with get_conn() as conn:
        original = conn.execute('SELECT rota FROM tarefas_bot WHERE id=?', (tarefa['tarefa_id'],)).fetchone()[0]
        assert len(original) == 64
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'WAHA')
    assert processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado,resposta FROM tarefas_bot WHERE id=?', (tarefa['tarefa_id'],)).fetchone()[:] == ('FALHOU', 'Resposta humana fictícia')


def test_resposta_humana_nao_e_aceita_entre_gravacao_e_aplicacao(monkeypatch):
    preferencias.salvar({'WHATSAPP_PROVIDER': 'WAHA', 'WAHA_URL': 'https://ficticio.example'})
    humano.controlar('554799990000', 'assumir')
    with get_conn() as conn:
        conn.execute("UPDATE configuracoes SET valor='https://outro-ficticio.example' WHERE chave='WAHA_URL'")
    with pytest.raises(processamento._ConexaoAlterada):
        humano.responder({'telefone': '554799990000', 'mensagem': 'Resposta humana fictícia', 'confirmar_envio': True})
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM tarefas_bot').fetchone()[0] == 0


def test_webhook_meta_repete_evento_se_a_configuracao_ainda_esta_em_transicao(monkeypatch):
    import hashlib
    import hmac
    import json
    from src.app import app
    monkeypatch.setitem(app.config, 'PROPAGATE_EXCEPTIONS', False)
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'META')
    monkeypatch.setattr(config, 'WHATSAPP_PHONE_NUMBER_ID', '123456789000')
    monkeypatch.setattr(config, 'WHATSAPP_BUSINESS_ACCOUNT_ID', '987654321000')
    monkeypatch.setattr(config, 'WHATSAPP_APP_SECRET', 'segredo-exclusivamente-ficticio')
    monkeypatch.setattr(config, 'WHATSAPP_META_AMBIENTE', 'TESTE')
    with get_conn() as conn:
        conn.execute("INSERT INTO configuracoes(chave,valor) VALUES('WHATSAPP_META_AMBIENTE','PRODUCAO')")
    payload = {'entry': [{'id': config.WHATSAPP_BUSINESS_ACCOUNT_ID, 'changes': [{'value': {
        'metadata': {'phone_number_id': config.WHATSAPP_PHONE_NUMBER_ID},
        'messages': [{'from': '554799990000', 'id': 'evento-exclusivamente-ficticio', 'type': 'text', 'text': {'body': 'oi'}}],
    }}]}]}
    corpo = json.dumps(payload).encode()
    assinatura = 'sha256=' + hmac.new(config.WHATSAPP_APP_SECRET.encode(), corpo, hashlib.sha256).hexdigest()
    cliente = app.test_client()
    resposta = cliente.post('/webhook', data=corpo, content_type='application/json', headers={'X-Hub-Signature-256': assinatura})
    assert resposta.status_code == 500
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM tarefas_bot').fetchone()[0] == 0
    monkeypatch.setattr(config, 'WHATSAPP_META_AMBIENTE', 'PRODUCAO')
    repetida = cliente.post('/webhook', data=corpo, content_type='application/json', headers={'X-Hub-Signature-256': assinatura})
    assert repetida.status_code == 200 and repetida.json['status'] == 'recebido'
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM tarefas_bot').fetchone()[0] == 1


@pytest.mark.parametrize('provedor', ['LOCAL', 'WAHA'])
def test_sessao_explicita_de_outra_conexao_nao_e_aceita(provedor):
    preferencias.salvar({'WHATSAPP_PROVIDER': provedor, 'WAHA_SESSION': 'sessao-ativa'})
    with pytest.raises(processamento._ConexaoAlterada):
        processamento.enfileirar({'telefone': '554799990000', 'texto': 'oi', 'session': 'outra-sessao'}, 'ficticio')
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM tarefas_bot').fetchone()[0] == 0


@pytest.mark.parametrize('provedor', ['LOCAL', 'WAHA'])
@pytest.mark.parametrize('formato', ['TEXTO', 'PDF', 'HUMANO'])
def test_transporte_recebe_sessao_pinada_sem_fallback_de_cadastro(monkeypatch, provedor, formato):
    from src import catalogo_pdf
    preferencias.salvar({'WHATSAPP_PROVIDER': provedor, 'WAHA_SESSION': 'sessao-ativa'})
    monkeypatch.setattr(whatsapp, '_sessao_conhecida', Mock(side_effect=AssertionError('Sessão antiga do cadastro não é autoridade.')))
    monkeypatch.setattr(bot, 'processar_mensagem', Mock(return_value='Informação fictícia'))
    pdf = Mock(return_value={'id': 'ficticio'})
    monkeypatch.setattr(whatsapp, 'enviar_pdf', pdf)
    monkeypatch.setattr(catalogo_pdf, 'gerar', Mock(return_value=b'%PDF-1.4\n%%EOF'))
    if formato == 'HUMANO':
        humano.controlar('554799990000', 'assumir')
        tarefa = humano.responder({'telefone': '554799990000', 'mensagem': 'Mensagem fictícia', 'confirmar_envio': True})['tarefa_id']
    else:
        tarefa = entrada('oi')['id']
        if formato == 'PDF':
            with get_conn() as conn:
                conn.execute("UPDATE tarefas_bot SET formato_saida='PDF', resposta='Catálogo fictício' WHERE id=?", (tarefa,))
    with get_conn() as conn:
        assert conn.execute('SELECT sessao FROM tarefas_bot WHERE id=?', (tarefa,)).fetchone()[0] == 'sessao-ativa'
    assert processamento.processar_proxima()
    envio = pdf if formato == 'PDF' else whatsapp.enviar_mensagem
    envio.assert_called_once()
    assert envio.call_args.kwargs['session'] == 'sessao-ativa'


def test_tarefa_com_sessao_trocada_nao_usa_o_hash_valido(monkeypatch):
    tarefa = entrada('oi')
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET sessao='sessao-alheia' WHERE id=?", (tarefa['id'],))
    responder = Mock(side_effect=AssertionError('A sessão não corresponde à conexão do evento.'))
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert processamento.processar_proxima()
    responder.assert_not_called()
    whatsapp.enviar_mensagem.assert_not_called()


def test_troca_inesperada_da_sessao_local_durante_resposta_nao_envia(monkeypatch):
    entrada('oi')
    def responder(*_):
        monkeypatch.setattr(config, 'WAHA_SESSION', 'outra-sessao')
        return 'Resposta fictícia'
    monkeypatch.setattr(bot, 'processar_mensagem', responder)
    assert processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_not_called()


def test_sessao_vazia_nao_e_aceita_com_provedor_real():
    with pytest.raises(ValueError, match='sessão do WhatsApp'):
        preferencias.salvar({'WAHA_SESSION': ''})
