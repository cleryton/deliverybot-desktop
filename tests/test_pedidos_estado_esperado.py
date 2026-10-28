"""Ações de telas antigas não podem pular etapas nem estornar outra operação."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock

import pytest

from src import config, estoque, pedidos, whatsapp
from src.db import get_conn, init_db


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'estado-pedidos.db'))
    for chave, valor in {'SEED_CATALOGO': False, 'WHATSAPP_PROVIDER': 'TESTE',
                         'MODO_TESTE': True, 'IA_PROVIDER': '', 'FORMAS_PAGAMENTO': 'Pix',
                         'ADMIN_PERMITIR_REMOTO': False}.items():
        monkeypatch.setattr(config, chave, valor)
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'estado-ficticio')
    notificar = Mock()
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', notificar)
    produto = estoque.salvar_produto({'nome': 'Lanche fictício', 'categoria': 'Teste',
                                      'preco': 12, 'estoque': 10})
    pedido = pedidos.criar_pedido('5500000000001', 'Cliente fictício',
                                  [{'produto_id': produto['id'], 'quantidade': 2}], 'Pix')

    def cliente():
        c = app.test_client()
        c.get('/gestao?acesso=estado-ficticio')
        with c.session_transaction() as sessao:
            headers = {'X-CSRF-Token': sessao['csrf']}
        return c, headers

    return cliente, pedido, produto, notificar


def saldos(produto_id):
    with get_conn() as conn:
        return (conn.execute('SELECT estoque FROM produtos WHERE id=?', (produto_id,)).fetchone()[0],
                conn.execute("SELECT count(*) FROM movimentos_estoque WHERE tipo='ESTORNO'").fetchone()[0])


def test_duas_telas_com_mesmo_estado_nao_pulam_etapa(ambiente):
    cliente, pedido, produto, notificar = ambiente
    primeiro, h1 = cliente()
    segundo, h2 = cliente()
    tela1 = primeiro.get('/gestao/api/pedidos').json[0]
    tela2 = segundo.get('/gestao/api/pedidos').json[0]
    rota = f"/gestao/api/pedidos/{pedido['id']}/avancar"
    assert primeiro.post(rota, json={'status': tela1['status']}, headers=h1).status_code == 200
    r = segundo.post(rota, json={'status': tela2['status']}, headers=h2)
    assert r.status_code == 400
    assert 'Atualize a lista' in r.json['erro']
    assert pedidos.obter_pedido(pedido['id'])['status'] == 'EM_PREPARO'
    assert notificar.call_count == 1
    assert saldos(produto['id']) == (8, 0)


def test_duas_acoes_concorrentes_com_mesmo_estado_avancam_uma_vez(ambiente):
    cliente, pedido, produto, notificar = ambiente
    clientes = [cliente(), cliente()]
    barreira = Barrier(2)

    def avancar(par):
        c, h = par
        barreira.wait(timeout=5)
        return c.post(f"/gestao/api/pedidos/{pedido['id']}/avancar",
                      json={'status': pedido['status']}, headers=h).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(avancar, clientes)) == [200, 400]
    assert pedidos.obter_pedido(pedido['id'])['status'] == 'EM_PREPARO'
    assert notificar.call_count == 1
    assert saldos(produto['id']) == (8, 0)


def test_cancelamento_da_tela_antiga_nao_devolve_estoque(ambiente):
    cliente, pedido, produto, notificar = ambiente
    c, h = cliente()
    raiz = f"/gestao/api/pedidos/{pedido['id']}"
    assert c.post(raiz + '/avancar', json={'status': 'RECEBIDO'}, headers=h).status_code == 200
    r = c.post(raiz + '/cancelar', json={'status': 'RECEBIDO'}, headers=h)
    assert r.status_code == 400
    assert 'Atualize a lista' in r.json['erro']
    assert pedidos.obter_pedido(pedido['id'])['status'] == 'EM_PREPARO'
    assert notificar.call_count == 1
    assert saldos(produto['id']) == (8, 0)
    assert c.post(raiz + '/cancelar', json={'status': 'EM_PREPARO'}, headers=h).status_code == 200
    assert pedidos.obter_pedido(pedido['id'])['status'] == 'CANCELADO'
    assert notificar.call_count == 2
    assert saldos(produto['id']) == (10, 1)


@pytest.mark.parametrize('acao', ['avancar', 'cancelar'])
@pytest.mark.parametrize('dados', [{}, {'status': None}, {'status': True}, {'status': {}},
                                  {'status': []}, {'status': 'CANCELADO'}, {'status': 'desconhecido'}])
def test_estado_ausente_ou_invalido_nao_muda_pedido(ambiente, acao, dados):
    cliente, pedido, produto, notificar = ambiente
    c, h = cliente()
    r = c.post(f"/gestao/api/pedidos/{pedido['id']}/{acao}", json=dados, headers=h)
    assert r.status_code == 400
    assert pedidos.obter_pedido(pedido['id'])['status'] == 'RECEBIDO'
    notificar.assert_not_called()
    assert saldos(produto['id']) == (8, 0)


def test_estado_esperado_nao_substitui_autenticacao_e_csrf(ambiente):
    cliente, pedido, produto, notificar = ambiente
    c, _ = cliente()
    for acao in ('avancar', 'cancelar'):
        assert c.post(f"/gestao/api/pedidos/{pedido['id']}/{acao}",
                      json={'status': 'RECEBIDO'}).status_code == 403
    assert pedidos.obter_pedido(pedido['id'])['status'] == 'RECEBIDO'
    assert saldos(produto['id']) == (8, 0)
    notificar.assert_not_called()


def test_apos_reler_pode_avancar_todas_as_etapas_sem_duplicar_estoque(ambiente):
    cliente, pedido, produto, notificar = ambiente
    c, h = cliente()
    # Instalações anteriores também podem exibir CONFIRMADO na etapa inicial.
    with get_conn() as conn:
        conn.execute("UPDATE pedidos SET status='CONFIRMADO' WHERE id=?", (pedido['id'],))
    for estado, proximo in [('CONFIRMADO', 'EM_PREPARO'), ('EM_PREPARO', 'PRONTO'), ('PRONTO', 'RETIRADO')]:
        r = c.post(f"/gestao/api/pedidos/{pedido['id']}/avancar", json={'status': estado}, headers=h)
        assert r.status_code == 200
        assert r.json['status'] == proximo
    assert notificar.call_count == 3
    assert saldos(produto['id']) == (8, 0)


def test_cancelamento_interno_sem_estado_preserva_compatibilidade(ambiente):
    _, pedido, produto, notificar = ambiente
    assert pedidos.cancelar_pedido(pedido['id'])['status'] == 'CANCELADO'
    assert saldos(produto['id']) == (10, 1)
    notificar.assert_not_called()
