"""Evidências acadêmicas: contagens reais, entrada insegura e saída sem dados dos casos."""
import importlib.util
import json
from pathlib import Path

import pytest
from defusedxml.common import DefusedXmlException

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('evidencias_tcc', ROOT / 'packaging/evidencias_tcc.py')
evidencias = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidencias)
SHA = 'a' * 40


def junit(casos):
    return ('<testsuites><testsuite>' + casos + '</testsuite></testsuites>').encode()


def test_conta_resultados_sem_confundir_ignorado_com_aprovado():
    dados = evidencias.resumir_junit(junit(
        '<testcase time="0.1"/><testcase time="0.2"><failure>erro privado</failure></testcase>'
        '<testcase time="0.3"><error/></testcase><testcase time="0.4"><skipped/></testcase>'))
    assert dados == {'executados': 4, 'aprovados': 1, 'falhas': 1, 'erros': 1, 'ignorados': 1,
                     'soma_duracoes_casos_s': 1.0, 'sem_falhas': False, 'validacao_completa': False}


def test_ignorado_nao_vira_validacao_completa():
    r = evidencias.resumir_junit(junit('<testcase><skipped/></testcase>'))
    assert r['sem_falhas'] and not r['validacao_completa'] and r['aprovados'] == 0


def test_aceita_raiz_testsuite_e_preserva_hash_sem_copiar_atributos():
    entrada = b'<testsuite><testcase name="telefone-secreto" classname="caminho-privado"><system-out>token-secreto</system-out></testcase></testsuite>'
    r = evidencias.consolidar([entrada], '2.33.1', SHA, True)
    texto = json.dumps(r)
    assert 'telefone-secreto' not in texto and 'caminho-privado' not in texto and 'token-secreto' not in texto
    assert r['relatorios'][0]['aprovados'] == 1
    assert len(r['relatorios'][0]['sha256']) == 64
    assert r['commit_do_checkout'] == SHA and r['alteracoes_versionadas_pendentes']
    assert r['validacao_completa']


@pytest.mark.parametrize('entrada', [b'', b'<html/>', b'<testsuites/>', junit('<testcase><failure/><skipped/></testcase>'),
                                    junit('<testcase time="-1"/>'), junit('<testcase time="NaN"/>'),
                                    junit('<testcase time="inf"/>'), junit('<testcase time="invalido"/>'),
                                    junit('<testcase time="1e308"/><testcase time="1e308"/>')],
                         ids=['vazio', 'formato', 'sem-casos', 'ambiguo', 'negativo', 'nan', 'infinito', 'nao-numerico', 'soma-infinita'])
def test_recusa_evidencia_invalida(entrada):
    with pytest.raises(ValueError):
        evidencias.resumir_junit(entrada)


def test_limita_leitura_e_recusa_entidades_externas(monkeypatch):
    monkeypatch.setattr(evidencias, 'MAX_BYTES', 10)
    with pytest.raises(ValueError):
        evidencias.resumir_junit(b'x' * 11)
    monkeypatch.setattr(evidencias, 'MAX_BYTES', 1000)
    with pytest.raises(DefusedXmlException):
        evidencias.resumir_junit(b'<!DOCTYPE testsuite [<!ENTITY arquivo SYSTEM "file:///privado">]><testsuite><testcase>&arquivo;</testcase></testsuite>')


def test_relatorios_distintos_ficam_separados_e_copia_e_recusada():
    a = junit('<testcase/>')
    b = junit('<testcase/><testcase/>')
    r = evidencias.consolidar([a, b], '2.33.1', SHA, False)
    assert [i['executados'] for i in r['relatorios']] == [1, 2]
    with pytest.raises(ValueError, match='repetido'):
        evidencias.consolidar([a, a], '2.33.1', SHA, False)


@pytest.mark.parametrize('versao,commit,pendentes', [('invalid', SHA, False), ('2.33.1', 'curto', False), ('2.33.1', SHA, 'false')])
def test_recusa_metadados_invalidos(versao, commit, pendentes):
    with pytest.raises(ValueError):
        evidencias.consolidar([junit('<testcase/>')], versao, commit, pendentes)


def test_recusa_consolidacao_sem_execucao():
    with pytest.raises(ValueError):
        evidencias.consolidar([], '2.33.1', SHA, False)


@pytest.mark.parametrize('caso,codigo', [('<testcase/>', 0), ('<testcase><failure/></testcase>', 1), ('<testcase><error/></testcase>', 1), ('<testcase><skipped/></testcase>', 0)])
def test_cli_exporta_contagens_e_retorna_falhas(tmp_path, monkeypatch, caso, codigo):
    monkeypatch.setattr(evidencias, 'ROOT', tmp_path)
    (tmp_path / 'VERSION').write_text('2.33.1')
    monkeypatch.setattr(evidencias.subprocess, 'check_output', lambda cmd, **kwargs: SHA if cmd[1] == 'rev-parse' else b'')
    entrada = tmp_path / 'testes.xml'
    entrada.write_bytes(junit(caso))
    saida = tmp_path / 'artifacts/tcc/resumo.json'
    assert evidencias.main([str(entrada), '--saida', str(saida)]) == codigo
    assert json.loads(saida.read_text())['sem_falhas'] == (codigo == 0)


@pytest.mark.parametrize('caminho', ['src/app.py', 'artifacts/tcc/../../../VERSION'])
def test_cli_nao_sobrescreve_codigo_nem_sai_da_pasta(tmp_path, monkeypatch, caminho):
    monkeypatch.setattr(evidencias, 'ROOT', tmp_path)
    saida = tmp_path / caminho
    assert evidencias.main([str(tmp_path / 'nao-lido.xml'), '--saida', str(saida)]) == 2
    assert not saida.exists()


def test_cli_nao_sobrescreve_entrada(tmp_path, monkeypatch):
    monkeypatch.setattr(evidencias, 'ROOT', tmp_path)
    entrada = tmp_path / 'artifacts/tcc/testes.xml'
    entrada.parent.mkdir(parents=True)
    conteudo = junit('<testcase/>')
    entrada.write_bytes(conteudo)
    assert evidencias.main([str(entrada), '--saida', str(entrada)]) == 2
    assert entrada.read_bytes() == conteudo


@pytest.mark.parametrize('conteudo', [b'<incompleto', b'<!DOCTYPE testsuite><testsuite/>'])
def test_cli_recusa_xml_inseguro_sem_criar_relatorio(tmp_path, monkeypatch, conteudo):
    monkeypatch.setattr(evidencias, 'ROOT', tmp_path)
    entrada = tmp_path / 'testes.xml'
    entrada.write_bytes(conteudo)
    saida = tmp_path / 'artifacts/tcc/resumo.json'
    assert evidencias.main([str(entrada), '--saida', str(saida)]) == 2
    assert not saida.exists()


def test_matriz_aponta_para_testes_e_modulos_existentes():
    import re
    matriz = (ROOT / 'docs/tcc/ARQUITETURA_E_REQUISITOS.md').read_text(encoding='utf-8')
    for caminho in re.findall(r'`((?:src|tests|web|packaging)/[^`]+|desktop.py|DeliveryBot.spec)`', matriz):
        arquivo, _, funcao = caminho.partition('::')
        p = ROOT / arquivo
        assert p.is_file(), arquivo
        if funcao:
            assert f'def {funcao}(' in p.read_text(encoding='utf-8'), caminho
