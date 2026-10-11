from .db import get_conn

# Ícone e cor de destaque por categoria -- usados como "retrato" do produto
# quando ele não tem foto cadastrada (campo `imagem`), e também nos
# distintivos de categoria da página do pedido. Categorias fora dessa lista
# caem no fallback "🍽️" / cor neutra.
ICONE_CATEGORIA = {
    "Lanche": "🍔",
    "Acompanhamento": "🍟",
    "Bebida": "🥤",
    "Sobremesa": "🍨",
}
ICONE_CATEGORIA_PADRAO = "📦"


def listar_produtos_ativos():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.*,f.hash AS foto_hash FROM produtos p LEFT JOIN fotos_produto f ON f.produto_id=p.id "
            "WHERE p.ativo = 1 AND (p.estoque IS NULL OR p.estoque > 0) ORDER BY p.categoria, p.nome"
        ).fetchall()
    from .estoque import nome_completo
    resultado=[dict(r) for r in rows]
    from . import fotos
    for p in resultado:
        p['nome']=nome_completo(p)
        p['foto_url'] = fotos.url(p)
    return resultado


def agrupar_por_categoria(produtos):
    grupos = {}
    for p in produtos:
        grupos.setdefault(p["categoria"], []).append(p)
    return grupos


def buscar_produto(produto_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM produtos "
            "WHERE id = ? AND ativo = 1 AND (estoque IS NULL OR estoque > 0)",
            (produto_id,),
        ).fetchone()
    return dict(row) if row else None


def icone_categoria(categoria: str) -> str:
    return ICONE_CATEGORIA.get(categoria, ICONE_CATEGORIA_PADRAO)


def texto_cardapio() -> str:
    """Monta o texto do cardápio para responder à opção 4 do menu do bot."""
    produtos = listar_produtos_ativos()
    grupos = agrupar_por_categoria(produtos)
    if not produtos:
        return "Nosso catálogo está sem produtos disponíveis no momento. Entre em contato com a loja."
    linhas = ["📋 *Nosso catálogo de produtos:*", ""]
    for categoria, itens in grupos.items():
        linhas.append(f"*{categoria}*")
        for item in itens:
            linhas.append(f"• {item['nome']} — R$ {item['preco']:.2f}")
        linhas.append("")
    return "\n".join(linhas).strip()
