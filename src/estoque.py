"""Catálogo genérico e movimentações de estoque em transações SQLite."""
import sqlite3
from contextlib import nullcontext
from decimal import Decimal, InvalidOperation

from .db import get_conn
from . import fotos, config


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


def medida(valor,campo='Quantidade',fracionado=False,minimo=0):
    if not fracionado:
        return inteiro(valor,campo,minimo)
    try:
        if isinstance(valor,bool):
            raise ValueError
        n=Decimal(str(valor).replace(',','.'))
        if not n.is_finite() or not Decimal(str(minimo))<=n<=999999 or n!=n.quantize(Decimal('0.001')):
            raise ValueError
        return float(n)
    except (ValueError,InvalidOperation):
        raise ValueError(f'{campo}: use até três casas decimais e respeite o limite de quantidade.') from None


def somar(a,b):
    return float((Decimal(str(a))+Decimal(str(b))).quantize(Decimal('0.001')))


def nome_completo(p):
    return p['nome']+(' · '+p['variacao'] if p.get('variacao') else '')


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
        produtos = [dict(r) for r in conn.execute('SELECT p.*,f.hash AS foto_hash FROM produtos p '
                    'LEFT JOIN fotos_produto f ON f.produto_id=p.id ORDER BY p.ativo DESC,p.nome')]
    for produto in produtos:
        produto['foto_url'] = fotos.url(produto)
    return produtos


def registrar_movimento(conn, produto_id, tipo, quantidade, saldo, motivo, pedido_id=None):
    conn.execute(
        "INSERT INTO movimentos_estoque (produto_id, tipo, quantidade, saldo, motivo, pedido_id) VALUES (?, ?, ?, ?, ?, ?)",
        (produto_id, tipo, quantidade, saldo, motivo, pedido_id),
    )


def salvar_produto(dados, produto_id=None, _conn=None, _foto=None):
    remover_foto = dados.get('remover_foto', False)
    if not isinstance(remover_foto, bool) or (remover_foto and _foto is not None):
        raise ValueError('Escolha uma nova foto ou remova a atual.')
    nome = texto(dados.get("nome", ""), "Nome", obrigatorio=True)
    categoria = texto(dados.get("categoria", ""), "Categoria", obrigatorio=True)
    descricao = texto(dados.get("descricao", ""), "Descrição", 2000)
    sku = texto(dados.get("sku", ""), "Código", 80)
    unidade = texto(dados.get("unidade", "un"), "Unidade", 20, True)
    fracionado=dados.get('fracionado',False)
    if type(fracionado) not in (bool,int) or fracionado not in (0,1):
        raise ValueError('Informe se a quantidade é fracionada.')
    fracionado=bool(fracionado)
    familia=texto(dados.get('familia',''),'Família',160)
    variacao=texto(dados.get('variacao',''),'Variação',160)
    custo=dinheiro(dados['custo'],'Custo') if dados.get('custo') not in ('',None) else None
    preco = dinheiro(dados.get("preco"))
    for campo in ("ativo", "controlar_estoque"):
        if campo in dados and not isinstance(dados[campo], bool):
            raise ValueError(f"{campo}: informe verdadeiro ou falso.")
    ativo = int(dados.get("ativo", True))
    try:
        with (get_conn() if _conn is None else nullcontext(_conn)) as conn:
            if _conn is None:
                conn.execute("BEGIN IMMEDIATE")
            anterior = None
            if produto_id is not None:
                anterior = conn.execute("SELECT * FROM produtos WHERE id = ?", (produto_id,)).fetchone()
                if anterior is None:
                    raise ValueError("Produto não encontrado.")
            controle = dados.get('controlar_estoque', anterior['estoque'] is not None if anterior else config.COMERCIO_ESTOQUE_PADRAO == 'SIM')
            saldo = medida(dados.get('estoque', 0), 'Estoque', fracionado) if controle else None
            minimo = medida(dados.get('estoque_minimo', 0), 'Estoque mínimo', fracionado) if controle else 0
            if anterior is not None:
                if anterior["estoque"] is not None and saldo is not None:
                    # Edição de descrição/preço não sobrescreve vendas feitas enquanto o formulário estava aberto.
                    saldo = anterior["estoque"]
                    medida(saldo,'Saldo atual',fracionado)
                conn.execute(
                    "UPDATE produtos SET nome=?, categoria=?, descricao=?, preco=?, sku=?, unidade=?, ativo=?, estoque=?, estoque_minimo=? WHERE id=?",
                    (nome, categoria, descricao, preco, sku, unidade, ativo, saldo, minimo, produto_id),
                )
            else:
                produto_id = conn.execute(
                    "INSERT INTO produtos (nome, categoria, descricao, preco, sku, unidade, ativo, estoque, estoque_minimo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (nome, categoria, descricao, preco, sku, unidade, ativo, saldo, minimo),
                ).lastrowid
            if (anterior is None and saldo is not None) or (anterior is not None and anterior['estoque'] != saldo):
                registrar_movimento(conn, produto_id, "CADASTRO" if anterior is None else "AJUSTE",
                                     (saldo or 0) - ((anterior["estoque"] or 0) if anterior else 0), saldo,
                                     "Cadastro inicial" if anterior is None else "Saldo alterado no cadastro")
            conn.execute('UPDATE produtos SET fracionado=?,familia=?,variacao=?,custo=? WHERE id=?',(fracionado,familia,variacao,custo,produto_id))
            fotos.salvar(conn, produto_id, _foto, remover_foto)
            produto = dict(conn.execute('SELECT p.*,f.hash AS foto_hash FROM produtos p '
                'LEFT JOIN fotos_produto f ON f.produto_id=p.id WHERE p.id=?', (produto_id,)).fetchone())
            produto['foto_url'] = fotos.url(produto)
    except sqlite3.IntegrityError as exc:
        raise ValueError("Já existe um produto com esse código. Use um código diferente.") from exc
    invalidar_catalogo()
    return produto


def ajustar_estoque(produto_id, quantidade, motivo):
    # Delta, nunca um saldo calculado no navegador: duas entradas simultâneas se somam.
    motivo = texto(motivo, "Motivo", 300, True)
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        produto = conn.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone()
        if produto is None or produto["estoque"] is None:
            raise ValueError("Produto não encontrado ou sem controle de estoque.")
        delta=medida(quantidade,'Movimento',bool(produto['fracionado']),-999999)
        if not delta:
            raise ValueError('Informe uma quantidade diferente de zero.')
        saldo = somar(produto["estoque"],delta)
        if not 0 <= saldo <= 999999:
            raise ValueError("A movimentação deixaria o estoque fora do limite permitido.")
        conn.execute("UPDATE produtos SET estoque=? WHERE id=?", (saldo, produto_id))
        registrar_movimento(conn, produto_id, "ENTRADA" if delta > 0 else "SAIDA", delta, saldo, motivo)
    invalidar_catalogo()


def listar_movimentos():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT m.*, p.nome AS produto_nome, p.unidade FROM movimentos_estoque m JOIN produtos p ON p.id=m.produto_id ORDER BY m.id DESC LIMIT 150")]
