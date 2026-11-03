"""Backups incompatíveis nunca substituem os dados atuais da loja."""
from contextlib import closing
from pathlib import Path
import sqlite3

import pytest

from desktop import preparar_dados, validar_backup
from src import config, db


def backup_incompativel(caminho):
    with closing(sqlite3.connect(caminho)) as conn:
        conn.executescript('''
            CREATE TABLE produtos(id INTEGER PRIMARY KEY,nome TEXT,preco REAL,ativo INTEGER,categoria TEXT);
            CREATE TABLE pedidos(id INTEGER PRIMARY KEY,cliente_id INTEGER,numero_pedido TEXT,status TEXT);
            CREATE TABLE clientes(id INTEGER PRIMARY KEY);
            CREATE TABLE itens_pedido(id INTEGER PRIMARY KEY);
            CREATE TABLE fila_preparo(id INTEGER PRIMARY KEY);
            CREATE TABLE links_pedido(id INTEGER PRIMARY KEY);
        ''')


@pytest.fixture
def atual(tmp_path, monkeypatch):
    caminho = tmp_path/'deliverybot.db'
    monkeypatch.setattr(config, 'DATABASE_PATH', str(caminho))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    db.init_db(seed_cardapio=False)
    with db.get_conn() as conn:
        conn.execute("INSERT INTO produtos(nome,categoria,preco) VALUES('Produto fictício','Teste',12)")
    return caminho


def test_schema_minimo_incompativel_e_recusado_antes_da_restauracao(tmp_path):
    caminho = tmp_path/'incompativel.db'
    backup_incompativel(caminho)
    with pytest.raises(ValueError, match='formato|incompatível'):
        validar_backup(caminho)


def test_pendente_incompativel_preserva_banco_e_arquivo_pendente(atual, monkeypatch):
    from src import seguranca
    pendente = atual.with_name('restaurar.db')
    backup_incompativel(pendente)
    banco_antes, pendente_antes = atual.read_bytes(), pendente.read_bytes()
    monkeypatch.setattr(seguranca, 'proteger_pasta', lambda _: None)
    with pytest.raises(ValueError, match='formato|incompatível'):
        preparar_dados(atual.parent)
    assert atual.read_bytes() == banco_antes and pendente.read_bytes() == pendente_antes
    assert not (atual.parent/'backups').exists()


def test_schema_atual_validado_sem_modificar_arquivo_ou_configuracao(atual):
    antes, banco_configurado = atual.read_bytes(), config.DATABASE_PATH
    assert validar_backup(atual) is None
    assert atual.read_bytes() == antes and config.DATABASE_PATH == banco_configurado


def test_schema_legado_com_migracoes_pendentes_continua_valido(tmp_path, monkeypatch):
    caminho = tmp_path/'legado.db'
    schema = (Path(__file__).resolve().parents[1]/'sql/schema.sql').read_text(encoding='utf-8')
    with closing(sqlite3.connect(caminho)) as conn:
        conn.executescript(schema)
        for tabela, colunas in db._MIGRACOES_COLUNAS.items():
            existentes = {r[1] for r in conn.execute(f'PRAGMA table_info({tabela})')}
            for coluna, _ in colunas:
                if coluna in existentes:
                    conn.execute(f'ALTER TABLE {tabela} DROP COLUMN {coluna}')
        conn.commit()
    antes, banco_configurado = caminho.read_bytes(), config.DATABASE_PATH
    assert validar_backup(caminho) is None
    assert caminho.read_bytes() == antes and config.DATABASE_PATH == banco_configurado
    monkeypatch.setattr(config, 'DATABASE_PATH', str(caminho))
    assert db.init_db(seed_cardapio=False)


def test_indices_incompativeis_que_impedem_migracao_sao_recusados(atual):
    with closing(sqlite3.connect(atual)) as conn:
        conn.execute('DROP INDEX idx_produtos_sku')
        conn.execute("INSERT INTO produtos(nome,categoria,preco,sku) VALUES('A','Teste',1,'DUPLICADO')")
        conn.execute("INSERT INTO produtos(nome,categoria,preco,sku) VALUES('B','Teste',2,'DUPLICADO')")
        conn.commit()
    antes = atual.read_bytes()
    with pytest.raises(ValueError, match='formato|incompatível'):
        validar_backup(atual)
    assert atual.read_bytes() == antes


@pytest.mark.parametrize('defeito', ['telefone_sem_unique', 'mensagem_sem_pk'])
def test_colunas_corretas_sem_chaves_essenciais_sao_recusadas(tmp_path, defeito):
    schema = (Path(__file__).resolve().parents[1]/'sql/schema.sql').read_text(encoding='utf-8')
    if defeito == 'telefone_sem_unique':
        assert 'telefone      TEXT NOT NULL UNIQUE,' in schema
        schema = schema.replace('telefone      TEXT NOT NULL UNIQUE,', 'telefone      TEXT NOT NULL,', 1)
    else:
        anterior = 'CREATE TABLE IF NOT EXISTS mensagens (\n    id            INTEGER PRIMARY KEY AUTOINCREMENT,'
        assert anterior in schema
        schema = schema.replace(anterior, 'CREATE TABLE IF NOT EXISTS mensagens (\n    id            INTEGER,', 1)
    caminho = tmp_path/'sem-chave.db'
    with closing(sqlite3.connect(caminho)) as conn:
        conn.executescript(schema)
    with pytest.raises(ValueError, match='formato|incompatível'):
        validar_backup(caminho)


def test_indice_com_nome_correto_mas_sem_unicidade_e_recusado(atual):
    with closing(sqlite3.connect(atual)) as conn:
        conn.executescript('DROP INDEX idx_produtos_sku; CREATE INDEX idx_produtos_sku ON produtos(nome);')
    with pytest.raises(ValueError, match='formato|incompatível'):
        validar_backup(atual)


def test_pedido_com_referencia_a_cliente_ausente_e_recusado(atual):
    with closing(sqlite3.connect(atual)) as conn:
        conn.execute("INSERT INTO pedidos(numero_pedido,cliente_id,forma_entrega,tempo_estimado_min,"
                     "forma_pagamento,total_itens,total_pedido) VALUES('#FICTICIO',999,'RETIRADA BALCAO',20,'Pix',12,12)")
        conn.commit()
    with pytest.raises(ValueError, match='formato|incompatíve'):
        validar_backup(atual)


@pytest.mark.parametrize('defeito', ['pk_sem_identificador_automatico', 'referencia_ausente'])
def test_metadados_incompativeis_com_as_operacoes_do_app_sao_recusados(tmp_path, defeito):
    schema = (Path(__file__).resolve().parents[1]/'sql/schema.sql').read_text(encoding='utf-8')
    if defeito == 'pk_sem_identificador_automatico':
        anterior = 'CREATE TABLE IF NOT EXISTS mensagens (\n    id            INTEGER PRIMARY KEY AUTOINCREMENT,'
        schema = schema.replace(anterior, 'CREATE TABLE IF NOT EXISTS mensagens (\n    id            INTEGER PRIMARY KEY DESC,', 1)
    else:
        schema = schema.replace('INTEGER NOT NULL REFERENCES clientes(id)', 'INTEGER NOT NULL', 1)
    caminho = tmp_path/'metadados.db'
    with closing(sqlite3.connect(caminho)) as conn:
        conn.executescript(schema)
    with pytest.raises(ValueError, match='formato|incompatível'):
        validar_backup(caminho)


def test_indice_parcial_com_filtro_alterado_e_recusado(atual):
    with closing(sqlite3.connect(atual)) as conn:
        conn.executescript("DROP INDEX idx_produtos_sku; CREATE UNIQUE INDEX idx_produtos_sku ON produtos(sku) WHERE sku='somente-este';")
    with pytest.raises(ValueError, match='formato|incompatível'):
        validar_backup(atual)
