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
    from .publicacao import endereco
    from .conexoes import url_local
    base = endereco()
    if not base or (not config.MODO_TESTE and url_local(base)):
        raise ValueError('A página de pedidos está indisponível. Inicie a página pública no aplicativo.')
    token = secrets.token_urlsafe(32)
    expira_em = (datetime.now(timezone.utc) + timedelta(minutes=config.VALIDADE_LINK_MIN)).strftime(_FORMATO_DATA)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO links_pedido (token, telefone, usado, expira_em) VALUES (?, ?, 0, ?)",
            (token, telefone, expira_em),
        )

    return f"{base}/m/{token}"


def obter_link(token: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM links_pedido WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def atualizar_resposta(resposta, telefone):
    """Uma resposta na fila não pode enviar o domínio de um túnel encerrado."""
    if not resposta.startswith('Faça o seu pedido em '):
        return resposta
    import re
    from .publicacao import endereco
    from .conexoes import url_local
    m = re.search(r'https?://[^\s]+/m/([A-Za-z0-9_-]+)', resposta)
    if not m:
        return resposta
    base = endereco()
    if not base or (not config.MODO_TESTE and url_local(base)):
        raise ValueError('A página pública está desconectada. Aguarde a conexão antes de reenviar o link.')
    ok, _, link = link_valido(m[1])
    if not link or link['telefone'] != telefone:
        raise ValueError('O link da resposta não pertence a este atendimento.')
    novo = base + '/m/' + m[1] if ok else gerar_link_pedido(telefone)
    return resposta[:m.start()] + novo + resposta[m.end():]


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
