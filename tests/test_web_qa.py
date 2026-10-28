"""Publicação QA usa apenas catálogo, pedidos e banco sintéticos."""
import re
import pytest
from src import config
from src.db import get_conn

@pytest.fixture
def qa(tmp_path,monkeypatch):
    for nome in list(vars(config)):
        if nome.isupper(): monkeypatch.setattr(config,nome,getattr(config,nome))
    from src.web_qa import criar_app
    app=criar_app(tmp_path/'qa','https://qa-ficticio.example','chave-ficticia-'+'a'*40)
    return app.test_client(),tmp_path

def csrf(r):
    return re.search(r'name="csrf_token" value="([^"]+)"',r.text)[1]

def novo(c):
    r=c.get('/',base_url='https://qa-ficticio.example')
    return c.post('/qa/novo',base_url='https://qa-ficticio.example',data={'csrf_token':csrf(r)})

def test_so_rotas_de_cliente_sao_publicadas_e_catalogo_ficticio(qa):
    c,_=qa
    r=c.get('/',base_url='https://qa-ficticio.example')
    assert r.status_code==200 and 'QA' in r.text
    assert r.headers['X-Robots-Tag']=='noindex, nofollow'
    for path in ['/gestao','/cozinha','/webhook','/remoto','/testar','/gestao/api/configuracoes','/static/gestao.js']:
        assert c.get(path,base_url='https://qa-ficticio.example').status_code==404
    r=novo(c);assert r.status_code==302 and r.location.startswith('/m/')
    pagina=c.get(r.location,base_url='https://qa-ficticio.example')
    assert pagina.status_code==200 and 'TESTE' in pagina.text
    assert '<option value="Dinheiro"' in pagina.text and '<option value="Pix"' in pagina.text
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM produtos').fetchone()[0]==8
        assert conn.execute('SELECT COUNT(*) FROM fotos_produto').fetchone()[0]==8
    assert config.WHATSAPP_PROVIDER=='TESTE' and config.MODO_TESTE and not config.WHATSAPP_TOKEN

def test_csrf_e_pedido_real_da_aplicacao_sem_envio_externo(qa,monkeypatch):
    from src import whatsapp
    c,_=qa
    assert c.post('/qa/novo',base_url='https://qa-ficticio.example').status_code==403
    url=novo(c).location
    pagina=c.get(url,base_url='https://qa-ficticio.example')
    from unittest.mock import Mock
    rede=Mock(side_effect=AssertionError('Não acessar a rede do WhatsApp'))
    monkeypatch.setattr(whatsapp._http,'request',rede)
    r=c.post(url,base_url='https://qa-ficticio.example',data={'csrf_token':csrf(pagina),'nome':'Pessoa QA','forma_entrega':'RETIRADA BALCAO','forma_pagamento':'Dinheiro','qtd_1':'1'},follow_redirects=True)
    assert r.status_code==200 and 'Nenhuma mensagem real' in r.text
    assert config.MODO_TESTE and rede.call_count==0
    assert c.get(url,base_url='https://qa-ficticio.example').status_code==410
    with get_conn() as conn: assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0]==1

def test_pasta_existente_sem_marcador_e_origem_invalida_recusadas(tmp_path):
    from src.web_qa import criar_app
    p=tmp_path/'nao-qa';p.mkdir();(p/'importante.txt').write_text('preservar')
    with pytest.raises(ValueError):criar_app(p,'https://qa-ficticio.example','a'*40)
    with pytest.raises(ValueError):criar_app(tmp_path/'outro','http://localhost:5000','a'*40)
    assert (p/'importante.txt').read_text()=='preservar'

def test_cookie_seguro_csrf_foto_pdf_e_limite_sem_host_forjado(qa):
    c,_=qa
    r=c.get('/',base_url='https://qa-ficticio.example')
    assert 'Secure' in r.headers['Set-Cookie'] and 'HttpOnly' in r.headers['Set-Cookie']
    assert c.get('/',base_url='https://invasor.example').status_code==400
    url=novo(c).location
    assert c.get(url+'/catalogo.pdf',base_url='https://qa-ficticio.example').data.startswith(b'%PDF')
    with get_conn() as conn:foto=conn.execute('SELECT hash FROM fotos_produto LIMIT 1').fetchone()[0]
    assert c.get('/produtos/fotos/'+foto+'.jpg',base_url='https://qa-ficticio.example').status_code==200


def test_proxy_https_aceita_origem_correta_sem_confiar_no_host_encaminhado(qa):
    c,_=qa
    r=c.get('/',base_url='http://qa-ficticio.example',headers={'X-Forwarded-Proto':'https','X-Forwarded-Host':'invasor.example'})
    assert r.status_code==200
    r=c.post('/qa/novo',base_url='http://qa-ficticio.example',headers={'X-Forwarded-Proto':'https','Origin':'https://qa-ficticio.example'},data={'csrf_token':csrf(r)})
    assert r.status_code==302

def test_mesma_sessao_reutiliza_link_e_catalogo_nao_duplica(qa):
    c,pasta=qa
    url=novo(c).location
    assert novo(c).location==url
    with get_conn() as conn: assert conn.execute('SELECT COUNT(*) FROM links_pedido').fetchone()[0]==1


def test_lanchonete_tem_perfil_ficticio_e_estoque_individual(qa):
    c,_=qa
    assert config.NOME_RESTAURANTE=='Lanchonete Demonstração'
    assert config.COMERCIO_SEGMENTO=='Lanchonete de testes'
    assert config.COMERCIO_MODELO=='PRODUCAO' and config.COMERCIO_ESTOQUE_PADRAO=='NAO'
    assert config.TELEFONE_RESTAURANTE=='(00) 0000-0000'
    assert 'Fictícia' in config.ENDERECO_RESTAURANTE
    assert not config.IA_PROVIDER and config.WHATSAPP_PROVIDER=='TESTE'
    with get_conn() as conn:
        itens=[dict(p) for p in conn.execute('SELECT * FROM produtos')]
    assert len(itens)==8 and all(p['nome'].startswith('TESTE - ') for p in itens)
    assert all('Não está à venda.' in p['descricao'] for p in itens)
    lanches=[p for p in itens if p['categoria']=='Lanche']
    bebidas=[p for p in itens if p['categoria']=='Bebida']
    assert len(lanches)==4 and all(p['estoque'] is None for p in lanches)
    assert len(bebidas)==2 and all(p['estoque']==1000 for p in bebidas)
    assert not any('Pizza' in p['nome'] or p['categoria']=='Pizzas' for p in itens)
    pagina=c.get(novo(c).location,base_url='https://qa-ficticio.example')
    assert 'Lanchonete Demonstração' in pagina.text and 'X-bacon' in pagina.text


def test_pedido_na_lanchonete_baixa_so_bebida(qa):
    c,_=qa
    url=novo(c).location
    pagina=c.get(url,base_url='https://qa-ficticio.example')
    r=c.post(url,base_url='https://qa-ficticio.example',data={
        'csrf_token':csrf(pagina),'nome':'Pessoa QA','forma_entrega':'RETIRADA BALCAO',
        'forma_pagamento':'Dinheiro','qtd_1':'2','qtd_6':'1'},follow_redirects=True)
    assert r.status_code==200 and 'Seu pedido foi recebido!' in r.text
    with get_conn() as conn:
        assert conn.execute("SELECT estoque FROM produtos WHERE sku='QA-DEMO-1'").fetchone()[0] is None
        assert conn.execute("SELECT estoque FROM produtos WHERE sku='QA-DEMO-6'").fetchone()[0]==999
        vendas=conn.execute("SELECT p.sku,m.quantidade FROM movimentos_estoque m JOIN produtos p ON p.id=m.produto_id WHERE m.tipo='VENDA'").fetchall()
        assert [(p['sku'],p['quantidade']) for p in vendas]==[('QA-DEMO-6',-1)]


def test_reabrir_qa_atualiza_demo_antiga_sem_duplicar_ou_repor_bebidas(qa):
    _,pasta=qa
    with get_conn() as conn:
        conn.execute("UPDATE produtos SET nome='TESTE - Pizza antiga',categoria='Pizzas',estoque=5 WHERE sku='QA-DEMO-3'")
        conn.execute("UPDATE produtos SET estoque=998 WHERE sku='QA-DEMO-6'")
        ids=[tuple(p) for p in conn.execute('SELECT id,sku FROM produtos ORDER BY id')]
    from src.web_qa import criar_app
    criar_app(pasta/'qa','https://qa-ficticio.example','chave-ficticia-'+'a'*40)
    with get_conn() as conn:
        assert [tuple(p) for p in conn.execute('SELECT id,sku FROM produtos ORDER BY id')]==ids
        assert conn.execute('SELECT COUNT(*) FROM fotos_produto').fetchone()[0]==8
        lanche=conn.execute("SELECT nome,estoque FROM produtos WHERE sku='QA-DEMO-3'").fetchone()
        assert lanche['nome']=='TESTE - X-bacon' and lanche['estoque'] is None
        assert conn.execute("SELECT estoque FROM produtos WHERE sku='QA-DEMO-6'").fetchone()[0]==998

def test_health_modo_qa_e_csrf_errado(qa):
    c,_=qa
    assert c.get('/healthz',base_url='https://qa-ficticio.example').json=={'ok':True,'ambiente':'QA','whatsapp':'SIMULADO'}
    r=c.get('/',base_url='https://qa-ficticio.example')
    assert c.post('/qa/novo',base_url='https://qa-ficticio.example',headers={'Origin':'https://invasor.example'},data={'csrf_token':csrf(r)}).status_code==403


@pytest.mark.parametrize('path,codigo', [('/gestao',404),('/m/inexistente',410),('/m/inexistente/comprovante',410)])
def test_recuperacao_nao_sugere_whatsapp_real_nem_reflete_url(qa,path,codigo):
    c,_=qa
    r=c.get(path+'?segredo=NAO_EXIBIR',base_url='https://qa-ficticio.example')
    assert r.status_code==codigo
    assert 'Voltar ao laboratório' in r.text and 'href="/"' in r.text
    assert 'NAO_EXIBIR' not in r.text and 'conversa com a loja no WhatsApp' not in r.text
    assert 'no-store' in r.headers['Cache-Control']


def test_sessao_expirada_pode_recomecar_sem_burlar_csrf(qa):
    c,_=qa
    url=novo(c).location
    r=c.post(url,base_url='https://qa-ficticio.example',data={'csrf_token':'incorreto','qtd_1':'1'})
    assert r.status_code==403 and 'Sua sessão precisa ser renovada' in r.text
    with get_conn() as conn: assert conn.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0]==0
    pagina=c.get(url,base_url='https://qa-ficticio.example')
    r=c.post(url,base_url='https://qa-ficticio.example',data={'csrf_token':csrf(pagina),'qtd_1':'1','nome':'Pessoa QA','forma_pagamento':'Dinheiro'},follow_redirects=True)
    assert r.status_code==200 and 'Seu pedido foi recebido!' in r.text
    assert 'Imprimir ou salvar comprovante' in r.text and 'não comprova pagamento' in r.text
    assert c.get('/static/recibo.js',base_url='https://qa-ficticio.example').status_code==200


def test_limite_orienta_sem_desativar_protecao(qa,monkeypatch):
    c,_=qa
    from src.politica_terminal import Limites
    monkeypatch.setattr(Limites,'consumir',lambda *args:False)
    r=novo(c)
    assert r.status_code==429 and r.headers['Retry-After']=='60'
    assert 'pequena pausa' in r.text and 'Voltar ao laboratório' in r.text
    with get_conn() as conn: assert conn.execute('SELECT COUNT(*) FROM links_pedido').fetchone()[0]==0


def test_falha_interna_nao_expoe_detalhes(qa,monkeypatch):
    c,_=qa
    from src import links
    def falhar(*args):raise RuntimeError('DETALHE_PRIVADO_NAO_EXIBIR')
    monkeypatch.setattr(links,'gerar_link_pedido',falhar)
    r=novo(c)
    assert r.status_code==500
    assert 'Não foi possível concluir' in r.text and 'DETALHE_PRIVADO' not in r.text
