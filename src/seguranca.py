"""Proteções HTTP, redução de dados em logs e proteção de segredos no Windows."""
import base64
import ctypes
import hmac
import logging
import os
import re
import secrets
import threading
import time
from datetime import timedelta
from urllib.parse import urlsplit

from flask import g, request, session
from flask.sessions import SecureCookieSessionInterface

from . import config

_tentativas = {}
_trava = threading.Lock()


def igual(a, b):
    return isinstance(a, str) and isinstance(b, str) and hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def local():
    return request.remote_addr in {"127.0.0.1", "::1"} and request.host.split(":")[0] in {"127.0.0.1", "localhost"}


def acesso_administrativo():
    return local() or (config.ADMIN_PERMITIR_REMOTO and request.is_secure)


def csrf():
    session.setdefault("csrf", secrets.token_urlsafe(32))
    return session["csrf"]


def csrf_valido():
    esperado = session.get("csrf", "")
    recebido = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
    origem = request.headers.get("Origin")
    if origem and origem != request.host_url.rstrip("/"):
        return False
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return False
    return bool(esperado and igual(recebido, esperado))


def login_bloqueado():
    agora = time.monotonic()
    with _trava:
        if len(_tentativas) > 4096:
            for chave in list(_tentativas):
                if agora - _tentativas[chave][1] > 300:
                    _tentativas.pop(chave, None)
            if len(_tentativas) > 4096:
                _tentativas.pop(next(iter(_tentativas)))
        n, inicio = _tentativas.get(request.remote_addr, (0, agora))
        return n >= 10 and agora - inicio < 300


def registrar_login(ok):
    with _trava:
        chave = request.remote_addr
        if ok:
            _tentativas.pop(chave, None)
        else:
            agora = time.monotonic()
            n, inicio = _tentativas.get(chave, (0, agora))
            _tentativas[chave] = (n + 1 if agora - inicio < 300 else 1, inicio if agora - inicio < 300 else agora)


def reduzir_dados(texto):
    texto = str(texto)
    texto = re.sub(r"(?i)(/m/|/webhook/waha/|/api/bot/mensagem/)[^\s?\"'<>]+", r"\1[privado]", texto)
    texto = re.sub(r"(?i)(acesso=|Bearer\s+)[^\s&\"']+", r"\1[privado]", texto)
    texto = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[e-mail]", texto)
    texto = re.sub(r"(?<!\d)(?:\+?\d[\s().-]*){10,15}(?!\d)", "[telefone/documento]", texto)
    return texto


class LogPrivado(logging.Filter):
    def filter(self, record):
        record.msg = reduzir_dados(record.getMessage())
        record.args = ()
        # Exceções de provedores podem repetir corpo, contatos e chaves na mensagem.
        if record.exc_info:
            record.msg += " (" + record.exc_info[0].__name__ + ")"
            record.exc_info = None
            record.exc_text = None
        return True


def configurar_logs():
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, LogPrivado) for f in handler.filters):
            handler.addFilter(LogPrivado())


def instalar(app):
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    configurar_logs()
    class SessaoSegura(SecureCookieSessionInterface):
        def get_cookie_secure(self, app):
            return request.is_secure or super().get_cookie_secure(app)
    app.session_interface = SessaoSegura()

    @app.before_request
    def preparar():
        g.csp_nonce = secrets.token_urlsafe(24)

    @app.context_processor
    def contexto():
        return {"csp_nonce": g.csp_nonce, "csrf_token": csrf}

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'nonce-" + g.csp_nonce + "'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; "
            "font-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response


def transporte_seguro(url):
    partes = urlsplit(url)
    if partes.scheme not in {"http", "https"} or not partes.hostname or partes.username or partes.password:
        raise ValueError("Endereço inválido para o serviço.")
    if partes.scheme != "https" and partes.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use HTTPS para serviços externos que recebem dados ou credenciais.")


def proteger_segredo(valor):
    if os.name != "nt" or not valor:
        return valor
    return "dpapi:v1:" + base64.b64encode(_dpapi(valor.encode(), False)).decode()


def revelar_segredo(valor):
    if not valor.startswith("dpapi:v1:"):
        return valor
    if os.name != "nt":
        raise ValueError("Esta credencial está protegida pela conta Windows de origem. Configure-a novamente.")
    try:
        return _dpapi(base64.b64decode(valor[9:], validate=True), True).decode()
    except Exception:
        raise ValueError("Não foi possível abrir uma credencial protegida. Use a conta Windows de origem ou configure-a novamente.") from None


def _dpapi(dados, abrir):
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]
    entrada_buffer = ctypes.create_string_buffer(dados)
    entropy_buffer = ctypes.create_string_buffer(b"DeliveryBot-segredos-v1")
    entrada = Blob(len(dados), ctypes.cast(entrada_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    entropy = Blob(len(b"DeliveryBot-segredos-v1"), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    saida = Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    funcao = crypt32.CryptUnprotectData if abrir else crypt32.CryptProtectData
    funcao.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p,
                       ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    funcao.restype = wintypes.BOOL
    if not funcao(ctypes.byref(entrada), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(saida)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(saida.pbData, saida.cbData)
    finally:
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree(ctypes.cast(saida.pbData, ctypes.c_void_p))


def proteger_pasta(pasta):
    """DACL herdável: apenas conta atual e SYSTEM; não segue atalhos/junções."""
    from pathlib import Path
    pasta = Path(pasta).resolve()
    if pasta in {Path(pasta.anchor), Path.home(), Path.cwd().resolve(), Path.home() / "Downloads", Path.home() / "Desktop"}:
        raise ValueError("Escolha uma subpasta exclusiva para os dados do DeliveryBot.")
    pasta.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        pasta.chmod(0o700)
        return
    from ctypes import wintypes
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    advapi.GetSecurityDescriptorDacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
    advapi.SetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    advapi.SetNamedSecurityInfoW.restype = wintypes.DWORD
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    sid_text = wintypes.LPWSTR()
    descriptor = ctypes.c_void_p()
    try:
        tamanho = wintypes.DWORD()
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(tamanho))
        buffer = ctypes.create_string_buffer(tamanho.value)
        if not advapi.GetTokenInformation(token, 1, buffer, tamanho, ctypes.byref(tamanho)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(sid_text)):
            raise ctypes.WinError(ctypes.get_last_error())
        sddl = f"D:P(A;OICI;FA;;;{sid_text.value})(A;OICI;FA;;;SY)"
        if not advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        presente, padrao, dacl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
        if not advapi.GetSecurityDescriptorDacl(descriptor, ctypes.byref(presente), ctypes.byref(dacl), ctypes.byref(padrao)):
            raise ctypes.WinError(ctypes.get_last_error())
        # Aplicar também aos arquivos antigos, removendo permissões explícitas herdadas de versões anteriores.
        def aplicar(alvo):
            erro = advapi.SetNamedSecurityInfoW(str(alvo), 1, 0x80000004, None, None, dacl, None)
            if erro:
                raise ctypes.WinError(erro)
        aplicar(pasta)
        def antigos(diretorio):
            for alvo in diretorio.iterdir():
                if alvo.is_symlink() or (hasattr(alvo, "is_junction") and alvo.is_junction()):
                    continue
                aplicar(alvo)
                if alvo.is_dir():
                    antigos(alvo)
        antigos(pasta)
    finally:
        if descriptor:
            kernel.LocalFree(descriptor)
        if sid_text:
            kernel.LocalFree(ctypes.cast(sid_text, ctypes.c_void_p))
        kernel.CloseHandle(token)
