"""Isolamento HTTP e HTTPS da estação do funcionário, sem contas de uso real."""
import hashlib
import time
from pathlib import Path

import pytest
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from test_caixa import loja,chave,venda
from src import terminal,seguranca,config,caixa
from src.db import get_conn
from src.cliente_terminal import validar_conexao,FalhaTerminal,Cliente

TOKEN='dispositivo-ficticio-'+'a'*40


@pytest.fixture
def api(loja,monkeypatch):
    monkeypatch.setattr(seguranca,'_tentativas',{})
    with get_conn() as c:
        c.execute("UPDATE terminal_config SET ativo=1,host='192.168.1.10' WHERE id=1")
        c.execute('INSERT INTO terminal_dispositivos(nome,hash) VALUES(?,?)',('Fictício',hashlib.sha256(TOKEN.encode()).hexdigest()))
    app=terminal.criar_api()
    app.config.update(SERVER_NAME='127.0.0.1:5443',PREFERRED_URL_SCHEME='https')
    client=app.test_client()
    def req(metodo,path,**kwargs):
        h={'Authorization':'Bearer '+TOKEN,**kwargs.pop('headers',{})}
        return client.open(path,method=metodo,headers=h,**kwargs)
    req.client=client
    return req


def entrar(api,login='conta2'):
    r=api('POST','/terminal/entrar',json={'login':login,'senha':'senha-ficticia-123'})
    assert r.status_code==200
    return r


def test_api_exige_https_dispositivo_e_conta_individual(api):
    assert api('GET','/terminal/estado').status_code==401
    assert api('GET','/terminal/estado',base_url='http://127.0.0.1:5443').status_code==403
    assert api('GET','/terminal/catalogo',headers={'Authorization':'Bearer incorreto'}).status_code==401
    r=entrar(api)
    assert 'Secure' in r.headers['Set-Cookie'] and 'HttpOnly' in r.headers['Set-Cookie']
    r=api('GET','/terminal/catalogo')
    assert r.status_code==200 and 'custo' not in r.json[0]
    assert 'Content-Security-Policy' in r.headers and 'Access-Control-Allow-Origin' not in r.headers


def test_funcionario_so_ve_seu_caixa_e_nao_acessa_administracao(api,loja):
    caixa.abrir(3,dict(chave=chave(),abertura=500))
    entrar(api)
    assert api('GET','/terminal/estado').json['caixas']==[]
    for caminho in ('/gestao','/gestao/api/configuracoes','/gestao/api/caixas','/terminal/configuracoes','/terminal/estornar'):
        assert api('GET',caminho).status_code==404
    assert api('POST','/terminal/abrir',json={'chave':chave(),'abertura':100,'operador_id':3}).status_code==200
    assert api('GET','/terminal/estado').json['caixas'][0]['operador_id']==2


def test_revogacao_de_conta_senha_dispositivo_e_desativacao_bloqueiam(api):
    entrar(api)
    with get_conn() as c:
        c.execute("UPDATE operadores SET versao='nova' WHERE id=2")
    assert api('GET','/terminal/estado').status_code==401
    entrar(api)
    with get_conn() as c:
        c.execute('UPDATE terminal_dispositivos SET ativo=0')
    assert api('GET','/terminal/estado').status_code==401
    with get_conn() as c:
        c.execute('UPDATE terminal_dispositivos SET ativo=1')
        c.execute('UPDATE terminal_config SET ativo=0')
    assert api('GET','/terminal/estado').status_code==403


def test_perfil_atendente_nao_tem_permissao_de_caixa(api):
    assert api('POST','/terminal/entrar',json={'login':'conta4','senha':'senha-ficticia-123'}).status_code==401
    assert api('GET','/terminal/estado').status_code==401


def test_origin_json_ambiguo_e_consulta_duplicada_sao_recusados(api):
    entrar(api)
    assert api('POST','/terminal/abrir',json={},headers={'Origin':'https://externo.invalid'}).status_code==403
    assert api('GET','/terminal/estado?a=1&a=2').status_code==403
    assert api('POST','/terminal/abrir',data='{"abertura":0,"abertura":100}',content_type='application/json').status_code==400
    assert api('POST','/terminal/abrir',data='x',content_type='text/plain').status_code==415


def test_convite_tem_expiracao_e_uso_unico(api):
    codigo='c'*40
    with get_conn() as c:
        c.execute('INSERT INTO terminal_convites(hash,expira_em) VALUES(?,?)',(hashlib.sha256(codigo.encode()).hexdigest(),time.time()+60))
    r=api('POST','/terminal/parear',json={'convite':codigo})
    assert r.status_code==200
    assert api('POST','/terminal/parear',json={'convite':codigo}).status_code==400
    with get_conn() as c:
        assert r.json['chave'] not in str(dict(c.execute('SELECT * FROM terminal_dispositivos ORDER BY id DESC LIMIT 1').fetchone()))
        c.execute('UPDATE terminal_convites SET usado=0,expira_em=0')
    assert api('POST','/terminal/parear',json={'convite':codigo}).status_code==400


def conexao(tmp_path,host='192.168.1.10'):
    cert,_=terminal._certificado(host,tmp_path)
    return {'formato':1,'url':'https://'+host+':5443','certificado':cert.read_text(),
            'impressao_sha256':x509.load_pem_x509_certificate(cert.read_bytes()).fingerprint(hashes.SHA256()).hex(),'convite':'c'*40}


@pytest.mark.parametrize('url',['http://192.168.1.10:5443','https://8.8.8.8:5443','https://user:pass@192.168.1.10:5443','https://192.168.1.10:5443/gestao','https://192.168.1.10:5443?token=a','https://192.168.1.10:99999','https://192.168.1.10:5443\n'])
def test_cliente_recusa_endereco_inseguro_ou_publico(tmp_path,url):
    d=conexao(tmp_path)
    d['url']=url
    with pytest.raises(FalhaTerminal):
        validar_conexao(d)


def test_cliente_confere_fingerprint_e_ip_do_certificado(tmp_path):
    d=conexao(tmp_path)
    assert validar_conexao(d)==d
    with pytest.raises(FalhaTerminal):
        validar_conexao(dict(d,impressao_sha256='0'*64))
    with pytest.raises(FalhaTerminal):
        validar_conexao(dict(d,url='https://192.168.1.11:5443'))


def test_servidor_tls_e_cliente_pareado_usam_certificado_sem_desabilitar_validacao(api,tmp_path,monkeypatch):
    servidor=terminal.ServidorTerminal('127.0.0.1',0,tmp_path/'tls',permitir_loopback=True)
    monkeypatch.setattr(terminal,'_servidor',servidor)
    monkeypatch.setattr('src.cliente_terminal.dpapi',lambda d,abrir=False:d)
    try:
        convite=terminal.convite()
        cliente=Cliente(tmp_path/'cliente',permitir_loopback=True)
        cliente.parear(convite)
        assert cliente.http.verify is not False and cliente.http.trust_env is False
        cliente.entrar('conta2','senha-ficticia-123')
        cliente.executar('abrir',{'abertura':100})
        assert cliente.consultar('estado')['caixas'][0]['esperado_centavos']==10000
        assert 'senha-ficticia' not in (tmp_path/'cliente/conexao.bin').read_text()
        assert not (tmp_path/'cliente/pendencia.bin').exists()
        assert 'convite' not in (tmp_path/'cliente/conexao.bin').read_text()
        cliente.sair()
        with pytest.raises(FalhaTerminal):
            cliente.consultar('estado')
    finally:
        servidor.close()


def test_timeout_preserva_operacao_cifrada_e_conferencia_nao_repete_automaticamente(tmp_path,monkeypatch):
    import src.cliente_terminal as m
    monkeypatch.setattr(m,'dpapi',lambda d,abrir=False:d)
    cliente=Cliente(tmp_path)
    cliente.usuario={'id':2}
    calls=[]
    def transporte(path,dados=None):
        calls.append((path,dados))
        if dados is not None:
            raise FalhaTerminal('Timeout simulado')
        return {'resultado':None}
    monkeypatch.setattr(cliente,'_request',transporte)
    with pytest.raises(FalhaTerminal):
        cliente.executar('abrir',{'abertura':100})
    assert (tmp_path/'pendencia.bin').exists()
    key=cliente.pendente['dados']['chave']
    assert cliente.conferir()=={'pendente':True,'acao':'abrir'}
    assert calls[-1][0]=='operacao/'+key and calls[-1][1] is None
    with pytest.raises(FalhaTerminal):
        cliente.executar('abrir',{'abertura':100})
    with pytest.raises(FalhaTerminal):
        cliente.conferir(True)
    assert calls[-1][1]['chave']==key
    monkeypatch.setattr(cliente,'_request',lambda *a:{'resultado':{'caixa_id':1}})
    assert not cliente.conferir()['pendente'] and not (tmp_path/'pendencia.bin').exists()


def test_pendencia_nao_pode_ser_repetida_por_outro_funcionario(tmp_path,monkeypatch):
    import src.cliente_terminal as m
    monkeypatch.setattr(m,'dpapi',lambda d,abrir=False:d)
    c=Cliente(tmp_path)
    c.usuario={'id':3}
    c.pendente={'usuario_id':2,'acao':'abrir','dados':{'chave':chave()}}
    assert c.conferir()['outro_funcionario']
    with pytest.raises(FalhaTerminal):
        c.conferir(True)


def test_somente_admin_confere_pendencia_de_conta_desativada(api):
    entrar(api)
    dados={'operador_id':3,'chave':chave()}
    assert api('POST','/terminal/conferir-admin',json=dados).status_code==403
    entrar(api,'conta1')
    assert api('POST','/terminal/conferir-admin',json=dados).json['cancelada'] is False
    with get_conn() as c:
        c.execute('UPDATE operadores SET ativo=0 WHERE id=3')
    assert api('POST','/terminal/conferir-admin',json=dados).json=={'resultado':None,'cancelada':True}


def test_resposta_truncada_preserva_pendencia_e_logout_local(tmp_path,monkeypatch):
    from unittest.mock import Mock
    import src.cliente_terminal as m
    monkeypatch.setattr(m,'dpapi',lambda d,abrir=False:d)
    c=Cliente(tmp_path)
    c.usuario={'id':2}
    c.url='https://192.168.1.10:5443'
    resposta=Mock()
    resposta.__enter__=Mock(return_value=resposta)
    resposta.__exit__=Mock(return_value=False)
    resposta.iter_content.side_effect=requests.exceptions.ChunkedEncodingError('Detalhes privados do transporte')
    chamada=Mock(return_value=resposta)
    monkeypatch.setattr(c.http,'request',chamada)
    with pytest.raises(FalhaTerminal,match='Sem resposta da loja'):
        c.executar('abrir',{'abertura':100})
    assert chamada.call_count==1 and (tmp_path/'pendencia.bin').exists()
    assert c.sair()=={'ok':True} and c.usuario is None
    assert (tmp_path/'pendencia.bin').exists()


def test_tls_entrega_corpos_curtos_e_encerra_repetidas_conexoes(api,tmp_path):
    s=terminal.ServidorTerminal('127.0.0.1',0,tmp_path/'tls',permitir_loopback=True)
    sessao=requests.Session()
    sessao.trust_env=False
    sessao.verify=str(s.cert)
    sessao.headers['Authorization']='Bearer '+TOKEN
    try:
        url=f'https://127.0.0.1:{s.porta}'
        for _ in range(12):
            r=sessao.post(url+'/terminal/entrar',json={'login':'conta2','senha':'senha-ficticia-123'},timeout=10)
            assert r.status_code==200
            r=sessao.post(url+'/terminal/sair',json={},timeout=10)
            assert r.status_code==200 and r.json()=={'ok':True}
    finally:
        sessao.close()
        s.close()
