"""A fila não transmite respostas automáticas antigas fora do comércio."""
import threading
from unittest.mock import Mock

import pytest
import requests

from src import bot, catalogo_pdf, config, humano, ia, preferencias, processamento, publicacao, whatsapp
from src.db import get_conn, init_db


TELEFONE = '5500000008155'
RECUSA_RAIZ = 'não foi dessa vez seu marcos'


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    for chave in preferencias.CAMPOS | {'MODO_TESTE'}:
        monkeypatch.setattr(config, chave, getattr(config, chave))
    for chave, valor in {
        'DATABASE_PATH': str(tmp_path / 'fila-escopo-ficticia.db'),
        'SEED_CATALOGO': False, 'WHATSAPP_PROVIDER': 'LOCAL', 'MODO_TESTE': False,
        'WAHA_SESSION': 'loja-ficticia', 'BASE_URL': 'https://loja-ficticia.example',
        'IA_PROVIDER': '', 'COMERCIO_CONFIGURADO': 'SIM',
        'COMERCIO_SEGMENTO': 'Lanchonete', 'COMERCIO_MODELO': 'PRODUCAO',
    }.items():
        monkeypatch.setattr(config, chave, valor)
    monkeypatch.setattr(publicacao, '_gerente', None)
    monkeypatch.setattr(processamento, '_servico_pronto', lambda: True)
    monkeypatch.setattr(processamento, '_parar', threading.Event())
    monkeypatch.setattr(processamento, '_acordar', threading.Event())
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', Mock(return_value={}))
    monkeypatch.setattr(whatsapp, 'enviar_pdf', Mock(side_effect=AssertionError('Não enviar PDF neste cenário.')))
    monkeypatch.setattr(catalogo_pdf, 'gerar', Mock(side_effect=AssertionError('Não gerar PDF neste cenário.')))
    monkeypatch.setattr(bot, 'processar_mensagem', Mock(side_effect=AssertionError('Não gerar outra resposta.')))
    init_db(seed_cardapio=False)


def preparar(texto, resposta=None, formato='TEXTO', estado='PENDENTE'):
    ident = processamento.enfileirar({'telefone': TELEFONE, 'texto': texto,
                                      'chat_id': '123456789@lid', 'session': 'loja-ficticia'},
                                     'evento-ficticio')['id']
    with get_conn() as conn:
        conn.execute('UPDATE tarefas_bot SET resposta=?,formato_saida=?,estado=? WHERE id=?',
                     (resposta, formato, estado, ident))
    return ident


def conferir_recusa(ident, esperado):
    assert processamento.processar_proxima()
    assert not processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_called_once_with(
        TELEFONE, esperado, chat_id='123456789@lid',
        session='loja-ficticia', permitir_externos=False)
    whatsapp.enviar_pdf.assert_not_called()
    catalogo_pdf.gerar.assert_not_called()
    bot.processar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado,formato_saida,resposta FROM tarefas_bot WHERE id=?',
                            (ident,)).fetchone()[:] == ('CONCLUIDA', 'TEXTO', esperado)
        assert conn.execute('SELECT count(*) FROM pedidos').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM links_pedido').fetchone()[0] == 0


@pytest.mark.parametrize('texto,esperado', [
    ('Qual a raiz quadrada de 81?', RECUSA_RAIZ), ('O X-Salada tem √81?', RECUSA_RAIZ),
    ('Qual o valor do X-Salada sqrt(81)?', RECUSA_RAIZ),
    ('Quero saber X-Salada 2 + 2', ia.RESPOSTA_FORA_ESCOPO),
])
@pytest.mark.parametrize('resposta', [None, '9'])
def test_entrada_alheia_nao_reabre_inferencia_nem_envia_resultado_antigo(texto, resposta, esperado):
    conferir_recusa(preparar(texto, resposta), esperado)


@pytest.mark.parametrize('resposta', [
    'A raiz quadrada de 81 é 9.', 'sqrt(81) = 9', '√81 = 9',
])
def test_resposta_antiga_e_conferida_mesmo_com_entrada_comercial(resposta):
    conferir_recusa(preparar('Quanto custa o X-Salada?', resposta), ia.RESPOSTA_FORA_ESCOPO)


def test_pdf_preparado_para_entrada_alheia_vira_recusa_textual_sem_anexo():
    conferir_recusa(preparar('Quero fazer um pedido com 2+2', processamento._LEGENDA_CATALOGO, 'PDF'), ia.RESPOSTA_FORA_ESCOPO)


def test_reenvio_manual_de_resposta_antiga_tambem_passara_pela_triagem():
    ident = preparar('Qual a raiz quadrada de 81?', '9', estado='VERIFICAR')
    processamento.reenviar(ident)
    conferir_recusa(ident, RECUSA_RAIZ)


def test_recusa_especifica_ja_persistida_nao_e_trocada_por_pdf():
    conferir_recusa(preparar('Quero comprar', RECUSA_RAIZ, formato='PDF'), RECUSA_RAIZ)


@pytest.mark.parametrize('texto', [
    'Quero um X-Salada entregue na Lua',
    'Quanto é o frete para Marte?',
    'Vocês entregam no espaço?',
])
@pytest.mark.parametrize('formato', ['TEXTO', 'PDF'])
def test_destino_incompativel_pede_area_real_sem_reaproveitar_pdf_ou_promessa(texto, formato):
    antiga = 'Seu X-Salada será entregue nesse destino em 20 minutos.'
    ident = preparar(texto, antiga, formato=formato)
    assert processamento.processar_proxima()
    assert not processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_called_once()
    envio = whatsapp.enviar_mensagem.call_args
    assert envio.args[0] == TELEFONE
    resposta = envio.args[1]
    orientacao = ia.normalizar_texto(resposta)
    assert 'cep' in orientacao and 'area' in orientacao
    assert 'atendid' in orientacao or 'atendimento' in orientacao
    assert resposta not in {antiga, RECUSA_RAIZ, processamento._LEGENDA_CATALOGO}
    assert envio.kwargs == {'chat_id': '123456789@lid', 'session': 'loja-ficticia',
                            'permitir_externos': False}
    whatsapp.enviar_pdf.assert_not_called()
    catalogo_pdf.gerar.assert_not_called()
    bot.processar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado,formato_saida,resposta FROM tarefas_bot WHERE id=?',
                            (ident,)).fetchone()[:] == ('CONCLUIDA', 'TEXTO', resposta)
        assert conn.execute('SELECT count(*) FROM pedidos').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM links_pedido').fetchone()[0] == 0


def test_raiz_quadrada_com_destino_incompativel_mantem_literal_pedido():
    ident = preparar('Quero X-Salada na Lua, qual a raiz quadrada de 81?',
                     processamento._LEGENDA_CATALOGO, formato='PDF')
    conferir_recusa(ident, RECUSA_RAIZ)


def test_falha_de_transporte_e_retry_preservam_literal_especifico_e_metadados(monkeypatch):
    ident = preparar('Qual a raiz quadrada de 81?', 'sqrt(81) = 9')
    enviar = Mock(side_effect=[requests.Timeout('Falha exclusivamente fictícia'), {}])
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', enviar)
    assert processamento.processar_proxima()
    assert not processamento.processar_proxima()
    with get_conn() as conn:
        assert conn.execute('SELECT estado,formato_saida,resposta FROM tarefas_bot WHERE id=?',
                            (ident,)).fetchone()[:] == ('FALHOU', 'TEXTO', RECUSA_RAIZ)
    processamento.reenviar(ident)
    assert processamento.processar_proxima()
    assert not processamento.processar_proxima()
    assert enviar.call_count == 2
    for chamada in enviar.call_args_list:
        assert chamada.args == (TELEFONE, RECUSA_RAIZ)
        assert chamada.kwargs == {'chat_id': '123456789@lid', 'session': 'loja-ficticia',
                                   'permitir_externos': False}
    with get_conn() as conn:
        assert conn.execute('SELECT estado,formato_saida,resposta FROM tarefas_bot WHERE id=?',
                            (ident,)).fetchone()[:] == ('CONCLUIDA', 'TEXTO', RECUSA_RAIZ)
        assert conn.execute("SELECT count(*) FROM mensagens WHERE direcao='SAIDA'").fetchone()[0] == 1
    whatsapp.enviar_pdf.assert_not_called()
    catalogo_pdf.gerar.assert_not_called()
    bot.processar_mensagem.assert_not_called()


@pytest.mark.parametrize('texto,resposta', [
    ('Qual o preço do X-Salada?', 'X-Salada custa R$ 22,00/un.'),
    ('Quanto fica meu pedido?', '2 × X-Salada — R$ 44,00. Taxa de entrega: R$ 5,00. Total: R$ 49,00.'),
    ('Rua da Oficina, 123, Centro', 'Endereço: Rua da Oficina, 123, Centro. Pagamento: Dinheiro.'),
    ('Rua Raiz, 81, Centro', 'Endereço: Rua Raiz, 81, Centro.'),
    ('Rua Lua, 123, Centro', 'Endereço: Rua Lua, 123, Centro.'),
    ('Avenida Marte, 900, Centro', 'Endereço: Avenida Marte, 900, Centro.'),
    ('Cliente Fictício', 'Cliente: Cliente Fictício. Pedido recebido. Número: #12345678.'),
    ('Meu telefone é 47 99999-0000', 'O telefone informado foi mantido no pedido.'),
])
def test_campos_e_valores_comerciais_nao_sao_reinterpretados_como_outro_segmento(texto, resposta):
    ident = preparar(texto, resposta)
    assert processamento.processar_proxima()
    assert whatsapp.enviar_mensagem.call_args.args == (TELEFONE, resposta)
    bot.processar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado,resposta FROM tarefas_bot WHERE id=?',
                            (ident,)).fetchone()[:] == ('CONCLUIDA', resposta)


def test_envio_humano_confirmado_preserva_autoria_e_conteudo():
    humano.controlar(TELEFONE, 'assumir')
    resposta = 'A raiz quadrada de 81 é 9.'
    tarefa = humano.responder({'telefone': TELEFONE, 'mensagem': resposta, 'confirmar_envio': True})
    assert processamento.processar_proxima()
    assert whatsapp.enviar_mensagem.call_args.args == (TELEFONE, resposta)
    assert whatsapp.enviar_mensagem.call_args.kwargs['permitir_externos'] is True
    bot.processar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado FROM tarefas_bot WHERE id=?',
                            (tarefa['tarefa_id'],)).fetchone()[0] == 'CONCLUIDA'


def test_privacidade_legal_continua_acessivel():
    resposta = 'Usamos seus dados para atendimento e pedidos. Contato: responsável fictício.'
    ident = preparar('PRIVACIDADE', resposta)
    assert processamento.processar_proxima()
    assert whatsapp.enviar_mensagem.call_args.args == (TELEFONE, resposta)
    with get_conn() as conn:
        assert conn.execute('SELECT estado FROM tarefas_bot WHERE id=?', (ident,)).fetchone()[0] == 'CONCLUIDA'


def test_pausa_humana_impede_tambem_o_envio_da_recusa():
    ident = preparar('Qual a raiz quadrada de 81?', '9')
    humano.solicitar(TELEFONE)
    assert processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_not_called()
    bot.processar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado FROM tarefas_bot WHERE id=?', (ident,)).fetchone()[0] == 'CONCLUIDA'


def test_rota_de_outra_conexao_nao_e_autorizada_pela_correcao_de_assunto():
    ident = preparar('Qual a raiz quadrada de 81?', '9')
    with get_conn() as conn:
        conn.execute('UPDATE tarefas_bot SET rota=? WHERE id=?', ('0' * 64, ident))
    assert processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_not_called()
    bot.processar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado,resposta FROM tarefas_bot WHERE id=?',
                            (ident,)).fetchone()[:] == ('FALHOU', '9')
