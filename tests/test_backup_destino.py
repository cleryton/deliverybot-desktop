"""Falhas de transferência nunca publicam backups corrompidos nem apagam os válidos."""
from pathlib import Path
import sqlite3

import pytest

from src import backups, config, rotinas
from src.db import init_db, get_conn


@pytest.fixture
def copia(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'teste.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    init_db()
    pasta = tmp_path / 'externo'
    pasta.mkdir()
    anterior = pasta / 'automatico-DeliveryBot-anterior.dbot'
    anterior.write_bytes(b'copia anterior preservada')
    origem = tmp_path / 'DeliveryBot-nova.dbot'
    senha = 'senha-apenas-para-teste'
    conn = sqlite3.connect(':memory:')
    try:
        conn.execute('CREATE TABLE produtos(id INTEGER PRIMARY KEY)')
        origem.write_bytes(backups.cifrar(conn.serialize(), senha))
    finally:
        conn.close()
    monkeypatch.setattr(backups, 'criar', lambda _: str(origem))
    monkeypatch.setattr(rotinas.seguranca, 'revelar_segredo', lambda _: senha)
    monkeypatch.setattr(rotinas, '_cfg', lambda: {
        'backup_ativo': True, 'ultima_copia': None, 'horas': 24,
        'senha': 'protegida', 'pasta': str(pasta), 'quantidade': 1, 'limpar': False,
    })
    return origem, pasta, anterior


@pytest.mark.parametrize('falha', ['corrupcao', 'disco_cheio', 'sincronizacao'])
def test_falha_no_destino_preserva_origem_retencao_e_marcador(copia, monkeypatch, falha):
    origem, pasta, anterior = copia
    if falha == 'sincronizacao':
        def falhar(_):
            raise OSError('falha ficticia de disco')
        monkeypatch.setattr(rotinas.os, 'fsync', falhar)
    else:
        def transferir(_, destino):
            Path(destino).write_bytes(b'arquivo incompleto')
            if falha == 'disco_cheio':
                raise OSError('disco cheio ficticio')
        monkeypatch.setattr(rotinas.shutil, 'copyfile', transferir)
    assert rotinas.executar(True) is False
    assert origem.exists()
    assert anterior.read_bytes() == b'copia anterior preservada'
    assert list(pasta.iterdir()) == [anterior]
    with get_conn() as conn:
        linha = conn.execute('SELECT ultima_copia, erro FROM rotinas WHERE id=1').fetchone()
    assert linha['ultima_copia'] is None
    assert linha['erro']


def test_publica_apenas_copia_verificada_e_so_entao_aplica_retencao(copia, monkeypatch):
    origem, pasta, anterior = copia
    verificar = rotinas.verificar_arquivo
    verificadas = []
    def conferir(arquivo, senha):
        verificadas.append(Path(arquivo))
        verificar(arquivo, senha)
        assert origem.exists() and anterior.exists()
    monkeypatch.setattr(rotinas, 'verificar_arquivo', conferir)
    assert rotinas.executar(True) is True
    assert verificadas == [origem, (pasta / ('automatico-' + origem.name)).with_suffix('.novo')]
    assert not origem.exists()
    assert not anterior.exists()
    arquivos = list(pasta.iterdir())
    assert len(arquivos) == 1 and arquivos[0].suffix == '.dbot'
    backups.verificar_arquivo(arquivos[0], 'senha-apenas-para-teste')
    with get_conn() as conn:
        linha = conn.execute('SELECT ultima_copia, erro FROM rotinas WHERE id=1').fetchone()
    assert linha['ultima_copia'] and linha['erro'] is None
