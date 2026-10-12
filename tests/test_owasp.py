"""Casos adversariais OWASP, exclusivamente em bancos e serviços fictícios."""
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from werkzeug.datastructures import MultiDict
from werkzeug.test import Client
from werkzeug.wrappers import Response
from src import config, estoque, seguranca, publicacao, whatsapp
from src.db import init_db, get_conn
from src.links import gerar_link_pedido
from src.validacao_http import ler_json


@pytest.mark.parametrize('entrada', [
    '{"nome":"primeiro","nome":"segundo"}', '{"a":{"q":1,"q":2}}',
    '{"n":NaN}', '{"n":Infinity}', '{"n":-Infinity}', '{"n":1e9999}',
    '{"n":'+'1'*129+'}', '['*33+'0'+']'*33, '{"t":"\\u0000"}',
    '{"t":"\\ud800"}', b'{"t":"\xff"}', '{"a":}',
    '['+','.join('0' for _ in range(25001))+']',
], ids=['campo-duplicado','campo-interno-duplicado','nan','infinito','menos-infinito','exponente',
        'inteiro-longo','profundidade','nul','surrogate','utf8-invalido','sintaxe','itens-excessivos'])
def test_json_hostil_rejeitado(entrada):
    with pytest.raises(ValueError):
        ler_json(entrada)


def test_json_legitimo_preserva_unicode_pontuacao_e_chaves_em_strings():
    original={'nome':"D'Ávila 🍕",'texto':'{[]}'*100+'\nObservação "sem cebola"',
              'dados':{'quantidade':2.5,'ativo':True,'opcional':None}}
    assert ler_json(json.dumps(original)) == original
    assert ler_json('{"emoji":"\\ud83c\\udf55"}') == {'emoji':'🍕'}
    assert ler_json('['*32+'0'+']'*32)


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(config,'DATABASE_PATH',str(tmp_path/'owasp.db'))
    for k,v in {'WHATSAPP_PROVIDER':'TESTE','MODO_TESTE':True,'SEED_CATALOGO':False,
                'IA_PROVIDER':'','BASE_URL':'http://localhost:5000','WEBHOOK_SECRET':'segredo-ficticio',
                'ADMIN_PERMITIR_REMOTO':False,'FORMAS_PAGAMENTO':'Pix,Dinheiro'}.items():
        monkeypatch.setattr(config,k,v)
    monkeypatch.setattr(whatsapp,'enviar_mensagem',Mock())
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config,'DESKTOP_TOKEN','owasp-ficticio')
    c=app.test_client();c.get('/gestao?acesso=owasp-ficticio')
    with c.session_transaction() as sessao:
        headers={'X-CSRF-Token':sessao['csrf']}
    return c,headers,app


@pytest.mark.parametrize('body',['{"nome":"a","nome":"b"}','{"preco":NaN}','{"x":'+ '['*33+'0'+']'*33+'}'])
def test_api_rejeita_json_ambiguo_sem_gravar(cliente,body):
    c,h,_=cliente
    r=c.post('/gestao/api/produtos',data=body,content_type='application/json',headers=h)
    assert r.status_code==400
    assert 'Traceback' not in r.text and body not in r.text
    assert estoque.listar_produtos()==[]


def test_api_exige_tipo_de_conteudo(cliente):
    c,h,_=cliente
    assert c.post('/gestao/api/produtos',data='{"nome":"teste"}',content_type='text/plain',headers=h).status_code==415


def test_parametros_repetidos_nao_iniciam_sessao(cliente):
    _,_,app=cliente
    anonimo=app.test_client()
    r=anonimo.get('/gestao?acesso=owasp-ficticio&acesso=outro')
    assert r.status_code==400
    assert anonimo.get('/gestao/api/produtos').status_code==401


def test_formulario_ambiguo_rejeitado_antes_do_pedido(cliente):
    c,_,_=cliente
    url=gerar_link_pedido('5500000000001').replace('http://localhost:5000','')
    c.get(url)
    with c.session_transaction() as sessao:
        token=sessao['csrf']
    r=c.post(url,data=MultiDict([('csrf_token',token),('nome','Ana'),('nome','Outra pessoa')]))
    assert r.status_code==403
    with get_conn() as conn:
        assert conn.execute('SELECT count(*) FROM pedidos').fetchone()[0]==0


def test_xss_e_sql_sao_dados_sem_criar_script_ou_modificar_consulta(cliente):
    c,h,_=cliente
    nome="D'Ávila <script>alert('teste')</script>"
    for valor in [nome,"'); DROP TABLE produtos; --"]:
        r=c.post('/gestao/api/produtos',json={'nome':valor,'categoria':'Teste','preco':10,'controlar_estoque':False},headers=h)
        assert r.status_code==201
    assert len(estoque.listar_produtos())==2
    url=gerar_link_pedido('5500000000002').replace('http://localhost:5000','')
    pagina=c.get(url).text
    assert '<script>alert(' not in pagina
    assert '&lt;script&gt;' in pagina
    with get_conn() as conn:
        assert conn.execute('SELECT count(*) FROM produtos').fetchone()[0]==2


def test_gateway_isola_admin_e_recusa_proxy_forjado(cliente):
    _,_,app=cliente
    gateway=Client(publicacao.PaginaPublica(app,lambda:'https://teste.example'),Response)
    for rota in ['/gestao','/gestao/api/produtos','/cozinha','/static/gestao.js','/static/experiencia.js']:
        r=gateway.get(rota,headers={'Host':'localhost','X-Forwarded-For':'127.0.0.1','Forwarded':'for=127.0.0.1'})
        assert r.status_code==404
        assert r.headers['X-Frame-Options']=='DENY'
        assert r.headers['X-Content-Type-Options']=='nosniff'
        assert 'Content-Security-Policy' in r.headers
    assert gateway.get('/jogar').status_code==200


def test_cabecalhos_e_sessao_defensivos(cliente):
    c,_,_=cliente
    r=c.get('/gestao',base_url='https://localhost')
    for campo,valor in {'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',
                        'Cross-Origin-Opener-Policy':'same-origin','Cross-Origin-Resource-Policy':'same-origin',
                        'X-Permitted-Cross-Domain-Policies':'none'}.items():
        assert r.headers[campo]==valor
    csp=r.headers['Content-Security-Policy']
    assert "object-src 'none'" in csp and "frame-ancestors 'none'" in csp and "base-uri 'none'" in csp
    assert 'Strict-Transport-Security' in r.headers


@pytest.mark.parametrize('url',['http://externo.example','https://@externo.example','https://u:p@externo.example',
                              'file:///etc/passwd','https://teste.example:99999','https://teste.example:0',
                              'https://teste.example\r\nX-Header: valor','https://te ste.example'])
def test_destinos_perigosos_rejeitados(url):
    with pytest.raises(ValueError):
        seguranca.transporte_seguro(url)


@pytest.mark.parametrize('url',['http://127.0.0.1:11434','http://[::1]:11434','http://localhost:3000','https://servico.example'])
def test_servicos_autorizados_continuam_compativeis(url):
    seguranca.transporte_seguro(url)
