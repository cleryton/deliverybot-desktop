"""Separação da conta de caixa e preservação financeira em backup fictício."""
from http.cookies import SimpleCookie
from unittest.mock import Mock
import sqlite3

import pytest
from test_aprimoramentos import banco,cliente
from src import backups,operadores
from src.db import get_conn


def contas(c,h):
    dados={'nome':'Responsável fictício','login':'admin.caixa','senha':'senha-ficticia-caixa-123','perfil':'ADMIN'}
    admin=c.post('/gestao/api/operadores',json=dados,headers=h).json['id']
    uid=c.post('/gestao/api/operadores',json={**dados,'login':'caixa.ficticio','perfil':'CAIXA'},headers=h).json['id']
    return admin,uid,dados


def test_caixa_nao_acessa_painel_api_ou_ponte_administrativa(cliente):
    from src.app import app
    c,h=cliente
    admin,uid,d=contas(c,h)
    c.post('/gestao/sair',headers=h)
    assert c.post('/gestao/login',data={'login':'caixa.ficticio','senha':d['senha'],'csrf_token':h['X-CSRF-Token']}).status_code==302
    assert 'Sua conta usa o DeliveryBot Funcionário' in c.get('/gestao').text
    for rota in ('produtos','pedidos','resumo','caixas','terminal','operadores','configuracoes','humano'):
        assert c.get('/gestao/api/'+rota).status_code==403
    assert c.post('/gestao/api/caixas/1/fechar',json={},headers=h).status_code==403
    assert c.put('/gestao/api/terminal/dispositivos/1/autorizacao',json={'operador_id':uid,'movimentar':True},headers=h).status_code==403
    janela=Mock()
    janela.get_cookies.return_value=[SimpleCookie('session='+c.get_cookie('session').value)]
    for admin_only in (True,False):
        with pytest.raises(ValueError):
            operadores.validar_sessao_nativa(app,janela,admin_only)


def test_backup_preserva_livro_e_remove_pareamentos(cliente):
    from src import caixa
    c,h=cliente
    admin,uid,d=contas(c,h)
    caixa.abrir(uid,dict(chave='a'*32,abertura=100))
    with get_conn() as conn:
        conn.execute("UPDATE terminal_config SET ativo=1,host='192.168.1.10'")
        conn.execute("INSERT INTO terminal_dispositivos(nome,hash) VALUES('Fictício','hash-ficticio')")
        conn.execute("INSERT INTO terminal_convites(hash,expira_em) VALUES('convite-ficticio',9999999999)")
        conn.execute('INSERT INTO terminal_autorizacoes VALUES(1,?,1,\'versao-ficticia\')',(uid,))
        conn.execute('INSERT INTO terminal_convites_autorizacoes VALUES(\'convite-ficticio\',?,1)',(uid,))
    arquivo=backups.criar('senha-backup-ficticia-123')
    raw=backups.abrir_arquivo(arquivo,'senha-backup-ficticia-123')
    with sqlite3.connect(':memory:') as restaurado:
        restaurado.deserialize(raw)
        assert restaurado.execute('SELECT abertura_centavos FROM caixas').fetchone()[0]==10000
        assert restaurado.execute('SELECT ativo,host FROM terminal_config').fetchone()==(0,'')
        assert restaurado.execute('SELECT COUNT(*) FROM terminal_dispositivos').fetchone()[0]==0
        assert restaurado.execute('SELECT COUNT(*) FROM terminal_convites').fetchone()[0]==0
        assert restaurado.execute('SELECT COUNT(*) FROM terminal_autorizacoes').fetchone()[0]==0
        assert restaurado.execute('SELECT COUNT(*) FROM terminal_convites_autorizacoes').fetchone()[0]==0


def test_vinculo_somente_admin_csrf_e_auditoria(cliente):
    c,h=cliente
    admin,uid,d=contas(c,h)
    with get_conn() as conn:
        conn.execute("INSERT INTO terminal_dispositivos(nome,hash) VALUES('Fictício','hash-ficticio')")
    rota='/gestao/api/terminal/dispositivos/1/autorizacao'
    dados={'operador_id':uid,'movimentar':True}
    assert c.put(rota,json=dados).status_code==403
    assert c.put(rota,json={**dados,'operador_id':admin},headers=h).status_code==400
    assert c.put(rota,json=dados,headers=h).status_code==200
    with get_conn() as conn:
        r=conn.execute('SELECT * FROM terminal_autorizacoes').fetchone()
        assert r['operador_id']==uid and r['movimentar']==1
        assert conn.execute("SELECT operador_id FROM auditoria_operadores WHERE acao='gestao.terminal_autorizar'").fetchone()[0]==admin


def test_caixas_exigem_csrf_e_fechamento_admin_nao_usa_conta_alvo(cliente):
    from src import caixa
    c,h=cliente
    admin,uid,d=contas(c,h)
    t=caixa.abrir(uid,dict(chave='a'*32,abertura=100))
    assert c.post('/gestao/api/caixas/'+str(t['caixa_id'])+'/fechar',json={'chave':'b'*32,'contado':100}).status_code==403
    with get_conn() as conn:
        conn.execute('UPDATE operadores SET ativo=0 WHERE id=?',(uid,))
    r=c.post('/gestao/api/caixas/'+str(t['caixa_id'])+'/fechar',json={'chave':'b'*32,'contado':99},headers=h)
    assert r.status_code==200 and r.json['diferenca_centavos']==-100
    with get_conn() as conn:
        assert conn.execute("SELECT operador_id FROM auditoria_operadores WHERE acao='CAIXA_FECHAR_ADMIN'").fetchone()[0]==admin
