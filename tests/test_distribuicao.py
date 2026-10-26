"""Organização usa apenas arquivos fictícios; preserva dados e versões úteis."""
import importlib.util
import sys
from pathlib import Path

import pytest

PASTA = Path(__file__).resolve().parents[1]/'packaging'
spec = importlib.util.spec_from_file_location('distribuicao', PASTA/'distribuicao.py')
d = importlib.util.module_from_spec(spec)
sys.modules['distribuicao'] = d
spec.loader.exec_module(d)
spec = importlib.util.spec_from_file_location('deliverybot_limpeza', PASTA/'limpar_pasta.py')
l = importlib.util.module_from_spec(spec)
spec.loader.exec_module(l)


def raiz_ficticia(pasta):
    pasta.mkdir(exist_ok=True)
    for nome, texto in {'VERSION':'3.1.0', 'desktop.py':'# fictício', '.gitignore':'dist/'}.items():
        (pasta/nome).write_text(texto,encoding='utf-8')
    for nome in d.DOCUMENTOS:
        p=pasta/nome
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text('Documento fictício.',encoding='utf-8')
    return pasta


def release(raiz, versao, completa=False):
    p=raiz/'dist'/('v'+versao)
    p.mkdir(parents=True)
    for nome in d.BINARIOS:
        (p/nome).write_bytes(b'MZ arquivo de teste '+versao.encode())
    if completa:
        d.finalizar(p,raiz)
    else:
        d.gerar_hashes(p)
    return p


def test_finaliza_documentos_versao_e_integridade(tmp_path):
    raiz=raiz_ficticia(tmp_path)
    p=release(raiz,'3.1.0',True)
    assert {x.name for x in p.iterdir()}==d.GERADOS
    assert d.verificar(p,completa=True,esperada='3.1.0')
    assert 'v3.1.0' in (raiz/'dist/LEIA-ME.txt').read_text(encoding='utf-8')
    (p/'Como usar o DeliveryBot.txt').write_text('alterado',encoding='utf-8')
    with pytest.raises(ValueError,match='Integridade divergente'):
        d.verificar(p,completa=True)


def test_nao_indica_distribuicao_incompleta(tmp_path):
    raiz=raiz_ficticia(tmp_path)
    p=raiz/'dist/v3.1.0'
    p.mkdir(parents=True)
    (p/'DeliveryBot.exe').write_bytes(b'MZ teste')
    with pytest.raises(ValueError):
        d.finalizar(p,raiz)
    assert not (raiz/'dist/LEIA-ME.txt').exists()
    assert not (p/'VERSAO.json').exists()


def test_cli_recalcula_hashes_apos_assinatura_sem_reescrever_documentos(tmp_path, monkeypatch):
    raiz = raiz_ficticia(tmp_path)
    pasta = release(raiz, '3.1.0', True)
    monkeypatch.setattr(d, 'ROOT', raiz)
    documentos = {nome: ((pasta/nome).read_bytes(), (pasta/nome).stat().st_mtime_ns)
                  for nome in d.GERADOS - set(d.BINARIOS) - {'SHA256SUMS.txt'}}
    (pasta/d.BINARIOS[0]).write_bytes(b'MZ assinatura ficticia adicionada')
    (pasta/'segredo.key').write_bytes(b'nao deve entrar no manifesto')
    with pytest.raises(ValueError, match='Integridade divergente'):
        d.verificar(pasta, completa=True)
    assert d.main(['--distpath', str(pasta), '--hashes']) == 0
    assert d.verificar(pasta, completa=True, esperada='3.1.0')
    assert 'segredo.key' not in (pasta/'SHA256SUMS.txt').read_text()
    assert all(((pasta/n).read_bytes(), (pasta/n).stat().st_mtime_ns) == estado
               for n, estado in documentos.items())


def test_cli_hashes_exige_os_quatro_executaveis_e_preserva_manifesto(tmp_path, monkeypatch):
    raiz = raiz_ficticia(tmp_path)
    pasta = release(raiz, '3.1.0', True)
    monkeypatch.setattr(d, 'ROOT', raiz)
    anterior = (pasta/'SHA256SUMS.txt').read_bytes()
    (pasta/d.BINARIOS[2]).unlink()
    with pytest.raises(ValueError):
        d.main(['--distpath', str(pasta), '--hashes'])
    assert (pasta/'SHA256SUMS.txt').read_bytes() == anterior


def test_cli_hashes_e_verificacao_sao_operacoes_exclusivas(tmp_path):
    with pytest.raises(SystemExit) as exc:
        d.main(['--distpath', str(tmp_path), '--hashes', '--verificar'])
    assert exc.value.code == 2 and not list(tmp_path.iterdir())


@pytest.mark.parametrize('linha', ['../fora.txt','/etc/passwd','DeliveryBot.exe\n','arquivo.db'])
def test_manifesto_nao_le_caminhos_ou_dados_privados(tmp_path,linha):
    p=tmp_path/'pacote'
    p.mkdir()
    (p/'SHA256SUMS.txt').write_text('0'*64+'  '+linha+'\n',encoding='utf-8')
    with pytest.raises(ValueError):
        d.verificar(p)


def test_limpeza_mantem_atual_retorno_dados_e_futuro(tmp_path):
    raiz=raiz_ficticia(tmp_path)
    vigente=release(raiz,'3.1.0',True)
    anterior=release(raiz,'3.0.0')
    velho=release(raiz,'2.9.0')
    futuro=release(raiz,'3.2.0')
    desconhecido=release(raiz,'2.8.0')
    (desconhecido/'clientes.db').write_bytes(b'dados preservados')
    (raiz/'data').mkdir()
    (raiz/'data/cliente.db').write_bytes(b'dados preservados')
    plano=l.planejar(raiz)
    assert plano['anterior']=='v3.0.0' and plano['remover']==['dist/v2.9.0']
    assert velho.exists()  # Simular não remove nada.
    resultado=l.aplicar(raiz)
    assert resultado['bytes_liberados']>0 and not velho.exists()
    assert all(p.exists() for p in (vigente,anterior,futuro,desconhecido,raiz/'data/cliente.db'))


def test_sem_atual_valida_nao_remove_nada(tmp_path):
    raiz=raiz_ficticia(tmp_path)
    velho=release(raiz,'3.0.0')
    with pytest.raises(ValueError):
        l.aplicar(raiz)
    assert velho.exists()


def test_arquivo_modificado_bloqueia_limpeza(tmp_path):
    raiz=raiz_ficticia(tmp_path)
    p=release(raiz,'3.1.0',True)
    velho=release(raiz,'3.0.0')
    (p/'DeliveryBot.exe').write_bytes(b'MZ alterado')
    with pytest.raises(ValueError,match='Integridade'):
        l.aplicar(raiz)
    assert velho.exists()


def test_caches_conhecidos_preservam_arquivos_desconhecidos(tmp_path):
    raiz=raiz_ficticia(tmp_path)
    release(raiz,'3.1.0',True)
    cache=raiz/'src/__pycache__'
    cache.mkdir(parents=True)
    (cache/'teste.pyc').write_bytes(b'cache ficticio')
    segredo=raiz/'build/DeliveryBot'
    segredo.mkdir(parents=True)
    (segredo/'certificado.pfx').write_bytes(b'preservado')
    assert 'src/__pycache__' in l.planejar(raiz)['remover']
    assert 'build/DeliveryBot' not in l.planejar(raiz)['remover']
    l.aplicar(raiz)
    assert not cache.exists() and (segredo/'certificado.pfx').exists()


def test_limpeza_recusa_vinculo_para_fora(tmp_path):
    raiz=raiz_ficticia(tmp_path/'projeto')
    release(raiz,'3.1.0',True)
    fora=tmp_path/'fora'
    fora.mkdir()
    (fora/'teste.pyc').write_bytes(b'preservado')
    (raiz/'src').mkdir()
    try:
        (raiz/'src/__pycache__').symlink_to(fora,target_is_directory=True)
    except OSError:
        pytest.skip('Criação de vínculos indisponível nesta conta Windows.')
    assert 'src/__pycache__' not in l.planejar(raiz)['remover']
    l.aplicar(raiz)
    assert (fora/'teste.pyc').exists()
