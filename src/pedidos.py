import random
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone

from . import config
from .db import get_conn
from .estoque import inteiro, registrar_movimento, invalidar_catalogo, medida, somar, nome_completo


def gerar_numero_pedido() -> str:
    """Gera um número de pedido de 8 dígitos, no estilo '#21535858' dos prints."""
    return "#" + "".join(str(random.randint(0, 9)) for _ in range(8))


def obter_ou_criar_cliente(telefone: str, nome: str, cep: str = "", endereco: str = "") -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM clientes WHERE telefone = ?", (telefone,)).fetchone()
        if row:
            conn.execute(
                "UPDATE clientes SET nome = ?, cep = COALESCE(NULLIF(?, ''), cep), "
                "endereco = COALESCE(NULLIF(?, ''), endereco) WHERE id = ?",
                (nome, cep, endereco, row["id"]),
            )
            return row["id"]

        cur = conn.execute(
            "INSERT INTO clientes (nome, telefone, cep, endereco) VALUES (?, ?, ?, ?)",
            (nome, telefone, cep, endereco),
        )
        return cur.lastrowid


def criar_pedido(
    telefone: str,
    nome_cliente: str,
    itens: list[dict],
    forma_pagamento: str,
    forma_entrega: str = "RETIRADA BALCAO",
    cep: str = "",
    endereco: str = "",
    token: str | None = None,
) -> dict:
    """itens: lista de {'produto_id': int, 'quantidade': int}. Retorna o pedido criado com os itens."""
    if not itens:
        raise ValueError("O pedido precisa ter pelo menos um item.")

    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        if forma_entrega not in {"RETIRADA BALCAO", "ENTREGA"}:
            raise ValueError("Forma de entrega inválida.")
        if forma_pagamento not in [v.strip() for v in config.FORMAS_PAGAMENTO.split(",")]:
            # Mantém as opções antigas para clientes com links já abertos.
            if forma_pagamento not in {"Cartao de credito", "Cartao de debito", "VALE ALIMENTACAO (COOPCERTO CABAL)"}:
                raise ValueError("Forma de pagamento inválida.")
        if token is not None:
            link = conn.execute("SELECT * FROM links_pedido WHERE token=?", (token,)).fetchone()
            agora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            if link is None or link["usado"] or link["expira_em"] <= agora or link["telefone"] != telefone:
                raise ValueError("Este link já foi usado ou expirou. Solicite um novo link ao bot.")
        quantidades = {}
        for item in itens:
            if not isinstance(item, dict):
                raise ValueError("Item inválido.")
            produto_id = inteiro(item.get("produto_id"), "Produto", 1)
            atual=conn.execute('SELECT fracionado FROM produtos WHERE id=?',(produto_id,)).fetchone()
            fracionado=bool(atual and atual['fracionado'])
            quantidade = medida(item.get("quantidade", 1), "Quantidade",fracionado,0.001 if fracionado else 1)
            quantidades[produto_id] = somar(quantidades.get(produto_id, 0),quantidade)
            if quantidades[produto_id] > 999999:
                raise ValueError("Quantidade acima do limite permitido.")
        total_itens = Decimal("0.00")
        itens_resolvidos = []
        for produto_id, quantidade in quantidades.items():
            produto = conn.execute(
                "SELECT * FROM produtos WHERE id = ? AND ativo = 1", (produto_id,)
            ).fetchone()
            if produto is None:
                raise ValueError("Um produto selecionado não está mais disponível. Atualize o catálogo.")
            if produto["estoque"] is not None and quantidade > produto["estoque"]:
                raise ValueError(f"Estoque insuficiente para {produto['nome']}. Disponível: {produto['estoque']} {produto['unidade']}.")
            subtotal = (Decimal(str(produto["preco"])) * Decimal(str(quantidade))).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
            total_itens += subtotal
            itens_resolvidos.append(
                {
                    "produto_id": produto["id"],
                    "nome": nome_completo(dict(produto)),
                    "quantidade": quantidade,
                    "preco_unitario": produto["preco"],
                    "subtotal": subtotal,
                    "custo": produto['custo'],
                }
            )

        if not itens_resolvidos:
            raise ValueError("Nenhum item válido foi encontrado no pedido.")

        taxa_entrega = Decimal(str(config.TAXA_ENTREGA)) if forma_entrega == "ENTREGA" else Decimal("0")
        total_pedido = total_itens + taxa_entrega

        conn.execute(
            "INSERT INTO clientes (nome, telefone, cep, endereco) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(telefone) DO UPDATE SET nome=excluded.nome, "
            "cep=COALESCE(NULLIF(excluded.cep, ''), clientes.cep), "
            "endereco=COALESCE(NULLIF(excluded.endereco, ''), clientes.endereco)",
            (nome_cliente, telefone, cep, endereco),
        )
        cliente_id = conn.execute("SELECT id FROM clientes WHERE telefone=?", (telefone,)).fetchone()["id"]

        numero_pedido = gerar_numero_pedido()
        while conn.execute(
            "SELECT 1 FROM pedidos WHERE numero_pedido = ?", (numero_pedido,)
        ).fetchone():
            numero_pedido = gerar_numero_pedido()

        cur = conn.execute(
            "INSERT INTO pedidos (numero_pedido, cliente_id, forma_entrega, tempo_estimado_min, "
            "forma_pagamento, total_itens, total_pedido, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'RECEBIDO')",
            (
                numero_pedido,
                cliente_id,
                forma_entrega,
                config.TEMPO_PREPARO_MIN,
                forma_pagamento,
                float(round(total_itens, 2)),
                float(round(total_pedido, 2)),
            ),
        )
        pedido_id = cur.lastrowid

        for item in itens_resolvidos:
            conn.execute(
                "INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario, nome_produto,custo_unitario) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (pedido_id, item["produto_id"], item["quantidade"], item["preco_unitario"], item["nome"],item['custo']),
            )
            produto = conn.execute("SELECT estoque FROM produtos WHERE id=?", (item["produto_id"],)).fetchone()
            if produto["estoque"] is not None:
                saldo = somar(produto["estoque"],-item["quantidade"])
                conn.execute("UPDATE produtos SET estoque=? WHERE id=?", (saldo, item["produto_id"]))
                registrar_movimento(conn, item["produto_id"], "VENDA", -item["quantidade"], saldo, numero_pedido, pedido_id)

        posicao = conn.execute(
            "SELECT COALESCE(MAX(posicao), 0) + 1 AS pos FROM fila_preparo"
        ).fetchone()["pos"]
        conn.execute(
            "INSERT INTO fila_preparo (pedido_id, posicao, status) VALUES (?, ?, 'AGUARDANDO')",
            (pedido_id, posicao),
        )
        if token is not None:
            conn.execute("UPDATE links_pedido SET usado=1, pedido_id=? WHERE token=?", (pedido_id, token))

    invalidar_catalogo()
    return obter_pedido(pedido_id)


def obter_pedido(pedido_id: int) -> dict | None:
    with get_conn() as conn:
        pedido = conn.execute(
            "SELECT p.*, c.nome AS cliente_nome, c.telefone AS cliente_telefone, "
            "c.cep AS cliente_cep, c.endereco AS cliente_endereco "
            "FROM pedidos p JOIN clientes c ON c.id = p.cliente_id WHERE p.id = ?",
            (pedido_id,),
        ).fetchone()
        if pedido is None:
            return None
        itens = conn.execute(
            "SELECT ip.*, COALESCE(ip.nome_produto, pr.nome) AS produto_nome FROM itens_pedido ip "
            "JOIN produtos pr ON pr.id = ip.produto_id WHERE ip.pedido_id = ?",
            (pedido_id,),
        ).fetchall()

    pedido = dict(pedido)
    pedido["itens"] = [dict(i) for i in itens]
    return pedido


def obter_pedido_por_numero(numero_pedido: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM pedidos WHERE numero_pedido = ?", (numero_pedido,)
        ).fetchone()
    return obter_pedido(row["id"]) if row else None


def registrar_mensagem(telefone: str, direcao: str, conteudo: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO mensagens (telefone, direcao, conteudo) VALUES (?, ?, ?)",
            (telefone, direcao, conteudo),
        )


def cancelar_pedido(pedido_id):
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        pedido = conn.execute("SELECT status FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
        if pedido is None or pedido["status"] in {"CANCELADO", "ENTREGUE", "RETIRADO"}:
            raise ValueError("Este pedido não pode ser cancelado.")
        # Estorna as vendas registradas, mesmo se o controle foi desligado depois.
        for movimento in conn.execute("SELECT * FROM movimentos_estoque WHERE pedido_id=? AND tipo='VENDA'", (pedido_id,)).fetchall():
            produto = conn.execute("SELECT estoque FROM produtos WHERE id=?", (movimento["produto_id"],)).fetchone()
            quantidade = -movimento["quantidade"]
            saldo = somar(produto["estoque"],quantidade) if produto["estoque"] is not None else None
            conn.execute("UPDATE produtos SET estoque=? WHERE id=?", (saldo, movimento["produto_id"]))
            registrar_movimento(conn, movimento["produto_id"], "ESTORNO", quantidade, saldo, "Pedido cancelado", pedido_id)
        conn.execute("UPDATE pedidos SET status='CANCELADO', atualizado_em=datetime('now') WHERE id=?", (pedido_id,))
        conn.execute("UPDATE fila_preparo SET status='CANCELADO', atualizado_em=datetime('now') WHERE pedido_id=?", (pedido_id,))
    invalidar_catalogo()
    return obter_pedido(pedido_id)
