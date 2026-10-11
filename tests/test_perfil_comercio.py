"""Perfis independentes e atualizações sem perder dados; somente dados fictícios."""
from io import BytesIO
import json

import pytest
from werkzeug.datastructures import FileStorage
from werkzeug.test import Client
from werkzeug.wrappers import Response

from src import config, estoque, pedidos, cardapio, preferencias, perfil_comercio, ia
from src.db import init_db, get_conn


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'loja.db'))
    for campo in preferencias.CAMPOS | {'MODO_TESTE', 'WHATSAPP_API_URL', 'SEED_CATALOGO'}:
        monkeypatch.setattr(config, campo, getattr(config, campo))
    for campo, valor in {'COMERCIO_SEGMENTO':'', 'COMERCIO_DESCRICAO':'', 'COMERCIO_MODELO':'REVENDA',
                         'COMERCIO_ESTOQUE_PADRAO':'SIM', 'COMERCIO_CONFIGURADO':'NAO',
                         'WHATSAPP_PROVIDER':'TESTE', 'IA_PROVIDER':'', 'TUNEL_AUTOMATICO':'NAO',
                         'MODO_TESTE':True, 'SEED_CATALOGO':False, 'FORMAS_PAGAMENTO':'Pix',
                         'NOME_RESTAURANTE':'Minha loja', 'BASE_URL':'http://localhost:5000'}.items():
        setattr(config, campo, valor)
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'perfil-ficticio')
    cliente = app.test_client()
    cliente.get('/gestao?acesso=perfil-ficticio', follow_redirects=True)
    with cliente.session_transaction() as s:
        csrf = s['csrf']
    yield tmp_path, app, cliente, {'X-CSRF-Token':csrf}
    estoque.invalidar_catalogo()


def perfil(modelo='PRODUCAO', **campos):
    return {'nome':'Comércio de teste', 'segmento':'Restaurante',
            'descricao':'Preparo refeições depois que o cliente faz o pedido.', 'modelo':modelo, **campos}


def item(**campos):
    return estoque.salvar_produto({'nome':'Refeição', 'categoria':'Pratos', 'preco':'20.00', **campos})


@pytest.mark.parametrize('modelo,controlado', [('REVENDA',True), ('PRODUCAO',False), ('SERVICOS',False), ('MISTO',True)])
def test_novos_itens_seguem_o_perfil_sem_catalogo_pronto(loja, modelo, controlado):
    salvo = perfil_comercio.salvar(perfil(modelo))
    assert salvo['configurado'] and salvo['controlar_estoque'] == controlado
    assert estoque.listar_produtos() == []
    p = item()
    assert p['estoque'] == (0 if controlado else None)
    assert bool(cardapio.buscar_produto(p['id'])) == (not controlado)


def test_producao_pode_ser_pedida_e_cancelada_sem_saldo_ficticio(loja):
    perfil_comercio.salvar(perfil())
    p = item()
    pedido = pedidos.criar_pedido('5511999990000','Cliente fictício',[{'produto_id':p['id'],'quantidade':8}],'Pix')
    assert pedido['total_itens'] == 160
    assert estoque.listar_produtos()[0]['estoque'] is None
    pedidos.cancelar_pedido(pedido['id'])
    assert estoque.listar_produtos()[0]['estoque'] is None
    assert estoque.listar_movimentos() == []
    assert cardapio.buscar_produto(p['id'])


def test_oficina_combina_servico_e_peca_com_contagem(loja):
    perfil_comercio.salvar(perfil('SERVICOS', segmento='Oficina', descricao='Faço revisões e vendo peças.'))
    servico = item(nome='Serviço de revisão', categoria='Serviços', unidade='serv')
    peca = item(nome='Filtro', categoria='Peças', controlar_estoque=True, estoque=2)
    pedido = pedidos.criar_pedido('5511999990000','Cliente fictício',[
        {'produto_id':servico['id'],'quantidade':1}, {'produto_id':peca['id'],'quantidade':2}],'Pix')
    atuais = {p['id']:p for p in estoque.listar_produtos()}
    assert atuais[servico['id']]['estoque'] is None and atuais[peca['id']]['estoque'] == 0
    assert cardapio.buscar_produto(servico['id']) and not cardapio.buscar_produto(peca['id'])
    pedidos.cancelar_pedido(pedido['id'])
    assert {p['id']:p['estoque'] for p in estoque.listar_produtos()} == {servico['id']:None, peca['id']:2}


def test_trocar_perfil_nao_muda_saldos_pedidos_ou_controle_na_edicao(loja):
    p = item(estoque=7)
    pedido = pedidos.criar_pedido('5511999990000','Cliente fictício',[{'produto_id':p['id'],'quantidade':2}],'Pix')
    perfil_comercio.salvar(perfil())
    atualizado = estoque.salvar_produto({'nome':'Refeição revisada','categoria':'Pratos','preco':25},p['id'])
    assert atualizado['estoque'] == 5
    assert pedidos.obter_pedido(pedido['id'])['itens'][0]['nome_produto'] == 'Refeição'
    assert pedidos.obter_pedido(pedido['id'])['total_itens'] == 40
    novo = item(nome='Encomenda')
    assert novo['estoque'] is None
    perfil_comercio.salvar(perfil('REVENDA'))
    assert estoque.salvar_produto({'nome':'Encomenda revisada','categoria':'Pratos','preco':30},novo['id'])['estoque'] is None


def test_restaurante_pode_escolher_contagem_e_saldo_zero_nao_e_ilimitado(loja):
    perfil_comercio.salvar(perfil(controlar_estoque=True))
    p = item(estoque=0)
    assert cardapio.buscar_produto(p['id']) is None
    with pytest.raises(ValueError, match='Estoque insuficiente'):
        pedidos.criar_pedido('5511999990000','Teste',[{'produto_id':p['id'],'quantidade':1}],'Pix')


@pytest.mark.parametrize('campo,valor', [('nome',''), ('segmento',''), ('descricao',''), ('descricao','x'*1201),
                                       ('modelo','AUTOMATICO'), ('modelo',[]), ('controlar_estoque','nao')])
def test_perfil_invalido_nao_salva_parcialmente(loja, campo, valor):
    antes = preferencias.obter()
    with pytest.raises(ValueError):
        perfil_comercio.salvar(perfil(**{campo:valor}))
    assert preferencias.obter() == antes
    with get_conn() as c:
        assert c.execute('SELECT COUNT(*) FROM configuracoes').fetchone()[0] == 0


def test_instalador_importa_acentos_uma_vez_e_configuracao_persiste(loja):
    pasta, _, _, _ = loja
    arquivo = pasta / 'perfil-instalacao.json'
    arquivo.write_text(json.dumps(perfil(descricao='Produção sob pedido.\nTambém vendo bebidas.')), encoding='utf-8-sig')
    assert perfil_comercio.importar_instalacao(pasta) and not arquivo.exists()
    assert not perfil_comercio.importar_instalacao(pasta)
    config.COMERCIO_DESCRICAO = ''
    config.COMERCIO_ESTOQUE_PADRAO = 'SIM'
    preferencias.carregar()
    assert perfil_comercio.obter()['descricao'] == 'Produção sob pedido.\nTambém vendo bebidas.'
    assert perfil_comercio.obter()['controlar_estoque'] is False


@pytest.mark.parametrize('existente', ['produto', 'configuracao', 'perfil'])
def test_reinstalacao_preserva_comercio_existente(loja, existente):
    pasta, _, _, _ = loja
    if existente == 'produto':
        item(estoque=9)
    elif existente == 'configuracao':
        preferencias.salvar({'NOME_RESTAURANTE':'Loja existente'})
    else:
        perfil_comercio.salvar(perfil('REVENDA', nome='Loja existente'))
    antes = preferencias.obter()
    produtos = estoque.listar_produtos()
    arquivo = pasta / 'perfil-instalacao.json'
    arquivo.write_text(json.dumps(perfil()), encoding='utf-8')
    assert not perfil_comercio.importar_instalacao(pasta)
    assert preferencias.obter() == antes and estoque.listar_produtos() == produtos
    assert not arquivo.exists()


def test_json_invalido_do_instalador_nao_impede_configuracao_manual(loja):
    pasta, _, _, _ = loja
    (pasta / 'perfil-instalacao.json').write_text('{quebrado', encoding='utf-8')
    with pytest.raises(ValueError,match='inicial inválida'):
        perfil_comercio.importar_instalacao(pasta)
    assert not perfil_comercio.obter()['configurado']
    assert perfil_comercio.salvar(perfil())['configurado']


def test_importacoes_respeitam_perfil_e_permitem_contagem_explicita(loja):
    from src import documentos_estoque as docs, catalogo_avancado
    perfil_comercio.salvar(perfil())
    catalogo_avancado.importar({'csv':'nome;categoria;preco\nPrato;Refeições;20\n', 'confirmar':True})
    r = docs.ler(FileStorage(stream=BytesIO(b'nome;categoria;preco;sku;estoque\nSobremesa;Doces;15;SOB;0\n'),filename='a.csv'),'ficticio')
    assert r['produtos'][0]['controlar_estoque'] is False
    docs.aplicar({'token':r['token'],'produtos':r['produtos'],'obsidian':False},'ficticio')
    assert all(p['estoque'] is None for p in estoque.listar_produtos())
    catalogo_avancado.importar({'csv':'nome;categoria;preco;controlar_estoque;estoque\nÁgua;Bebidas;5;sim;4\n','confirmar':True})
    assert next(p for p in estoque.listar_produtos() if p['nome']=='Água')['estoque'] == 4


def test_perfil_atualiza_referencia_da_ia_sem_prometer_agenda(loja):
    ia.invalidar_cache_prompt()
    antes = ia._system_prompt()
    perfil_comercio.salvar(perfil('SERVICOS', segmento='Oficina', descricao='Revisões e reparos de bicicletas.'))
    depois = ia._system_prompt()
    assert antes != depois and 'Revisões e reparos de bicicletas.' in depois
    assert 'Não prometa agenda' in depois


def test_api_exige_acesso_csrf_e_perfil_admin_e_nao_publica_descricao(loja):
    _, app, c, headers = loja
    assert app.test_client().get('/gestao/api/comercio').status_code == 401
    assert c.put('/gestao/api/comercio',json=perfil()).status_code == 403
    assert c.put('/gestao/api/comercio',json=perfil(),headers=headers).status_code == 200
    from src.publicacao import PaginaPublica
    publico = Client(PaginaPublica(app,lambda:'https://loja-ficticia.example'),Response)
    assert publico.get('/gestao/api/comercio').status_code == 404
    assert 'descricao' not in c.get('/gestao/api/resumo').json['comercio']
    assert c.post('/gestao/api/operadores',json={'nome':'Admin fictício','login':'admin.teste','senha':'senha-ficticia-123','perfil':'ADMIN'},headers=headers).status_code == 200
    assert c.post('/gestao/login',data={'login':'admin.teste','senha':'senha-ficticia-123','csrf_token':headers['X-CSRF-Token']}).status_code == 302
    assert c.post('/gestao/api/operadores',json={'nome':'Atendente fictício','login':'atendente.teste','senha':'senha-ficticia-123','perfil':'ATENDENTE'},headers=headers).status_code == 200
    c.post('/gestao/sair',data={'csrf_token':headers['X-CSRF-Token']})
    c.post('/gestao/login',data={'login':'atendente.teste','senha':'senha-ficticia-123','csrf_token':headers['X-CSRF-Token']})
    assert c.get('/gestao/api/comercio').status_code == 403
    assert c.put('/gestao/api/comercio',json=perfil('REVENDA'),headers=headers).status_code == 403


def test_catalogo_de_servicos_esconde_descricao_interna(loja):
    _, _, c, _ = loja
    perfil_comercio.salvar(perfil('SERVICOS', descricao='Descrição interna fictícia.'))
    item(nome='Revisão',categoria='Serviços',unidade='serv')
    from src.links import gerar_link_pedido
    caminho = '/m/' + gerar_link_pedido('5511999990000').rsplit('/',1)[-1]
    html = c.get(caminho).get_data(as_text=True)
    assert 'Revisão' in html and 'Serviços' in html
    assert 'Descrição interna fictícia.' not in html
