"""Fallback de compra sem HTTPS, com anexos e WhatsApp exclusivamente simulados."""
from unittest.mock import Mock

import pypdfium2 as pdfium
import pytest
import requests

from src import catalogo_pdf, config, estoque, humano, processamento, publicacao, whatsapp
from src.db import get_conn, init_db


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'catalogo.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    monkeypatch.setattr(config, 'MODO_TESTE', False)
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'LOCAL')
    monkeypatch.setattr(config, 'IA_PROVIDER', '')
    monkeypatch.setattr(config, 'BASE_URL', '')
    monkeypatch.setattr(publicacao, '_gerente', None)
    monkeypatch.setattr(processamento, '_servico_pronto', lambda: True)
    processamento._parar.clear()
    init_db()


def entrada():
    return processamento.enfileirar({'telefone': '5547999990000', 'texto': '2', 'chat_id': '123456789@lid', 'session': 'loja'}, 'compra')['id']


@pytest.mark.parametrize('provedor', ['LOCAL', 'META', 'WAHA'])
def test_pdf_substitui_espera_por_link_sem_criar_pedido(monkeypatch, provedor):
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', provedor)
    estoque.salvar_produto({'nome': 'Produto fictício', 'categoria': 'Teste', 'preco': '12.50', 'estoque': 37, 'custo': '3.21'})
    ident = entrada()
    enviar = Mock()
    texto = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_pdf', enviar)
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', texto)
    assert processamento.processar_proxima() is False
    assert processamento.processar_proxima() is True
    assert processamento.enfileirar({'telefone': '5547999990000', 'texto': '2', 'session': 'loja'}, 'compra')['duplicada'] is True
    assert processamento.processar_proxima() is False
    enviar.assert_called_once()
    texto.assert_not_called()
    telefone, pdf, legenda = enviar.call_args.args
    assert telefone == '5547999990000' and pdf.startswith(b'%PDF-')
    assert enviar.call_args.kwargs == {'chat_id': '123456789@lid', 'session': 'loja'}
    assert 'PEDIDO PELO WHATSAPP' in legenda and 'PRIVACIDADE' in legenda
    assert 'localhost' not in legenda and 'https://' not in legenda
    with pdfium.PdfDocument(pdf) as doc:
        conteudo = ''.join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    assert 'Produto fictício' in conteudo and '12,50' in conteudo
    assert 'Estoque: 37' not in conteudo and '3,21' not in conteudo
    with get_conn() as conn:
        linha = conn.execute('SELECT formato_saida,estado FROM tarefas_bot WHERE id=?', (ident,)).fetchone()
        assert tuple(linha) == ('PDF', 'CONCLUIDA')
        assert conn.execute('SELECT count(*) FROM pedidos').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM links_pedido').fetchone()[0] == 0


def test_reconexao_antes_da_alternativa_mantem_link(monkeypatch):
    entrada()
    pdf = Mock()
    texto = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_pdf', pdf)
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', texto)
    assert processamento.processar_proxima() is False
    monkeypatch.setattr(config, 'BASE_URL', 'https://loja.example')
    assert processamento.processar_proxima() is True
    assert 'https://loja.example/m/' in texto.call_args.args[1]
    pdf.assert_not_called()


def test_timeout_de_pdf_exige_conferencia_e_retry_manual_permanece_documento(monkeypatch):
    ident = entrada()
    enviar = Mock(side_effect=[requests.Timeout('falha ficticia'), {'id': 'aceito'}])
    monkeypatch.setattr(whatsapp, 'enviar_pdf', enviar)
    texto = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', texto)
    assert processamento.processar_proxima() is False
    assert processamento.processar_proxima() is True
    assert processamento.situacao()['falhas'][0]['estado'] == 'FALHOU'
    assert processamento.processar_proxima() is False
    assert enviar.call_count == 1
    monkeypatch.setattr(config, 'BASE_URL', 'https://loja.example')
    processamento.reenviar(ident)
    assert processamento.processar_proxima() is True
    assert enviar.call_count == 2
    texto.assert_not_called()


def test_pausa_humana_impede_catalogo_automatico(monkeypatch):
    entrada()
    enviar = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_pdf', enviar)
    assert processamento.processar_proxima() is False
    humano.solicitar('5547999990000')
    assert processamento.processar_proxima() is True
    enviar.assert_not_called()


def test_falha_ao_gerar_pdf_nao_inicia_transporte(monkeypatch):
    entrada()
    enviar = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_pdf', enviar)
    monkeypatch.setattr(catalogo_pdf, 'gerar', Mock(side_effect=ValueError('falha ficticia')))
    assert processamento.processar_proxima() is False
    assert processamento.processar_proxima() is True
    assert processamento.situacao()['falhas'][0]['estado'] == 'FALHOU'
    enviar.assert_not_called()


def test_privacidade_nao_vira_catalogo(monkeypatch):
    ident = processamento.enfileirar({'telefone': '5547999990000', 'texto': 'PRIVACIDADE'}, 'privacidade')['id']
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET resposta=?,erro=?,tentativas=1 WHERE id=?", ('https://loja-antiga.example/privacidade', processamento._ERRO_HTTPS, ident))
    enviar = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_pdf', enviar)
    assert processamento.processar_proxima() is False
    enviar.assert_not_called()


def test_migracao_preserva_tarefa_antiga_e_define_texto():
    ident = entrada()
    with get_conn() as conn:
        conn.execute('ALTER TABLE tarefas_bot DROP COLUMN formato_saida')
    init_db(forcar=True)
    with get_conn() as conn:
        linha = conn.execute('SELECT texto,formato_saida FROM tarefas_bot WHERE id=?', (ident,)).fetchone()
    assert tuple(linha) == ('2', 'TEXTO')


@pytest.mark.parametrize('estado', ['PROCESSANDO', 'ENVIANDO'])
def test_reinicio_respeita_o_ponto_em_que_o_documento_parou(monkeypatch, estado):
    ident = entrada()
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado=?,formato_saida='PDF',resposta=? WHERE id=?", (estado, processamento._LEGENDA_CATALOGO, ident))
    enviar = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_pdf', enviar)
    processamento.recuperar_interrompidas()
    assert processamento.processar_proxima() is (estado == 'PROCESSANDO')
    assert enviar.call_count == int(estado == 'PROCESSANDO')
    if estado == 'ENVIANDO':
        assert processamento.situacao()['falhas'][0]['estado'] == 'VERIFICAR'
