"""Protege os workers contra geração excessiva de PDFs, sem dados reais."""
from concurrent.futures import ThreadPoolExecutor
import threading
from unittest.mock import Mock

import pytest

from src import catalogo_publico, config, db, politica_terminal


@pytest.fixture
def protecao(monkeypatch):
    relogio = [100.0]
    monkeypatch.setattr(politica_terminal.time, 'monotonic', lambda: relogio[0])
    p = catalogo_publico.ProtecaoCatalogo()
    monkeypatch.setattr(catalogo_publico, 'protecao', p)
    return p, relogio


def test_limite_por_link_sem_reter_token_e_renova_apos_janela(protecao):
    p, relogio = protecao
    token = 'token-ficticio-que-nao-deve-ser-retido'
    for _ in range(3):
        with p.reservar(token):
            pass
    with pytest.raises(catalogo_publico.CatalogoOcupado) as erro:
        with p.reservar(token):
            pytest.fail('Não deve iniciar a geração acima do limite.')
    assert erro.value.aguardar == 60
    assert token not in repr(p.limites.itens)
    with p.reservar('outro-link'):
        pass
    relogio[0] += 60
    with p.reservar(token):
        pass


def test_limite_global_nao_pode_ser_contornado_trocando_link(protecao):
    p, _ = protecao
    for n in range(30):
        with p.reservar('link-' + str(n)):
            pass
    with pytest.raises(catalogo_publico.CatalogoOcupado) as erro:
        with p.reservar('outro-link'):
            pytest.fail('O limite global deve bloquear novos links.')
    assert erro.value.aguardar == 60


def test_geracoes_concorrentes_limitadas_e_vagas_liberadas(protecao):
    p, _ = protecao
    prontas = threading.Barrier(3)
    liberar = threading.Event()

    def gerar(token):
        with p.reservar(token):
            prontas.wait(timeout=5)
            assert liberar.wait(timeout=5)

    with ThreadPoolExecutor(max_workers=2) as executor:
        tarefas = [executor.submit(gerar, 'link-' + str(n)) for n in range(2)]
        try:
            prontas.wait(timeout=5)
            with pytest.raises(catalogo_publico.CatalogoOcupado) as erro:
                with p.reservar('terceiro-link'):
                    pytest.fail('Uma terceira geração não deve começar.')
            assert erro.value.aguardar == 15
        finally:
            liberar.set()
        for tarefa in tarefas:
            tarefa.result(timeout=5)
    with p.reservar('nova-geracao'):
        pass


def test_erro_da_geracao_libera_vaga(protecao):
    p, _ = protecao
    for n in range(2):
        with pytest.raises(ValueError, match='Falha fictícia'):
            with p.reservar('falha-' + str(n)):
                raise ValueError('Falha fictícia')
    with p.reservar('apos-falha'):
        pass


@pytest.fixture
def cliente(tmp_path, monkeypatch, protecao):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticio.db'))
    monkeypatch.setattr(config, 'MODO_TESTE', True)
    monkeypatch.setattr(config, 'IA_PROVIDER', '')
    monkeypatch.setattr(config, 'OLLAMA_AQUECER_AO_INICIAR', False)
    monkeypatch.setattr(config, 'BASE_URL', 'https://loja-ficticia.example')
    db.init_db(seed_cardapio=False)
    from src.app import app
    from src import catalogo_pdf, links
    gerar = Mock(return_value=b'%PDF-1.4 ficticio')
    monkeypatch.setattr(catalogo_pdf, 'gerar', gerar)
    link = links.gerar_link_pedido('0000000000001').rsplit('/', 1)[-1]
    return app.test_client(), link, gerar


def test_rota_pdf_recusa_excesso_antes_de_gerar_e_preserva_compra(cliente):
    c, token, gerar = cliente
    url = '/m/' + token
    for _ in range(3):
        resposta = c.get(url + '/catalogo.pdf')
        assert resposta.status_code == 200
        assert resposta.mimetype == 'application/pdf'
    resposta = c.get(url + '/catalogo.pdf')
    assert resposta.status_code == 429 and resposta.headers['Retry-After'] == '60'
    assert 'no-store' in resposta.headers['Cache-Control']
    assert token not in resposta.text and gerar.call_count == 3
    assert c.get(url).status_code == 200


def test_link_invalido_nao_consumir_limite_ou_gerar_pdf(cliente, protecao):
    c, _, gerar = cliente
    p, _ = protecao
    for _ in range(5):
        assert c.get('/m/invalido/catalogo.pdf').status_code == 410
    assert not p.limites.itens
    gerar.assert_not_called()
