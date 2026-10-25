"""Integração com o WhatsApp. Suporta dois provedores, escolhidos por
WHATSAPP_PROVIDER no .env:

- LOCAL -> componente WhatsApp integrado ao aplicativo Windows.
- WAHA  -> WhatsApp HTTP API externo (github.com/devlikeapro/waha).
           Login por QR Code, sem precisar de conta comercial verificada.
- META  -> WhatsApp Business Cloud API oficial (precisa de app + token da Meta).
- TESTE -> nenhum provedor configurado: mensagens só aparecem no console.
"""
import logging

import requests

from . import config
from .db import get_conn

logger = logging.getLogger(__name__)

# Sessão HTTP reaproveitada entre chamadas (keep-alive) em vez de abrir uma
# conexão TCP nova a cada mensagem enviada -- mais rápido e mais leve tanto
# para o WAHA quanto para a Cloud API da Meta.
_http = requests.Session()


def _numero_limpo(telefone: str) -> str:
    """Remove @c.us, @lid, espaços, '+', etc. Deixa só os dígitos do telefone."""
    return "".join(ch for ch in telefone if ch.isdigit())


# ---------------------------------------------------------------------------
# chatId/sessão do WAHA por telefone.
#
# Guardamos em memória (rápido, caminho comum) E no banco (coluna
# clientes.chat_id / clientes.waha_session), para sobreviver a um restart do
# Flask -- sem isso, mandar uma mensagem "por conta própria" (ex: confirmar
# um pedido feito pelo link /m/<token>) logo após reiniciar o processo cairia
# de volta no chatId reconstruído como "<numero>@c.us", que falha sempre que
# o WhatsApp identifica o contato por LID em vez de número de telefone.
# ---------------------------------------------------------------------------
_chat_id_cache: dict[str, str] = {}
_sessao_cache: dict[str, str] = {}


def _lembrar_chat_id(telefone: str, chat_id: str, sessao: str | None) -> None:
    if not telefone or not chat_id:
        return
    _chat_id_cache[telefone] = chat_id
    if sessao:
        _sessao_cache[telefone] = sessao

    try:
        with get_conn() as conn:
            # Upsert: cria um registro mínimo do cliente se ele ainda não
            # existe (primeira mensagem antes de qualquer pedido), ou só
            # atualiza chat_id/sessão se já existir. O nome placeholder é
            # substituído pelo nome real assim que o cliente finaliza um
            # pedido (pedidos.obter_ou_criar_cliente sobrescreve o nome).
            conn.execute(
                "INSERT INTO clientes (nome, telefone, chat_id, waha_session) "
                "VALUES ('Cliente', ?, ?, ?) "
                "ON CONFLICT(telefone) DO UPDATE SET "
                "chat_id = excluded.chat_id, "
                "waha_session = COALESCE(excluded.waha_session, clientes.waha_session)",
                (telefone, chat_id, sessao),
            )
    except Exception:
        logger.warning("Não foi possível persistir a rota de atendimento")


def _chat_id_conhecido(telefone: str) -> str | None:
    if telefone in _chat_id_cache:
        return _chat_id_cache[telefone]

    with get_conn() as conn:
        row = conn.execute("SELECT chat_id FROM clientes WHERE telefone = ?", (telefone,)).fetchone()
    if row and row["chat_id"]:
        _chat_id_cache[telefone] = row["chat_id"]
        return row["chat_id"]
    return None


def _sessao_conhecida(telefone: str) -> str | None:
    if telefone in _sessao_cache:
        return _sessao_cache[telefone]

    with get_conn() as conn:
        row = conn.execute("SELECT waha_session FROM clientes WHERE telefone = ?", (telefone,)).fetchone()
    if row and row["waha_session"]:
        _sessao_cache[telefone] = row["waha_session"]
        return row["waha_session"]
    return None


def enviar_mensagem(
    telefone: str, texto: str, chat_id: str | None = None, session: str | None = None,
    *, permitir_externos: bool = False
) -> dict:
    from .links import atualizar_resposta
    texto = atualizar_resposta(texto, telefone, permitir_externos=permitir_externos)
    if config.MODO_TESTE:
        logger.info("Modo de teste: envio simulado, conteúdo omitido por privacidade")
        return {"modo_teste": True}

    if config.WHATSAPP_PROVIDER in {"WAHA", "LOCAL"}:
        return _enviar_via_waha(telefone, texto, chat_id, session)

    return _enviar_via_meta(telefone, texto)


def _enviar_via_waha(
    telefone: str, texto: str, chat_id: str | None = None, session: str | None = None
) -> dict:
    chat_id_final = (
        chat_id
        or _chat_id_conhecido(telefone)
        or f"{_numero_limpo(telefone)}@c.us"
    )
    sessao_final = session or _sessao_conhecida(telefone) or config.WAHA_SESSION

    payload = {"session": sessao_final, "chatId": chat_id_final, "text": texto}
    headers = {"Content-Type": "application/json"}
    endereco = config.WAHA_URL
    if config.WHATSAPP_PROVIDER == "LOCAL":
        from .whatsapp_local import credenciais
        endereco, chave = credenciais()
        headers["X-Api-Key"] = chave
    elif config.WAHA_API_KEY:
        headers["X-Api-Key"] = config.WAHA_API_KEY

    from .seguranca import transporte_seguro
    transporte_seguro(endereco)

    resp = _http.post(f"{endereco}/api/sendText", json=payload, headers=headers, timeout=30, allow_redirects=False)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        logger.error("Falha no envio WhatsApp, HTTP %s", resp.status_code)
        raise
    return resp.json() if resp.content else {}


def enviar_pdf(telefone, pdf, legenda, chat_id=None, session=None):
    from .whatsapp_documentos import enviar
    return enviar(telefone, pdf, legenda, chat_id, session)


def _enviar_via_meta(telefone: str, texto: str) -> dict:
    payload = {
        "messaging_product": "whatsapp",
        "to": _numero_limpo(telefone),
        "type": "text",
        "text": {"body": texto, "preview_url": True},
    }
    headers = {
        "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    resp = _http.post(config.WHATSAPP_API_URL, json=payload, headers=headers, timeout=10, allow_redirects=False)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        logger.error("Falha no envio Meta, HTTP %s", resp.status_code)
        raise
    retorno = resp.json()
    try:
        from .meta_custos import registrar_envio
        registrar_envio(retorno)
    except Exception:
        # O envio já foi aceito: falha de contabilidade não pode provocar uma duplicação.
        logger.warning('Envio Meta aceito; registro local de custos indisponível.')
    return retorno


# ---------------------------------------------------------------------------
# Leitura das mensagens recebidas (formato de webhook difere por provedor)
# ---------------------------------------------------------------------------

def extrair_mensagem_recebida_meta(payload: dict) -> dict | None:
    """Extrai {telefone, texto, nome} do payload de webhook da Meta Cloud API."""
    try:
        entry = payload["entry"][0]
        change = entry["changes"][0]["value"]
        mensagens = change.get("messages")
        if not mensagens:
            return None

        msg = mensagens[0]
        telefone = msg["from"]
        nome = change.get("contacts", [{}])[0].get("profile", {}).get("name", "Cliente")

        if msg.get("type") == "text":
            texto = msg["text"]["body"]
        elif msg.get("type") == "interactive":
            interativo = msg["interactive"]
            if interativo.get("type") == "button_reply":
                texto = interativo["button_reply"]["title"]
            elif interativo.get("type") == "list_reply":
                texto = interativo["list_reply"]["title"]
            else:
                texto = ""
        else:
            texto = ""

        return {"telefone": telefone, "texto": texto.strip(), "nome": nome, "id":msg.get('id')}
    except (KeyError, IndexError, TypeError):
        return None


def extrair_mensagem_recebida_waha(payload: dict) -> dict | None:
    """Extrai {telefone, texto, nome, chat_id, session} do payload de webhook
    do WAHA.

    chat_id guarda o identificador ORIGINAL vindo do WAHA (pode ser
    "5542999...@c.us" ou "128325...@lid") e é persistido (memória + banco)
    para ser reutilizado depois em qualquer envio para esse telefone.

    Mensagens de GRUPO (chatId terminando em "@g.us") são ignoradas -- o bot
    só atende conversas privadas.
    """
    try:
        if payload.get("event") != "message":
            return None

        dados = payload["payload"]
        if dados.get("fromMe"):
            return None  # ignora eco de mensagens enviadas pelo próprio bot

        chat_id_original = dados.get("from", "")

        if chat_id_original.endswith("@g.us"):
            return None  # mensagem de grupo -- ignorada

        telefone = _numero_limpo(dados.get("telefone") or chat_id_original)
        texto = (dados.get("body") or "").strip()
        nome = (
            dados.get("_data", {}).get("notifyName")
            or dados.get("notifyName")
            or "Cliente"
        )

        if not telefone:
            return None

        sessao = payload.get("session")
        _lembrar_chat_id(telefone, chat_id_original, sessao)

        return {
            "telefone": telefone,
            "texto": texto,
            "nome": nome,
            "chat_id": chat_id_original,
            "session": sessao,
        }
    except (KeyError, TypeError):
        return None


def extrair_mensagem_recebida(payload: dict) -> dict | None:
    """Detecta automaticamente se o payload veio da Meta ou do WAHA."""
    if "event" in payload and "payload" in payload:
        return extrair_mensagem_recebida_waha(payload)
    return extrair_mensagem_recebida_meta(payload)
