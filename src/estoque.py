"""Catálogo genérico e movimentações de estoque em transações SQLite."""
import sqlite3
from decimal import Decimal, InvalidOperation

from .db import get_conn


def inteiro(valor, campo, minimo=0):
    try:
        if isinstance(valor, bool) or str(valor).strip() != str(int(valor)):
            raise ValueError
        numero = int(valor)
        if not minimo <= numero <= 999999:
            raise ValueError
        return numero
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{campo}: informe um número inteiro entre {minimo} e 999999.") from None


def dinheiro(valor, campo="Preço"):
    try:
        numero = Decimal(str(valor).replace(",", "."))
        if not numero.is_finite() or not 0 <= numero <= 99999999:
            raise InvalidOperation
        if numero != numero.quantize(Decimal("0.01")):
            raise InvalidOperation
        return float(numero)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{campo}: informe um valor válido com até duas casas decimais.") from None


def texto(valor, campo, limite=160, obrigatorio=False):
    if not isinstance(valor, str):
        raise ValueError(f"{campo}: informe um texto.")
    valor = valor.strip()
    if len(valor) > limite or (obrigatorio and not valor):
        raise ValueError(f"{campo}: preencha um texto de até {limite} caracteres.")
    return valor


def invalidar_catalogo():
    from .ia import invalidar_cache_prompt
    invalidar_cache_prompt()


def listar_produtos():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM produtos ORDER BY ativo DESC, nome")]


def registrar_movimento(conn, produto_id, tipo, quantidade, saldo, motivo, pedido_id=None):
    conn.execute(
        "INSERT INTO movimentos_estoque (produto_id, tipo, quantidade, saldo, motivo, pedido_id) VALUES (?, ?, ?, ?, ?, ?)",
        (produto_id, tipo, quantidade, saldo, motivo, pedido_id),
    )


def salvar_produto(dados, produto_id=None):
    nome = texto(dados.get("nome", ""), "Nome", obrigatorio=True)
    categoria = texto(dados.get("categoria", ""), "Categoria", obrigatorio=True)
    descricao = texto(dados.get("descricao", ""), "Descrição", 2000)
    sku = texto(dados.get("sku", ""), "Código", 80)
    unidade = texto(dados.get("unidade", "un"), "Unidade", 20, True)
    preco = dinheiro(dados.get("preco"))
    for campo in ("ativo", "controlar_estoque"):
        if campo in dados and not isinstance(dados[campo], bool):
            raise ValueError(f"{campo}: informe verdadeiro ou falso.")
    ativo = int(dados.get("ativo", True))
    saldo = inteiro(dados.get("estoque", 0), "Estoque") if dados.get("controlar_estoque", True) else None
    minimo = inteiro(dados.get("estoque_minimo", 0), "Estoque mínimo")
    try:
        with get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            anterior = None
            if produto_id is not None:
                anterior = conn.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
                if anterior is None:
                    raise ValueError("Produto não encontrado.")
                if anterior["estoque"] is not None and saldo is not None:
                    # Edição de descrição/preço não sobrescreve vendas feitas enquanto o formulário estava aberto.
                    saldo = anterior["estoque"]
                conn.execute(
                    "UPDATE produtos SET nome=?, categoria=?, descricao=?, preco=?, sku=?, unidade=?, ativo=?, estoque=?, estoque_minimo=? WHERE id=?",
                    (nome, categoria, descricao, preco, sku, unidade, ativo, saldo, minimo, produto_id),
                )
            else:
                produto_id = conn.execute(
                    "INSERT INTO produtos (nome, categoria, descricao, preco, sku, unidade, ativo, estoque, estoque_minimo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (nome, categoria, descricao, preco, sku, unidade, ativo, saldo, minimo),
                ).lastrowid
            if anterior is None or anterior["estoque"] != saldo:
                registrar_movimento(conn, produto_id, "CADASTRO" if anterior is None else "AJUSTE",
                                     (saldo or 0) - ((anterior["estoque"] or 0) if anterior else 0), saldo,
                                     "Cadastro inicial" if anterior is None else "Saldo alterado no cadastro")
            produto = dict(conn.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone())
    except sqlite3.IntegrityError as exc:
        raise ValueError("Já existe um produto com esse código. Use um código diferente.") from exc
    invalidar_catalogo()
    return produto


def ajustar_estoque(produto_id, quantidade, motivo):
    # Delta, nunca um saldo calculado no navegador: duas entradas simultâneas se somam.
    if isinstance(quantidade, bool):
        raise ValueError("Quantidade inválida.")
    try:
        delta = int(quantidade)
        if str(delta) != str(quantidade).strip() or not delta or abs(delta) > 999999:
            raise ValueError
    except (ValueError, TypeError, OverflowError):
        raise ValueError("Informe uma quantidade inteira diferente de zero, até 999999.") from None
    motivo = texto(motivo, "Motivo", 300, True)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        produto = conn.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone()
        if produto is None or produto["estoque"] is None:
            raise ValueError("Produto não encontrado ou sem controle de estoque.")
        saldo = produto["estoque"] + delta
        if not 0 <= saldo <= 999999:
            raise ValueError("A movimentação deixaria o estoque fora do limite permitido.")
        conn.execute("UPDATE produtos SET estoque=? WHERE id=?", (saldo, produto_id))
        registrar_movimento(conn, produto_id, "ENTRADA" if delta > 0 else "SAIDA", delta, saldo, motivo)
    invalidar_catalogo()


def listar_movimentos():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT m.*, p.nome AS produto_nome, p.unidade FROM movimentos_estoque m JOIN produtos p ON p.id=m.produto_id ORDER BY m.id DESC LIMIT 150")]
