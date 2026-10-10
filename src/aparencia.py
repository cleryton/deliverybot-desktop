"""Preferência visual da instalação, independente dos dados comerciais."""
from .db import get_conn

TEMAS = frozenset({'sistema', 'claro', 'escuro'})


def tema():
    with get_conn() as conn:
        linha = conn.execute("SELECT valor FROM configuracoes WHERE chave='APARENCIA_TEMA'").fetchone()
    valor = linha['valor'] if linha else 'sistema'
    return valor if valor in TEMAS else 'sistema'


def salvar(valor):
    if not isinstance(valor, str) or valor not in TEMAS:
        raise ValueError('Escolha Claro, Escuro ou Seguir o Windows.')
    with get_conn() as conn:
        conn.execute("INSERT INTO configuracoes (chave,valor) VALUES ('APARENCIA_TEMA',?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (valor,))
    return valor
