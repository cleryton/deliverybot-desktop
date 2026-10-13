"""Preparação de número próprio: valida acesso pela API sem registrar ou cobrar nada."""
import re
import requests

from . import config, preferencias, publicacao
from .db import get_conn
from .seguranca import transporte_seguro

_http = requests.Session()
_http.trust_env = False


def _id(valor, nome):
    if not isinstance(valor, str) or not re.fullmatch(r'[0-9]{5,40}', valor):
        raise ValueError(f'{nome}: cole o identificador numérico fornecido pela Meta.')
    return valor


def _consulta(caminho, token, params=None):
    transporte_seguro(f'https://graph.facebook.com/{config.WHATSAPP_GRAPH_VERSION}/{caminho}')
    try:
        r = _http.get(f'https://graph.facebook.com/{config.WHATSAPP_GRAPH_VERSION}/{caminho}',
                      headers={'Authorization': 'Bearer ' + token}, params=params,
                      timeout=10, allow_redirects=False)
    except requests.RequestException:
        raise ValueError('Não foi possível validar o número na Meta. Confira a conexão e tente novamente.') from None
    if r.status_code != 200:
        raise ValueError('A Meta recusou a consulta. Confira a validade e as permissões do token para este número e conta.')
    try:
        dados = r.json()
    except ValueError:
        raise ValueError('A Meta retornou dados inesperados.') from None
    if not isinstance(dados, dict):
        raise ValueError('A Meta retornou dados inesperados.')
    return dados


def verificar(dados):
    numero = _id(dados.get('WHATSAPP_PHONE_NUMBER_ID', config.WHATSAPP_PHONE_NUMBER_ID), 'ID do número')
    waba = _id(dados.get('WHATSAPP_BUSINESS_ACCOUNT_ID', config.WHATSAPP_BUSINESS_ACCOUNT_ID), 'ID da conta WhatsApp Business')
    token = dados.get('WHATSAPP_TOKEN') or config.WHATSAPP_TOKEN
    if not isinstance(token, str) or not token or len(token) > 2000 or any(c.isspace() or ord(c) < 32 for c in token):
        raise ValueError('Informe o token de acesso da conta Meta.')
    info = _consulta(numero, token, {'fields': 'id,display_phone_number,verified_name'})
    if info.get('id') != numero:
        raise ValueError('O identificador retornado pela Meta é diferente do número informado.')
    cursor, pertence = None, False
    for _ in range(10):
        params = {'fields': 'id', 'limit': 100}
        if cursor:
            params['after'] = cursor
        conta = _consulta(waba + '/phone_numbers', token, params)
        if not isinstance(conta.get('data'), list):
            raise ValueError('Não foi possível conferir os números desta conta WhatsApp Business.')
        pertence = any(isinstance(n, dict) and n.get('id') == numero for n in conta['data'])
        if pertence:
            break
        paging = conta.get('paging') or {}
        if not isinstance(paging, dict) or not isinstance(paging.get('cursors', {}), dict):
            raise ValueError('A Meta retornou uma paginação inválida.')
        cursor = (paging.get('cursors') or {}).get('after')
        if not paging.get('next') or not isinstance(cursor, str) or len(cursor) > 2000:
            break
    if not pertence:
        raise ValueError('O número não foi encontrado na conta WhatsApp Business informada.')
    return {'validado': True, 'numero_id': numero, 'waba_id': waba,
            'telefone': str(info.get('display_phone_number', ''))[:80],
            'nome': str(info.get('verified_name', ''))[:160],
            'aviso': 'A consulta confirma acesso ao número. Registro, permissões, publicação, pagamento e webhook de produção precisam estar prontos na Meta; esta validação não envia mensagens nem comprova entrega.'}


def situacao():
    endereco = publicacao.endereco()
    with get_conn() as c:
        pendentes = c.execute("SELECT COUNT(*) FROM tarefas_bot WHERE estado!='CONCLUIDA'").fetchone()[0]
        ultima = c.execute('SELECT MAX(entregue_em) FROM meta_mensagens_custo WHERE numero_id=?', (config.WHATSAPP_PHONE_NUMBER_ID,)).fetchone()[0]
    return {'provedor': config.WHATSAPP_PROVIDER, 'ambiente': config.WHATSAPP_META_AMBIENTE,
            'numero_id': config.WHATSAPP_PHONE_NUMBER_ID, 'waba_id': config.WHATSAPP_BUSINESS_ACCOUNT_ID,
            'credenciais': {k: bool(getattr(config, k)) for k in ('WHATSAPP_TOKEN', 'WHATSAPP_APP_SECRET', 'WHATSAPP_VERIFY_TOKEN')},
            'callback': endereco.rstrip('/') + '/webhook' if endereco.startswith('https://') else '',
            'dominio_fixo': config.TUNEL_MODO == 'FIXO', 'pendentes': pendentes, 'ultima_entrega_confirmada': ultima}


def migrar(dados):
    if dados.get('confirmar_migracao') is not True:
        raise ValueError('Confirme a troca da conexão local para o número próprio cadastrado na Meta.')
    if dados.get('numero_anterior') != config.WHATSAPP_PHONE_NUMBER_ID:
        raise ValueError('A configuração mudou. Atualize a página antes de confirmar a troca.')
    with get_conn() as c:
        if c.execute("SELECT 1 FROM tarefas_bot WHERE estado!='CONCLUIDA' LIMIT 1").fetchone():
            raise ValueError('Conclua ou revise as mensagens pendentes antes de trocar o número da Meta.')
    validado = verificar(dados)
    if validado['numero_id'] == config.WHATSAPP_PHONE_NUMBER_ID:
        raise ValueError('Para migrar, informe o ID de um número próprio diferente do número atual.')
    permitidos = {'WHATSAPP_PHONE_NUMBER_ID', 'WHATSAPP_BUSINESS_ACCOUNT_ID', 'WHATSAPP_TOKEN', 'WHATSAPP_APP_SECRET', 'WHATSAPP_VERIFY_TOKEN'}
    novos = {k: v for k, v in dados.items() if k in permitidos}
    novos.update(WHATSAPP_PROVIDER='META', WHATSAPP_META_AMBIENTE='PRODUCAO')
    preferencias.salvar(novos, numero_meta_esperado=dados['numero_anterior'])
    return {**validado, 'salvo': True, 'ambiente': 'PRODUCAO', 'aviso': 'Conexão local trocada. Produtos, pedidos e custos anteriores foram preservados. Confira o webhook na Meta e faça um teste autorizado de recebimento e resposta antes de atender clientes.'}
