"""Página pública isolada do painel e ciclo de vida do conector incluído no app."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

import requests
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from . import config

_gerente = None


def validar_dominio(url):
    try:
        p = urlsplit(url)
        host = (p.hostname or '').lower()
        if host == 'whatsapp.com' or host.endswith('.whatsapp.com') or host == 'wa.me' or host.endswith('.wa.me'):
            raise ValueError('O WhatsApp não hospeda a página de pedidos. Use o túnel temporário ou um domínio próprio configurado na Cloudflare.')
        if p.scheme != 'https' or p.username or p.password or p.query or p.fragment or p.path not in {'', '/'} or p.port not in {None, 443}:
            raise ValueError()
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or '.' not in host or host.endswith(('.localhost', '.local', '.internal', '.lan', '.home')) or all(parte.isdigit() for parte in host.split('.')):
            raise ValueError()
        if len(host) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', parte) for parte in host.split('.')):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
    except (ValueError, TypeError) as exc:
        if str(exc).startswith('O WhatsApp não hospeda'):
            raise ValueError(str(exc)) from None
        raise ValueError('Informe um domínio público HTTPS, sem caminho, porta especial ou credenciais.') from None
    return 'https://' + host


def endereco():
    """URL temporária é somente da sessão; não sobrescreve o domínio manual salvo."""
    if _gerente and _gerente.ativo:
        s = _gerente.situacao()
        base = s['url'] if s['estado'] == 'ONLINE' else ''
    else:
        base = config.BASE_URL
    try:
        return validar_dominio(base)
    except ValueError:
        # Endereços locais só existem no simulador, que não envia mensagens reais.
        return base if config.MODO_TESTE and not (_gerente and _gerente.ativo) else ''


def situacao():
    return _gerente.situacao() if _gerente else {'disponivel': False, 'ativo': False, 'estado': 'DESLIGADO', 'url': '', 'mensagem': 'O túnel integrado está disponível no aplicativo Windows.', 'porta': config.TUNEL_PORTA}


def preparar_para_whatsapp(progresso, timeout=120):
    """Deixa o HTTPS público pronto antes de iniciar a sessão do WhatsApp."""
    gerente = _gerente
    if gerente is None:
        base = endereco()
        if not base:
            raise ValueError('Configure um endereço público HTTPS para receber pedidos antes de conectar o WhatsApp.')
        return base

    atual = gerente.situacao()
    if atual['estado'] != 'ONLINE':
        progresso('Iniciando a página HTTPS para receber pedidos…')
        if not gerente.ativo or atual['estado'] == 'ERRO':
            gerente.iniciar()

    limite = time.monotonic() + timeout
    while True:
        atual = gerente.situacao()
        if atual['estado'] == 'ONLINE' and atual['url']:
            progresso('Página HTTPS pronta. Preparando o login do WhatsApp…')
            return atual['url']
        if atual['estado'] == 'ERRO':
            raise ValueError('Não foi possível iniciar a página HTTPS: ' + atual['mensagem'])
        if time.monotonic() >= limite:
            raise ValueError('A página HTTPS ainda não ficou pronta. Confira a internet e o firewall e tente conectar o WhatsApp novamente.')
        progresso('Aguardando a página HTTPS ficar pronta antes do login do WhatsApp…')
        time.sleep(1)


def _resposta_publica(texto, status=200, headers=None):
    protecoes = {'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                 'X-Frame-Options':'DENY','Referrer-Policy':'no-referrer',
                 'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                 'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Resource-Policy':'same-origin',
                 'X-Permitted-Cross-Domain-Policies':'none'}
    protecoes.update(headers or {})
    return Response(texto,status=status,headers=protecoes,mimetype='text/plain')


class PaginaPublica:
    """Permite somente endpoints públicos conhecidos; ignora identidade de proxy."""
    ENDPOINTS = {'pagina_pedido', 'enviar_pedido', 'pagina_minijogo', 'catalogo_cliente_pdf', 'foto_produto', 'aviso_privacidade', 'primeiros_passos.confirmar', 'verificar_webhook', 'receber_webhook', 'receber_webhook_waha'}

    ASSETS = {'pedido.css', 'pedido.js', 'pong.css', 'pong-core.js', 'pong.js', 'remoto.css', 'remoto.js'}

    REMOTOS = {'remoto.pagina', 'remoto.entrar', 'remoto.estado', 'remoto.avancar', 'remoto.sair'}

    def __init__(self, app, obter_url, verificacao='', esta_pronto=lambda: True):
        self.app = app
        self.obter_url = obter_url
        self.verificacao = verificacao
        self.esta_pronto = esta_pronto

    def __call__(self, environ, start_response):
        if self.verificacao and environ.get('PATH_INFO') == '/_deliverybot/health/' + self.verificacao and environ.get('REQUEST_METHOD') == 'GET':
            return _resposta_publica(self.verificacao)(environ, start_response)
        url = self.obter_url()
        if not url or not self.esta_pronto():
            return _resposta_publica('Página de pedidos reconectando. Tente novamente em instantes.',503,{'Retry-After':'10'})(environ, start_response)
        host = urlsplit(url).netloc
        env = dict(environ)
        # Mesmo com Host/X-Forwarded-For forjados, este servidor nunca é local.
        for k in list(env):
            if k.startswith(('HTTP_X_FORWARDED_', 'HTTP_CF_')) or k in {'HTTP_FORWARDED', 'HTTP_AUTHORIZATION'}:
                env.pop(k, None)
        env.update(REMOTE_ADDR='198.51.100.1', HTTP_HOST=host, SERVER_NAME=host, SERVER_PORT='443')
        env['wsgi.url_scheme'] = 'https'
        try:
            endpoint, args = self.app.url_map.bind_to_environ(env).match()
        except HTTPException:
            return _resposta_publica('Página não encontrada.',404)(env, start_response)
        imagem = endpoint == 'static' and re.fullmatch(r'produtos/[a-zA-Z0-9_.-]+\.(?:png|jpg|jpeg|webp|gif)', args.get('filename', ''), re.I)
        asset_publico = endpoint == 'static' and args.get('filename') in self.ASSETS
        if endpoint not in self.ENDPOINTS | self.REMOTOS and not imagem and not asset_publico:
            return _resposta_publica('Página não encontrada.',404)(env, start_response)
        env['deliverybot.remote_gateway'] = endpoint in self.REMOTOS
        return self.app(env, start_response)


class Publicacao:
    def __init__(self, app):
        self.app = app
        self.ativo = False
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._processo = None
        self._servidor = None
        self._http_thread = None
        self._estado = 'DESLIGADO'
        self._url = ''
        self._mensagem = 'Clique em Iniciar página de pedidos para gerar um endereço público.'
        self._porta = config.TUNEL_PORTA
        self._modo = config.TUNEL_MODO
        self._dominio = ''
        self._token = ''
        self._verificacao = secrets.token_urlsafe(32)
        self._webhook_chave = None
        self._webhook_apos = 0.0
        self._webhook_retry_chave = None
        self._webhook_falhas = 0
        self._webhook_ciclo = 0
        self._meta_webhook_thread = None
        self._meta_webhook_resultado = None
        self._webhook_aviso = ''
        self._diagnostico_https = ''

    def situacao(self):
        with self._lock:
            return dict(disponivel=True, ativo=self.ativo, estado=self._estado, url=self._url,
                        mensagem=self._mensagem, porta=self._porta, modo=self._modo)

    def _status(self, estado, mensagem, url=''):
        with self._lock:
            self._estado, self._mensagem, self._url = estado, mensagem, url

    def _verificar_https(self, http, url):
        """Confirma o destino real, sem clientes, tokens de compra ou redirecionamentos."""
        self._diagnostico_https = ''
        try:
            base = validar_dominio(url)
            with http.get(base + '/_deliverybot/health/' + self._verificacao,
                          timeout=(3, 5), allow_redirects=False, stream=True) as resposta:
                if resposta.status_code != 200:
                    return False
                conteudo = b''
                for bloco in resposta.iter_content(chunk_size=128):
                    conteudo += bloco
                    if len(conteudo) > 128:
                        return False
                return conteudo == self._verificacao.encode('ascii')
        except (requests.RequestException, ValueError, TypeError) as exc:
            pendentes, vistos = [exc], set()
            while pendentes:
                erro = pendentes.pop()
                if id(erro) in vistos:
                    continue
                vistos.add(id(erro))
                if isinstance(erro, socket.gaierror) or type(erro).__name__ == 'NameResolutionError':
                    self._diagnostico_https = 'DNS'
                    break
                pendentes.extend(e for e in (getattr(erro,'reason',None), getattr(erro,'__cause__',None), *getattr(erro,'args',())) if isinstance(e, BaseException))
            return False

    def _atualizar_webhook(self, url):
        if config.MODO_TESTE or config.WHATSAPP_PROVIDER not in {'WAHA', 'META'}:
            return True
        if config.WHATSAPP_PROVIDER == 'META':
            return self._atualizar_webhook_meta(url)
        chave = (url, config.WAHA_URL, config.WAHA_SESSION, config.WAHA_WEBHOOK_BASE_URL, config.WEBHOOK_SECRET)
        if self._webhook_chave == chave:
            return True
        if self._webhook_retry_chave != chave:
            self._webhook_retry_chave, self._webhook_apos = chave, 0.0
        if time.monotonic() < self._webhook_apos:
            return False
        from .conexoes import renovar_webhook_publico
        try:
            renovar_webhook_publico()
        except ValueError:
            self._webhook_apos = time.monotonic() + 15
            return False
        self._webhook_chave, self._webhook_apos = chave, 0.0
        return True

    @staticmethod
    def _chave_meta(url):
        return (config.WHATSAPP_PROVIDER, url, config.WHATSAPP_APP_ID,
                config.WHATSAPP_BUSINESS_ACCOUNT_ID, config.WHATSAPP_PHONE_NUMBER_ID,
                config.WHATSAPP_TOKEN, config.WHATSAPP_APP_SECRET, config.WHATSAPP_VERIFY_TOKEN)

    def _atualizar_webhook_meta(self, url):
        """Uma tarefa por vez: a rede da Meta nunca bloqueia a saúde do túnel."""
        chave = self._chave_meta(url)
        with self._lock:
            if self._meta_webhook_thread and self._meta_webhook_thread.is_alive():
                self._webhook_aviso = 'Atualizando automaticamente o webhook da Meta. O atendimento aguarda a confirmação.'
                return False
            resultado, self._meta_webhook_resultado = self._meta_webhook_resultado, None
            if self._webhook_retry_chave != chave:
                self._webhook_retry_chave = chave
                self._webhook_apos, self._webhook_falhas = 0.0, 0
            if resultado and resultado['chave'] == chave:
                if resultado['ok']:
                    self._webhook_chave, self._webhook_apos = chave, 0.0
                    self._webhook_falhas = 0
                else:
                    self._webhook_falhas += 1
                    self._webhook_apos = time.monotonic() + min(300, 15 * 2 ** min(self._webhook_falhas - 1, 5))
            if self._webhook_chave == chave:
                return True
            self._webhook_aviso = 'Atualizando automaticamente o webhook da Meta. O atendimento aguarda a confirmação.'
            if not all(chave[2:]):
                self._webhook_aviso = 'Meta: complete os IDs do aplicativo e da conta WhatsApp e as credenciais em Meta oficial e custos.'
                return False
            if time.monotonic() < self._webhook_apos:
                self._webhook_aviso = 'A Meta ainda não confirmou o webhook. A atualização será tentada novamente; confira a validade e as permissões da credencial se persistir.'
                return False
            ciclo = self._webhook_ciclo

            def permitir():
                with self._lock:
                    return (self.ativo and not self._stop.is_set() and _gerente is self
                            and self._estado == 'ONLINE' and self._webhook_ciclo == ciclo
                            and not config.MODO_TESTE and self._chave_meta(self._url) == chave)

            def atualizar():
                from .meta_configuracao import renovar_webhook_automatico
                ok = False
                try:
                    ok = bool(renovar_webhook_automatico(url, permitir=permitir)) and permitir()
                except Exception:
                    # Falhas não encerram o monitor e não expõem tokens ou respostas da Meta.
                    pass
                with self._lock:
                    self._meta_webhook_resultado = {'chave': chave, 'ok': ok}

            self._meta_webhook_thread = threading.Thread(target=atualizar, name='DeliveryBot-Meta-Webhook', daemon=True)
            self._meta_webhook_thread.start()
            return False

    def iniciar(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.situacao()
            if self._modo != config.TUNEL_MODO:
                self._modo = config.TUNEL_MODO
            if self._modo == 'FIXO' and not (config.TUNEL_URL and config.TUNEL_TOKEN):
                raise ValueError('Salve o domínio HTTPS e o token da Cloudflare para usar o endereço fixo.')
            if self._modo == 'FIXO':
                validar_dominio(config.TUNEL_URL)
            self._dominio, self._token, self._porta = config.TUNEL_URL, config.TUNEL_TOKEN, config.TUNEL_PORTA
            self.ativo = True
            self._webhook_ciclo += 1
            self._webhook_chave = None
            self._webhook_retry_chave = None
            self._stop.clear()
            self._status('INICIANDO', 'Iniciando a página pública em segundo plano…')
            self._thread = threading.Thread(target=self._executar, name='DeliveryBot-Publicacao', daemon=True)
            self._thread.start()
            return self.situacao()

    def _binario(self):
        raiz = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
        pin = json.loads((raiz / 'packaging/cloudflared.json').read_text(encoding='utf-8'))
        exe = raiz / 'cloudflare/runtime/cloudflared.exe'
        if not exe.exists() or hashlib.sha256(exe.read_bytes()).hexdigest() != pin['sha256']:
            raise ValueError('O componente da página pública está ausente ou alterado. Reinstale o aplicativo pela distribuição oficial.')
        return exe

    def _comando(self, exe, pasta, info):
        # Uma configuração própria evita interferência de túneis do usuário.
        arquivo = pasta / 'conector.yml'
        arquivo.write_text('{}\n', encoding='utf-8')
        cmd = [str(exe), 'tunnel', '--config', str(arquivo), '--no-autoupdate', '--metrics', '127.0.0.1:0', '--loglevel', 'info']
        env = {k: v for k, v in os.environ.items() if not k.startswith(('TUNNEL_', 'NO_AUTOUPDATE', 'NO_TLS_VERIFY'))}
        if self._modo == 'FIXO':
            env['TUNNEL_TOKEN'] = self._token
            cmd += ['run', '--protocol', 'http2']
            info['url'] = self._dominio
        else:
            cmd += ['--protocol', 'http2', '--url', f'http://127.0.0.1:{self._porta}']
        return cmd, env

    @staticmethod
    def _ler(processo, info, trava):
        # Não grava saída do conector: pode conter endereços e segredos.
        try:
            for linha in iter(processo.stdout.readline, ''):
                url = re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)(?=[\s|]|$)', linha)
                metricas = re.search(r'Starting metrics server on (127\.0\.0\.1:\d+)/metrics', linha)
                with trava:
                    if url:
                        info['url'] = 'https://' + url[1]
                    if metricas:
                        info['metricas'] = 'http://' + metricas[1] + '/ready'
        except (OSError, ValueError):
            pass  # O processo foi encerrado pelo aplicativo.

    def _executar(self):
        try:
            exe = self._binario()
            pasta = Path(config.DATABASE_PATH).resolve().parent / 'publicacao'
            pasta.mkdir(exist_ok=True)
            from .seguranca import proteger_pasta
            proteger_pasta(pasta)
            from waitress import create_server
            try:
                gateway = PaginaPublica(self.app, lambda: self.situacao()['url'], self._verificacao, lambda: self.situacao()['estado'] == 'ONLINE')
                self._servidor = create_server(gateway, host='127.0.0.1', port=self._porta, threads=6)
            except OSError:
                if self._modo == 'FIXO':
                    raise ValueError('A porta da página pública está ocupada. Altere a porta e atualize o destino na Cloudflare.') from None
                self._servidor = create_server(gateway, host='127.0.0.1', port=0, threads=6)
                self._porta = self._servidor.effective_port
            self._http_thread = threading.Thread(target=self._servidor.run, name='DeliveryBot-Publico-HTTP', daemon=True)
            self._http_thread.start()
            tentativas = 0
            while not self._stop.is_set():
                info, trava = {}, threading.Lock()
                cmd, env = self._comando(exe, pasta, info)
                from .conexoes import _opcoes_processo
                self._processo = subprocess.Popen(cmd, env=env, cwd=pasta, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace', **_opcoes_processo())
                leitor = threading.Thread(target=self._ler, args=(self._processo, info, trava), daemon=True)
                leitor.start()
                inicio = time.monotonic()
                ultimo_pronto = inicio
                https_url, https_ate = '', 0.0
                with requests.Session() as http:
                    http.trust_env = False
                    while not self._stop.wait(2) and self._processo.poll() is None:
                        with trava:
                            url, metricas = info.get('url', ''), info.get('metricas', '')
                        pronto = False
                        if url and metricas:
                            try:
                                with http.get(metricas, timeout=2, allow_redirects=False) as r:
                                    pronto = r.status_code == 200
                            except requests.RequestException:
                                pass
                        if pronto and (url != https_url or time.monotonic() >= https_ate):
                            pronto = self._verificar_https(http, url)
                            if pronto:
                                https_url, https_ate = url, time.monotonic() + 20
                            else:
                                https_ate = 0.0
                        if pronto:
                            ultimo_pronto = time.monotonic()
                            tentativas = 0
                            self._status('ONLINE', 'Página HTTPS verificada e pronta para receber pedidos. A conexão é monitorada automaticamente.', url)
                            if not self._atualizar_webhook(url):
                                aviso = (self._webhook_aviso if config.WHATSAPP_PROVIDER == 'META' else 'Reconectando o recebimento das mensagens do WAHA externo; confira esse servidor se a demora continuar.')
                                self._status('ONLINE', 'Página HTTPS pronta. ' + aviso, url)
                        else:
                            https_ate = 0.0
                            mensagem = ('O endereço não foi encontrado no DNS. No domínio fixo, configure o registro do seu domínio na Cloudflare. No temporário, o aplicativo tentará gerar outra conexão automaticamente.' if self._diagnostico_https == 'DNS' else 'Verificando o acesso HTTPS aos pedidos. Confira a internet; no domínio fixo, confira também o destino na Cloudflare.')
                            self._status('RECONECTANDO' if time.monotonic()-inicio > 15 else 'INICIANDO', mensagem)
                        # Um domínio temporário sem DNS deve ser substituído dentro
                        # do prazo de preparação do login, não somente após ele.
                        espera = 30 if self._modo == 'RAPIDO' and self._diagnostico_https == 'DNS' and not https_url else 120
                        if not pronto and time.monotonic()-ultimo_pronto > espera:
                            break
                self._status('RECONECTANDO', 'Conexão interrompida. O aplicativo tentará novamente automaticamente.')
                self._matar()
                leitor.join(timeout=3)
                tentativas += 1
                self._status('RECONECTANDO', 'Conexão interrompida. O aplicativo tentará novamente automaticamente.')
                if self._stop.wait(min(60, 3 * 2 ** min(tentativas, 5))):
                    break
        except Exception as exc:
            self._status('ERRO', str(exc) if isinstance(exc, ValueError) else 'Não foi possível abrir a página pública. Confira a instalação e tente novamente.')
        finally:
            self._token = ''
            self._matar()
            if self._servidor:
                self._servidor.close()
            if self._http_thread:
                self._http_thread.join(timeout=5)

    def _matar(self):
        p = self._processo
        if p:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait(timeout=5)
            if p.stdout:
                p.stdout.close()
            self._processo = None

    def encerrar(self):
        self._stop.set()
        self._status('DESLIGADO', 'Página pública desligada. Os pedidos salvos continuam no aplicativo.')
        if self._thread:
            self._thread.join(timeout=15)
            if self._thread.is_alive():
                raise ValueError('A página pública ainda está encerrando. Aguarde alguns segundos.')
        self.ativo = False
        self._status('DESLIGADO', 'Página pública desligada. Os pedidos salvos continuam no aplicativo.')


def preparar(app):
    global _gerente
    _gerente = Publicacao(app)
    if config.TUNEL_AUTOMATICO == 'SIM':
        try:
            _gerente.iniciar()
        except ValueError as exc:
            # Uma credencial indisponível nunca impede de abrir a gestão local.
            _gerente.ativo = True
            _gerente._status('ERRO', str(exc))
    return _gerente
