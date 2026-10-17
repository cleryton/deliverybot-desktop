"""Sincronização de webhook: somente contas e transporte simulados."""
import threading
from unittest.mock import Mock

import pytest

from src import config, meta_configuracao as meta, publicacao


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    for chave, valor in {
        'MODO_TESTE': False, 'WHATSAPP_PROVIDER': 'META',
        'WHATSAPP_APP_ID': '11111111111', 'WHATSAPP_BUSINESS_ACCOUNT_ID': '22222222222',
        'WHATSAPP_PHONE_NUMBER_ID': '33333333333', 'WHATSAPP_TOKEN': 'token-ficticio',
        'WHATSAPP_APP_SECRET': 'segredo-ficticio', 'WHATSAPP_VERIFY_TOKEN': 'verificacao-ficticia',
    }.items():
        monkeypatch.setattr(config, chave, valor)
    monkeypatch.setattr(publicacao, '_gerente', None)
    monkeypatch.setattr(meta, '_post', Mock(return_value=True))


def gerente(monkeypatch, url='https://loja-ficticia.trycloudflare.com'):
    g = publicacao.Publicacao(None)
    g.ativo = True
    g._status('ONLINE', 'Teste fictício', url)
    monkeypatch.setattr(publicacao, '_gerente', g)
    return g


def concluir(g):
    g._meta_webhook_thread.join(timeout=2)
    assert not g._meta_webhook_thread.is_alive()


def test_automatico_aplica_callback_atual_sem_preparar_tunel_ou_enviar_mensagens(monkeypatch):
    g = gerente(monkeypatch)
    preparar = Mock(side_effect=AssertionError('Não deve aguardar o próprio monitor.'))
    monkeypatch.setattr(publicacao, 'preparar_para_whatsapp', preparar)
    assert meta.renovar_webhook_automatico(g.situacao()['url'], permitir=lambda: True)
    assert meta._post.call_count == 2
    primeira, segunda = meta._post.call_args_list
    assert primeira.args[0] == '11111111111/subscriptions'
    assert primeira.args[2]['callback_url'] == g.situacao()['url'] + '/webhook'
    assert primeira.args[2]['fields'] == 'messages'
    assert segunda.args[0] == '22222222222/subscribed_apps'
    assert not any('/messages' in c.args[0] for c in meta._post.call_args_list)
    preparar.assert_not_called()


@pytest.mark.parametrize('url', ['http://localhost:5000', 'https://loja.whatsapp.com', 'https://127.0.0.1', 'https://outro.example'])
def test_automatico_nao_publica_endereco_local_ou_diferente_do_tunel(monkeypatch, url):
    gerente(monkeypatch)
    try:
        resultado = meta.renovar_webhook_automatico(url, permitir=lambda: True)
    except ValueError:
        resultado = False
    assert not resultado
    meta._post.assert_not_called()


@pytest.mark.parametrize('campo', ['WHATSAPP_TOKEN', 'WHATSAPP_APP_SECRET', 'WHATSAPP_VERIFY_TOKEN', 'WHATSAPP_APP_ID', 'WHATSAPP_BUSINESS_ACCOUNT_ID'])
def test_automatico_nao_usa_credenciais_incompletas(monkeypatch, campo):
    g = gerente(monkeypatch)
    monkeypatch.setattr(config, campo, '')
    try:
        resultado = meta.renovar_webhook_automatico(g.situacao()['url'], permitir=lambda: True)
    except ValueError:
        resultado = False
    assert not resultado
    meta._post.assert_not_called()


def test_parada_impede_aplicacao_e_troca_de_conta_interrompe_segunda_chamada(monkeypatch):
    g = gerente(monkeypatch)
    assert not meta.renovar_webhook_automatico(g.situacao()['url'], permitir=lambda: False)
    meta._post.assert_not_called()
    def trocar(*args):
        monkeypatch.setattr(config, 'WHATSAPP_APP_ID', '99999999999')
        return True
    meta._post.side_effect = trocar
    assert not meta.renovar_webhook_automatico(g.situacao()['url'], permitir=lambda: True)
    assert meta._post.call_count == 1


def test_falha_da_assinatura_nao_vincula_conta(monkeypatch):
    g = gerente(monkeypatch)
    meta._post.return_value = False
    assert not meta.renovar_webhook_automatico(g.situacao()['url'], permitir=lambda: True)
    assert meta._post.call_count == 1


def test_monitor_atualiza_uma_vez_por_url_e_renova_apos_troca(monkeypatch):
    g = gerente(monkeypatch)
    url = g.situacao()['url']
    assert not g._atualizar_webhook(url)
    concluir(g)
    assert g._atualizar_webhook(url)
    assert g._atualizar_webhook(url)
    assert meta._post.call_count == 2
    novo = 'https://nova-loja-ficticia.trycloudflare.com'
    g._status('ONLINE', 'Mudou', novo)
    assert not g._atualizar_webhook(novo)
    concluir(g)
    assert g._atualizar_webhook(novo)
    assert meta._post.call_count == 4
    assert meta._post.call_args_list[2].args[2]['callback_url'] == novo + '/webhook'


def test_monitor_nao_bloqueia_nem_duplica_tarefa_enquanto_meta_demora(monkeypatch):
    g = gerente(monkeypatch)
    entrou, liberar = threading.Event(), threading.Event()
    def lento(*args, **kwargs):
        entrou.set()
        assert liberar.wait(2)
        return kwargs['permitir']()
    chamada = Mock(side_effect=lento)
    monkeypatch.setattr(meta, 'renovar_webhook_automatico', chamada)
    try:
        assert not g._atualizar_webhook(g.situacao()['url'])
        assert entrou.wait(1)
        assert not g._atualizar_webhook(g.situacao()['url'])
        assert chamada.call_count == 1
        # Mesmo após iniciar, a parada revoga a autorização da tarefa.
        g._stop.set()
    finally:
        liberar.set()
        concluir(g)
    assert not g._meta_webhook_resultado['ok']


def test_falha_repetida_usa_espera_crescente_e_url_nova_nao_herda_espera(monkeypatch):
    g = gerente(monkeypatch)
    tempo = [100.0]
    monkeypatch.setattr(publicacao.time, 'monotonic', lambda: tempo[0])
    chamada = Mock(return_value=False)
    monkeypatch.setattr(meta, 'renovar_webhook_automatico', chamada)
    url = g.situacao()['url']
    assert not g._atualizar_webhook(url)
    concluir(g)
    assert not g._atualizar_webhook(url)
    assert g._webhook_apos == 115
    tempo[0] = 114
    assert not g._atualizar_webhook(url)
    assert chamada.call_count == 1
    tempo[0] = 115
    assert not g._atualizar_webhook(url)
    concluir(g)
    assert not g._atualizar_webhook(url)
    assert g._webhook_apos == 145
    novo = 'https://outra-ficticia.trycloudflare.com'
    g._status('ONLINE', 'Mudou', novo)
    assert not g._atualizar_webhook(novo)
    concluir(g)
    assert chamada.call_count == 3


def test_resultado_antigo_nao_confirma_conta_nova(monkeypatch):
    g = gerente(monkeypatch)
    entered, release = threading.Event(), threading.Event()
    def alterar(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return kwargs['permitir']()
    monkeypatch.setattr(meta, 'renovar_webhook_automatico', alterar)
    try:
        assert not g._atualizar_webhook(g.situacao()['url'])
        assert entered.wait(1)
        monkeypatch.setattr(config, 'WHATSAPP_TOKEN', 'novo-token-ficticio')
    finally:
        release.set()
        concluir(g)
    assert not g._meta_webhook_resultado['ok']
    assert g._webhook_chave is None


@pytest.mark.parametrize('campo,valor', [('MODO_TESTE', True), ('WHATSAPP_PROVIDER', 'LOCAL'), ('WHATSAPP_PROVIDER', 'TESTE')])
def test_outros_provedores_e_simulador_nao_iniciam_meta(monkeypatch, campo, valor):
    g = gerente(monkeypatch)
    monkeypatch.setattr(config, campo, valor)
    assert g._atualizar_webhook(g.situacao()['url'])
    meta._post.assert_not_called()


def test_url_trocada_durante_resposta_da_meta_nao_vincula_callback_antigo(monkeypatch):
    g = gerente(monkeypatch)
    antigo = g.situacao()['url']
    def mudar_url(*args):
        g._status('ONLINE', 'Novo túnel', 'https://novo-ficticio.trycloudflare.com')
        return True
    meta._post.side_effect = mudar_url
    assert not meta.renovar_webhook_automatico(antigo, permitir=lambda: True)
    assert meta._post.call_count == 1


def test_erro_do_worker_e_sanitizado_e_credencial_incompleta_nao_cria_worker(monkeypatch):
    g = gerente(monkeypatch)
    url = g.situacao()['url']
    chamada = Mock(side_effect=RuntimeError('token-ficticio e segredo-ficticio'))
    monkeypatch.setattr(meta, 'renovar_webhook_automatico', chamada)
    assert not g._atualizar_webhook(url)
    concluir(g)
    assert not g._atualizar_webhook(url)
    assert 'token-ficticio' not in g._webhook_aviso
    monkeypatch.setattr(config, 'WHATSAPP_APP_ID', '')
    assert not g._atualizar_webhook(url)
    assert chamada.call_count == 1
    assert 'complete os IDs' in g._webhook_aviso


def test_novo_ciclo_do_tunel_revoga_tarefa_anterior(monkeypatch):
    g = gerente(monkeypatch)
    entrou, liberar = threading.Event(), threading.Event()
    def trabalho(*args, **kwargs):
        entrou.set()
        assert liberar.wait(2)
        return kwargs['permitir']()
    monkeypatch.setattr(meta, 'renovar_webhook_automatico', trabalho)
    try:
        assert not g._atualizar_webhook(g.situacao()['url'])
        assert entrou.wait(1)
        g._webhook_ciclo += 1
    finally:
        liberar.set()
        concluir(g)
    assert not g._meta_webhook_resultado['ok']


def test_espera_da_meta_nao_retarda_troca_para_waha(monkeypatch):
    from src import conexoes
    g = gerente(monkeypatch)
    g._webhook_apos = publicacao.time.monotonic() + 300
    g._webhook_retry_chave = g._chave_meta(g.situacao()['url'])
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'WAHA')
    renovar = Mock(return_value=True)
    monkeypatch.setattr(conexoes, 'renovar_webhook_publico', renovar)
    assert g._atualizar_webhook(g.situacao()['url'])
    renovar.assert_called_once()
