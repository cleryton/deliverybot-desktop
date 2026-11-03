"""Backups portáveis autenticados: AES-256-GCM com chave derivada por scrypt."""
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from . import config
from .db import get_conn

MAGIC = b"DELIVERYBOT-BACKUP-1\n"
LIMITE = 256 * 1024 * 1024
LOCAL_MAGIC = b"DELIVERYBOT-BACKUP-WINDOWS-1\n"


def _chaves_banco(conn, tabela):
    colunas = conn.execute('SELECT name,type,pk FROM pragma_table_info(?) ORDER BY pk', (tabela,)).fetchall()
    primaria = tuple((r['name'], r['type'].upper()) for r in colunas if r['pk'])
    indices = conn.execute('SELECT name,"unique",origin,partial FROM pragma_index_list(?)', (tabela,)).fetchall()
    unica = set()
    for indice in indices:
        if not indice['unique']:
            continue
        campos = tuple(r['name'] for r in conn.execute('SELECT name FROM pragma_index_info(?) ORDER BY seqno',
                                                      (indice['name'],)))
        condicao = None
        if indice['partial']:
            sql = conn.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (indice['name'],)).fetchone()[0]
            normal = re.sub(r'\s+', ' ', sql).casefold()
            condicao = re.sub(r'\s+', '', normal.partition(' where ')[2])
        unica.add((campos, condicao))
    referencias = {tuple(r) for r in conn.execute(
        'SELECT "table","from","to",on_update,on_delete FROM pragma_foreign_key_list(?)', (tabela,))}
    # INTEGER PRIMARY KEY sem índice próprio é o identificador automático usado
    # pelo app. INT PRIMARY KEY ou WITHOUT ROWID não têm o mesmo comportamento.
    automatica = len(primaria) == 1 and primaria[0][1] == 'INTEGER' and not any(r['origin'] == 'pk' for r in indices)
    return primaria, unica, referencias, automatica


def validar_banco(caminho):
    """Prova a compatibilidade e as migrações numa cópia, sem trocar o banco ativo."""
    from .db import _MIGRACOES_COLUNAS, _aplicar_migracoes, _colunas_existentes
    arquivo = Path(caminho)
    if not arquivo.is_file() or not 0 < arquivo.stat().st_size <= LIMITE:
        raise ValueError('Escolha um banco de dados do DeliveryBot de até 256 MB.')
    schema = (Path(__file__).resolve().parents[1]/'sql/schema.sql').read_text(encoding='utf-8')
    prazo = time.monotonic() + 30

    def esgotado():
        return time.monotonic() >= prazo

    def progresso(*_):
        if esgotado():
            raise ValueError('Não foi possível validar o formato do backup no prazo permitido.')

    try:
        with closing(sqlite3.connect(arquivo.resolve().as_uri()+'?mode=ro', uri=True)) as origem, \
                closing(sqlite3.connect(':memory:')) as modelo, closing(sqlite3.connect(':memory:')) as copia:
            for conn in (origem, modelo, copia):
                conn.row_factory = sqlite3.Row
                conn.execute('PRAGMA trusted_schema=OFF')
                conn.set_progress_handler(esgotado, 1000)
            # Somente o schema distribuído com o app é executado. O backup não
            # pode fornecer vistas, gatilhos ou tabelas virtuais para a migração.
            objetos = origem.execute('SELECT type,sql FROM sqlite_master').fetchall()
            if any(r['type'] in {'trigger', 'view'} or
                   (r['sql'] or '').lstrip().upper().startswith('CREATE VIRTUAL TABLE') for r in objetos):
                raise ValueError('O arquivo possui estruturas que não fazem parte do backup do DeliveryBot.')
            if origem.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('O arquivo de backup está corrompido.')
            modelo.executescript(schema)
            _aplicar_migracoes(modelo)
            tabelas = {r[0] for r in origem.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'produtos', 'pedidos', 'clientes', 'itens_pedido', 'fila_preparo', 'links_pedido'} <= tabelas:
                raise ValueError('O backup não tem o formato esperado.')
            esperadas = {r[0]: _colunas_existentes(modelo, r[0]) for r in modelo.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            for tabela in tabelas & esperadas.keys():
                migraveis = {nome for nome, _ in _MIGRACOES_COLUNAS.get(tabela, ())}
                if not esperadas[tabela] - migraveis <= _colunas_existentes(origem, tabela):
                    raise ValueError('O backup não tem o formato esperado para restaurar com segurança.')
            origem.backup(copia, pages=256, progress=progresso)
            # Limita valores criados por expressões do schema do arquivo, sem
            # reduzir o máximo de 16 MB por nota do snapshot Obsidian.
            copia.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 17 * 1024 * 1024)
            copia.executescript(schema)
            _aplicar_migracoes(copia)
            if any(not colunas <= _colunas_existentes(copia, tabela) for tabela, colunas in esperadas.items()):
                raise ValueError('O backup não tem o formato esperado após a migração.')
            for tabela in esperadas:
                pk, unicas, referencias, automatica = _chaves_banco(modelo, tabela)
                pk_copia, unicas_copia, referencias_copia, automatica_copia = _chaves_banco(copia, tabela)
                if (pk_copia != pk or not unicas <= unicas_copia or not referencias <= referencias_copia
                        or automatica != automatica_copia):
                    raise ValueError('O backup não tem as chaves do formato esperado para restaurar com segurança.')
            if copia.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or copia.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('O backup tem dados incompatíveis com o formato esperado.')
    except (sqlite3.Error, TypeError, AttributeError, OverflowError) as exc:
        raise ValueError('O backup tem formato incompatível ou não permite a migração segura.') from exc


def _chave(senha, salt):
    if not isinstance(senha, str) or not 12 <= len(senha) <= 256:
        raise ValueError("Use uma senha de backup com 12 a 256 caracteres.")
    return Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(senha.encode("utf-8"))


def cifrar(dados, senha):
    if len(dados) > LIMITE:
        raise ValueError("O backup ultrapassa o limite de 256 MB.")
    salt, nonce = os.urandom(16), os.urandom(12)
    header = MAGIC + salt + nonce
    return header + AESGCM(_chave(senha, salt)).encrypt(nonce, dados, header)


def decifrar(dados, senha):
    if len(dados) > LIMITE + 1024 or not dados.startswith(MAGIC) or len(dados) < len(MAGIC) + 44:
        raise ValueError("Escolha um backup criptografado válido do DeliveryBot (.dbot).")
    pos = len(MAGIC)
    salt, nonce = dados[pos:pos+16], dados[pos+16:pos+28]
    try:
        return AESGCM(_chave(senha, salt)).decrypt(nonce, dados[pos+28:], dados[:pos+28])
    except InvalidTag:
        raise ValueError("Senha incorreta ou backup alterado. Os dados atuais não foram modificados.") from None


def criar(senha):
    # Cópia em memória: nenhum arquivo intermediário desprotegido.
    _chave(senha, b"0" * 16)
    with get_conn() as origem, closing(sqlite3.connect(":memory:")) as copia:
        origem.backup(copia)
        # Credenciais não são portáveis; devem ser informadas de novo após restaurar.
        from .preferencias import SEGREDOS
        copia.execute("PRAGMA secure_delete=ON")
        copia.executemany("DELETE FROM configuracoes WHERE chave=?", [(k,) for k in SEGREDOS])
        # O token do túnel não acompanha a cópia portátil: reativar só após configurar.
        copia.execute("UPDATE configuracoes SET valor='NAO' WHERE chave='TUNEL_AUTOMATICO'")
        # Dispositivos remotos precisam de novo pareamento após restaurar a cópia portátil.
        copia.execute('UPDATE terminal_config SET ativo=0,host=\'\' WHERE id=1')
        copia.execute('DELETE FROM terminal_convites_autorizacoes')
        copia.execute('DELETE FROM terminal_autorizacoes')
        copia.execute('DELETE FROM terminal_convites')
        copia.execute('DELETE FROM terminal_dispositivos')
        if copia.execute("SELECT 1 FROM sqlite_master WHERE name='rotinas'").fetchone():
            copia.execute("UPDATE rotinas SET senha='',backup_ativo=0,pasta=''")
        from . import cerebro
        copia.execute("CREATE TABLE IF NOT EXISTS deliverybot_cerebro_snapshot (caminho TEXT PRIMARY KEY, conteudo BLOB NOT NULL)")
        copia.execute("DELETE FROM deliverybot_cerebro_snapshot")
        copia.executemany(
            "INSERT INTO deliverybot_cerebro_snapshot(caminho,conteudo) VALUES(?,?)",
            list(cerebro.snapshot().items()),
        )
        dados = _serializar(copia)
    pasta = Path(config.DATABASE_PATH).resolve().parent / "backups"
    pasta.mkdir(exist_ok=True)
    destino = pasta / ("DeliveryBot-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".dbot")
    with destino.open("xb") as arquivo:
        arquivo.write(cifrar(dados, senha))
    return str(destino)


def criar_local(banco, destino):
    """Cópia automática de recuperação, protegida pela mesma conta Windows."""
    from .seguranca import _dpapi
    if os.name != "nt":
        raise ValueError("A recuperação automática protegida requer Windows.")
    with closing(sqlite3.connect(banco)) as origem, closing(sqlite3.connect(":memory:")) as copia:
        origem.backup(copia)
        dados = _serializar(copia)
    Path(destino).write_bytes(LOCAL_MAGIC + _dpapi(dados, False))


def verificar_arquivo(arquivo, senha):
    dados=abrir_arquivo(arquivo,senha)
    with closing(sqlite3.connect(':memory:')) as c:
        c.deserialize(dados)
        if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('O backup não passou na verificação de recuperação.')


def _serializar(conn):
    dados = bytearray(conn.serialize())
    # sqlite3_deserialize exige o cabeçalho de rollback journal (SQLite, bytes 18/19).
    # A API backup já incorporou todas as páginas do WAL na cópia consistente.
    dados[18:20] = b"\x01\x01"
    return bytes(dados)


def abrir_arquivo(caminho, senha):
    from .seguranca import _dpapi
    arquivo = Path(caminho)
    if arquivo.stat().st_size > LIMITE + 1024:
        raise ValueError("Backup maior que o limite permitido.")
    dados = arquivo.read_bytes()
    if dados.startswith(LOCAL_MAGIC):
        if os.name != "nt":
            raise ValueError("Abra a cópia de recuperação na conta Windows de origem.")
        return _dpapi(dados[len(LOCAL_MAGIC):], True)
    return decifrar(dados, senha)


def snapshot_no_banco(conn):
    """Lê a cópia Obsidian embutida nos backups recentes; backups antigos continuam válidos."""
    tabela = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='deliverybot_cerebro_snapshot'"
    ).fetchone()
    if not tabela:
        return None
    from .cerebro import _validar_snapshot
    return _validar_snapshot({
        caminho: bytes(conteudo)
        for caminho, conteudo in conn.execute(
            "SELECT caminho,conteudo FROM deliverybot_cerebro_snapshot"
        )
    })
