"""Envio de catálogo PDF em memória, sem depender de uma URL pública."""
import base64
import re

from . import config
from .seguranca import transporte_seguro

LIMITE_PDF = 8 * 1024 * 1024
NOME = 'Catalogo-DeliveryBot.pdf'


def _resposta(resp):
    if resp.status_code not in {200, 201}:
        raise ValueError('O WhatsApp não confirmou o envio do documento. Confira antes de tentar novamente.')
    dados = resp.json()
    if not isinstance(dados, dict):
        raise ValueError('Resposta inválida ao enviar o documento.')
    return dados


def enviar(telefone, pdf, legenda, chat_id=None, session=None):
    from . import whatsapp
    if not isinstance(pdf, bytes) or not pdf.startswith(b'%PDF-') or len(pdf) > LIMITE_PDF:
        raise ValueError('O catálogo deve ser um PDF de até 8 MB.')
    if not isinstance(legenda, str) or not legenda.strip() or len(legenda) > 1000:
        raise ValueError('Informe uma legenda de até 1000 caracteres para o catálogo.')
    numero = whatsapp._numero_limpo(telefone)
    if not re.fullmatch(r'[0-9]{10,20}', numero):
        raise ValueError('Destino do catálogo inválido.')
    if config.MODO_TESTE:
        return {'modo_teste': True}
    if config.WHATSAPP_PROVIDER in {'LOCAL', 'WAHA'}:
        destino = chat_id or whatsapp._chat_id_conhecido(telefone) or numero + '@c.us'
        if not re.fullmatch(r'[0-9]{5,20}@(c\.us|lid)', destino):
            raise ValueError('O catálogo só pode ser enviado a uma conversa privada.')
        endereco, chave = config.WAHA_URL, config.WAHA_API_KEY
        if config.WHATSAPP_PROVIDER == 'LOCAL':
            from .whatsapp_local import credenciais
            endereco, chave = credenciais()
        transporte_seguro(endereco)
        payload = {'session': session or whatsapp._sessao_conhecida(telefone) or config.WAHA_SESSION,
                   'chatId': destino, 'caption': legenda,
                   'file': {'mimetype': 'application/pdf', 'filename': NOME,
                            'data': base64.b64encode(pdf).decode('ascii')}}
        retorno = _resposta(whatsapp._http.post(endereco.rstrip('/') + '/api/sendFile',
            json=payload, headers={'X-Api-Key': chave or ''}, timeout=60, allow_redirects=False))
        if not isinstance(retorno.get('id'), (str, dict)) or not retorno['id']:
            raise ValueError('O WhatsApp não informou o identificador do documento. Confira o recebimento.')
        return retorno
    if config.WHATSAPP_PROVIDER != 'META':
        raise ValueError('Conecte o WhatsApp para enviar o catálogo.')
    if not re.fullmatch(r'[0-9]{5,40}', config.WHATSAPP_PHONE_NUMBER_ID) or not re.fullmatch(r'v[0-9]{1,3}\.[0-9]+', config.WHATSAPP_GRAPH_VERSION):
        raise ValueError('Configuração da Meta inválida para documentos.')
    base = f'https://graph.facebook.com/{config.WHATSAPP_GRAPH_VERSION}/{config.WHATSAPP_PHONE_NUMBER_ID}'
    headers = {'Authorization': 'Bearer ' + config.WHATSAPP_TOKEN}
    upload = _resposta(whatsapp._http.post(base + '/media', headers=headers,
        data={'messaging_product': 'whatsapp', 'type': 'application/pdf'}, files={'file': (NOME, pdf, 'application/pdf')},
        timeout=60, allow_redirects=False))
    ident = upload.get('id')
    if not isinstance(ident, str) or not re.fullmatch(r'[0-9]{1,100}', ident):
        raise ValueError('A Meta não confirmou o recebimento do PDF.')
    retorno = _resposta(whatsapp._http.post(base + '/messages', headers=headers,
        json={'messaging_product': 'whatsapp', 'to': numero, 'type': 'document',
              'document': {'id': ident, 'filename': NOME, 'caption': legenda}},
        timeout=30, allow_redirects=False))
    mensagens = retorno.get('messages')
    if not isinstance(mensagens, list) or not any(isinstance(m, dict) and isinstance(m.get('id'), str) and m['id'] for m in mensagens):
        raise ValueError('A Meta não confirmou o identificador da mensagem PDF.')
    try:
        from .meta_custos import registrar_envio
        registrar_envio(retorno)
    except Exception:
        # A mensagem já foi aceita; não provoque duplicação por falha contábil.
        whatsapp.logger.warning('Documento Meta aceito; registro de custos indisponível.')
    return retorno
