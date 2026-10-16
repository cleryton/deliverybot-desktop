"""Medidas sintéticas para testar o analisador; não são resultados de pesquisa."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('avaliacao_tcc', ROOT/'packaging/avaliacao_tcc.py')
av = importlib.util.module_from_spec(spec)
spec.loader.exec_module(av)


def coleta():
    d = av.planejar('2.40.0','a'*40,False)
    d['origem'] = 'SIMULACAO'
    d['ambiente'].update(modelo='modelo-ficticio', modelo_digest='b'*64, ollama_versao='ficticia',
        cpu='CPU fictícia', gpu='Sem GPU', ram_gb=16, temperatura=0.3, seed=None,
        janela_contexto=4096, prompt_a_sha256='c'*64, prompt_b_sha256='d'*64,
        catalogo_sha256='e'*64, notas_sha256='f'*64, aquecimento_excluido=True)
    for r in d['registros']:
        r.update(estado='OK',chamou_modelo=True,duracao_ms=100,fallback=False,factual_correto=True,
                 riscos={k:False for k in av.RISCOS},
                 avaliacoes={a:{k:3 if r['condicao']=='A' else 4 for k in av.DIMENSOES} for a in ('R01','R02')})
    return d


def test_plano_tem_72_tentativas_sem_notas_nem_resultados_fabricados():
    d = av.planejar('2.40.0','a'*40,True)
    assert len(d['registros']) == 72
    assert {av._registro(r) for r in d['registros']} == av.COMBINACOES
    pares = [d['registros'][i]['condicao'] for i in range(0,72,2)]
    assert pares.count('A') == pares.count('B') == 18
    s = av.analisar(d)
    assert not s['coleta_completa']
    assert s['condicoes']['A']['factual']['proporcao'] is None
    assert s['comparacao_modelo']['pares_elegiveis'] == 0


def test_diferencas_pareadas_e_denominadores_sem_afirmar_significancia():
    s = av.analisar(coleta())
    assert s['coleta_completa'] and s['origem_declarada'] == 'SIMULACAO'
    assert s['condicoes']['A']['estados'] == {'PENDENTE':0,'OK':36,'ERRO':0,'TIMEOUT':0,'BLOQUEADA':0}
    assert s['condicoes']['A']['factual'] == {'numerador':36,'denominador':36,'proporcao':1}
    c = s['comparacao_modelo']
    assert c['pares_elegiveis'] == 36
    assert c['editorial']['naturalidade'] == {'n_pares':36,'delta_medio_b_menos_a':1,'b_maior':36,'iguais':0,'b_menor':0}
    assert 'significancia' not in s
    assert any('SIMULACAO' in texto for texto in s['limites'])


def test_timeout_e_erro_nao_desaparecem_e_nao_recebem_nota():
    d = coleta()
    for estado,r in zip(('TIMEOUT','ERRO'),d['registros'][:2]):
        r.update(estado=estado,factual_correto=None,riscos={k:None for k in av.RISCOS},
            avaliacoes={a:{k:None for k in av.DIMENSOES} for a in ('R01','R02')},duracao_ms=10000)
    s = av.analisar(d)
    for cond in ('A','B'):
        c = s['condicoes'][cond]
        assert c['conclusao']['denominador'] == 36 and c['conclusao']['numerador'] == 35
        assert c['factual']['denominador'] == 35
    assert s['condicoes']['A']['latencias']['timeout']['p95_ms'] == 10000
    assert s['comparacao_modelo']['pares_elegiveis'] == 35


def test_bloqueio_de_protecao_fica_separado_de_falha_e_resposta_correta():
    d=coleta();r=d['registros'][0]
    r.update(estado='BLOQUEADA',chamou_modelo=False,factual_correto=None,riscos={k:None for k in av.RISCOS},
        avaliacoes={a:{k:None for k in av.DIMENSOES} for a in ('R01','R02')})
    s=av.analisar(d)['condicoes'][r['condicao']]
    assert s['estados']['BLOQUEADA']==1 and s['estados']['ERRO']==0
    assert s['latencias']['bloqueada']['n']==1
    assert s['factual']['proporcao']==1 and s['factual_por_tentativa']['proporcao']==35/36


def test_fallback_e_resposta_local_nao_recebem_credito_do_modelo():
    d = coleta()
    d['registros'][0]['chamou_modelo'] = False
    d['registros'][2]['fallback'] = True
    s = av.analisar(d)
    assert s['comparacao_modelo']['pares_elegiveis'] == 34
    local = sum(c['latencias']['local']['n'] for c in s['condicoes'].values())
    fallback = sum(c['latencias']['fallback']['n'] for c in s['condicoes'].values())
    assert local == fallback == 1


def test_percentil_r7_sem_excluir_extremos_e_sem_confundir_com_media():
    assert av.percentil([],0.95) is None
    assert av.percentil([42],0.95) == 42
    assert av.percentil([0,100],0.95) == 95
    assert av.percentil([100,0,10],0.95) == pytest.approx(91)


def test_sintese_mostra_riscos_e_desacordo_dos_avaliadores():
    d = coleta()
    r = next(r for r in d['registros'] if r['condicao']=='B')
    r['factual_correto'] = False
    r['riscos']['operacao_nao_persistida'] = True
    r['avaliacoes']['R01']['clareza'] = 1
    s = av.analisar(d)['condicoes']['B']
    assert s['factual']['numerador'] == 35
    assert s['riscos']['operacao_nao_persistida']['numerador'] == 1
    assert s['editorial']['clareza']['concordancia_exata']['numerador'] == 35


@pytest.mark.parametrize('campo,valor', [('duracao_ms',True),('duracao_ms',-1),('duracao_ms',float('nan')),
    ('duracao_ms',float('inf')),('duracao_ms',10**500),('chamou_modelo','sim'),('factual_correto',1),
    ('repeticao',True),('condicao',[]),('estado',[]),('caso','C99')])
def test_medidas_invalidas_nao_viram_evidencias(campo,valor):
    d = coleta();d['registros'][0][campo] = valor
    with pytest.raises(ValueError): av.analisar(d)


@pytest.mark.parametrize('campo,valor', [('ram_gb',0),('seed',True),('temperatura',3),
    ('janela_contexto',True),('modelo_digest','curto'),('cpu',''),('aquecimento_excluido',False)])
def test_exige_ambiente_identificavel_e_aquecimento_separado(campo,valor):
    d = coleta();d['ambiente'][campo] = valor
    with pytest.raises(ValueError): av.analisar(d)


def test_nao_aceita_remover_duplicar_ou_incluir_dados_pessoais():
    for mudar in (lambda d:d['registros'].pop(),
                  lambda d:d['registros'].__setitem__(0,copy.deepcopy(d['registros'][1])),
                  lambda d:d['registros'][0].update(resposta='mensagem privada'),
                  lambda d:d.update(telefone='contato privado')):
        d = coleta();mudar(d)
        with pytest.raises(ValueError): av.analisar(d)


def test_pendente_e_erro_nao_aceitam_medidas_ou_julgamentos_de_sucesso():
    d = coleta();d['registros'][0]['estado'] = 'PENDENTE'
    with pytest.raises(ValueError): av.analisar(d)
    d = coleta();d['registros'][0]['estado'] = 'TIMEOUT'
    with pytest.raises(ValueError): av.analisar(d)
    d = coleta();d['registros'][0]['avaliacoes']['R02']['naturalidade'] = True
    with pytest.raises(ValueError): av.analisar(d)


def test_relatorio_so_publica_hash_do_ambiente_nao_textos_informados():
    d = coleta();d['ambiente']['cpu'] = 'identificador-que-nao-deve-ser-publicado'
    s = av.analisar(d)
    assert 'identificador-que' not in json.dumps(s)
    assert len(s['ambiente_sha256']) == 64
    assert 'registros' not in s and 'avaliacoes' not in s


def test_coleta_completa_pode_ter_resultado_negativo_sem_virar_dado_invalido():
    d=coleta()
    for r in d['registros']:
        r['factual_correto']=False
        r['riscos']['link_nao_autorizado']=True
    s=av.analisar(d)
    assert s['coleta_completa']
    assert s['condicoes']['A']['factual']['proporcao']==0
    assert s['condicoes']['A']['riscos']['link_nao_autorizado']['proporcao']==1


def test_documentos_e_casos_do_protocolo_tem_referencias_validas():
    import re
    from urllib.parse import unquote
    protocolo=(ROOT/'docs/tcc/AVALIACAO.md').read_text(encoding='utf-8')
    assert set(re.findall(r'\| (C\d\d) \|',protocolo))==set(av.CASOS)
    arquivos=list((ROOT/'docs/tcc').glob('*.md'))
    for arquivo in arquivos:
        for link in re.findall(r'\[[^\]]+\]\(([^)]+)\)',arquivo.read_text(encoding='utf-8')):
            if '://' not in link and not link.startswith('#'):
                destino=(arquivo.parent/unquote(link.split('#')[0])).resolve()
                assert destino.is_relative_to(ROOT) and destino.is_file(), (arquivo.name,link)


@pytest.fixture
def laboratorio(tmp_path,monkeypatch):
    monkeypatch.setattr(av,'ROOT',tmp_path)
    (tmp_path/'VERSION').write_text('2.40.0')
    monkeypatch.setattr(av.subprocess,'check_output',lambda cmd,**kwargs:'a'*40 if cmd[1]=='rev-parse' else b'')
    return tmp_path


def test_cli_prepara_sem_sobrescrever_e_analisa_sem_ligar_servicos(laboratorio):
    pasta = laboratorio/'artifacts/tcc'
    entrada = pasta/'coleta.json';saida=pasta/'resumo.json'
    assert av.main(['--preparar','--saida',str(entrada)]) == 0
    original=entrada.read_bytes()
    assert av.main(['--preparar','--saida',str(entrada)]) == 2
    assert entrada.read_bytes() == original
    assert av.main(['--analisar',str(entrada),'--saida',str(saida)]) == 1
    assert not json.loads(saida.read_text())['coleta_completa']
    completa=pasta/'simulacao.json';completa.write_text(json.dumps(coleta()))
    assert av.main(['--analisar',str(completa),'--saida',str(pasta/'sintese.json')]) == 0


@pytest.mark.parametrize('arquivo', ['src/app.py','artifacts/tcc/../../../VERSION'])
def test_cli_nao_escreve_fora_do_laboratorio(laboratorio,arquivo):
    assert av.main(['--preparar','--saida',str(laboratorio/arquivo)]) == 2
    assert (laboratorio/'VERSION').read_text() == '2.40.0'


@pytest.mark.parametrize('texto', ['{"formato":1,"formato":1}', '{invalido', '{"token":"segredo-privado"}',
    '[NaN]', '['*1000+']'*1000])
def test_cli_recusa_entrada_ambigua_sem_vazar_conteudo(laboratorio,texto,capsys):
    entrada=laboratorio/'entrada.json';entrada.write_text(texto)
    saida=laboratorio/'artifacts/tcc/resumo.json'
    assert av.main(['--analisar',str(entrada),'--saida',str(saida)]) == 2
    assert not saida.exists()
    assert 'segredo-privado' not in capsys.readouterr().out


def test_cli_limita_tamanho_e_preserva_entrada(laboratorio,monkeypatch):
    entrada=laboratorio/'entrada.json';entrada.write_text('x'*101)
    monkeypatch.setattr(av,'MAX_BYTES',100)
    assert av.main(['--analisar',str(entrada),'--saida',str(laboratorio/'artifacts/tcc/resumo.json')]) == 2
    assert entrada.read_text() == 'x'*101


def test_cli_localiza_registro_invalido_sem_mostrar_o_valor(laboratorio,capsys):
    d=coleta();d['registros'][3]['duracao_ms']='segredo-nao-deve-aparecer'
    entrada=laboratorio/'medidas.json';entrada.write_text(json.dumps(d))
    assert av.main(['--analisar',str(entrada),'--saida',str(laboratorio/'artifacts/tcc/resumo.json')])==2
    mensagem=capsys.readouterr().out
    assert 'Registro 4' in mensagem and 'segredo-nao-deve-aparecer' not in mensagem
