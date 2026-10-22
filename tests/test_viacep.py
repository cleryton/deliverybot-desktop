"""Consulta de CEP sem rede real: respostas externas são dados não confiáveis."""
from unittest.mock import Mock

import pytest
import requests

from src import viacep

ENDERECO={'cep':'01001-000','logradouro':'Praça fictícia','bairro':'Centro','localidade':'São Paulo','uf':'SP'}


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    if hasattr(viacep,'_cache'):viacep._cache.clear()
    chamada=Mock(return_value=Mock(status_code=200,json=Mock(return_value=dict(ENDERECO))))
    monkeypatch.setattr(viacep.requests,'get',chamada)
    return chamada


@pytest.mark.parametrize('dados',[None,[],True,42,'texto',{'erro':True},
    {**ENDERECO,'uf':None},{**ENDERECO,'uf':'ZZ'}, {**ENDERECO,'localidade':''},
    {**ENDERECO,'logradouro':['rua']},{**ENDERECO,'cep':'99999-999'},
    {**ENDERECO,'bairro':'x'*161}])
def test_resposta_invalida_nao_crasha_nem_autoriza_entrega(sem_rede,dados):
    sem_rede.return_value.json.return_value=dados
    assert viacep.consultar_cep('01001-000') is None
    ok,_,endereco=viacep.validar_area_entrega('01001-000')
    assert not ok and endereco is None


def test_reutiliza_endereco_sem_compartilhar_mutacao_do_chamador(sem_rede):
    primeiro=viacep.consultar_cep('01001-000')
    primeiro['cidade']='Cidade alterada'
    segundo=viacep.consultar_cep('01001000')
    assert segundo['cidade']=='São Paulo' and sem_rede.call_count==1


def test_expira_cache_e_limita_tamanho(sem_rede,monkeypatch):
    agora=[100.0]
    monkeypatch.setattr(viacep.time,'monotonic',lambda:agora[0])
    assert viacep.consultar_cep('01001000')
    agora[0]+=viacep.CACHE_TTL+1
    assert viacep.consultar_cep('01001000') and sem_rede.call_count==2
    for i in range(viacep.CACHE_LIMITE+3):
        cep=f'{10000000+i:08}'
        sem_rede.return_value.json.return_value={**ENDERECO,'cep':cep}
        assert viacep.consultar_cep(cep)
    assert len(viacep._cache)<=viacep.CACHE_LIMITE


@pytest.mark.parametrize('cep',[None,12,{},'','123','１２３４５６７８'])
def test_cep_invalido_nao_acessa_api(sem_rede,cep):
    assert viacep.consultar_cep(cep) is None
    sem_rede.assert_not_called()


def test_timeout_nao_fica_em_cache_e_proxima_tentativa_recupera(sem_rede):
    sem_rede.side_effect=[requests.Timeout('sem rede'),sem_rede.return_value]
    assert viacep.consultar_cep('01001000') is None
    assert viacep.consultar_cep('01001000')['uf']=='SP'
    assert sem_rede.call_count==2


def test_cep_geral_aceita_rua_vazia_mas_confere_area_em_cada_uso(sem_rede):
    sem_rede.return_value.json.return_value={**ENDERECO,'logradouro':'','bairro':''}
    assert viacep.validar_area_entrega('01001000',['São Paulo'])[0]
    assert not viacep.validar_area_entrega('01001000',['Curitiba'])[0]
    assert sem_rede.call_count==1
