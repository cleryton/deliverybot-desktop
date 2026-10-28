"""Consumidor local reservado, com concorrência simulada e nenhuma conta real."""
from concurrent.futures import ThreadPoolExecutor
import threading
import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest

from src import bot, config, humano, ia, processamento, publicacao, whatsapp
from src.db import get_conn, init_db


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticia.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
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
