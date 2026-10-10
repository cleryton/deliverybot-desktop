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


def test_atendimento_humano_pausa_envio_e_retoma(cliente,monkeypatch):
    from src import humano,bot,processamento,whatsapp
    from unittest.mock import Mock
    t='5511999990011'
    assert 'humano' in bot.processar_mensagem(t,'ATENDENTE')
    assert bot.processar_mensagem(t,'4') is None
    humano.controlar(t,'assumir')
    with pytest.raises(ValueError):
        humano.responder({'telefone':t,'mensagem':'Olá'})
    tarefa=humano.responder({'telefone':t,'mensagem':'Olá, sou da loja','confirmar_envio':True})
    with pytest.raises(ValueError):
        humano.controlar(t,'retomar')
    config.WHATSAPP_PROVIDER='LOCAL'
    config.MODO_TESTE=False
    monkeypatch.setattr(processamento,'_servico_pronto',lambda:True)
    envio=Mock()
    monkeypatch.setattr(whatsapp,'enviar_mensagem',envio)
    processamento._parar.clear()
    assert processamento.processar_proxima()
    envio.assert_called_once()
    assert envio.call_args.args[1]=='Olá, sou da loja'
    humano.controlar(t,'retomar')
    assert not humano.pausado(t)


def test_fracionados_cancelamento_e_custo_historico():
    from src import estoque,pedidos,catalogo_avancado
    from datetime import date
    p=estoque.salvar_produto({'nome':'Tecido','categoria':'Materiais','preco':10,'custo':4,'unidade':'m','fracionado':True,'estoque':1.5,'variacao':'Azul','familia':'Tecidos'})
    pedido=pedidos.criar_pedido('5511999990033','Cliente fictício',[{'produto_id':p['id'],'quantidade':'0.250'}],'Dinheiro')
    assert pedido['total_pedido']==2.5
    assert estoque.listar_produtos()[0]['estoque']==1.25
    assert pedido['itens'][0]['produto_nome']=='Tecido · Azul'
    estoque.salvar_produto({**p,'custo':8,'ativo':True,'controlar_estoque':True},p['id'])
    hoje=date.today().isoformat()
    r=catalogo_avancado.relatorio(hoje,hoje)
    assert r['custos_registrados']==1 and r['margem_parcial']==1.5
    pedidos.cancelar_pedido(pedido['id'])
    assert estoque.listar_produtos()[0]['estoque']==1.5
    assert catalogo_avancado.relatorio(hoje,hoje)['pedidos']==0


def test_csv_conferencia_atomicidade_e_duplicados():
    from src import estoque,catalogo_avancado
    csv='nome;categoria;preco;sku;estoque\nCaderno;Papelaria;12.50;CAD;3\n'
    assert not catalogo_avancado.importar({'csv':csv})['importado']
    assert not estoque.listar_produtos()
    assert catalogo_avancado.importar({'csv':csv,'confirmar':True})['quantidade']==1
    with pytest.raises(ValueError):
        catalogo_avancado.importar({'csv':csv.replace('CAD','OUTRO')+ 'Duplicado;Papelaria;10;CAD;1\n','confirmar':True})
    assert len(estoque.listar_produtos())==1


def test_formulario_publico_compra_fracionada(cliente):
    from src import estoque
    from src.links import gerar_link_pedido
    p=estoque.salvar_produto({'nome':'Tecido','categoria':'Materiais','preco':10,'unidade':'m','fracionado':True,'estoque':2})
    c,h=cliente
    caminho='/m/'+gerar_link_pedido('5511999990044').rsplit('/',1)[-1]
    c.get(caminho)
    r=c.post(caminho,data={'csrf_token':h['X-CSRF-Token'],'nome':'Cliente fictício','forma_pagamento':'Dinheiro','forma_entrega':'RETIRADA BALCAO','qtd_'+str(p['id']):'0.5'})
    assert r.status_code==200
    assert estoque.listar_produtos()[0]['estoque']==1.5
