"""Downloads simulados: nenhum instalador ou serviço real é executado."""
import hashlib
from pathlib import Path
from unittest.mock import Mock
from urllib.parse import quote

import pytest
from src import atualizacoes, config
from src.db import init_db


@pytest.fixture
def loja(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DATABASE_PATH',str(tmp_path/'loja.db'))
    init_db(seed_cardapio=False)
    monkeypatch.setattr(atualizacoes,'_estado',{})
    monkeypatch.setattr(atualizacoes,'_baixado',None)
    monkeypatch.setattr(atualizacoes,'atual',lambda:'2.9.0')


def release(exe=b'instalador ficticio'):
    soma=hashlib.sha256(exe).hexdigest()
    manifesto=(soma+'  '+atualizacoes.INSTALADOR+'\n').encode()
    return {'tag_name':'v2.10.0','html_url':atualizacoes.REPOSITORIO+'/releases/tag/v2.10.0','assets':[{'name':nome,'size':len(dados),'browser_download_url':atualizacoes.REPOSITORIO+'/releases/download/v2.10.0/'+quote(nome)} for nome,dados in [(atualizacoes.INSTALADOR,exe),('SHA256SUMS.txt',manifesto)]]},manifesto


def resposta(dados):
    r=Mock()
    r.__enter__=Mock(return_value=r);r.__exit__=Mock(return_value=False)
    r.iter_content.return_value=[dados]
    return r


def test_versoes_origem_e_arquivos(loja):
    r,_=release()
    assert atualizacoes.validar_release(r)['nova']
    r['tag_name']='v2.9.0';r['html_url']=atualizacoes.REPOSITORIO+'/releases/tag/v2.9.0'
    with pytest.raises(ValueError):
        atualizacoes.validar_release(r)  # Assets de outra tag são rejeitados.
    for valor in ['../2.10.0','v2.1','v2.9.0-beta','02.0.0','v2.0.0.exe']:
        with pytest.raises(ValueError):
            atualizacoes.versao(valor)
    r,_=release();r['assets'][0]['browser_download_url']='https://malicioso.example/instalador.exe'
    with pytest.raises(ValueError):
        atualizacoes.validar_release(r)
    with pytest.raises(ValueError):
        atualizacoes._abrir('http://github.com/arquivo')


def test_download_alterado_bloqueia_backup_e_execucao(loja,monkeypatch):
    r,manifesto=release();atualizacoes._estado.update(atualizacoes.validar_release(r))
    monkeypatch.setattr(atualizacoes,'_abrir',lambda u:resposta(manifesto if u.endswith('.txt') else b'arquivo alterado'))
    backup=Mock();monkeypatch.setattr(atualizacoes.backups,'criar',backup)
    with pytest.raises(ValueError,match='alterado'):
        atualizacoes.baixar('senha-ficticia-para-backup')
    backup.assert_not_called()
    assert not list(Path(config.DATABASE_PATH).parent.rglob('*.exe'))
    assert not list(Path(config.DATABASE_PATH).parent.rglob('*.download'))
    with pytest.raises(ValueError):
        atualizacoes.instalar()


def test_download_backup_verificado_e_assinatura_obrigatoria(loja,monkeypatch):
    exe=b'instalador ficticio';r,manifesto=release(exe)
    atualizacoes._estado.update(atualizacoes.validar_release(r))
    monkeypatch.setattr(atualizacoes,'_abrir',lambda u:resposta(manifesto if u.endswith('.txt') else exe))
    monkeypatch.setattr(atualizacoes,'assinatura',lambda _:False)
    atualizacoes.baixar('senha-ficticia-para-backup')
    b=atualizacoes.situacao()['download']
    assert Path(b['caminho']).read_bytes()==exe and Path(b['backup']).exists()
    assert not b['assinatura_confiavel']
    iniciar=Mock();monkeypatch.setattr(atualizacoes.subprocess,'Popen',iniciar)
    with pytest.raises(ValueError,match='assinatura'):
        atualizacoes.instalar()
    iniciar.assert_not_called()
    assert 'senha' not in atualizacoes.situacao()


def test_consulta_optativa_e_intervalo(loja,monkeypatch):
    consulta=Mock();monkeypatch.setattr(atualizacoes,'consultar',consulta)
    atualizacoes.rotina();consulta.assert_not_called()
    atualizacoes.configurar({'automatica':True})
    atualizacoes.rotina();atualizacoes.rotina()
    consulta.assert_called_once()


def test_nome_normalizado_pelo_github_e_manifesto_legacy(loja,monkeypatch):
    exe=b'instalador ficticio';r,manifesto=release(exe)
    r['assets'][0]['name']='Instalar.DeliveryBot.exe'
    r['assets'][0]['browser_download_url']=atualizacoes.REPOSITORIO+'/releases/download/v2.10.0/Instalar.DeliveryBot.exe'
    atualizacoes._estado.update(atualizacoes.validar_release(r))
    manifesto=manifesto.replace(atualizacoes.INSTALADOR.encode(),b'Instalar DeliveryBot.exe')
    monkeypatch.setattr(atualizacoes,'_abrir',lambda u:resposta(manifesto if u.endswith('.txt') else exe))
    monkeypatch.setattr(atualizacoes,'assinatura',lambda _:False)
    atualizacoes.baixar('senha-ficticia-para-backup')
    assert Path(atualizacoes.situacao()['download']['caminho']).read_bytes()==exe
