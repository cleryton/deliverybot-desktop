"""Gera e valida o link único de pedido.

Cada link (`/m/<token>`) enviado ao cliente serve para UM único pedido:
- ao ser gerado, fica associado ao telefone do cliente e com um prazo de validade;
- assim que o pedido é concluído com sucesso, o token é marcado como usado;
- qualquer acesso posterior ao mesmo link (reenvio, F5, print antigo, etc.)
  cai numa página de "link inválido/expirado" em vez de abrir outro pedido.
"""
import secrets
from datetime import datetime, timedelta, timezone

from . import config
from .db import get_conn

_FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


def gerar_link_pedido(telefone: str) -> str:
    token = secrets.token_urlsafe(32)
    expira_em = (datetime.now(timezone.utc) + timedelta(minutes=config.VALIDADE_LINK_MIN)).strftime(_FORMATO_DATA)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO links_pedido (token, telefone, usado, expira_em) VALUES (?, ?, 0, ?)",
            (token, telefone, expira_em),
        )

    return f"{config.BASE_URL}/m/{token}"


def obter_link(token: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM links_pedido WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def link_valido(token: str) -> tuple[bool, str, dict | None]:
    link = obter_link(token)
    if link is None:
        return False, "Este link de pedido não existe.", None
    if link["usado"]:
        return False, "Este link já foi usado para um pedido e não pode ser reutilizado.", link
    if datetime.now(timezone.utc) >= datetime.strptime(link["expira_em"], _FORMATO_DATA).replace(tzinfo=timezone.utc):
        return False, "Este link de pedido expirou. Volte ao WhatsApp e digite 2 para gerar um novo.", link
    return True, "ok", link


def marcar_link_usado(token: str, pedido_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE links_pedido SET usado = 1, pedido_id = ? WHERE token = ?",
            (pedido_id, token),
        )
