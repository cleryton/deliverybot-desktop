"""Página pública isolada do painel e ciclo de vida do conector incluído no app."""
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
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
        if p.scheme != 'https' or p.username or p.password or p.query or p.fragment or p.path not in {'', '/'} or p.port not in {None, 443}:
            raise ValueError()
        if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) or '.' not in host or host.endswith(('.localhost', '.local', '.internal')):
            raise ValueError()
        if len(host) > 253 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', parte) for parte in host.split('.')):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('Informe um domínio público HTTPS, sem caminho, porta especial ou credenciais.') from None
    return 'https://' + host


def endereco():
    """URL temporária é somente da sessão; não sobrescreve o domínio manual salvo."""
    if _gerente and _gerente.ativo:
        s = _gerente.situacao()
        return s['url'] if s['estado'] == 'ONLINE' else ''
    return config.BASE_URL


def situacao():
    return _gerente.situacao() if _gerente else {'disponivel': False, 'ativo': False, 'estado': 'DESLIGADO', 'url': '', 'mensagem': 'O túnel integrado está disponível no aplicativo Windows.', 'porta': config.TUNEL_PORTA}


def preparar_para_whatsapp(progresso, timeout=120):
    """Deixa o HTTPS público pronto antes de iniciar a sessão do WhatsApp."""
    gerente = _gerente
    if gerente is None:
        # Em instalações sem o gerenciador integrado, preserva o endereço manual.
        return endereco()

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


class PaginaPublica:
    """Permite somente endpoints públicos conhecidos; ignora identidade de proxy."""
    ENDPOINTS = {'pagina_pedido', 'enviar_pedido', 'aviso_privacidade', 'primeiros_passos.confirmar', 'verificar_webhook', 'receber_webhook', 'receber_webhook_waha'}

    def __init__(self, app, obter_url):
        self.app = app
        self.obter_url = obter_url

    def __call__(self, environ, start_response):
        url = self.obter_url()
        if not url:
            return Response('Página de pedidos reconectando. Tente novamente em instantes.', status=503)(environ, start_response)
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
            return Response('Página não encontrada.', status=404)(env, start_response)
        imagem = endpoint == 'static' and re.fullmatch(r'produtos/[a-zA-Z0-9_.-]+\.(?:png|jpg|jpeg|webp|gif)', args.get('filename', ''), re.I)
        if endpoint not in self.ENDPOINTS and not imagem:
            return Response('Página não encontrada.', status=404)(env, start_response)
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

    def situacao(self):
        with self._lock:
            return dict(disponivel=True, ativo=self.ativo, estado=self._estado, url=self._url,
                        mensagem=self._mensagem, porta=self._porta, modo=self._modo)

    def _status(self, estado, mensagem, url=''):
        with self._lock:
            self._estado, self._mensagem, self._url = estado, mensagem, url

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
                url = re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)\b', linha)
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
                self._servidor = create_server(PaginaPublica(self.app, lambda: self.situacao()['url']), host='127.0.0.1', port=self._porta, threads=6)
            except OSError:
                if self._modo == 'FIXO':
                    raise ValueError('A porta da página pública está ocupada. Altere a porta e atualize o destino na Cloudflare.') from None
                self._servidor = create_server(PaginaPublica(self.app, lambda: self.situacao()['url']), host='127.0.0.1', port=0, threads=6)
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
                        if pronto:
                            ultimo_pronto = time.monotonic()
                            tentativas = 0
                            self._status('ONLINE', 'Conector ligado. Teste o link no celular usando dados móveis para confirmar que a página abre.', url)
                        else:
                            self._status('RECONECTANDO' if time.monotonic()-inicio > 15 else 'INICIANDO', 'Aguardando conexão com a Cloudflare. Confira a internet e o firewall.')
                        if not pronto and time.monotonic()-ultimo_pronto > 120:
                            break
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
