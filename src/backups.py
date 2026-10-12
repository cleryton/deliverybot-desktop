"""Backups portáveis autenticados: AES-256-GCM com chave derivada por scrypt."""
import os
import sqlite3
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
