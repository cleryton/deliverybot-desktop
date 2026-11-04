"""A fila não transmite respostas automáticas antigas fora do comércio."""
import threading
from unittest.mock import Mock

import pytest

from src import bot, catalogo_pdf, config, humano, ia, preferencias, processamento, publicacao, whatsapp
from src.db import get_conn, init_db


TELEFONE = '5500000008155'


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


def conferir_recusa(ident):
    assert processamento.processar_proxima()
    assert not processamento.processar_proxima()
    whatsapp.enviar_mensagem.assert_called_once_with(
        TELEFONE, ia.RESPOSTA_FORA_ESCOPO, chat_id='123456789@lid',
        session='loja-ficticia', permitir_externos=False)
    whatsapp.enviar_pdf.assert_not_called()
    catalogo_pdf.gerar.assert_not_called()
    bot.processar_mensagem.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT estado,formato_saida,resposta FROM tarefas_bot WHERE id=?',
                            (ident,)).fetchone()[:] == ('CONCLUIDA', 'TEXTO', ia.RESPOSTA_FORA_ESCOPO)
        assert conn.execute('SELECT count(*) FROM pedidos').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM links_pedido').fetchone()[0] == 0


@pytest.mark.parametrize('texto', [
    'Qual a raiz quadrada de 81?', 'O X-Salada tem √81?',
    'Qual o valor do X-Salada sqrt(81)?', 'Quero saber X-Salada 2 + 2',
])
@pytest.mark.parametrize('resposta', [None, '9'])
def test_entrada_alheia_nao_reabre_inferencia_nem_envia_resultado_antigo(texto, resposta):
    conferir_recusa(preparar(texto, resposta))


@pytest.mark.parametrize('resposta', [
    'A raiz quadrada de 81 é 9.', 'sqrt(81) = 9', '√81 = 9',
])
def test_resposta_antiga_e_conferida_mesmo_com_entrada_comercial(resposta):
    conferir_recusa(preparar('Quanto custa o X-Salada?', resposta))


def test_pdf_preparado_para_entrada_alheia_vira_recusa_textual_sem_anexo():
    conferir_recusa(preparar('Quero fazer um pedido com 2+2', processamento._LEGENDA_CATALOGO, 'PDF'))


def test_reenvio_manual_de_resposta_antiga_tambem_passara_pela_triagem():
    ident = preparar('Qual a raiz quadrada de 81?', '9', estado='VERIFICAR')
    processamento.reenviar(ident)
    conferir_recusa(ident)


@pytest.mark.parametrize('texto,resposta', [
    ('Qual o preço do X-Salada?', 'X-Salada custa R$ 22,00/un.'),
    ('Quanto fica meu pedido?', '2 × X-Salada — R$ 44,00. Taxa de entrega: R$ 5,00. Total: R$ 49,00.'),
    ('Rua da Oficina, 123, Centro', 'Endereço: Rua da Oficina, 123, Centro. Pagamento: Dinheiro.'),
    ('Rua Raiz, 81, Centro', 'Endereço: Rua Raiz, 81, Centro.'),
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
