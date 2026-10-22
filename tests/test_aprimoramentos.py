"""Regressões das melhorias, exclusivamente com dados e serviços fictícios."""
import pytest
from src import config, preferencias
from src.db import init_db, get_conn


def test_prompt_ollama_tom_humano_preserva_regras_e_catalogo():
    from src import ia
    ia.invalidar_cache_prompt()
    prompt = ia._system_prompt_ollama()
    assert "próxima, esperta, gentil e segura" in prompt
    assert "PERSONALIDADE DA EQUIPE" in prompt
    assert "acompanhe a animação" in prompt
    assert "Use humor leve só quando o contexto convidar" in prompt
    assert "Em reclamações, atrasos, pagamento ou dados pessoais" in prompt
    assert "Varie o ritmo e o começo das respostas" in prompt
    assert "Personalidade muda o tom, nunca os fatos" in prompt
    assert "Nunca invente preço" in prompt


def test_cofre_obsidian_cria_estrutura_e_preserva_notas_editadas():
    from src import cerebro
    situacao = cerebro.situacao()
    nota = __import__('pathlib').Path(situacao['arquivo'])
    assert situacao['cofre_obsidian']
    assert nota.is_file() and nota.name == 'Início.md'
    assert (nota.parent / '.obsidian' / 'app.json').is_file()
    assert (nota.parent / 'Estilo de atendimento.md').is_file()
    assert (nota.parent / 'Informações da loja.md').is_file()
    assert '[[Perguntas frequentes]]' in nota.read_text(encoding='utf-8')
    configuracao = nota.parent / '.obsidian' / 'app.json'
    configuracao.write_text('{"vimMode": true}\n', encoding='utf-8')
    cerebro.situacao()
    assert configuracao.read_text(encoding='utf-8') == '{"vimMode": true}\n'
    estilo = nota.parent / 'Estilo de atendimento.md'
    estilo.write_text('# Estilo customizado\nUse linguagem simples e acolhedora.\n', encoding='utf-8')
    cerebro.arquivo_estilo()
    assert 'Use linguagem simples e acolhedora.' in cerebro.instrucoes_contexto()
    assert estilo.read_text(encoding='utf-8').startswith('# Estilo customizado')


def test_cofre_obsidian_so_le_conhecimento_explicitamente_aprovado():
    from src import cerebro
    cerebro.situacao()
    pasta = cerebro.diretorio() / 'Conhecimento'
    (pasta / 'Entrega.md').write_text('---\natendimento: true\n---\n# Entrega\n\nEntregamos na região central até 18h.\n', encoding='utf-8')
    (pasta / 'Rascunho.md').write_text('---\natendimento: false\n---\n# Rascunho\n\nNão deve aparecer no prompt.\n', encoding='utf-8')
    contexto = cerebro.instrucoes_contexto()
    assert 'Entregamos na região central até 18h.' in contexto
    assert 'Não deve aparecer no prompt.' not in contexto
    assert 'Informe dias, horários e canais oficiais.' not in contexto


def test_restaurar_snapshot_obsidian_e_seguro_e_preserva_notas_extras():
    from src import cerebro
    cerebro.situacao()
    pasta = cerebro.diretorio()
    extras = pasta / 'Conhecimento' / 'Nota adicional.md'
    extras.write_text('Esta nota não está no snapshot.', encoding='utf-8')
    quantidade = cerebro.restaurar_snapshot({'Estilo de atendimento.md': b'# Voz anterior\nTexto original.\n'})
    assert quantidade == 1
    assert 'Texto original.' in (pasta / 'Estilo de atendimento.md').read_text(encoding='utf-8')
    assert extras.read_text(encoding='utf-8') == 'Esta nota não está no snapshot.'
    with pytest.raises(ValueError):
        cerebro.restaurar_snapshot({'../fora.md': b'nao gravar'})
    assert not (pasta.parent / 'fora.md').exists()


def test_backup_criptografado_inclui_notas_do_obsidian():
    from src import backups, cerebro
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(':memory:')) as backup_antigo:
        assert backups.snapshot_no_banco(backup_antigo) is None
    cerebro.situacao()
    pasta = cerebro.diretorio()
    nota = pasta / 'Conhecimento' / 'Entrega.md'
    nota.write_text('---\natendimento: true\n---\n# Entrega\n\nÁrea central.\n', encoding='utf-8')
    caminho = backups.criar('senha-ficticia-com-mais-de-12')
    backups.verificar_arquivo(caminho, 'senha-ficticia-com-mais-de-12')
    dados = backups.abrir_arquivo(caminho, 'senha-ficticia-com-mais-de-12')
    with closing(sqlite3.connect(':memory:')) as banco:
        banco.deserialize(dados)
        snapshot = backups.snapshot_no_banco(banco)
    assert snapshot['Conhecimento/Entrega.md'].decode('utf-8').find('Área central.') >= 0
    assert '.obsidian/app.json' in snapshot
    with get_conn() as banco_atual:
        assert not banco_atual.execute("SELECT 1 FROM sqlite_master WHERE name='deliverybot_cerebro_snapshot'").fetchone()


def test_prompt_ollama_aplica_nota_apenas_como_preferencia_de_estilo(monkeypatch):
    from src import ia, cerebro
    monkeypatch.setattr(ia, '_system_prompt', lambda: 'REGRAS E CATÁLOGO')
    monkeypatch.setattr(cerebro, 'instrucoes_contexto', lambda: 'Use tom acolhedor e direto.')
    prompt = ia._system_prompt_ollama()
    assert 'REGRAS E CATÁLOGO' in prompt
    assert 'Use tom acolhedor e direto.' in prompt
    assert 'informações locais explicitamente aprovadas pela equipe' in prompt
    assert 'Catálogo, preços, estoque, pedidos e disponibilidade em tempo real' in prompt


def test_permissoes_auditoria_e_revogacao(cliente):
    c,h=cliente
    admin={'nome':'Administrador fictício','login':'admin','senha':'senha-admin-ficticia','perfil':'ADMIN'}
    assert c.post('/gestao/api/operadores',json={**admin,'perfil':'ATENDENTE'},headers=h).status_code==400
    uid=c.post('/gestao/api/operadores',json=admin,headers=h).json['id']
    assert c.put(f'/gestao/api/operadores/{uid}',json={'ativo':False,'perfil':'ADMIN'},headers=h).status_code==400
    funcionario=c.post('/gestao/api/operadores',json={**admin,'login':'vendas','perfil':'ATENDENTE'},headers=h).json['id']
    assert c.post('/gestao/api/produtos',json={'nome':'Caderno','categoria':'Papelaria','preco':10,'custo':4},headers=h).status_code==201
    contas=c.get('/gestao/api/operadores').json
    assert all('senha_hash' not in u and 'versao' not in u for u in contas)
    c.post('/gestao/sair',headers=h)
    assert c.get('/gestao/api/produtos').status_code==401
    assert c.get('/gestao').headers['Referrer-Policy']=='same-origin'
    assert c.post('/gestao/login',data={'login':'vendas','senha':admin['senha'],'csrf_token':h['X-CSRF-Token']},headers={'Origin':'null'}).status_code==403
    assert c.post('/gestao/login',data={'login':'vendas','senha':admin['senha'],'csrf_token':h['X-CSRF-Token']}).status_code==302
    assert c.get('/gestao/api/produtos').status_code==200
    assert 'custo' not in c.get('/gestao/api/produtos').json[0]
    for caminho in ['configuracoes','backup','operadores','relatorios','privacidade','rotinas','preparacao']:
        assert c.get('/gestao/api/'+caminho).status_code in {403,405}
    assert c.post('/gestao/api/produtos',json={},headers=h).status_code==403
    assert c.get('/gestao/api/humano').status_code==200
    c.post('/gestao/sair',headers=h)
    assert c.post('/gestao/login',data={'login':'admin','senha':admin['senha'],'csrf_token':h['X-CSRF-Token']}).status_code==302
    assert c.put(f'/gestao/api/operadores/{funcionario}',json={'ativo':False,'perfil':'ATENDENTE'},headers=h).status_code==200
    assert any(a['operador_id']==uid and a['acao']=='gestao.produtos' for a in c.get('/gestao/api/operadores/auditoria').json)


def test_tema_persistente_com_acesso_csrf_e_login(cliente):
    from src.app import app
    from src import aparencia
    c, h = cliente
    outro = app.test_client()
    assert outro.get('/gestao/api/aparencia').status_code == 401
    assert outro.put('/gestao/api/aparencia', json={'tema':'escuro'}, headers=h).status_code == 401
    assert c.get('/gestao/api/aparencia').json == {'tema':'sistema'}
    assert c.put('/gestao/api/aparencia', json={'tema':'escuro'}).status_code == 403
    assert c.put('/gestao/api/aparencia', json={'tema':'escuro'}, headers={**h,'Origin':'https://outro.example'}).status_code == 403
    for invalido in ['dark', '<script>', None, 1, ['escuro']]:
        assert c.put('/gestao/api/aparencia', json={'tema':invalido}, headers=h).status_code == 400
    assert aparencia.tema() == 'sistema'
    assert c.put('/gestao/api/aparencia', json={'tema':'escuro'}, headers=h).json == {'tema':'escuro'}
    assert 'data-theme-choice="escuro"' in c.get('/gestao').text
    # Nova conexão lê a preferência gravada, sem depender do armazenamento do navegador.
    resposta = outro.get('/gestao?acesso=preparacao-ficticia', follow_redirects=True)
    assert resposta.status_code == 200 and 'data-theme-choice="escuro"' in resposta.text
    c.post('/gestao/api/operadores', json={'nome':'Responsável','login':'admin','senha':'senha-ficticia-123','perfil':'ADMIN'}, headers=h)
    c.post('/gestao/sair', headers=h)
    assert 'data-theme-choice="escuro"' in c.get('/gestao').text
    assert c.put('/gestao/api/aparencia', json={'tema':'claro'}, headers=h).status_code == 200
    assert 'data-theme-choice="claro"' in c.get('/gestao').text
    with get_conn() as conn:
        conn.execute("UPDATE configuracoes SET valor='valor-antigo' WHERE chave='APARENCIA_TEMA'")
    assert aparencia.tema() == 'sistema'


def test_ponte_nativa_exige_cookie_assinado_e_perfil(cliente):
    from src.app import app
    from src import operadores
    from http.cookies import SimpleCookie
    from unittest.mock import Mock
    c,h=cliente
    c.post('/gestao/api/operadores',json={'nome':'Responsável','login':'admin','senha':'senha-ficticia-123','perfil':'ADMIN'},headers=h)
    janela=Mock()
    janela.get_cookies.return_value=[SimpleCookie('session='+c.get_cookie('session').value)]
    operadores.validar_sessao_nativa(app,janela)
    janela.get_cookies.return_value=[SimpleCookie('session=adulterado')]
    with pytest.raises(ValueError):
        operadores.validar_sessao_nativa(app,janela)
    c.post('/gestao/sair',headers=h)
    janela.get_cookies.return_value=[SimpleCookie('session='+c.get_cookie('session').value)]
    with pytest.raises(ValueError):
        operadores.validar_sessao_nativa(app,janela)
    operadores.validar_sessao_nativa(app,janela,administrador=False)


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


def test_resposta_antiga_nao_atravessa_pausa_humana(cliente,monkeypatch):
    from src import processamento,humano,whatsapp
    from unittest.mock import Mock
    config.WHATSAPP_PROVIDER='LOCAL';config.MODO_TESTE=False
    monkeypatch.setattr(processamento,'_servico_pronto',lambda:True)
    enviar=Mock();monkeypatch.setattr(whatsapp,'enviar_mensagem',enviar)
    telefone='5511999990077'
    with get_conn() as c:
        c.execute("INSERT INTO tarefas_bot(chave,telefone,texto,origem,resposta,estado) VALUES(?,?,?,?,?,'PENDENTE')",('ficticia',telefone,'4','WAHA','Catálogo antigo'))
    humano.controlar(telefone,'assumir')
    processamento._parar.clear()
    # A transferência já conclui a tarefa e preserva a entrada para a equipe.
    assert not processamento.processar_proxima()
    assert humano.conversa(telefone)[0]['conteudo']=='4'
    with get_conn() as c:
        assert c.execute("SELECT estado,resposta FROM tarefas_bot WHERE chave='ficticia'").fetchone()[:]==('CONCLUIDA',None)
    enviar.assert_not_called()


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
    assert 'privacidade' in bot.processar_mensagem(t,'PRIVACIDADE').casefold()
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
    p=estoque.salvar_produto({'nome':'Tecido','categoria':'Materiais','preco':10,'custo':4,'unidade':'m','fracionado':True,'estoque':1.5,'variacao':'Azul','familia':'Tecidos'})
    pedido=pedidos.criar_pedido('5511999990033','Cliente fictício',[{'produto_id':p['id'],'quantidade':'0.250'}],'Dinheiro')
    assert pedido['total_pedido']==2.5
    assert estoque.listar_produtos()[0]['estoque']==1.25
    assert pedido['itens'][0]['produto_nome']=='Tecido · Azul'
    estoque.salvar_produto({**p,'custo':8,'ativo':True,'controlar_estoque':True},p['id'])
    # Data fixa evita divergência entre o relógio local e o timestamp UTC do SQLite.
    with get_conn() as conn:
        conn.execute("UPDATE pedidos SET criado_em='2026-10-10 12:00:00' WHERE id=?", (pedido['id'],))
    hoje='2026-10-10'
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
    assert r.status_code==303
    assert c.get(r.location).status_code==200
    assert estoque.listar_produtos()[0]['estoque']==1.5
