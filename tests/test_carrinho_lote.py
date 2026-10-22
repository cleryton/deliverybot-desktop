"""Orçamento em lote preserva quantidades, preços e estoque da transação."""
from decimal import Decimal

import pytest

from src import config, db, pedidos


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path/'ficticio.db'))
    db.init_db(seed_cardapio=False)
    with db.get_conn() as conn:
        conn.executemany('INSERT INTO produtos(nome,categoria,preco,estoque,fracionado,custo) VALUES(?,?,?,?,?,?)',
                         [(f'Produto {i}', 'Teste', 10.01, 100, 1, 3) for i in range(850)])


@pytest.mark.parametrize('tamanho,limite', [(1,1),(120,1),(850,3)])
def test_consultas_de_catalogo_crescem_por_lote_e_nao_por_item(loja,tamanho,limite):
    with db.get_conn() as conn:
        consultas=[]
        conn.set_trace_callback(lambda sql: consultas.append(sql) if sql.lstrip().upper().startswith('SELECT') else None)
        total,itens=pedidos._resolver_itens(conn,[{'produto_id':i,'quantidade':'0.5'} for i in range(1,tamanho+1)])
    assert len(consultas)<=limite
    assert total==Decimal('5.01')*tamanho and len(itens)==tamanho
    assert [i['produto_id'] for i in itens]==list(range(1,tamanho+1))


def test_itens_repetidos_somam_antes_de_validar_saldo(loja):
    with db.get_conn() as conn:
        total,itens=pedidos._resolver_itens(conn,[{'produto_id':1,'quantidade':'0.4'},{'produto_id':1,'quantidade':'0.6'}])
        assert total==Decimal('10.01') and itens[0]['quantidade']==1
        with pytest.raises(ValueError,match='Estoque insuficiente'):
            pedidos._resolver_itens(conn,[{'produto_id':1,'quantidade':60},{'produto_id':1,'quantidade':60}])


@pytest.mark.parametrize('mudanca', ['inativo','ausente','inteiro'])
def test_dados_atuais_do_banco_sempre_prevalecem(loja,mudanca):
    with db.get_conn() as conn:
        if mudanca=='inativo':conn.execute('UPDATE produtos SET ativo=0 WHERE id=1')
        elif mudanca=='ausente':conn.execute('DELETE FROM produtos WHERE id=1')
        else:conn.execute('UPDATE produtos SET fracionado=0 WHERE id=1')
        with pytest.raises(ValueError):
            pedidos._resolver_itens(conn,[{'produto_id':1,'quantidade':'0.5'}])


def test_orcamento_publico_nao_expoe_custo_e_relê_preco(loja):
    itens=[{'produto_id':1,'quantidade':1}]
    antes=pedidos.cotacao(itens,'RETIRADA BALCAO')
    with db.get_conn() as conn:conn.execute('UPDATE produtos SET preco=15 WHERE id=1')
    depois=pedidos.cotacao(itens,'RETIRADA BALCAO')
    assert antes['total_pedido']==10.01 and depois['total_pedido']==15
    assert 'custo' not in depois['itens'][0]


def test_orcamento_grande_nao_mistura_precos_durante_edicao_concorrente(loja,monkeypatch):
    abrir=db._connect
    alterado=[]
    class Conexao:
        def __init__(self):self.conn=abrir()
        def __getattr__(self,nome):return getattr(self.conn,nome)
        def execute(self,sql,*args):
            cursor=self.conn.execute(sql,*args)
            if 'FROM produtos WHERE id IN' not in sql or alterado:return cursor
            def linhas():
                yield from cursor
                outra=abrir()
                try:
                    outra.execute('UPDATE produtos SET preco=99 WHERE id=850');outra.commit()
                    alterado.append(True)
                finally:outra.close()
            return linhas()
    monkeypatch.setattr(db,'_connect',Conexao)
    cotacao=pedidos.cotacao([{'produto_id':i,'quantidade':1} for i in range(1,851)],'RETIRADA BALCAO')
    assert alterado and cotacao['total_itens']==float(Decimal('10.01')*850)
    assert pedidos.cotacao([{'produto_id':850,'quantidade':1}],'RETIRADA BALCAO')['total_itens']==99
