import logging
from .db import get_conn
from . import pedidos as pedidos_repo
from . import recibo
from . import whatsapp

_TRANSICOES = {
    "AGUARDANDO": "EM_PREPARO",
    "EM_PREPARO": "PRONTO",
    "PRONTO": "RETIRADO",
}

_STATUS_FILA_PARA_PEDIDO = {
    "AGUARDANDO": "CONFIRMADO",
    "EM_PREPARO": "EM_PREPARO",
    "PRONTO": "PRONTO",
    "RETIRADO": "RETIRADO",
}


def listar_fila():
    """Lista os pedidos ainda em aberto, já com os itens de cada um (a
    cozinha precisa ver O QUE foi pedido, não só o total em reais)."""
    with get_conn() as conn:
        pedidos_rows = conn.execute(
            "SELECT f.pedido_id, f.status, f.posicao, f.atualizado_em AS status_atualizado_em, "
            "p.numero_pedido, p.total_pedido, p.forma_entrega, p.forma_pagamento, "
            "p.criado_em AS pedido_criado_em, "
            "c.nome AS cliente_nome, c.telefone AS cliente_telefone "
            "FROM fila_preparo f "
            "JOIN pedidos p ON p.id = f.pedido_id "
            "JOIN clientes c ON c.id = p.cliente_id "
            "WHERE f.status NOT IN ('RETIRADO', 'ENTREGUE', 'CANCELADO') "
            "ORDER BY f.posicao"
        ).fetchall()

        fila = [dict(r) for r in pedidos_rows]
        if not fila:
            return fila

        ids = [p["pedido_id"] for p in fila]
        marcadores = ",".join("?" * len(ids))
        itens_rows = conn.execute(
            f"SELECT i.pedido_id, i.quantidade, i.observacao, COALESCE(i.nome_produto, pr.nome) AS produto_nome "
            f"FROM itens_pedido i "
            f"JOIN produtos pr ON pr.id = i.produto_id "
            f"WHERE i.pedido_id IN ({marcadores}) "
            f"ORDER BY i.id",
            ids,
        ).fetchall()

    itens_por_pedido: dict[int, list[dict]] = {}
    for item in itens_rows:
        itens_por_pedido.setdefault(item["pedido_id"], []).append(dict(item))

    for pedido in fila:
        pedido["itens"] = itens_por_pedido.get(pedido["pedido_id"], [])

    return fila


def avancar_status(pedido_id: int) -> dict:
    """Avança o pedido para o próximo status da fila e notifica o cliente no WhatsApp."""
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        fila = conn.execute(
            "SELECT * FROM fila_preparo WHERE pedido_id = ?", (pedido_id,)
        ).fetchone()
        if fila is None:
            raise ValueError("Pedido não encontrado na fila de preparo.")

        proximo = _TRANSICOES.get(fila["status"])
        if proximo is None:
            raise ValueError(f"Pedido já está no status final ({fila['status']}).")

        entrega = conn.execute("SELECT forma_entrega FROM pedidos WHERE id=?", (pedido_id,)).fetchone()["forma_entrega"]
        status_pedido = "ENTREGUE" if proximo == "RETIRADO" and entrega == "ENTREGA" else _STATUS_FILA_PARA_PEDIDO[proximo]
        conn.execute(
            "UPDATE fila_preparo SET status = ?, atualizado_em = datetime('now') WHERE pedido_id = ?",
            (proximo, pedido_id),
        )
        conn.execute(
            "UPDATE pedidos SET status = ?, atualizado_em = datetime('now') WHERE id = ?",
            (status_pedido, pedido_id),
        )

    pedido = pedidos_repo.obter_pedido(pedido_id)
    if pedido['origem'] == 'Balcão manual':
        return pedido
    mensagem = recibo.montar_mensagem_status(pedido, status_pedido)
    try:
        whatsapp.enviar_mensagem(pedido["cliente_telefone"], mensagem)
        pedidos_repo.registrar_mensagem(pedido["cliente_telefone"], "SAIDA", mensagem)
    except Exception:
        logging.getLogger(__name__).exception("Pedido atualizado, mas a notificação falhou")
        pedido["aviso"] = "Pedido atualizado. Não foi possível notificar o cliente pelo WhatsApp."
    return pedido
