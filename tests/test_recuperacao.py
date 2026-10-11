"""Supervisão e permissões com serviços fictícios; sem contas ou inferências reais."""
from unittest.mock import Mock
import threading

import pytest
import requests

from src import cerebro, config, conexoes, preferencias, recuperacao
from src.db import init_db


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    for chave in preferencias.CAMPOS:
        monkeypatch.setattr(config, chave, getattr(config, chave))
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path/'ficticio.db'))
    config.IA_PROVIDER = 'OLLAMA'
    config.OLLAMA_URL = 'http://127.0.0.1:11434'
    config.OLLAMA_MODEL = 'modelo-ficticio'
    config.CEREBRO_RECUPERACAO_AUTOMATICA = 'SIM'
    init_db(seed_cardapio=False)
    cerebro.arquivo_inicio()
    g = recuperacao.Recuperacao()
    monkeypatch.setattr(recuperacao, '_gerente', g)
    monkeypatch.setattr(conexoes, 'status_jobs', lambda: {})
    monkeypatch.setattr(conexoes, 'status_ollama', lambda: {'online':True, 'modelo_instalado':True})
    monkeypatch.setattr(conexoes, '_waha', Mock(side_effect=AssertionError('Não conectar contas.')))
    monkeypatch.setattr(conexoes, 'baixar_modelo', Mock(side_effect=AssertionError('Não baixar modelos.')))
    return g


def fila(ambiente, monkeypatch, online=False):
    monkeypatch.setattr(conexoes, 'status_ollama', lambda: {'online':online, 'modelo_instalado':online})
    tarefas = []
    monkeypatch.setattr(conexoes, 'iniciar_tarefa', lambda nome, func: tarefas.append((nome, func)))
    return tarefas


def test_pronto_so_apos_verificacao_sem_iniciar_servicos(ambiente, monkeypatch):
    inicio = Mock(); monkeypatch.setattr(conexoes, 'iniciar_tarefa', inicio)
    d = ambiente.verificar(reparar=True, automatico=True)
    assert d['estado'] == 'PRONTO' and d['cofre']['estado'] == 'PRONTO'
    assert d['verificado_em'] and d['tentativas'] == 0
    inicio.assert_not_called()


def test_verificacao_do_cofre_e_de_leitura_nao_cria_pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path/'ficticio.db'))
    assert cerebro.verificar_funcionamento()['estado'] == 'AUSENTE'
    assert not cerebro.diretorio().exists()


def test_recupera_estrutura_ausente_sem_sobrescrever_edicoes(ambiente):
    pasta = cerebro.diretorio()
    estilo = pasta/'Estilo de atendimento.md'
    estilo.write_text('# Voz própria\nFale com calma.', encoding='utf-8')
    perfil = next((pasta/'Atendimentos').glob('*/Perfil.md'))
    perfil.unlink()
    # A pasta está presente; remover um padrão não significa perder a revisão da equipe.
    ambiente.verificar(reparar=True)
    assert not perfil.exists()
    assert estilo.read_text(encoding='utf-8') == '# Voz própria\nFale com calma.'
    estilo.unlink()
    ambiente.verificar(reparar=True)
    assert estilo.is_file() and perfil.is_file()


def test_nova_categoria_prepara_notas_sem_substituir_estilo_existente(ambiente):
    estilo = cerebro.diretorio()/'Estilo de atendimento.md'
    estilo.write_text('# Minha voz\nUse perguntas diretas.', encoding='utf-8')
    config.COMERCIO_CONFIGURADO = 'SIM'
    config.COMERCIO_SEGMENTO = 'Oficina'
    ambiente.verificar(reparar=True)
    assert estilo.read_text(encoding='utf-8') == '# Minha voz\nUse perguntas diretas.'
    assert (cerebro.diretorio()/'Atendimentos/Oficinas e peças/Perfil.md').is_file()


def test_nota_vazia_nao_e_recriada_e_suspensao_e_preservada(ambiente):
    estilo = cerebro.diretorio()/'Estilo de atendimento.md'
    estilo.write_text('', encoding='utf-8')
    d = ambiente.verificar(reparar=True)
    assert d['estado'] == 'ATENCAO' and d['cofre']['estado'] == 'REVISAO'
    assert estilo.read_bytes() == b''


def test_offline_enfileira_uma_recuperacao_sem_trocar_provedor(ambiente, monkeypatch):
    tarefas = fila(ambiente, monkeypatch)
    d = ambiente.verificar(reparar=True, automatico=True)
    assert d['estado'] == 'RECUPERANDO' and d['tentativas'] == 1
    assert tarefas[0][0] == 'ollama'
    preparar = Mock(); monkeypatch.setattr(conexoes, 'iniciar_ollama', preparar)
    monkeypatch.setattr(conexoes, 'status_ollama', lambda: {'online':True,'modelo_instalado':True})
    tarefas[0][1](lambda *args: None)
    assert preparar.call_args.kwargs['ativar'] is False
    assert preparar.call_args.kwargs['permitir_inicio']()
    assert config.IA_PROVIDER == 'OLLAMA'
    conexoes.baixar_modelo.assert_not_called()


def test_intervalos_e_limite_e_retentativa_manual(ambiente, monkeypatch):
    tarefas = fila(ambiente, monkeypatch)
    agora = [100.0];monkeypatch.setattr(recuperacao.time, 'monotonic', lambda: agora[0])
    ambiente.verificar(reparar=True, automatico=True)
    ambiente.verificar(reparar=True, automatico=True)
    assert len(tarefas) == 1
    agora[0] = 160;ambiente.verificar(reparar=True, automatico=True)
    agora[0] = 279;ambiente.verificar(reparar=True, automatico=True)
    assert len(tarefas) == 2
    agora[0] = 280;ambiente.verificar(reparar=True, automatico=True)
    agora[0] = 10000;d=ambiente.verificar(reparar=True, automatico=True)
    assert len(tarefas) == 3 and 'Limite' in d['mensagem']
    ambiente.verificar(reparar=True)
    assert len(tarefas) == 4 and ambiente.situacao()['tentativas'] == 1


@pytest.mark.parametrize('caso', ['desativado','outro_provedor','remoto','ocupado','sem_modelo','encerrado'])
def test_condicoes_que_impedem_inicio_automatico(ambiente, monkeypatch, caso):
    tarefas = fila(ambiente, monkeypatch)
    if caso == 'desativado': config.CEREBRO_RECUPERACAO_AUTOMATICA = 'NAO'
    if caso == 'outro_provedor': config.IA_PROVIDER = 'ANTHROPIC'
    if caso == 'remoto': config.OLLAMA_URL = 'https://ollama-ficticio.example'
    if caso == 'ocupado': monkeypatch.setattr(conexoes,'status_jobs',lambda:{'ollama':{'estado':'EXECUTANDO'}})
    if caso == 'sem_modelo': monkeypatch.setattr(conexoes,'status_ollama',lambda:{'online':True,'modelo_instalado':False})
    if caso == 'encerrado': ambiente.encerrar()
    ambiente.verificar(reparar=True, automatico=True)
    assert not tarefas


@pytest.mark.parametrize('alteracao', ['opcao','provedor','modelo','encerrar'])
def test_revalida_autorizacao_ao_executar_tarefa(ambiente, monkeypatch, alteracao):
    tarefas = fila(ambiente, monkeypatch)
    ambiente.verificar(reparar=True, automatico=True)
    iniciar = Mock();monkeypatch.setattr(conexoes, 'iniciar_ollama', iniciar)
    if alteracao == 'opcao': config.CEREBRO_RECUPERACAO_AUTOMATICA = 'NAO'
    if alteracao == 'provedor': config.IA_PROVIDER = 'ANTHROPIC'
    if alteracao == 'modelo': config.OLLAMA_MODEL = 'outro'
    if alteracao == 'encerrar': ambiente.encerrar()
    tarefas[0][1](lambda *args:None)
    iniciar.assert_not_called()


def test_falha_preparo_fica_visivel_mesmo_com_api_online(ambiente, monkeypatch):
    tarefas = fila(ambiente, monkeypatch)
    ambiente.verificar(reparar=True, automatico=True)
    monkeypatch.setattr(conexoes,'iniciar_ollama',Mock(side_effect=ValueError('Sem memória.')))
    with pytest.raises(ValueError): tarefas[0][1](lambda *args:None)
    monkeypatch.setattr(conexoes,'status_ollama',lambda:{'online':True,'modelo_instalado':True})
    assert ambiente.verificar()['ollama']['estado'] == 'FALHA'
    ambiente.resultado_inferencia(True,config.OLLAMA_URL,config.OLLAMA_MODEL)
    assert ambiente.verificar()['estado'] == 'PRONTO'


def test_tres_falhas_de_inferencia_pedem_recuperacao(ambiente, monkeypatch):
    tarefas = fila(ambiente, monkeypatch, online=True)
    ambiente.resultado_inferencia(False,config.OLLAMA_URL,config.OLLAMA_MODEL)
    assert ambiente.verificar(reparar=True,automatico=True)['estado'] == 'ATENCAO'
    assert not tarefas
    for _ in range(2): ambiente.resultado_inferencia(False,config.OLLAMA_URL,config.OLLAMA_MODEL)
    assert ambiente.verificar(reparar=True,automatico=True)['estado'] == 'RECUPERANDO'
    assert len(tarefas) == 1
    ambiente.resultado_inferencia(True,config.OLLAMA_URL,config.OLLAMA_MODEL)
    assert ambiente.verificar()['estado'] == 'PRONTO'


def test_ignora_resultado_de_modelo_antigo_e_reinicia_limite_quando_config_muda(ambiente, monkeypatch):
    tarefas = fila(ambiente, monkeypatch)
    ambiente.verificar(reparar=True, automatico=True)
    config.OLLAMA_MODEL = 'novo-modelo'
    ambiente.verificar(reparar=True, automatico=True)
    ambiente.resultado_inferencia(False,config.OLLAMA_URL,'modelo-ficticio')
    assert len(tarefas) == 2 and ambiente.situacao()['tentativas'] == 1
    assert ambiente.situacao()['falhas_inferencia'] == 0


def test_verificacoes_concorrentes_nao_enfileiram_duplicatas(ambiente, monkeypatch):
    tarefas = fila(ambiente, monkeypatch)
    ambiente._verificacao.acquire()
    try: ambiente.verificar(reparar=True)
    finally: ambiente._verificacao.release()
    assert not tarefas


def test_nota_derivada_nao_contem_segredos_e_preserva_edicao_manual(ambiente):
    d = ambiente.verificar()
    pasta = cerebro.diretorio();p=pasta/'Estado do funcionamento.md'
    texto=p.read_text(encoding='utf-8');mtime=p.stat().st_mtime_ns
    cerebro.registrar_funcionamento({**d,'mensagem':'senha privada','token':'segredo','verificado_em':'mudou'})
    assert p.stat().st_mtime_ns == mtime and 'senha privada' not in texto
    assert 'atendimento: false' in texto
    assert 'Estado do funcionamento.md' in [n['nome'] for n in cerebro.visualizacao()['notas']]
    assert '[[Estado do funcionamento]]' in (pasta/'Mapa do atendimento.md').read_text(encoding='utf-8')
    assert 'Resumo técnico atualizado' not in cerebro.instrucoes_contexto()
    p.write_text('# Minha nota de estado\nConteúdo preservado.', encoding='utf-8')
    ambiente.verificar()
    assert p.read_text(encoding='utf-8') == '# Minha nota de estado\nConteúdo preservado.'


def test_contexto_ollama_reconhece_atencao_sem_expor_erros_brutos(ambiente, monkeypatch):
    from src import ia
    fila(ambiente, monkeypatch);ambiente.verificar()
    monkeypatch.setattr(ia,'_system_prompt',lambda:'Regras oficiais.')
    prompt=ia._system_prompt_ollama('O atendimento funciona?')
    assert 'ESTADO OPERACIONAL VERIFICADO PELO APLICATIVO: ATENCAO' in prompt
    assert 'não diga que tudo está funcionando normalmente' in prompt
    assert config.OLLAMA_URL not in prompt
    monkeypatch.setattr(cerebro,'instrucoes_contexto',Mock(side_effect=ValueError('Atalho inseguro')))
    assert 'Regras oficiais.' in ia._system_prompt_ollama('Oi')
    assert ambiente.situacao()['cofre']['estado'] == 'ERRO'


def test_telemetria_conta_uma_falha_por_inferencia_e_limpa_apos_sucesso(ambiente, monkeypatch):
    from src import ia
    monkeypatch.setattr(ia._http,'post',Mock(side_effect=requests.ConnectionError()))
    monkeypatch.setattr(ia.time,'sleep',lambda _:None)
    with pytest.raises(ia.IAIndisponivel): ia._chamar_ollama([])
    assert ambiente.situacao()['falhas_inferencia'] == 1
    resposta=Mock(status_code=200);resposta.json.return_value={'message':{'content':'Resposta fictícia'}}
    monkeypatch.setattr(ia._http,'post',Mock(return_value=resposta))
    ia._chamar_ollama([])
    assert ambiente.situacao()['falhas_inferencia'] == 0


def test_iniciar_ollama_revalidacao_bloqueia_processo(ambiente, monkeypatch):
    monkeypatch.setattr(conexoes,'_tags',Mock(side_effect=ValueError('Offline')))
    monkeypatch.setattr(conexoes,'_executable',lambda _: 'ollama-ficticio.exe')
    popen=Mock();monkeypatch.setattr(conexoes.subprocess,'Popen',popen)
    with pytest.raises(ValueError,match='cancelada'):
        conexoes.iniciar_ollama(lambda *args:None,ativar=False,permitir_inicio=lambda:False)
    popen.assert_not_called()


def test_aquecimento_da_recuperacao_nao_reseleciona_ia(ambiente, monkeypatch):
    resposta=Mock();resposta.json.return_value={}
    monkeypatch.setattr(conexoes,'http',lambda:Mock(post=Mock(return_value=resposta)))
    salvar=Mock();monkeypatch.setattr(preferencias,'salvar',salvar)
    conexoes._aquecer_ativar(config.OLLAMA_URL,config.OLLAMA_MODEL,lambda *args:None,ativar=False)
    salvar.assert_not_called()


def test_monitor_para_ao_encerrar_sem_servicos_reais(ambiente, monkeypatch):
    observado=threading.Event()
    monkeypatch.setattr(ambiente,'verificar',lambda **kwargs:observado.set())
    ambiente.iniciar();assert observado.wait(2)
    ambiente.encerrar();assert not ambiente._thread.is_alive()
    assert not ambiente.situacao()['disponivel']
    assert not recuperacao.contexto_operacional()
    assert 'Encerrada ou indisponível' in (cerebro.diretorio()/'Estado do funcionamento.md').read_text(encoding='utf-8')


def test_api_exige_desktop_csrf_e_booleano(ambiente, monkeypatch):
    from src.app import app
    monkeypatch.setitem(app.config,'DESKTOP_TOKEN','token-ficticio')
    monkeypatch.setattr(conexoes,'status_whatsapp',lambda:{'servico':False})
    c=app.test_client()
    assert c.put('/gestao/api/cerebro/recuperacao',json={'automatico':True}).status_code == 401
    c.get('/gestao?acesso=token-ficticio')
    assert c.put('/gestao/api/cerebro/recuperacao',json={'automatico':True}).status_code == 403
    with c.session_transaction() as s: headers={'X-CSRF-Token':s['csrf']}
    assert c.put('/gestao/api/cerebro/recuperacao',json={'automatico':'SIM'},headers=headers).status_code == 400
    assert c.put('/gestao/api/cerebro/recuperacao',json={'automatico':False},headers=headers).status_code == 200
    assert config.CEREBRO_RECUPERACAO_AUTOMATICA == 'NAO'
    agendar=Mock(return_value={'estado':'EXECUTANDO'});monkeypatch.setattr(conexoes,'iniciar_tarefa',agendar)
    assert c.post('/gestao/api/conexoes/cerebro-recuperar',headers=headers).status_code == 202
    assert agendar.call_args.args == ('recuperacao',recuperacao.verificar_recuperar)
    monkeypatch.setattr(cerebro,'situacao',Mock(side_effect=ValueError('Cofre inválido')))
    r=c.get('/gestao/api/conexoes')
    assert r.status_code == 200 and r.json['cerebro']['erro'] and r.json['recuperacao']['disponivel']
    monkeypatch.setitem(app.config,'DESKTOP_TOKEN',None)
    monkeypatch.setattr(__import__('src.gestao',fromlist=['gestao']),'autorizado',lambda:True)
    assert c.put('/gestao/api/cerebro/recuperacao',json={'automatico':True},headers=headers).status_code == 403


def test_gateway_publico_nao_expoe_estado_ou_recuperacao(ambiente):
    from werkzeug.test import Client
    from werkzeug.wrappers import Response
    from src.app import app
    from src.publicacao import PaginaPublica
    c=Client(PaginaPublica(app,lambda:'https://loja-ficticia.example'),Response)
    assert c.get('/gestao/api/conexoes').status_code == 404
    assert c.put('/gestao/api/cerebro/recuperacao',json={'automatico':True}).status_code == 404
    assert c.post('/gestao/api/conexoes/cerebro-recuperar').status_code == 404


def test_atendente_nao_habilita_nem_inicia_recuperacao(ambiente, monkeypatch):
    from src.app import app
    monkeypatch.setitem(app.config,'DESKTOP_TOKEN','token-ficticio')
    c=app.test_client();c.get('/gestao?acesso=token-ficticio')
    with c.session_transaction() as s: h={'X-CSRF-Token':s['csrf']}
    admin={'nome':'Administrador fictício','login':'admin','senha':'senha-ficticia-123','perfil':'ADMIN'}
    assert c.post('/gestao/api/operadores',json=admin,headers=h).status_code == 200
    assert c.post('/gestao/api/operadores',json={**admin,'login':'vendas','perfil':'ATENDENTE'},headers=h).status_code == 200
    c.post('/gestao/sair',headers=h)
    c.post('/gestao/login',data={'login':'vendas','senha':admin['senha'],'csrf_token':h['X-CSRF-Token']})
    assert c.put('/gestao/api/cerebro/recuperacao',json={'automatico':True},headers=h).status_code == 403
    assert c.post('/gestao/api/conexoes/cerebro-recuperar',headers=h).status_code == 403
