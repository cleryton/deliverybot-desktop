"""Orientação local, progresso real e configuração sem efeitos colaterais."""
import pytest
from src import config, preferencias, estoque, tutorial, publicacao, conexoes, processamento
from src.db import init_db


def dados(**campos):
    s = dict(modelo='REVENDA', perfil=False, loja=False, produtos=False, privacidade=False,
             operacao={'whatsapp_ok':False}, endereco_publico=False, abertura_recebida=False)
    return {**s, **campos}


@pytest.mark.parametrize('modelo,trecho', [('REVENDA','foto'), ('PRODUCAO','refeição'), ('SERVICOS','Serviço ou Hora'), ('MISTO','foto')])
def test_guia_respeita_operacao(modelo, trecho):
    steps = tutorial.etapas(dados(modelo=modelo))
    assert len(steps) == 8
    assert trecho in steps[2]['instrucoes'][0]
    assert len({s['id'] for s in steps}) == 8
    assert all(s['pagina'] in {'comercio','configuracoes','produtos','privacidade','conexoes','publicacao','inicio'} for s in steps)


def test_ia_opcional_nao_finge_estar_pronta():
    steps = tutorial.etapas(dados())
    assert steps[5]['opcional'] and steps[5]['concluida'] is None
    assert all(s['concluida'] is False for s in steps if not s['opcional'])
    assert 'não cria um pedido' in steps[-1]['instrucoes'][0]


def test_progresso_independente_e_sem_alterar_estado():
    s = dados(perfil=True, produtos=True)
    steps = tutorial.etapas(s)
    assert [x['id'] for x in steps if x['concluida']] == ['comercio','catalogo']
    assert s == dados(perfil=True, produtos=True)
    assert tutorial.etapas(dados())[0]['concluida'] is False


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path/'tutorial.db'))
    for key in preferencias.CAMPOS | {'MODO_TESTE', 'SEED_CATALOGO'}:
        monkeypatch.setattr(config, key, getattr(config,key))
    for key,value in {'WHATSAPP_PROVIDER':'TESTE','MODO_TESTE':True,'SEED_CATALOGO':False,
                      'COMERCIO_MODELO':'PRODUCAO','COMERCIO_CONFIGURADO':'NAO','COMERCIO_ESTOQUE_PADRAO':'NAO',
                      'BASE_URL':'http://localhost:5000','LGPD_RESPONSAVEL':'','LGPD_CONTATO':'',
                      'NOME_RESTAURANTE':'Minha loja','TELEFONE_RESTAURANTE':''}.items():
        setattr(config,key,value)
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config,'DESKTOP_TOKEN','guia-ficticio')
    monkeypatch.setattr(publicacao, 'situacao', lambda:{'estado':'DESLIGADO'})
    monkeypatch.setattr(processamento, 'ativo', lambda:False)
    monkeypatch.setattr(conexoes,'status_jobs',lambda:{})
    def proibido(*args, **kwargs):
        pytest.fail('A leitura do tutorial iniciou um serviço.')
    monkeypatch.setattr(conexoes,'conectar_whatsapp',proibido)
    monkeypatch.setattr(conexoes,'iniciar_ollama',proibido)
    c=app.test_client()
    c.get('/gestao?acesso=guia-ficticio')
    yield c,app
    estoque.invalidar_catalogo()


def test_api_recalcula_perfil_e_disponibilidade(cliente):
    c,_=cliente
    s=c.get('/gestao/api/preparacao').json
    assert not s['perfil'] and not s['produtos']
    p=estoque.salvar_produto({'nome':'Item fictício','categoria':'Teste','preco':'10','ativo':False})
    assert not c.get('/gestao/api/preparacao').json['produtos']
    estoque.salvar_produto({'nome':p['nome'],'categoria':'Teste','preco':'10','ativo':True},p['id'])
    config.COMERCIO_CONFIGURADO='SIM'
    s=c.get('/gestao/api/preparacao').json
    assert s['tutorial'][0]['concluida'] and s['tutorial'][2]['concluida']
    estoque.salvar_produto({'nome':p['nome'],'categoria':'Teste','preco':'10','controlar_estoque':True,'estoque':0},p['id'])
    assert not c.get('/gestao/api/preparacao').json['produtos']


def test_api_nao_expoe_descricao_nem_credenciais(cliente):
    c,_=cliente
    config.COMERCIO_DESCRICAO='DESCRICAO_PRIVADA_TESTE'
    config.WHATSAPP_TOKEN='SEGREDO_FICTICIO_TESTE'
    r=c.get('/gestao/api/preparacao')
    assert r.status_code == 200
    assert 'DESCRICAO_PRIVADA_TESTE' not in r.text and 'SEGREDO_FICTICIO_TESTE' not in r.text


def test_guia_restrito_ao_administrador(cliente):
    c,app=cliente
    assert app.test_client().get('/gestao/api/preparacao').status_code==401
    with c.session_transaction() as s:
        csrf=s['csrf']
    h={'X-CSRF-Token':csrf}
    assert c.post('/gestao/api/operadores',json={'nome':'Admin fictício','login':'admin.teste','senha':'senha-ficticia-123','perfil':'ADMIN'},headers=h).status_code==200
    assert c.post('/gestao/api/operadores',json={'nome':'Atendente fictício','login':'atendente.teste','senha':'senha-ficticia-123','perfil':'ATENDENTE'},headers=h).status_code==200
    c.post('/gestao/sair',data={'csrf_token':csrf})
    c.post('/gestao/login',data={'login':'atendente.teste','senha':'senha-ficticia-123','csrf_token':csrf})
    assert c.get('/gestao/api/preparacao').status_code==403
