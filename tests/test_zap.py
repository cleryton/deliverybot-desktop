"""Política de CI: scanner passivo não pode mascarar falhas ou ampliar o alvo."""
import pytest
import importlib.util
from pathlib import Path

path=Path(__file__).resolve().parent.parent/'packaging/validar_zap.py'
spec=importlib.util.spec_from_file_location('deliverybot_validar_zap',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def report(alerts=None, url='http://127.0.0.1:5030'):
    return {'site':[{'@name':url,'alerts':alerts or []}]}


def test_relatorio_local_sem_alertas_aprovado():
    assert module.validar(report())['bloqueios']==0


@pytest.mark.parametrize('plugin',['10010','10011','10020','10021','10038'])
def test_controles_essenciais_bloqueiam_mesmo_com_risco_baixo(plugin):
    assert module.validar(report([{'riskcode':'1','pluginid':plugin}]))['bloqueios']==1


def test_risco_alto_bloqueia_e_demais_alertas_continuam_no_relatorio():
    result=module.validar(report([{'riskcode':'3','pluginid':'90000'},{'riskcode':'2','pluginid':'10055'}]))
    assert result['alertas']==2 and result['bloqueios']==1


@pytest.mark.parametrize('data',[{}, {'site':[]}, report(url='https://loja-real.example'),
                               report(url='http://127.0.0.1:80'), {'site':[{'@name':'http://127.0.0.1:5030'}]},
                               report([{'riskcode':'5'}]), report([{}])])
def test_relatorio_incompleto_ou_externo_nao_aprova(data):
    with pytest.raises((ValueError,TypeError,KeyError)):
        module.validar(data)
