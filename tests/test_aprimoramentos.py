"""Regressões das melhorias, exclusivamente com dados e serviços fictícios."""
import pytest
from src import config, preferencias
from src.db import init_db, get_conn


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path/'loja.db'))
    for key in preferencias.CAMPOS | {'MODO_TESTE'}:
        monkeypatch.setattr(config,key,getattr(config,key))
    config.WHATSAPP_PROVIDER='TESTE'
    config.MODO_TESTE=True
    init_db(seed_cardapio=False)


@pytest.fixture
def cliente(monkeypatch):
    from src.app import app
    monkeypatch.setitem(app.config,'DESKTOP_TOKEN','preparacao-ficticia')
    c=app.test_client()
    c.get('/gestao?acesso=preparacao-ficticia')
    with c.session_transaction() as s:
        headers={'X-CSRF-Token':s['csrf']}
    return c,headers


def test_preparacao_endereco_publico_e_expiracao(cliente):
    c,h=cliente
    config.BASE_URL='http://localhost:5000'
    assert c.post('/gestao/api/preparacao/testar',headers=h).status_code==400
    config.BASE_URL='https://loja.example'
    r=c.post('/gestao/api/preparacao/testar',headers=h).json
    caminho=r['url'].replace(config.BASE_URL,'')
    assert c.get(caminho).status_code==200
    assert c.get('/gestao/api/preparacao').json['abertura_recebida']
    config.BASE_URL='https://outra.example'
    assert not c.get('/gestao/api/preparacao').json['abertura_recebida']
    assert c.get(caminho).status_code==410
    assert c.post('/gestao/api/preparacao/testar').status_code==403


def test_fechar_esconde_e_sair_encerra():
    from unittest.mock import Mock
    from src.bandeja import Bandeja
    janela=Mock()
    b=Bandeja(janela)
    b.ativa=True
    assert b.ao_fechar() is False
    janela.hide.assert_called_once()
    janela.destroy.assert_not_called()
    b.sair()
    janela.destroy.assert_called_once()
    assert b.ao_fechar() is True


def test_backup_automatico_verificado_rotacao_e_segredo(tmp_path):
    from src import rotinas, backups
    from pathlib import Path
    r=rotinas.configurar({'backup_ativo':True,'limpar':False,'horas':24,'quantidade':2,'senha':'senha-ficticia-separada','pasta':str(tmp_path/'copias')})
    assert 'senha' not in r and r['senha_configurada']
    for _ in range(3):
        assert rotinas.executar(True)
    arquivos=list((tmp_path/'copias').glob('*.dbot'))
    assert len(arquivos)==2 and not rotinas.situacao()['atrasado']
    import sqlite3
    c=sqlite3.connect(':memory:')
    try:
        c.deserialize(backups.abrir_arquivo(arquivos[0],'senha-ficticia-separada'))
        assert c.execute('SELECT senha,backup_ativo,pasta FROM rotinas').fetchone()==('',0,'')
    finally:
        c.close()
