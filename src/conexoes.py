"""Controles de conexão, tarefas em segundo plano e inicialização local sem terminal."""
import copy
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time
from urllib.parse import quote, urlsplit

import requests

from . import config, preferencias, whatsapp_local

_local_http = threading.local()
_lock = threading.Lock()
_jobs = {}


def http():
    if not hasattr(_local_http, "sessao"):
        _local_http.sessao = requests.Session()
    return _local_http.sessao


def url_local(url):
    return urlsplit(url).hostname in {"localhost", "127.0.0.1", "::1"}


def url_webhook():
    if config.WHATSAPP_PROVIDER in {"LOCAL", "TESTE"}:
        return f"http://127.0.0.1:{os.getenv('DELIVERYBOT_PORT', '5000')}/webhook/waha/{config.WEBHOOK_SECRET}"
    base = config.WAHA_WEBHOOK_BASE_URL
    if not base:
        if url_local(config.WAHA_URL):
            base = f"http://host.docker.internal:{os.getenv('DELIVERYBOT_PORT', '5000')}"
        elif not url_local(config.BASE_URL):
            base = config.BASE_URL
        else:
            raise ValueError("Para um WAHA remoto, informe o endereço público da loja ou o endereço do aplicativo visto pelo WAHA nas configurações.")
    return base.rstrip("/") + "/webhook/waha/" + config.WEBHOOK_SECRET


def _waha(metodo, caminho, dados=None, aceitar_404=False):
    if config.WHATSAPP_PROVIDER in {"LOCAL", "TESTE"}:
        endereco, chave = whatsapp_local.credenciais()
    else:
        endereco, chave = config.WAHA_URL, config.WAHA_API_KEY
    try:
        resposta = http().request(metodo, endereco + caminho, json=dados,
                                 headers={"X-Api-Key": chave, "Accept": "application/json"},
                                 timeout=(2, 10 if metodo != "GET" else 3), allow_redirects=False)
    except requests.RequestException:
        raise ValueError("O serviço WhatsApp não respondeu. Clique em Conectar WhatsApp ou confira as configurações avançadas.") from None
    if resposta.status_code == 404 and aceitar_404:
        return None
    if resposta.status_code in {401,403}:
        raise ValueError("A chave de acesso WAHA não foi aceita. Confira-a em Configurações.")
    if not 200 <= resposta.status_code < 300:
        raise ValueError(f"O WAHA retornou erro {resposta.status_code}. Verifique o serviço e tente novamente.")
    try:
        return resposta.json() if resposta.content else {}
    except ValueError:
        raise ValueError("Este endereço não retornou a API do WAHA. Confira as configurações.") from None


def _sessao_path():
    return "/api/sessions/" + quote(config.WAHA_SESSION, safe="")


def status_whatsapp():
    try:
        info = _waha("GET", _sessao_path(), aceitar_404=True)
        if info is None:
            return {"servico": True, "conectado": False, "estado": "SEM_SESSAO", "mensagem": "Serviço disponível. Clique em Conectar WhatsApp para gerar o QR Code."}
        if not isinstance(info, dict):
            raise ValueError("Resposta inválida do serviço WAHA.")
        estado = info.get("status", "DESCONHECIDO")
        textos = {"WORKING": "WhatsApp conectado", "SCAN_QR_CODE": "Escaneie o QR Code com seu celular", "STARTING": "Preparando a conexão…", "STOPPED": "Conexão pausada", "FAILED": "Conexão interrompida. Clique em Conectar WhatsApp.", "PASSKEY_REQUIRED": "Abra o painel WAHA para concluir a confirmação do WhatsApp.", "PASSKEY_CONFIRMATION_REQUIRED": "Confirme a conexão no painel WAHA."}
        try:
            esperado = url_webhook()
            configurado = any(w.get("url") == esperado and "message" in (w.get("events") or []) for w in ((info.get("config") or {}).get("webhooks") or []))
        except ValueError:
            configurado = False
        return {"servico": True, "conectado": estado == "WORKING", "estado": estado,
                "mensagem": info.get("error") or textos.get(estado, estado), "webhook_configurado": configurado,
                "numero": (info.get("me") or {}).get("id", "").split("@")[0]}
    except ValueError as exc:
        return {"servico": False, "conectado": False, "estado": "INDISPONIVEL", "mensagem": str(exc)}


def qr_whatsapp():
    dados = _waha("GET", f"/api/{quote(config.WAHA_SESSION, safe='')}/auth/qr?format=image")
    if not isinstance(dados, dict) or dados.get("mimetype") != "image/png" or not isinstance(dados.get("data"), str) or len(dados["data"]) > 2_000_000:
        raise ValueError("O QR Code ainda não está disponível. Aguarde alguns segundos e atualize.")
    # Confere o formato antes de exibir uma imagem enviada por um serviço externo.
    import base64
    try:
        imagem = base64.b64decode(dados["data"], validate=True)
        if not imagem.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError
    except ValueError:
        raise ValueError("O WAHA retornou um QR Code inválido.") from None
    return {"imagem": "data:image/png;base64," + dados["data"]}


def conectar_whatsapp(progresso):
    if not config.WEBHOOK_SECRET:
        preferencias.salvar({"WEBHOOK_SECRET": secrets.token_urlsafe(32)})
    if config.WHATSAPP_PROVIDER == "LOCAL":
        whatsapp_local.iniciar(progresso)
    callback = url_webhook()
    info = _waha("GET", _sessao_path(), aceitar_404=True)
    cfg = copy.deepcopy((info or {}).get("config") or {})
    cfg["webhooks"] = [w for w in (cfg.get("webhooks") or []) if not urlsplit(w.get("url", "")).path.startswith("/webhook/waha/")]
    cfg["webhooks"].append({"url": callback, "events": ["message"], "retries": {"policy": "constant", "delaySeconds": 3, "attempts": 5}})
    cfg["ignore"] = {**(cfg.get("ignore") or {}), "groups": True, "status": True, "channels": True, "broadcast": True}
    progresso("Configurando o recebimento automático das mensagens…")
    if info is None:
        _waha("POST", "/api/sessions", {"name": config.WAHA_SESSION, "start": True, "config": cfg})
    else:
        payload = {"name": config.WAHA_SESSION, "config": cfg}
        if "apps" in info:
            payload["apps"] = info["apps"]
        _waha("PUT", _sessao_path(), payload)
        if info.get("status") == "FAILED":
            _waha("POST", _sessao_path() + "/restart")
        elif info.get("status") == "STOPPED":
            _waha("POST", _sessao_path() + "/start")
    preferencias.salvar({"WHATSAPP_PROVIDER": "LOCAL" if config.WHATSAPP_PROVIDER == "LOCAL" else "WAHA"})
    from .processamento import invalidar_conexao
    invalidar_conexao()
    progresso("Conexão preparada. Escaneie o QR Code se solicitado; se já estiver conectado, a sessão será reutilizada.")


def pausar_whatsapp():
    _waha("POST", _sessao_path() + "/stop")
    from .processamento import invalidar_conexao
    invalidar_conexao()


def _tags(url):
    try:
        resposta = http().get(url.rstrip("/") + "/api/tags", timeout=(1, 2), allow_redirects=False)
        resposta.raise_for_status()
        modelos = resposta.json()["models"]
        if not isinstance(modelos, list):
            raise ValueError
        return [m["name"] for m in modelos if isinstance(m, dict) and isinstance(m.get("name"), str)]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise ValueError("O Ollama não respondeu. Clique em Iniciar Ollama ou confira o endereço configurado.") from None


def _modelo_instalado(modelo, modelos):
    return modelo in modelos or (":" not in modelo and modelo + ":latest" in modelos)


def status_ollama():
    try:
        modelos = _tags(config.OLLAMA_URL)
        pronto = _modelo_instalado(config.OLLAMA_MODEL, modelos)
        return {"online": True, "modelo_instalado": pronto, "modelos": modelos,
                "modelo": config.OLLAMA_MODEL, "ativo": config.IA_PROVIDER == "OLLAMA",
                "mensagem": "Ollama disponível" if pronto else "Ollama iniciado. Baixe ou selecione um modelo instalado."}
    except ValueError as exc:
        return {"online": False, "modelo_instalado": False, "modelos": [], "modelo": config.OLLAMA_MODEL,
                "ativo": config.IA_PROVIDER == "OLLAMA", "mensagem": str(exc)}


def status_jobs():
    with _lock:
        return copy.deepcopy(_jobs)


def iniciar_tarefa(nome, funcao):
    with _lock:
        if _jobs.get(nome, {}).get("estado") == "EXECUTANDO":
            return dict(_jobs[nome])
        _jobs[nome] = {"estado": "EXECUTANDO", "mensagem": "Preparando…", "percentual": None}
    def progresso(mensagem, percentual=None):
        with _lock:
            _jobs[nome].update(mensagem=mensagem, percentual=percentual)
    def executar():
        try:
            funcao(progresso)
            with _lock:
                _jobs[nome]["estado"] = "CONCLUIDO"
        except Exception as exc:
            with _lock:
                _jobs[nome].update(estado="ERRO", mensagem=str(exc) if isinstance(exc, ValueError) else "Não foi possível iniciar. Confira o serviço e tente novamente.")
    threading.Thread(target=executar, name="Conexao-" + nome, daemon=True).start()
    return {"estado": "EXECUTANDO", "mensagem": "Preparando…", "percentual": None}


def _executable(nome):
    exe = shutil.which(nome)
    if exe:
        return exe
    local = Path(os.getenv("LOCALAPPDATA", str(Path.home())))
    candidatos = {"ollama": [local / "Programs/Ollama/ollama.exe"]}
    return next((str(p) for p in candidatos.get(nome, []) if p.exists()), None)


def _opcoes_processo():
    if os.name != "nt":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": startup}


def iniciar_ollama(progresso):
    url, modelo = config.OLLAMA_URL, config.OLLAMA_MODEL
    try:
        modelos = _tags(url)
    except ValueError:
        if not url_local(url):
            raise ValueError("Ollama remoto indisponível. Este botão inicia somente o Ollama instalado neste computador.") from None
        exe = _executable("ollama")
        if not exe:
            raise ValueError("O Ollama não está instalado. Use Instalar Ollama, conclua a instalação e clique novamente em Iniciar.")
        progresso("Iniciando Ollama em segundo plano…")
        ambiente = dict(os.environ, OLLAMA_HOST=urlsplit(url).netloc)
        logs = Path(config.DATABASE_PATH).resolve().parent / "ollama.log"
        with logs.open("ab") as log:
            subprocess.Popen([exe, "serve"], env=ambiente, stdout=log, stderr=log, **_opcoes_processo())
        limite = time.monotonic() + 60
        while time.monotonic() < limite:
            try:
                modelos = _tags(url)
                break
            except ValueError:
                time.sleep(1)
        else:
            raise ValueError("O Ollama não iniciou. Confira o arquivo ollama.log na pasta de dados.")
    if not _modelo_instalado(modelo, modelos):
        progresso("Ollama iniciado. Clique em Baixar modelo para preparar " + modelo + ", ou escolha um modelo já instalado.")
        return
    _aquecer_ativar(url, modelo, progresso)


def _aquecer_ativar(url, modelo, progresso):
    progresso("Carregando o modelo na memória para atender mais rápido…")
    try:
        resp = http().post(url + "/api/generate", json={"model": modelo, "prompt": "", "stream": False, "keep_alive": config.OLLAMA_KEEP_ALIVE}, timeout=(5, config.OLLAMA_TIMEOUT_SEGUNDOS), allow_redirects=False)
        resp.raise_for_status()
        if resp.json().get("error"):
            raise ValueError
    except (requests.RequestException, ValueError):
        raise ValueError("Não foi possível carregar o modelo. Confira a memória disponível e tente novamente.") from None
    if config.OLLAMA_URL != url or config.OLLAMA_MODEL != modelo:
        raise ValueError("O modelo ou endereço foi alterado durante a preparação. Clique novamente em Iniciar Ollama.")
    preferencias.salvar({"IA_PROVIDER": "OLLAMA"})
    progresso("Ollama pronto e ativado no atendimento.")


def baixar_modelo(progresso):
    url, modelo = config.OLLAMA_URL, config.OLLAMA_MODEL
    _tags(url)
    progresso("Baixando " + modelo + ". O download pode ocupar alguns GB…")
    try:
        concluido = False
        with http().post(url + "/api/pull", json={"model": modelo, "stream": True}, stream=True, timeout=(5, 120), allow_redirects=False) as resp:
            resp.raise_for_status()
            for linha in resp.iter_lines():
                if not linha:
                    continue
                dados = json.loads(linha)
                if dados.get("error"):
                    raise ValueError("O Ollama não conseguiu baixar este modelo. Confira o nome e o espaço livre em disco.")
                total, completo = dados.get("total", 0), dados.get("completed", 0)
                percentual = min(100, int(100 * completo / total)) if total else None
                progresso("Baixando " + modelo + " · " + str(dados.get("status", "Preparando")), percentual)
                if dados.get("status") == "success":
                    concluido = True
        if not concluido or not _modelo_instalado(modelo, _tags(url)):
            raise ValueError("O download não foi concluído. Clique novamente em Baixar modelo para retomar.")
    except requests.RequestException:
        raise ValueError("O download foi interrompido. Confira a internet e clique em Baixar modelo para retomar.") from None
    _aquecer_ativar(url, modelo, progresso)


def iniciar_whatsapp_local(progresso):
    if not config.WEBHOOK_SECRET:
        preferencias.salvar({"WEBHOOK_SECRET": secrets.token_urlsafe(32)})
    whatsapp_local.iniciar(progresso)
    preferencias.salvar({"WHATSAPP_PROVIDER": "LOCAL"})
    conectar_whatsapp(progresso)
