"""Comprovante recarregável somente na sessão que confirmou a compra."""
import re
from unittest.mock import Mock

import pytest

from src import config, db, estoque, whatsapp
from src.links import gerar_link_pedido

BASE='https://loja-ficticia.example'


@pytest.fixture
def loja(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DATABASE_PATH',str(tmp_path/'ficticio.db'))
    monkeypatch.setattr(config,'MODO_TESTE',True)
    monkeypatch.setattr(config,'IA_PROVIDER','')
    monkeypatch.setattr(config,'BASE_URL',BASE)
    monkeypatch.setattr(config,'FORMAS_PAGAMENTO','Pix,Dinheiro')
    db.init_db(seed_cardapio=False)
    from src.app import app
    envio=Mock();monkeypatch.setattr(whatsapp,'enviar_mensagem',envio)
    produto=estoque.salvar_produto({'nome':'Produto fictício','preco':12,'estoque':10,'categoria':'Teste'})
    c=app.test_client()
    url='/m/'+gerar_link_pedido('5511999990001').rsplit('/',1)[-1]
    html=c.get(url,base_url=BASE).text
    csrf=re.search(r'name="csrf_token" value="([^"]+)"',html)[1]
    dados={'csrf_token':csrf,'qtd_'+str(produto['id']):'1','nome':'Pessoa fictícia','forma_pagamento':'Pix'}
    return app,c,url,dados,envio


def test_confirmacao_redireciona_e_atualizacao_nao_repete_compra_ou_whatsapp(loja):
    app,c,url,dados,envio=loja
    resposta=c.post(url,base_url=BASE,data=dados)
    assert resposta.status_code==303 and resposta.location==url+'/comprovante'
    for _ in range(3):
        r=c.get(resposta.location,base_url=BASE)
        assert r.status_code==200 and 'R$ 12,00' in r.text
        assert 'no-store' in r.headers['Cache-Control']
    assert c.post(url,base_url=BASE,data=dados).status_code==410
    assert c.get(url,base_url=BASE).status_code==410
    assert envio.call_count==3
    with db.get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0]==1
        assert conn.execute('SELECT estoque FROM produtos').fetchone()[0]==9


def test_token_sozinho_ou_sessao_de_outro_cliente_nao_libera_recibo(loja):
    app,c,url,dados,_=loja
    assert c.get(url+'/comprovante',base_url=BASE).status_code==410
    c.post(url,base_url=BASE,data=dados)
    outro=app.test_client()
    indisponivel=outro.get(url+'/comprovante',base_url=BASE)
    assert indisponivel.status_code==410 and 'Não refaça o pedido' in indisponivel.text
    assert 'quero fazer um pedido' not in indisponivel.text
    assert c.get('/m/outro-token/comprovante',base_url=BASE).status_code==410


def test_recibo_expira_e_cookie_nao_contem_dados_pessoais_ou_token(loja,monkeypatch):
    from src import comprovantes
    _,c,url,dados,_=loja
    c.post(url,base_url=BASE,data=dados)
    with c.session_transaction(base_url=BASE) as sessao:
        texto=str(dict(sessao))
        assert 'Pessoa fictícia' not in texto and url.split('/')[-1] not in texto and '5511999990001' not in texto
    agora=comprovantes.time()
    monkeypatch.setattr(comprovantes,'time',lambda:agora+comprovantes.DURACAO+1)
    assert c.get(url+'/comprovante',base_url=BASE).status_code==410


def test_sessao_guarda_no_maximo_cinco_recibos_e_recusa_estrutura_invalida(loja):
    from src import comprovantes
    app,_,_,_,_=loja
    with app.test_request_context():
        from flask import session
        session['comprovantes']='invalido'
        for i in range(8):comprovantes.registrar(str(i),i+1,True,False)
        assert len(session['comprovantes'])==5
        assert comprovantes.consultar('7',8)
        assert not comprovantes.consultar('0',1)
        assert not comprovantes.consultar('7',9)


def test_apagar_pedido_invalida_comprovante_sem_expor_erro(loja):
    _,c,url,dados,_=loja
    c.post(url,base_url=BASE,data=dados)
    with db.get_conn() as conn:conn.execute('UPDATE links_pedido SET pedido_id=NULL')
    assert c.get(url+'/comprovante',base_url=BASE).status_code==410
