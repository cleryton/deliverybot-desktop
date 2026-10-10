"""Componente integrado ao executável; não precisa de Docker ou Node instalado."""
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time

import requests

from . import config

_lock = threading.RLock()
_processo = None
_endereco = None
_chave = None
_sessao = None
_callback = None


def recursos():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)) / "whatsapp-native"


def credenciais():
    if not _lock.acquire(blocking=False):
        raise ValueError("Preparando a conexão integrada. Aguarde alguns segundos.")
    try:
        if not _processo or _processo.poll() is not None:
            raise ValueError("A conexão integrada está desligada. Clique em Conectar WhatsApp.")
        return _endereco, _chave
    finally:
        _lock.release()


def iniciar(progresso=lambda *args: None, *, teste=False):
    global _processo, _endereco, _chave, _sessao, _callback
    from .conexoes import _opcoes_processo
    with _lock:
        callback = f"http://127.0.0.1:{os.getenv('DELIVERYBOT_PORT', '5000')}/webhook/waha/{config.WEBHOOK_SECRET}"
        if _processo and _processo.poll() is None:
            if _sessao == config.WAHA_SESSION and _callback == callback:
                return
            encerrar()
        raiz = recursos()
        node = raiz / "runtime/node.exe"
        executavel = str(node) if node.exists() else (None if getattr(sys, "frozen", False) else shutil.which("node"))
        if not executavel or not (raiz / "node_modules/@whiskeysockets/baileys/package.json").exists():
            raise ValueError("O componente WhatsApp não foi encontrado. Reinstale o aplicativo pela versão mais recente.")
        with socket.socket() as reserva:
            reserva.bind(("127.0.0.1", 0))
            porta = reserva.getsockname()[1]
        _chave = secrets.token_urlsafe(32)
        _endereco = f"http://127.0.0.1:{porta}"
        _sessao, _callback = config.WAHA_SESSION, callback
        pasta = Path(config.DATABASE_PATH).resolve().parent
        ambiente = dict(os.environ, DELIVERYBOT_NATIVE_KEY=_chave, DELIVERYBOT_NATIVE_PORT=str(porta),
                        DELIVERYBOT_NATIVE_DATA=str(pasta / "whatsapp"), DELIVERYBOT_NATIVE_SESSION=config.WAHA_SESSION,
                        DELIVERYBOT_NATIVE_CALLBACK=callback,
                        DELIVERYBOT_NATIVE_TEST="1" if teste else "0")
        progresso("Preparando a conexão integrada do WhatsApp…")
        comando = [executavel, str(raiz / "server.mjs")]
        if teste:
            comando.append("--self-test")
        with (pasta / "whatsapp.log").open("ab") as log:
            _processo = subprocess.Popen(comando, env=ambiente, stdin=subprocess.PIPE, stdout=log, stderr=log,
                                         **_opcoes_processo())
        limite = time.monotonic() + 30
        with requests.Session() as http:
            while time.monotonic() < limite:
                if _processo.poll() is not None:
                    raise ValueError("Não foi possível iniciar a conexão integrada. Confira whatsapp.log na pasta de dados.")
                try:
                    resp = http.get(_endereco + "/health", headers={"X-Api-Key": _chave}, timeout=(1, 1), allow_redirects=False)
                    if resp.status_code == 200 and resp.json().get("engine") == "DELIVERYBOT_NATIVE":
                        progresso("Conexão integrada disponível. A sessão ativa será retomada automaticamente.")
                        return
                except (requests.RequestException, ValueError):
                    pass
                time.sleep(.2)
        encerrar()
        raise ValueError("A conexão integrada demorou para iniciar. Reabra o aplicativo.")


def encerrar():
    global _processo, _endereco, _chave
    with _lock:
        processo = _processo
        _processo = None
        _endereco = _chave = None
        if processo:
            if processo.poll() is None:
                try:
                    processo.stdin.write(b"shutdown\n")
                    processo.stdin.flush()
                    processo.wait(timeout=8)
                except (OSError, subprocess.TimeoutExpired):
                    processo.kill()
                    processo.wait(timeout=5)
            if processo.stdin:
                processo.stdin.close()
