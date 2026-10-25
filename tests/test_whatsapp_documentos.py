"""Contratos HTTP de documentos, sem credenciais ou transportes reais."""
import base64
from unittest.mock import Mock

import pytest

from src import config, meta_custos, whatsapp, whatsapp_documentos

PDF = b'%PDF-1.4\nconteudo-ficticio\n%%EOF'
TELEFONE = '5547999990000'


def resposta(dados, status=200):
    r = Mock(status_code=status)
    r.json.return_value = dados
    return r


@pytest.fixture(autouse=True)
def ambiente(monkeypatch):
    monkeypatch.setattr(config, 'MODO_TESTE', False)
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'META')
    monkeypatch.setattr(config, 'WHATSAPP_GRAPH_VERSION', 'v25.0')
    monkeypatch.setattr(config, 'WHATSAPP_PHONE_NUMBER_ID', '123456789')
    monkeypatch.setattr(config, 'WHATSAPP_TOKEN', 'token-ficticio')
    monkeypatch.setattr(config, 'WAHA_URL', 'https://waha.example')
    monkeypatch.setattr(config, 'WAHA_API_KEY', 'chave-ficticia')
    monkeypatch.setattr(whatsapp, '_http', Mock())
    monkeypatch.setattr(meta_custos, 'registrar_envio', Mock())


@pytest.mark.parametrize('provedor', ['LOCAL', 'WAHA'])
def test_envio_inline_preserva_lid_sessao_e_nao_precisa_https_publico(monkeypatch, provedor):
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', provedor)
    monkeypatch.setattr(config, 'BASE_URL', '')
    from src import whatsapp_local
    monkeypatch.setattr(whatsapp_local, 'credenciais', lambda: ('http://127.0.0.1:3555', 'chave-local'))
    whatsapp._http.post.return_value = resposta({'id': 'documento-aceito'})
    assert whatsapp.enviar_pdf(TELEFONE, PDF, 'Catálogo', '123456789@lid', 'loja')['id']
    chamada = whatsapp._http.post.call_args
    assert chamada.args[0].endswith('/api/sendFile')
    assert chamada.kwargs['allow_redirects'] is False
    p = chamada.kwargs['json']
    assert p['chatId'] == '123456789@lid' and p['session'] == 'loja'
    assert base64.b64decode(p['file']['data']) == PDF
    assert 'url' not in p['file'] and p['file']['mimetype'] == 'application/pdf'


def test_meta_upload_e_envio_por_id_sem_url_publica():
    whatsapp._http.post.side_effect = [resposta({'id': '987654'}), resposta({'messages': [{'id': 'wamid.pdf'}]})]
    whatsapp.enviar_pdf(TELEFONE, PDF, 'Catálogo')
    upload, envio = whatsapp._http.post.call_args_list
    assert upload.args[0] == 'https://graph.facebook.com/v25.0/123456789/media'
    assert upload.kwargs['files']['file'][1:] == (PDF, 'application/pdf')
    assert upload.kwargs['data'] == {'messaging_product': 'whatsapp', 'type': 'application/pdf'}
    assert envio.kwargs['json']['document']['id'] == '987654'
    assert envio.kwargs['json']['type'] == 'document'
    assert 'link' not in envio.kwargs['json']['document']
    assert all(c.kwargs['allow_redirects'] is False for c in whatsapp._http.post.call_args_list)
    meta_custos.registrar_envio.assert_called_once()


def test_falha_de_custos_nao_reenvia_documento_ja_aceito():
    whatsapp._http.post.side_effect = [resposta({'id': '987654'}), resposta({'messages': [{'id': 'wamid.pdf'}]})]
    meta_custos.registrar_envio.side_effect = RuntimeError('falha local ficticia')
    assert whatsapp.enviar_pdf(TELEFONE, PDF, 'Catálogo')['messages']
    assert whatsapp._http.post.call_count == 2


@pytest.mark.parametrize('upload', [resposta({}, 302), resposta({}, 401), resposta({'id': 'https://intruso.example'}), resposta([])])
def test_upload_invalido_nao_dispara_mensagem(upload):
    whatsapp._http.post.return_value = upload
    with pytest.raises(ValueError):
        whatsapp.enviar_pdf(TELEFONE, PDF, 'Catálogo')
    assert whatsapp._http.post.call_count == 1


@pytest.mark.parametrize('pdf', [b'nao e PDF', b'%PDF-' + b'x' * (8 * 1024 * 1024), 'arquivo.pdf'], ids=['invalido', 'grande', 'caminho'])
def test_arquivo_invalido_ou_grande_nao_acessa_rede(pdf):
    with pytest.raises(ValueError):
        whatsapp.enviar_pdf(TELEFONE, pdf, 'Catálogo')
    whatsapp._http.post.assert_not_called()


def test_modo_teste_nunca_acessa_rede(monkeypatch):
    monkeypatch.setattr(config, 'MODO_TESTE', True)
    assert whatsapp.enviar_pdf(TELEFONE, PDF, 'Catálogo') == {'modo_teste': True}
    whatsapp._http.post.assert_not_called()


def test_documento_sem_identificador_nao_e_marcado_como_aceito():
    whatsapp._http.post.side_effect = [resposta({'id': '987654'}), resposta({'messages': []})]
    with pytest.raises(ValueError):
        whatsapp.enviar_pdf(TELEFONE, PDF, 'Catálogo')
    meta_custos.registrar_envio.assert_not_called()


def test_grupo_nao_e_destino_permitido(monkeypatch):
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'WAHA')
    with pytest.raises(ValueError):
        whatsapp.enviar_pdf(TELEFONE, PDF, 'Catálogo', '123456789@g.us', 'loja')
    whatsapp._http.post.assert_not_called()
