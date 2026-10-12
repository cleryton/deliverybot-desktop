"""Livro financeiro e pedidos do balcão em banco fictício, sem transportes reais."""
import secrets
from concurrent.futures import ThreadPoolExecutor

import pytest
from werkzeug.security import generate_password_hash

from src import caixa, config, estoque, pedidos, fila
from src.db import get_conn, init_db


def chave():
    return secrets.token_hex(16)


@pytest.fixture
def loja(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DATABASE_PATH',str(tmp_path/'ficticio.db'))
    monkeypatch.setattr(config,'SEED_CATALOGO',False)
    monkeypatch.setattr(config,'FORMAS_PAGAMENTO','Dinheiro,Pix,Cartao de credito')
    init_db()
    with get_conn() as c:
        for uid,perfil in [(1,'ADMIN'),(2,'CAIXA'),(3,'CAIXA'),(4,'ATENDENTE')]:
            c.execute('INSERT INTO operadores(id,nome,login,senha_hash,perfil,versao) VALUES(?,?,?,?,?,?)',(uid,'Fictício','conta'+str(uid),generate_password_hash('senha-ficticia-123'),perfil,'versao'))
    p=estoque.salvar_produto({'nome':'Produto fictício','categoria':'Teste','preco':'12.30','controlar_estoque':True,'estoque':10})
    return p['id']


def venda(pid,forma='DINHEIRO',recebido='20.00',pago=True):
    itens=[{'produto_id':pid,'quantidade':1}]
    return dict(chave=chave(),nome='Balcão fictício',itens=itens,cotacao=pedidos.cotacao(itens,'RETIRADA BALCAO'),pago=pago,forma=forma,recebido=recebido)


def test_dinheiro_troco_nao_e_contado_como_venda_e_outros_pagamentos_nao_inflam_caixa(loja):
    caixa.abrir(2,dict(chave=chave(),abertura='100'))
    r=caixa.vender(2,venda(loja))
    assert r['troco_centavos']==770 and r['total_centavos']==1230
    caixa.vender(2,venda(loja,'PIX'))
    caixa.vender(2,venda(loja,'CARTAO'))
    t=caixa.consultar(2)[0]
    assert t['esperado_centavos']==11230
    assert t['recebimentos']=={'DINHEIRO':1230,'PIX':1230,'CARTAO':1230}
    assert t['vendas_centavos']==3690 and t['pendente_centavos']==0
    p=pedidos.obter_pedido(r['pedido_id'])
    assert p['total_pago']==12.30 and p['origem']=='Balcão manual'
    assert len(fila.listar_fila())==3 and estoque.listar_produtos()[0]['estoque']==7


def test_sangria_suprimento_conferencia_e_fechamento_imutavel(loja):
    caixa.abrir(2,dict(chave=chave(),abertura=100))
    caixa.movimentar(2,dict(chave=chave(),tipo='SANGRIA',valor=20,motivo='Entrega ao responsável'))
    caixa.movimentar(2,dict(chave=chave(),tipo='SUPRIMENTO',valor=5,motivo='Troco'))
    d=dict(chave=chave(),contado=84)
    fechado=caixa.fechar(2,d)
    assert fechado['esperado_centavos']==8500 and fechado['diferenca_centavos']==-100
    assert caixa.fechar(2,d)==fechado
    with pytest.raises(ValueError):
        caixa.movimentar(2,dict(chave=chave(),tipo='SANGRIA',valor=1,motivo='Após fechamento'))


def test_pedido_pendente_nao_gera_dinheiro_e_recebimento_posterior_nao_duplica(loja):
    caixa.abrir(2,dict(chave=chave(),abertura=0))
    r=caixa.vender(2,venda(loja,pago=False))
    assert caixa.consultar(2)[0]['pendente_centavos']==1230
    assert caixa.consultar(2)[0]['esperado_centavos']==0
    d=dict(chave=chave(),forma='DINHEIRO',recebido='12.30')
    caixa.receber(2,r['pedido_id'],d)
    caixa.receber(2,r['pedido_id'],d)
    assert caixa.consultar(2)[0]['esperado_centavos']==1230
    with pytest.raises(ValueError,match='já teve'):
        caixa.receber(2,r['pedido_id'],dict(d,chave=chave()))


def test_retentativa_e_confirmacoes_concorrentes_so_criam_uma_venda(loja):
    caixa.abrir(2,dict(chave=chave(),abertura=100))
    d=venda(loja)
    with ThreadPoolExecutor(max_workers=3) as pool:
        r=list(pool.map(lambda _:caixa.vender(2,d),range(3)))
    assert r[0]==r[1]==r[2]
    assert len(caixa.vendas(2))==1 and estoque.listar_produtos()[0]['estoque']==9
    with pytest.raises(ValueError,match='dados diferentes'):
        caixa.vender(2,dict(d,nome='Outro'))
    assert caixa.resultado(3,d['chave']) is None
    assert caixa.resultado(2,d['chave'])==r[0]


@pytest.mark.parametrize('falha',['sem-caixa','total','estoque','recebido','troco','forma'])
def test_falha_reverte_pedido_estoque_e_movimento(loja,falha):
    if falha!='sem-caixa':
        caixa.abrir(2,dict(chave=chave(),abertura=0 if falha=='troco' else 100))
    d=venda(loja)
    if falha=='total':
        d['cotacao']['total_pedido']=0.01
    if falha=='estoque':
        with get_conn() as c:
            c.execute('UPDATE produtos SET estoque=0')
    if falha=='recebido':
        d['recebido']=1
    if falha=='forma':
        d['forma']='inventado'
    with pytest.raises(ValueError):
        caixa.vender(2,d)
    with get_conn() as c:
        assert c.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0]==0
        assert c.execute('SELECT COUNT(*) FROM movimentos_caixa').fetchone()[0]==0
        assert c.execute('SELECT estoque FROM produtos').fetchone()[0]==(0 if falha=='estoque' else 10)


def test_ignora_preco_e_operador_enviados_e_usa_dados_do_cadastro(loja):
    caixa.abrir(2,dict(chave=chave(),abertura=100))
    d=venda(loja)
    d['itens'][0]['preco']=0.01
    d['operador_id']=3
    r=caixa.vender(2,d)
    assert r['total_centavos']==1230 and not caixa.vendas(3)
    with pytest.raises(ValueError):
        caixa.receber(3,r['pedido_id'],dict(chave=chave(),forma='PIX'))


def test_estorno_exige_administrador_devolucao_e_caixa_aberto(loja):
    caixa.abrir(2,dict(chave=chave(),abertura=100))
    r=caixa.vender(2,venda(loja))
    with pytest.raises(ValueError):
        pedidos.cancelar_pedido(r['pedido_id'])
    d=dict(chave=chave(),devolucao_confirmada=True)
    with pytest.raises(ValueError):
        caixa.estornar(2,r['pedido_id'],d)
    with pytest.raises(ValueError):
        caixa.estornar(1,r['pedido_id'],dict(d,devolucao_confirmada=False))
    caixa.estornar(1,r['pedido_id'],d)
    assert caixa.consultar(2)[0]['esperado_centavos']==10000
    assert pedidos.obter_pedido(r['pedido_id'])['status']=='CANCELADO'
    assert estoque.listar_produtos()[0]['estoque']==10
    assert caixa.estornar(1,r['pedido_id'],d)=={'pedido_id':r['pedido_id'],'caixa_id':r['caixa_id']}


def test_caixa_fechado_nao_e_reescrito_por_cancelamento_posterior(loja):
    caixa.abrir(2,dict(chave=chave(),abertura=0))
    r=caixa.vender(2,venda(loja,'PIX'))
    caixa.fechar(2,dict(chave=chave(),contado=0))
    with pytest.raises(ValueError,match='ainda aberto'):
        caixa.estornar(1,r['pedido_id'],dict(chave=chave(),devolucao_confirmada=True))


def test_caixa_nao_envia_atualizacoes_ao_whatsapp(loja,monkeypatch):
    from src import whatsapp
    monkeypatch.setattr(whatsapp,'enviar_mensagem',lambda *a:pytest.fail('Balcão não deve enviar mensagens'))
    caixa.abrir(2,dict(chave=chave(),abertura=0))
    r=caixa.vender(2,venda(loja,'PIX'))
    assert fila.avancar_status(r['pedido_id'])['status']=='EM_PREPARO'


def test_entrega_manual_conserva_endereco_e_taxa_oficial(loja,monkeypatch):
    monkeypatch.setattr(config,'TAXA_ENTREGA',5.0)
    caixa.abrir(2,dict(chave=chave(),abertura=0))
    d=venda(loja,'PIX')
    d.update(entrega='ENTREGA',endereco='Rua Fictícia, 123')
    d['cotacao']=pedidos.cotacao(d['itens'],'ENTREGA')
    r=caixa.vender(2,d)
    p=pedidos.obter_pedido(r['pedido_id'])
    assert r['total_centavos']==1730 and p['cliente_endereco']=='Rua Fictícia, 123'
    assert p['forma_entrega']=='ENTREGA'
    with pytest.raises(ValueError):
        caixa.vender(2,dict(d,chave=chave(),endereco=''))


@pytest.mark.parametrize('valor',['NaN','Infinity',-1,'0.001',True,None,'99999999999999999999999'])
def test_dinheiro_invalido_e_recusado(valor):
    with pytest.raises(ValueError):
        caixa.centavos(valor)


def test_atendente_e_conta_revogada_nao_operam_caixa(loja):
    with pytest.raises(ValueError):
        caixa.abrir(4,dict(chave=chave(),abertura=0))
    with get_conn() as c:
        c.execute('UPDATE operadores SET ativo=0 WHERE id=2')
    with pytest.raises(ValueError):
        caixa.abrir(2,dict(chave=chave(),abertura=0))


def test_admin_consegue_conferir_caixa_de_conta_desativada(loja):
    t=caixa.abrir(2,dict(chave=chave(),abertura=50))
    with get_conn() as c:
        c.execute('UPDATE operadores SET ativo=0 WHERE id=2')
    r=caixa.fechar_pelo_admin(1,t['caixa_id'],dict(chave=chave(),contado=45))
    assert r['diferenca_centavos']==-500
    with get_conn() as c:
        assert c.execute("SELECT operador_id FROM auditoria_operadores WHERE acao='CAIXA_FECHAR_ADMIN'").fetchone()[0]==1


def test_obsidian_guia_caixa_nao_publica_financas_nem_entra_no_prompt(loja):
    from src import cerebro
    pasta=cerebro.arquivo_inicio().parent
    assert '[[Pedidos manuais e caixa]]' in (pasta/'Mapa do atendimento.md').read_text(encoding='utf-8')
    nota=pasta/'Pedidos manuais e caixa.md'
    assert 'atendimento: false' in nota.read_text(encoding='utf-8')
    texto='# Guia personalizado\nPreservar edição manual.'
    nota.write_text(texto,encoding='utf-8')
    cerebro.arquivo_inicio()
    assert nota.read_text(encoding='utf-8')==texto
    assert 'Preservar edição manual' not in cerebro.instrucoes_contexto('pedidos manuais caixa')
