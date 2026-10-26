import random
import json
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from contextlib import nullcontext

from . import config
from .db import get_conn
from .estoque import inteiro, registrar_movimento, invalidar_catalogo, medida, somar, nome_completo


class CotacaoAlterada(ValueError):
    """O cadastro mudou após o resumo; o cliente deve revisar novamente."""


def cotacao(itens, forma_entrega):
    """Calcula o mesmo orçamento usado na gravação, sem reservar saldo."""
    with get_conn() as conn:
        conn.execute('BEGIN')
        total, resolvidos = _resolver_itens(conn, itens)
    return _cotacao(total, resolvidos, forma_entrega)


def _cotacao(total, itens, entrega):
    taxa = Decimal(str(config.TAXA_ENTREGA)) if entrega == 'ENTREGA' else Decimal('0')
    return {'itens':[{k:float(v) if isinstance(v, Decimal) else v for k,v in i.items() if k!='custo'} for i in itens],
            'taxa_entrega':float(taxa), 'total_itens':float(total), 'total_pedido':float(total+taxa)}


def _resolver_itens(conn, itens):
    if not itens:
        raise ValueError("O pedido precisa ter pelo menos um item.")
    entradas = []
    for item in itens:
        if not isinstance(item, dict):
            raise ValueError("Item inválido.")
        produto_id = inteiro(item.get("produto_id"), "Produto", 1)
        entradas.append((produto_id, item.get('quantidade', 1)))
    # Até 400 parâmetros por consulta: funciona também em bancos SQLite antigos.
    # Sem cache de preços ou saldo; a cotação e a gravação usam seu próprio snapshot.
    ids = list(dict.fromkeys(pid for pid, _ in entradas))
    produtos = {}
    for inicio in range(0, len(ids), 400):
        lote = ids[inicio:inicio+400]
        marcadores = ','.join('?' for _ in lote)
        produtos.update((p['id'], p) for p in conn.execute(
            f'SELECT * FROM produtos WHERE id IN ({marcadores})', lote))
    quantidades = {}
    for produto_id, valor in entradas:
        atual=produtos.get(produto_id)
        fracionado=bool(atual and atual['fracionado'])
        quantidade = medida(valor, "Quantidade",fracionado,0.001 if fracionado else 1)
        quantidades[produto_id] = somar(quantidades.get(produto_id, 0),quantidade)
        if quantidades[produto_id] > 999999:
            raise ValueError("Quantidade acima do limite permitido.")
    total_itens = Decimal("0.00")
    itens_resolvidos = []
    for produto_id, quantidade in quantidades.items():
        produto = produtos.get(produto_id)
        if produto is None or produto['ativo'] != 1:
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

    return total_itens, itens_resolvidos


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
    conversa: str | None = None,
    _conn=None,
) -> dict:
    """itens: lista de {'produto_id': int, 'quantidade': int}. Retorna o pedido criado com os itens."""
    if not itens:
        raise ValueError("O pedido precisa ter pelo menos um item.")

    with (get_conn() if _conn is None else nullcontext(_conn)) as conn:
        if _conn is None:
            conn.execute("BEGIN IMMEDIATE")
        carrinho = None
        if conversa is not None:
            carrinho = conn.execute("SELECT *, atualizado_em > datetime('now','-30 minutes') AS valido FROM carrinhos_conversa WHERE telefone=? AND token=?", (telefone, conversa)).fetchone()
            if not carrinho or not carrinho['valido']:
                raise ValueError('O resumo expirou. Monte e revise seu pedido novamente.')
            if carrinho['pedido_id'] is not None:
                return obter_pedido(carrinho['pedido_id'])
            dados = json.loads(carrinho['dados'])
            if not dados.get('cotacao'):
                raise ValueError('Revise o resumo antes de confirmar.')
            if (itens, nome_cliente, forma_pagamento, forma_entrega, cep, endereco) != (dados['itens'], dados['nome'], dados['pagamento'], dados['entrega'], dados.get('cep',''), dados.get('endereco','')):
                raise ValueError('Os dados devem corresponder ao resumo revisado.')
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
        total_itens, itens_resolvidos = _resolver_itens(conn, itens)

        taxa_entrega = Decimal(str(config.TAXA_ENTREGA)) if forma_entrega == "ENTREGA" else Decimal("0")
        total_pedido = total_itens + taxa_entrega
        if carrinho is not None and dados['cotacao'] != _cotacao(total_itens, itens_resolvidos, forma_entrega):
            raise CotacaoAlterada('Os preços ou produtos mudaram. Confira o novo resumo antes de confirmar.')

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
            conn.execute("UPDATE carrinhos_conversa SET pedido_id=?, dados='{}' WHERE telefone=? AND pedido_id IS NULL", (pedido_id, telefone))
        if conversa is not None:
            conn.execute("UPDATE carrinhos_conversa SET pedido_id=?, dados='{}' WHERE telefone=? AND token=?", (pedido_id, telefone, conversa))
            # A mesma conversa não pode concluir de novo um link antigo aberto.
            conn.execute("UPDATE links_pedido SET usado=1, pedido_id=? WHERE telefone=? AND usado=0", (pedido_id, telefone))

    invalidar_catalogo()
    return obter_pedido(pedido_id, _conn=_conn)


def listar_pedidos(limite=200):
    """Lê cabeçalhos e itens em lote no mesmo snapshot, sem abrir N conexões."""
    limite = inteiro(limite, 'Limite', 1)
    if limite > 200:
        raise ValueError('Consulte até 200 pedidos por vez.')
    with get_conn() as conn:
        conn.execute('BEGIN')
        linhas = conn.execute(
            'SELECT p.*, c.nome AS cliente_nome, c.telefone AS cliente_telefone, '
            'c.cep AS cliente_cep, c.endereco AS cliente_endereco '
            'FROM pedidos p JOIN clientes c ON c.id=p.cliente_id '
            'ORDER BY p.id DESC LIMIT ?', (limite,)).fetchall()
        resultado = [dict(p, itens=[]) for p in linhas]
        if not resultado:
            return resultado
        por_id = {p['id']: p for p in resultado}
        marcadores = ','.join('?' for _ in por_id)
        for item in conn.execute(
                'SELECT ip.*, COALESCE(ip.nome_produto, pr.nome) AS produto_nome '
                'FROM itens_pedido ip JOIN produtos pr ON pr.id=ip.produto_id '
                f'WHERE ip.pedido_id IN ({marcadores}) ORDER BY ip.id', tuple(por_id)):
            por_id[item['pedido_id']]['itens'].append(dict(item))
    return resultado


def obter_pedido(pedido_id: int, _conn=None) -> dict | None:
    with (get_conn() if _conn is None else nullcontext(_conn)) as conn:
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


def registrar_mensagem(telefone: str, direcao: str, conteudo: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO mensagens (telefone, direcao, conteudo) VALUES (?, ?, ?)",
            (telefone, direcao, conteudo),
        )


def cancelar_pedido(pedido_id, _conn=None, _estorno_caixa=False):
    with (get_conn() if _conn is None else nullcontext(_conn)) as conn:
        if _conn is None:
            conn.execute("BEGIN IMMEDIATE")
        if not _estorno_caixa and conn.execute("SELECT 1 FROM movimentos_caixa WHERE pedido_id=? AND tipo='VENDA'", (pedido_id,)).fetchone():
            raise ValueError('Pedido recebido no caixa. Confirme a devolução em Caixas dos funcionários para estornar e cancelar.')
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
    return obter_pedido(pedido_id, _conn=_conn)
