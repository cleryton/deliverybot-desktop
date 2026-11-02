"""Identificação por compra, com banco e clientes inteiramente fictícios."""
import pytest

from src import config, db, estoque, fila, pedidos, privacidade, recibo


TELEFONE = '5511999990173'


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticio.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    monkeypatch.setattr(config, 'FORMAS_PAGAMENTO', 'Pix,Dinheiro')
    monkeypatch.setattr(config, 'MODO_TESTE', True)
    db.init_db()
    return estoque.salvar_produto({'nome': 'Lanche fictício', 'categoria': 'Teste', 'preco': 10, 'estoque': 20})['id']


def comprar(produto, nome='Cliente primeiro', cep='01000-000', endereco='Rua primeira, 123', entrega='ENTREGA'):
    return pedidos.criar_pedido(TELEFONE, nome, [{'produto_id': produto, 'quantidade': 1}],
                               'Pix', forma_entrega=entrega, cep=cep, endereco=endereco)


def test_nova_compra_nao_altera_identificacao_endereco_ou_recibo_da_anterior(loja):
    primeiro = comprar(loja)
    segundo = comprar(loja, 'Cliente segundo', '02000-000', 'Rua segunda, 456')
    antigo = pedidos.obter_pedido(primeiro['id'])
    assert antigo == primeiro
    assert antigo['cliente_endereco'] == 'Rua primeira, 123'
    assert segundo['cliente_endereco'] == 'Rua segunda, 456'
    por_id = {p['id']: p for p in pedidos.listar_pedidos()}
    assert por_id[primeiro['id']] == primeiro and por_id[segundo['id']] == segundo
    nomes = {p['pedido_id']: p['cliente_nome'] for p in fila.listar_fila()}
    assert nomes == {primeiro['id']: 'Cliente primeiro', segundo['id']: 'Cliente segundo'}
    mensagem = recibo.montar_recibo(antigo)
    assert 'Rua primeira' in mensagem and 'Rua segunda' not in mensagem
    assert not {'nome_cliente', 'telefone_cliente', 'cep_cliente', 'endereco_cliente'} & antigo.keys()


def test_retirada_sem_endereco_nao_herda_endereco_de_compra_anterior(loja):
    comprar(loja)
    retirada = comprar(loja, 'Cliente retirada', '', '', 'RETIRADA BALCAO')
    assert retirada['cliente_endereco'] == retirada['cliente_cep'] == ''
    assert pedidos.obter_pedido(retirada['id'])['cliente_endereco'] == ''


def test_atualizar_cadastro_nao_reescreve_compra_confirmada(loja):
    primeiro = comprar(loja)
    pedidos.obter_ou_criar_cliente(TELEFONE, 'Nome novo', '03000-000', 'Rua terceira, 789')
    assert pedidos.obter_pedido(primeiro['id']) == primeiro


def test_migracao_legada_congela_so_dados_ainda_disponiveis_e_e_idempotente(loja):
    with db.get_conn() as conn:
        for campo in ('nome_cliente', 'telefone_cliente', 'cep_cliente', 'endereco_cliente'):
            conn.execute('ALTER TABLE pedidos DROP COLUMN ' + campo)
        cid = conn.execute('INSERT INTO clientes(nome,telefone,cep,endereco) VALUES(?,?,?,?)',
                           ('Legado conhecido', TELEFONE, '01000-000', 'Rua conhecida')).lastrowid
        pid = conn.execute("INSERT INTO pedidos(numero_pedido,cliente_id,forma_entrega,tempo_estimado_min,"
                           "forma_pagamento,total_itens,total_pedido) VALUES('#12345678',?,'ENTREGA',30,'Pix',10,15)", (cid,)).lastrowid
    db.init_db(forcar=True)
    migrado = pedidos.obter_pedido(pid)
    assert migrado['cliente_nome'] == 'Legado conhecido' and migrado['cliente_endereco'] == 'Rua conhecida'
    with db.get_conn() as conn:
        conn.execute("UPDATE clientes SET nome='Cadastro posterior', endereco='Outro endereço' WHERE id=?", (cid,))
    db.init_db(forcar=True)
    assert pedidos.obter_pedido(pid) == migrado


def test_migracao_nao_herda_dados_futuros_quando_legado_nao_tem_endereco(loja):
    primeiro = comprar(loja)
    with db.get_conn() as conn:
        conn.execute('UPDATE pedidos SET cep_cliente=NULL,endereco_cliente=NULL WHERE id=?', (primeiro['id'],))
        conn.execute('UPDATE clientes SET cep=NULL,endereco=NULL WHERE telefone=?', (TELEFONE,))
    db.init_db(forcar=True)
    pedidos.obter_ou_criar_cliente(TELEFONE, 'Cadastro posterior', '02000-000', 'Endereço posterior')
    db.init_db(forcar=True)
    antigo = pedidos.obter_pedido(primeiro['id'])
    assert antigo['cliente_endereco'] == antigo['cliente_cep'] == ''


def test_correcao_explicita_e_remocao_tambem_abrangem_retratos_dos_pedidos(loja):
    primeiro = comprar(loja)
    segundo = comprar(loja, 'Outro nome', '02000-000', 'Outra rua')
    titular = {'telefone': TELEFONE, 'identidade_confirmada': True}
    privacidade.corrigir({**titular, 'nome': 'Identidade corrigida', 'cep': '', 'endereco': ''})
    assert pedidos.obter_pedido(primeiro['id'])['cliente_nome'] == 'Identidade corrigida'
    for pedido in (primeiro, segundo):
        pedidos.cancelar_pedido(pedido['id'])
    privacidade.remover_identificacao({**titular, 'confirmar_remocao': True})
    db.init_db(forcar=True)
    with db.get_conn() as conn:
        linhas = conn.execute('SELECT nome_cliente,telefone_cliente,cep_cliente,endereco_cliente FROM pedidos').fetchall()
    for linha in linhas:
        assert linha['nome_cliente'] == 'Cliente sem identificação'
        assert linha['telefone_cliente'].startswith('removido:')
        assert linha['cep_cliente'] == linha['endereco_cliente'] == ''
    assert TELEFONE not in str([dict(l) for l in linhas])
    assert pedidos.obter_pedido(primeiro['id'])['total_pedido'] == primeiro['total_pedido']
