"""Permissões revalidadas na gravação e dados de pedidos por perfil, só dados fictícios."""
from unittest.mock import Mock

import pytest

from src import config, estoque, operadores, pedidos, seguranca, whatsapp
from src.db import get_conn, init_db


@pytest.fixture
def loja(tmp_path, monkeypatch):
    for campo, valor in {
        'DATABASE_PATH': str(tmp_path/'permissoes-ficticias.db'), 'SEED_CATALOGO': False,
        'MODO_TESTE': True, 'WHATSAPP_PROVIDER': 'TESTE', 'IA_PROVIDER': '',
        'FORMAS_PAGAMENTO': 'Pix,Dinheiro', 'ADMIN_PERMITIR_REMOTO': False,
    }.items():
        monkeypatch.setattr(config, campo, valor)
    monkeypatch.setattr(seguranca, '_tentativas', {})
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', Mock())
    init_db(seed_cardapio=False)
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'desktop-permissoes-ficticio')
    with get_conn() as conn:
        for uid, perfil in ((1, 'ADMIN'), (2, 'ADMIN'), (3, 'ATENDENTE'), (4, 'CAIXA')):
            conn.execute('INSERT INTO operadores(id,nome,login,senha_hash,perfil,versao) VALUES(?,?,?,?,?,?)',
                         (uid, 'Pessoa fictícia', 'conta.ficticia'+str(uid), 'hash-ficticio',
                          perfil, 'versao-ficticia-'+str(uid)))
    cliente = app.test_client()
    cliente.get('/gestao?acesso=desktop-permissoes-ficticio')
    with cliente.session_transaction() as sessao:
        sessao['operador_id'] = 1
        sessao['operador_versao'] = 'versao-ficticia-1'
        headers = {'X-CSRF-Token': sessao['csrf']}
    return cliente, headers


def _conta(login='nova.ficticia', perfil='ADMIN'):
    return {'nome': 'Nova pessoa fictícia', 'login': login,
            'senha': 'senha-ficticia-de-teste-123', 'perfil': perfil}


@pytest.mark.parametrize('uid,exibe_custo', [(1, True), (3, False)])
def test_custos_do_pedido_seguem_perfil_tambem_ao_avancar(loja, uid, exibe_custo):
    cliente, headers = loja
    with cliente.session_transaction() as sessao:
        sessao['operador_id'] = uid
        sessao['operador_versao'] = 'versao-ficticia-'+str(uid)
    produto = estoque.salvar_produto({'nome': 'Produto fictício', 'categoria': 'Teste',
                                      'preco': 10, 'custo': 3.21, 'estoque': 5})
    pedido = pedidos.criar_pedido('5500000000001', 'Cliente fictício',
                                  [{'produto_id': produto['id'], 'quantidade': 1}], 'Pix')
    leitura = cliente.get('/gestao/api/pedidos')
    assert leitura.status_code == 200
    assert ('custo_unitario' in leitura.json[0]['itens'][0]) is exibe_custo
    resposta = cliente.post(f"/gestao/api/pedidos/{pedido['id']}/avancar",
                            headers=headers, json={'status': 'CONFIRMADO'})
    assert resposta.status_code == 200
    assert ('custo_unitario' in resposta.json['itens'][0]) is exibe_custo
    assert pedidos.obter_pedido(pedido['id'])['itens'][0]['custo_unitario'] == 3.21


@pytest.mark.parametrize('operacao', ['criar', 'alterar'])
@pytest.mark.parametrize('revogacao', ['perfil', 'ativo', 'versao'])
def test_revogacao_durante_hash_nao_permite_administrar_contas(loja, monkeypatch, operacao, revogacao):
    cliente, headers = loja
    senha_valida = operadores.senha_valida
    def revogar_durante_hash(senha):
        resultado = senha_valida(senha)
        with get_conn() as conn:
            if revogacao == 'perfil':
                conn.execute("UPDATE operadores SET perfil='ATENDENTE',versao='revogada-ficticia' WHERE id=1")
            elif revogacao == 'ativo':
                conn.execute("UPDATE operadores SET ativo=0,versao='revogada-ficticia' WHERE id=1")
            else:
                conn.execute("UPDATE operadores SET versao='revogada-ficticia' WHERE id=1")
        return resultado
    monkeypatch.setattr(operadores, 'senha_valida', revogar_durante_hash)
    if operacao == 'criar':
        resposta = cliente.post('/gestao/api/operadores', headers=headers, json=_conta())
    else:
        resposta = cliente.put('/gestao/api/operadores/1', headers=headers,
                                json={'ativo': True, 'perfil': 'ADMIN', 'senha': _conta()['senha']})
    assert resposta.status_code == 400
    with get_conn() as conn:
        atual = dict(conn.execute('SELECT perfil,ativo,versao FROM operadores WHERE id=1').fetchone())
        assert atual == {'perfil': 'ATENDENTE' if revogacao == 'perfil' else 'ADMIN',
                         'ativo': 0 if revogacao == 'ativo' else 1, 'versao': 'revogada-ficticia'}
        assert conn.execute('SELECT COUNT(*) FROM operadores').fetchone()[0] == 4
        assert not conn.execute("SELECT 1 FROM operadores WHERE login='nova.ficticia'").fetchone()


def _sem_contas(cliente):
    with get_conn() as conn:
        conn.execute('DELETE FROM operadores')
    with cliente.session_transaction() as sessao:
        sessao.pop('operador_id', None)
        sessao.pop('operador_versao', None)


def test_primeiro_cadastro_mantem_bootstrap_e_segundo_exige_o_responsavel(loja):
    cliente, headers = loja
    _sem_contas(cliente)
    assert cliente.post('/gestao/api/operadores', headers=headers,
                         json=_conta(perfil='ATENDENTE')).status_code == 400
    resposta = cliente.post('/gestao/api/operadores', headers=headers, json=_conta())
    assert resposta.status_code == 200
    with cliente.session_transaction() as sessao:
        assert sessao['operador_id'] == resposta.json['id']
    assert cliente.post('/gestao/api/operadores', headers=headers,
                         json=_conta('outra.ficticia', 'ATENDENTE')).status_code == 200


def test_outro_primeiro_cadastro_vencedor_nao_libera_segunda_conta_sem_login(loja, monkeypatch):
    cliente, headers = loja
    _sem_contas(cliente)
    senha_valida = operadores.senha_valida
    def primeiro_cadastro_concorrente(senha):
        resultado = senha_valida(senha)
        with get_conn() as conn:
            conn.execute('INSERT INTO operadores(nome,login,senha_hash,perfil,versao) VALUES(?,?,?,?,?)',
                         ('Responsável fictício vencedor', 'vencedor.ficticio', resultado, 'ADMIN', 'versao-vencedora-ficticia'))
        return resultado
    monkeypatch.setattr(operadores, 'senha_valida', primeiro_cadastro_concorrente)
    resposta = cliente.post('/gestao/api/operadores', headers=headers, json=_conta())
    assert resposta.status_code == 400
    with get_conn() as conn:
        assert conn.execute('SELECT COUNT(*) FROM operadores').fetchone()[0] == 1
        assert conn.execute('SELECT login FROM operadores').fetchone()[0] == 'vencedor.ficticio'
    with cliente.session_transaction() as sessao:
        assert 'operador_id' not in sessao and 'operador_versao' not in sessao
