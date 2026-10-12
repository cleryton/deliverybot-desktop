import json
import hashlib
import logging
import os
import sqlite3
from contextlib import contextmanager

from . import config

logger = logging.getLogger(__name__)

_SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sql")
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

# Colunas que podem não existir ainda em um banco criado por uma versão
# anterior do projeto. init_db() adiciona qualquer uma que estiver faltando,
# então atualizar o código nunca exige apagar o banco manualmente.
_MIGRACOES_COLUNAS = {
    "mensagens": [("ia_permitida", "INTEGER NOT NULL DEFAULT 1")],
    "clientes": [
        ("chat_id", "TEXT"),
        ("waha_session", "TEXT"),
    ],
    "produtos": [
        ("imagem", "TEXT"),
        ("sku", "TEXT NOT NULL DEFAULT ''"),
        ("unidade", "TEXT NOT NULL DEFAULT 'un'"),
        ("estoque", "INTEGER DEFAULT NULL"),
        ("estoque_minimo", "INTEGER NOT NULL DEFAULT 0"),
        ("fracionado", "INTEGER NOT NULL DEFAULT 0"),
        ("familia", "TEXT NOT NULL DEFAULT ''"),
        ("variacao", "TEXT NOT NULL DEFAULT ''"),
        ("custo", "REAL"),
    ],
    "itens_pedido": [("nome_produto", "TEXT"), ("custo_unitario", "REAL")],
    "tarefas_bot": [("entrada_registrada", "INTEGER NOT NULL DEFAULT 0")],
}

# Guarda quais bancos (por caminho) já passaram pela inicialização neste
# processo -- indexado pelo caminho, e não por um booleano único, porque os
# testes automatizados trocam de DATABASE_PATH a cada teste (cada um com seu
# próprio banco temporário) e cada um precisa ser inicializado de verdade.
_bancos_inicializados: set[str] = set()


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(config.DATABASE_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL permite leituras e escritas simultâneas sem o erro clássico
    # "database is locked" do SQLite -- importante aqui porque o Flask recebe
    # o webhook do WhatsApp e serve a página do pedido ao mesmo tempo.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA secure_delete = ON")
    conn.execute("PRAGMA trusted_schema = OFF")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _colunas_existentes(conn: sqlite3.Connection, tabela: str) -> set[str]:
    linhas = conn.execute(f"PRAGMA table_info({tabela})").fetchall()
    return {linha["name"] for linha in linhas}


def _aplicar_migracoes(conn: sqlite3.Connection) -> None:
    for tabela, colunas in _MIGRACOES_COLUNAS.items():
        existentes = _colunas_existentes(conn, tabela)
        for nome_coluna, tipo_coluna in colunas:
            if nome_coluna not in existentes:
                logger.info("Migrando banco: adicionando coluna %s.%s", tabela, nome_coluna)
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome_coluna} {tipo_coluna}")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_produtos_sku ON produtos(sku) WHERE sku != ''")
    conn.execute("UPDATE itens_pedido SET nome_produto = (SELECT nome FROM produtos WHERE id = produto_id) WHERE nome_produto IS NULL")
    # O identificador de um evento pode conter o telefone. Mantém a deduplicação sem guardá-lo em texto.
    for row in conn.execute("SELECT id, chave FROM tarefas_bot WHERE chave NOT LIKE 'sha256:%'").fetchall():
        conn.execute("UPDATE tarefas_bot SET chave=? WHERE id=?", ("sha256:" + hashlib.sha256(row["chave"].encode()).hexdigest(), row["id"]))


def init_db(seed_cardapio: bool | None = None, forcar: bool = False) -> bool:
    """Cria as tabelas (se não existirem), aplica migrações pendentes e
    popula o cardápio inicial.

    Por padrão só faz esse trabalho uma vez por banco (controlado por
    `forcar`) -- não há necessidade de rodar o schema inteiro e checar o
    cardápio a cada requisição HTTP.
    """
    if seed_cardapio is None:
        seed_cardapio = config.SEED_CATALOGO
    caminho_absoluto = os.path.abspath(config.DATABASE_PATH)
    if caminho_absoluto in _bancos_inicializados and not forcar:
        return True

    schema_path = os.path.join(_SQL_DIR, "schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        schema_sql = f.read()

    with get_conn() as conn:
        conn.executescript(schema_sql)
        _aplicar_migracoes(conn)

        if seed_cardapio:
            existing = conn.execute("SELECT COUNT(*) AS n FROM produtos").fetchone()["n"]
            if existing == 0:
                cardapio_path = os.path.join(_DATA_DIR, "cardapio.json")
                with open(cardapio_path, encoding="utf-8") as f:
                    itens = json.load(f)
                for item in itens:
                    conn.execute(
                        "INSERT INTO produtos (nome, categoria, descricao, preco, ativo, imagem) "
                        "VALUES (?, ?, ?, ?, 1, ?)",
                        (
                            item["nome"],
                            item["categoria"],
                            item.get("descricao", ""),
                            item["preco"],
                            item.get("imagem"),
                        ),
                    )
                logger.info("Cardápio inicial carregado: %d produtos", len(itens))

    _bancos_inicializados.add(caminho_absoluto)
    return True
