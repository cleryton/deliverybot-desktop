"""Configuração individual: nenhuma credencial do autor é incluída no aplicativo."""
import secrets
import time
import threading
from functools import wraps
import requests

from . import config, preferencias, publicacao
from .db import get_conn
from .meta_oficial import _id, _consulta, _http

_lock = threading.RLock()


def _exclusivo(funcao):
    @wraps(funcao)
    def executar(*args, **kwargs):
        if not _lock.acquire(blocking=False):
            raise ValueError('Uma configuração da Meta já está em andamento. Aguarde a conclusão.')
        try:
            return funcao(*args, **kwargs)
        finally:
            _lock.release()
    return executar


def _credenciais(dados):
    # Primeira conexão exige valores explícitos: nunca reaproveita a conta de outra pessoa.
    app = _id(dados.get('WHATSAPP_APP_ID'), 'ID do aplicativo')
    waba = _id(dados.get('WHATSAPP_BUSINESS_ACCOUNT_ID'), 'ID da conta WhatsApp Business')
    token, segredo = dados.get('WHATSAPP_TOKEN'), dados.get('WHATSAPP_APP_SECRET')
    for valor in (token, segredo):
        if not isinstance(valor, str) or not 10 <= len(valor) <= 2000 or any(c.isspace() or ord(c) < 32 for c in valor):
            raise ValueError('Informe o token e o segredo do seu próprio aplicativo Meta.')
    return app, waba, token, segredo


def consultar(dados):
    app, waba, token, segredo = _credenciais(dados)
    debug = _consulta('debug_token', app + '|' + segredo, {'input_token': token}).get('data')
    if not isinstance(debug, dict) or debug.get('is_valid') is not True or debug.get('app_id') != app:
        raise ValueError('O token não é válido para este aplicativo. Confira as credenciais da sua conta.')
    scopes = debug.get('scopes')
    if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes) or not {'whatsapp_business_messaging', 'whatsapp_business_management'} <= set(scopes):
        raise ValueError('O token precisa das permissões de mensagens e gerenciamento do WhatsApp.')
    for campo in ('expires_at', 'data_access_expires_at'):
        valor = debug.get(campo)
        if valor is not None and (isinstance(valor, bool) or not isinstance(valor, int) or valor < 0 or (valor and valor <= time.time())):
            raise ValueError('A credencial expirou ou possui validade inesperada. Gere um token na sua conta Meta.')
    numeros, cursor = [], None
    for _ in range(10):
        params = {'fields': 'id,display_phone_number,verified_name', 'limit': 100}
        if cursor:
            params['after'] = cursor
        pagina = _consulta(waba + '/phone_numbers', token, params)
        if not isinstance(pagina.get('data'), list):
            raise ValueError('Não foi possível listar os números da sua conta.')
        for n in pagina['data']:
            if not isinstance(n, dict):
                continue
            ident = _id(n.get('id'), 'ID retornado pela Meta')
            if not any(p['id'] == ident for p in numeros):
                numeros.append({'id': ident, 'telefone': str(n.get('display_phone_number', ''))[:80],
                                'nome': str(n.get('verified_name', ''))[:160]})
        paging = pagina.get('paging') or {}
        if not isinstance(paging, dict) or not isinstance(paging.get('cursors', {}), dict):
            raise ValueError('A Meta retornou uma paginação inválida.')
        cursor = (paging.get('cursors') or {}).get('after')
        if not paging.get('next'):
            break
        if not isinstance(cursor, str) or not cursor or len(cursor) > 2000:
            raise ValueError('Não foi possível concluir a consulta dos números.')
    else:
        raise ValueError('A conta tem muitos números. Consulte a configuração avançada.')
    if not numeros:
        raise ValueError('Nenhum número disponível. Confira a conta WhatsApp e os ativos atribuídos ao token na Meta.')
    return {'numeros': numeros, 'expira_em': debug.get('expires_at'),
            'acesso_dados_expira_em': debug.get('data_access_expires_at'),
            'usuario_sistema': debug.get('type') == 'SYSTEM_USER'}


def _post(caminho, token, dados=None):
    try:
        r = _http.post(f'https://graph.facebook.com/{config.WHATSAPP_GRAPH_VERSION}/{caminho}',
                       headers={'Authorization': 'Bearer ' + token}, data=dados,
                       timeout=15, allow_redirects=False)
        return r.status_code == 200 and r.json().get('success') is True
    except (requests.RequestException, ValueError, AttributeError):
        return False


@_exclusivo
def configurar_webhook(conta_esperada=None):
    if conta_esperada and any(getattr(config, k) != v for k, v in conta_esperada.items()):
        raise ValueError('A conta mudou. Atualize a página antes de configurar o webhook.')
    if config.WHATSAPP_PROVIDER != 'META':
        raise ValueError('Conecte sua conta Meta antes de configurar o webhook.')
    app = _id(config.WHATSAPP_APP_ID, 'ID do aplicativo')
    waba = _id(config.WHATSAPP_BUSINESS_ACCOUNT_ID, 'ID da conta WhatsApp Business')
    snapshot = {k: getattr(config, k) for k in ('WHATSAPP_PROVIDER', 'WHATSAPP_APP_ID', 'WHATSAPP_BUSINESS_ACCOUNT_ID', 'WHATSAPP_TOKEN', 'WHATSAPP_APP_SECRET', 'WHATSAPP_VERIFY_TOKEN')}
    publicacao.preparar_para_whatsapp(lambda mensagem: None, timeout=30)
    callback = publicacao.validar_dominio(publicacao.endereco()) + '/webhook'
    # Meta verifica o challenge em nosso endpoint, usando a chave local já salva.
    if any(getattr(config, k) != v for k, v in snapshot.items()):
        raise ValueError('A conta mudou durante a preparação. Atualize a página e tente novamente.')
    aplicado = _post(app + '/subscriptions', app + '|' + snapshot['WHATSAPP_APP_SECRET'],
                    {'object': 'whatsapp_business_account', 'callback_url': callback,
                     'verify_token': snapshot['WHATSAPP_VERIFY_TOKEN'], 'fields': 'messages', 'include_values': 'true'})
    mesma_conta = all(getattr(config, k) == v for k, v in snapshot.items())
    vinculado = _post(waba + '/subscribed_apps', snapshot['WHATSAPP_TOKEN']) if aplicado and mesma_conta else False
    vinculado = vinculado and all(getattr(config, k) == v for k, v in snapshot.items())
    return {'webhook_configurado': aplicado and vinculado, 'callback': callback,
            'aviso': 'Webhook configurado pela Meta. Faça um teste de recebimento e resposta com seu próprio WhatsApp.'
                     if aplicado and vinculado else 'A Meta não confirmou toda a configuração do webhook. A conexão local foi preservada. Confira permissões e HTTPS, ou configure no painel Meta e tente novamente.'}


@_exclusivo
def conectar(dados):
    if dados.get('confirmar') is not True:
        raise ValueError('Confirme que deseja conectar sua própria conta Meta neste computador.')
    anterior = dados.get('numero_anterior')
    if anterior != config.WHATSAPP_PHONE_NUMBER_ID:
        raise ValueError('A conexão mudou. Atualize a página antes de continuar.')
    ambiente = dados.get('WHATSAPP_META_AMBIENTE')
    if ambiente not in {'TESTE', 'PRODUCAO'} or not isinstance(dados.get('configurar_webhook'), bool):
        raise ValueError('Escolha teste ou produção e se deseja configurar o webhook.')
    with get_conn() as c:
        if c.execute("SELECT 1 FROM tarefas_bot WHERE estado!='CONCLUIDA' LIMIT 1").fetchone():
            raise ValueError('Revise as mensagens pendentes antes de conectar outra conta.')
    esperada = {k: getattr(config, k) for k in ('WHATSAPP_PROVIDER', 'WHATSAPP_APP_ID', 'WHATSAPP_PHONE_NUMBER_ID', 'WHATSAPP_BUSINESS_ACCOUNT_ID')}
    validado = consultar(dados)
    numero = _id(dados.get('WHATSAPP_PHONE_NUMBER_ID'), 'Número escolhido')
    if not any(n['id'] == numero for n in validado['numeros']):
        raise ValueError('Escolha um número pertencente à conta consultada.')
    if dados['configurar_webhook']:
        publicacao.preparar_para_whatsapp(lambda mensagem: None, timeout=30)
        publicacao.validar_dominio(publicacao.endereco())
    app, waba, token, segredo = _credenciais(dados)
    # Mantém a chave quando a conta/app e segredo são os mesmos; troca de conta gera outra.
    mesmo = (config.WHATSAPP_PROVIDER == 'META' and config.WHATSAPP_APP_ID == app
             and config.WHATSAPP_BUSINESS_ACCOUNT_ID == waba and config.WHATSAPP_APP_SECRET == segredo)
    chave = config.WHATSAPP_VERIFY_TOKEN if mesmo else secrets.token_urlsafe(32)
    preferencias.salvar({'WHATSAPP_PROVIDER': 'META', 'WHATSAPP_META_AMBIENTE': ambiente,
        'WHATSAPP_APP_ID': app, 'WHATSAPP_BUSINESS_ACCOUNT_ID': waba, 'WHATSAPP_PHONE_NUMBER_ID': numero,
        'WHATSAPP_TOKEN': token, 'WHATSAPP_APP_SECRET': segredo, 'WHATSAPP_VERIFY_TOKEN': chave},
        numero_meta_esperado=anterior, conta_meta_esperada=esperada, meta_sem_pendencias=True)
    r = {'salvo': True, 'aviso': 'Sua conta foi salva com proteção local. Nenhuma mensagem foi enviada.',
         'webhook_configurado': False}
    if dados['configurar_webhook']:
        try:
            r.update(configurar_webhook({'WHATSAPP_APP_ID': app, 'WHATSAPP_BUSINESS_ACCOUNT_ID': waba,
                'WHATSAPP_PHONE_NUMBER_ID': numero, 'WHATSAPP_TOKEN': token, 'WHATSAPP_APP_SECRET': segredo,
                'WHATSAPP_VERIFY_TOKEN': chave, 'WHATSAPP_PROVIDER': 'META'}))
        except ValueError:
            r['aviso'] = 'Sua conta foi salva, mas o webhook ainda precisa de atenção. Confira o HTTPS e use Atualizar webhook da conta já salva. Nenhuma mensagem foi enviada.'
    return r
