"""Eventos e Graph simulados; nenhuma conta, telefone ou envio real nos testes."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
import requests

from src import config, preferencias, meta_custos as custos, meta_oficial as meta, whatsapp, conexoes
from src.db import get_conn, init_db

NUMERO, WABA, NOVO = '123456789000', '987654321000', '123456789111'
BASE = datetime(2026, 10, 13, 15, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'loja.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    for k in preferencias.CAMPOS | {'MODO_TESTE', 'WHATSAPP_API_URL'}:
        monkeypatch.setattr(config, k, getattr(config, k))
    preferencias.aplicar({'WHATSAPP_PROVIDER':'META', 'WHATSAPP_PHONE_NUMBER_ID':NUMERO,
        'WHATSAPP_BUSINESS_ACCOUNT_ID':WABA, 'WHATSAPP_META_AMBIENTE':'TESTE',
        'WHATSAPP_TOKEN':'token-ficticio', 'WHATSAPP_VERIFY_TOKEN':'verificacao-ficticia', 'WHATSAPP_APP_SECRET':'segredo-ficticio', 'IA_PROVIDER':''})
    monkeypatch.setattr(custos, 'agora', lambda: BASE)
    init_db()


def evento(estado='delivered', chave='mensagem-ficticia', pricing=None, numero=NUMERO, waba=WABA, data=None, destino='5511999990000'):
    s={'id':chave,'status':estado,'timestamp':str(int((data or BASE).timestamp())),'recipient_id':destino}
    if pricing is not None:s['pricing']=pricing
    return {'object':'whatsapp_business_account','entry':[{'id':waba,'changes':[{'field':'messages','value':{'metadata':{'phone_number_id':numero},'statuses':[s]}}]}]}


def preco(cobravel=True,categoria='utility',modelo='PMP'):
    return {'billable':cobravel,'category':categoria,'pricing_model':modelo}


def tarifa(**valores):
    custos.configurar({'tarifas':valores})


def total(ambiente='TODOS'):
    return custos.relatorio('2026-10',ambiente)


def test_cobra_uma_vez_so_apos_entrega_e_nao_guarda_dados_do_cliente():
    tarifa(utility='0.123456')
    custos.registrar_envio({'messages':[{'id':'mensagem-ficticia'}]})
    custos.registrar_status(evento('sent',pricing=preco()))
    assert total()['totais']['estimativa_micros']==0
    assert total()['totais']['entregues']==0
    for estado in ('delivered','read','sent','delivered','read'):
        custos.registrar_status(evento(estado,pricing=preco()))
    r=total()
    assert r['totais']['enviadas']==r['totais']['entregues']==1
    assert r['totais']['estimativa_micros']==123456
    assert r['mensagens'][0]['estado']=='read'
    with get_conn() as c:
        registro=dict(c.execute('SELECT * FROM meta_mensagens_custo').fetchone())
    assert '5511999990000' not in json.dumps(registro)
    assert 'mensagem-ficticia' not in json.dumps(registro)
    assert 'telefone' not in registro and 'texto' not in registro


def test_falha_e_envio_aceito_sem_entrega_nao_geram_estimativa():
    tarifa(utility='0.5')
    custos.registrar_status(evento('failed',pricing=preco()))
    assert total()['totais']['estimativa_micros']==0
    assert total()['totais']['falhas']==1


def test_gratuidade_so_e_confirmada_por_billable_booleano():
    custos.registrar_status(evento(pricing=preco(False)))
    custos.registrar_status(evento(chave='sem-preco',pricing={'category':'service'}))
    custos.registrar_status(evento(chave='texto-falso',pricing={'billable':'false','category':'service'}))
    r=total()
    assert r['totais']['gratuitas']==1
    assert r['totais']['sem_estimativa']==2 and r['incompleto']


def test_preco_do_envio_nao_e_tratado_como_cobranca_confirmada():
    tarifa(utility='0.1')
    custos.registrar_status(evento('sent',pricing=preco()))
    custos.registrar_status(evento())
    assert total()['mensagens'][0]['cobravel'] is None
    assert total()['mensagens'][0]['estimativa_micros'] is None


def test_evento_antigo_nao_reverte_cobranca_confirmada(monkeypatch):
    tarifa(utility='0.1')
    leitura=BASE+timedelta(minutes=1)
    monkeypatch.setattr(custos,'agora',lambda:leitura)
    custos.registrar_status(evento('read',pricing=preco(),data=leitura))
    custos.registrar_status(evento('delivered',pricing=preco(False),data=BASE))
    custos.registrar_status(evento('sent',pricing=preco(False),data=BASE))
    assert total()['mensagens'][0]['cobravel']==1
    assert total()['mensagens'][0]['estimativa_micros']==100000


@pytest.mark.parametrize('pricing,destino',[(preco(),'5511999990000'),(preco(categoria='nova_categoria'),'5511999990000'),(preco(modelo='CBP'),'5511999990000'),(preco(),'14155550000'),(None,'5511999990000')])
def test_tarifa_ausente_categoria_desconhecida_conversa_ou_mercado_nao_inventam_zero(pricing,destino):
    tarifa(service='0.1')
    custos.registrar_status(evento(pricing=pricing,destino=destino))
    assert total()['mensagens'][0]['estimativa_micros'] is None
    assert total()['incompleto']


def test_alterar_tarifa_nao_reescreve_historico_nem_evento_repetido(monkeypatch):
    tarifa(utility='0.1')
    custos.registrar_status(evento(pricing=preco()))
    monkeypatch.setattr(custos,'agora',lambda:BASE+timedelta(minutes=1))
    tarifa(utility='0.2')
    custos.registrar_status(evento('read',pricing=preco()))
    custos.registrar_status(evento(chave='nova',pricing=preco(),data=BASE+timedelta(minutes=1)))
    assert total()['totais']['estimativa_micros']==300000


def test_evento_atrasado_usa_tarifa_vigente_na_data_de_entrega(monkeypatch):
    tarifa(utility='0.1')
    monkeypatch.setattr(custos,'agora',lambda:BASE+timedelta(minutes=2))
    tarifa(utility='0.3')
    custos.registrar_status(evento(pricing=preco()))
    assert total()['totais']['estimativa_micros']==100000


def test_sem_precificacao_no_primeiro_evento_e_confirmada_depois():
    tarifa(utility='0.2')
    custos.registrar_status(evento())
    custos.registrar_status(evento('read',pricing=preco()))
    assert total()['totais']['estimativa_micros']==200000


def test_mercado_ausente_no_envio_e_identificado_na_entrega():
    tarifa(utility='0.2')
    custos.registrar_status(evento('sent',destino=None))
    custos.registrar_status(evento(pricing=preco()))
    assert total()['totais']['estimativa_micros']==200000


def test_orcamento_considera_so_producao_e_avisa_dados_pendentes():
    tarifa(utility='0.8')
    custos.configurar({'limite':'1','alerta_percentual':80})
    custos.registrar_status(evento(pricing=preco()))
    assert total()['orcamento']['gasto_micros']==0
    config.WHATSAPP_META_AMBIENTE='PRODUCAO'
    custos.registrar_status(evento(chave='producao',pricing=preco()))
    assert total()['orcamento']['nivel']=='ATENCAO'
    custos.registrar_status(evento(chave='producao-2',pricing=preco()))
    assert total()['orcamento']['nivel']=='EXCEDIDO'
    custos.registrar_status(evento(chave='pendente'))
    assert total('TESTE')['orcamento']['incompleto']
    assert total('TESTE')['totais']['enviadas']==1


def test_mes_usa_data_de_entrega_no_fuso_sao_paulo(monkeypatch):
    data=datetime(2026,11,1,2,59,tzinfo=timezone.utc)
    monkeypatch.setattr(custos,'agora',lambda:data)
    custos.registrar_status(evento(pricing=preco(False),data=data))
    assert total()['totais']['entregues']==1
    assert custos.relatorio('2026-11')['totais']['entregues']==0


@pytest.mark.parametrize('valor',[True,-1,'NaN','Infinity','0.0000001',{},'100000001'])
def test_valores_financeiros_invalidos_nao_sao_gravados(valor):
    with pytest.raises(ValueError):custos.configurar({'tarifas':{'utility':valor}})
    assert custos.configuracao()['tarifas']['utility'] is None


def test_eventos_de_contas_desconhecidas_ou_malformados_nao_criam_custos():
    assert custos.registrar_status(evento(numero=NOVO,pricing=preco()))==0
    assert custos.registrar_status(evento(waba='outra-conta',pricing=preco()))==0
    for p in ({'entry':None},{'entry':[None,{'changes':[None]}]},{'entry':[{'changes':False}]}):
        assert custos.registrar_status(p)==0
    assert total()['totais']['enviadas']==0


def respostas_graph(monkeypatch,numero=NOVO):
    chamada=Mock(side_effect=[Mock(status_code=200,json=Mock(return_value={'id':numero,'display_phone_number':'+55 11 3000-0000','verified_name':'Loja fictícia'})),Mock(status_code=200,json=Mock(return_value={'data':[{'id':numero}]}))])
    monkeypatch.setattr(meta._http,'get',chamada)
    return chamada


def candidato(**extra):
    return {'WHATSAPP_PHONE_NUMBER_ID':NOVO,'WHATSAPP_BUSINESS_ACCOUNT_ID':WABA,'numero_anterior':NUMERO,'confirmar_migracao':True,**extra}


def test_migracao_valida_numero_conta_e_preserva_historico_e_segredos(monkeypatch):
    custos.registrar_status(evento(pricing=preco(False)))
    consulta=respostas_graph(monkeypatch)
    r=meta.migrar(candidato())
    assert r['salvo'] and config.WHATSAPP_PHONE_NUMBER_ID==NOVO
    assert config.WHATSAPP_META_AMBIENTE=='PRODUCAO'
    assert config.WHATSAPP_TOKEN=='token-ficticio'
    assert config.WHATSAPP_API_URL.endswith('/'+NOVO+'/messages')
    for args,kw in consulta.call_args_list:
        assert args[0].startswith('https://graph.facebook.com/v25.0/')
        assert kw['allow_redirects'] is False and kw['timeout']==10
        assert kw['headers']['Authorization']=='Bearer token-ficticio'
    with get_conn() as c:
        assert c.execute('SELECT COUNT(*) FROM meta_numeros').fetchone()[0]==2
        assert c.execute('SELECT COUNT(*) FROM meta_mensagens_custo').fetchone()[0]==1
        protegido=c.execute("SELECT valor FROM configuracoes WHERE chave='WHATSAPP_TOKEN'").fetchone()
    assert 'token-ficticio' not in json.dumps(r)
    custos.registrar_status(evento('read',pricing=preco(False)))
    assert total()['totais']['enviadas']==1


@pytest.mark.parametrize('campo,valor',[('numero_anterior','outro'),('confirmar_migracao',False)])
def test_migracao_exige_confirmacao_e_configuracao_atual(campo,valor,monkeypatch):
    consulta=respostas_graph(monkeypatch)
    with pytest.raises(ValueError):meta.migrar(candidato(**{campo:valor}))
    consulta.assert_not_called()
    assert config.WHATSAPP_PHONE_NUMBER_ID==NUMERO


@pytest.mark.parametrize('estado',['PENDENTE','PROCESSANDO','ENVIANDO','FALHOU','VERIFICAR'])
def test_troca_com_pendencia_e_bloqueada_inclusive_pelas_preferencias(estado,monkeypatch):
    with get_conn() as c:
        c.execute('INSERT INTO tarefas_bot(origem,chave,telefone,texto,estado) VALUES(?,?,?,?,?)',('META:default','ficticia','5511999990000','oi',estado))
    consulta=respostas_graph(monkeypatch)
    with pytest.raises(ValueError,match='pendentes'):meta.migrar(candidato())
    consulta.assert_not_called()
    with pytest.raises(ValueError,match='pendentes'):preferencias.salvar({'WHATSAPP_PHONE_NUMBER_ID':NOVO})
    # Renovar o token continua possível para recuperar uma fila parada.
    preferencias.salvar({'WHATSAPP_TOKEN':'novo-token-ficticio'})
    assert config.WHATSAPP_PHONE_NUMBER_ID==NUMERO


def test_numero_nao_pertence_a_conta_nao_troca_conexao(monkeypatch):
    respostas_graph(monkeypatch,numero=NUMERO)
    with pytest.raises(ValueError):meta.migrar(candidato())
    assert config.WHATSAPP_PHONE_NUMBER_ID==NUMERO


@pytest.mark.parametrize('status',[301,400,401,403,500])
def test_erro_meta_e_redirecionamento_nao_expoem_token(status,monkeypatch):
    monkeypatch.setattr(meta._http,'get',Mock(return_value=Mock(status_code=status)))
    with pytest.raises(ValueError) as e:meta.verificar(candidato())
    assert config.WHATSAPP_TOKEN not in str(e.value)


def test_falha_da_contabilidade_nao_repete_envio_ja_aceito(monkeypatch):
    resposta=Mock(json=Mock(return_value={'messages':[{'id':'id-ficticio'}]}))
    envio=Mock(return_value=resposta)
    monkeypatch.setattr(whatsapp._http,'post',envio)
    monkeypatch.setattr(custos,'registrar_envio',Mock(side_effect=RuntimeError('indisponível')))
    assert whatsapp._enviar_via_meta('5511999990000','Teste fictício')['messages']
    envio.assert_called_once()


def test_webhook_exige_assinatura_e_numero_atual(monkeypatch):
    from src.app import app
    p=evento(pricing=preco(False))
    raw=json.dumps(p).encode()
    cliente=app.test_client()
    assert cliente.post('/webhook',data=raw,content_type='application/json').status_code==403
    assert total()['totais']['enviadas']==0
    headers={'X-Hub-Signature-256':'sha256='+hmac.new(config.WHATSAPP_APP_SECRET.encode(),raw,hashlib.sha256).hexdigest()}
    assert cliente.post('/webhook',data=raw,content_type='application/json',headers=headers).status_code==200
    assert total()['totais']['entregues']==1
    monkeypatch.setattr(whatsapp,'extrair_mensagem_recebida',lambda payload:{'texto':'oi','telefone':'5511999990000'})
    config.WHATSAPP_PHONE_NUMBER_ID=NOVO
    fila=Mock()
    monkeypatch.setattr('src.processamento.enfileirar',fila)
    assert cliente.post('/webhook',data=raw,content_type='application/json',headers=headers).status_code==200
    fila.assert_not_called()


def test_meta_nao_consulta_waha_para_status(monkeypatch):
    waha=Mock()
    monkeypatch.setattr(conexoes,'_waha',waha)
    r=conexoes.status_whatsapp()
    assert r['estado']=='META_CONFIGURADA' and not r['conectado']
    waha.assert_not_called()


def test_validacao_nao_segue_url_da_paginacao_da_meta(monkeypatch):
    get=Mock(side_effect=[Mock(status_code=200,json=Mock(return_value={'id':NOVO})),
        Mock(status_code=200,json=Mock(return_value={'data':[],'paging':{'next':'http://host-malicioso.local/','cursors':{'after':'cursor-ficticio'}}})),
        Mock(status_code=200,json=Mock(return_value={'data':[{'id':NOVO}]}))])
    monkeypatch.setattr(meta._http,'get',get)
    assert meta.verificar(candidato())['validado']
    assert all(c.args[0].startswith('https://graph.facebook.com/') for c in get.call_args_list)
    assert get.call_args_list[-1].kwargs['params']['after']=='cursor-ficticio'


def test_numero_alterado_durante_consulta_nao_e_sobrescrito(monkeypatch):
    def consulta(caminho,*args):
        if caminho==NOVO:return {'id':NOVO}
        preferencias.salvar({'WHATSAPP_PHONE_NUMBER_ID':'123456789222'})
        return {'data':[{'id':NOVO}]}
    monkeypatch.setattr(meta,'_consulta',consulta)
    with pytest.raises(ValueError,match='alterado durante'):meta.migrar(candidato())
    assert config.WHATSAPP_PHONE_NUMBER_ID=='123456789222'


def test_orcamento_exige_centavos_e_periodo_extremo_e_validado():
    with pytest.raises(ValueError):custos.configurar({'limite':'0.005'})
    with pytest.raises(ValueError):custos.relatorio('9999-12')


def test_endpoints_restritos_ao_administrador_e_csrf(monkeypatch):
    from src.app import app
    from src import operadores
    monkeypatch.setitem(app.config,'DESKTOP_TOKEN','teste-local')
    cliente=app.test_client()
    assert cliente.get('/gestao/api/meta/custos').status_code==401
    cliente.get('/gestao?acesso=teste-local',follow_redirects=True)
    assert cliente.put('/gestao/api/meta/custos',json={'limite':'10'}).status_code==403
    with cliente.session_transaction() as s:csrf=s['csrf']
    assert cliente.put('/gestao/api/meta/custos',json={'limite':'10'},headers={'X-CSRF-Token':csrf}).status_code==200
    assert cliente.get('/gestao/api/meta/custos').status_code==200
    monkeypatch.setattr(operadores,'admin',lambda:False)
    monkeypatch.setattr(operadores,'existem',lambda:True)
    for perfil in ('ATENDENTE','CAIXA'):
        monkeypatch.setattr(operadores,'usuario',lambda dados=None,p=perfil:{'id':7,'perfil':p})
        for endpoint in ('custos','tarifas','situacao'):
            assert cliente.get('/gestao/api/meta/'+endpoint).status_code==403
        assert cliente.post('/gestao/api/meta/migrar',json=candidato(),headers={'X-CSRF-Token':csrf}).status_code==403
