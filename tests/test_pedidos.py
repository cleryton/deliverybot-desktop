import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from src import config


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Cada teste roda num banco SQLite novo e isolado."""
    db_path = tmp_path / "teste.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    from src.db import init_db
    init_db()
    yield


def test_gera_numero_pedido_com_oito_digitos():
    from src.pedidos import gerar_numero_pedido
    numero = gerar_numero_pedido()
    assert numero.startswith("#")
    assert len(numero) == 9
    assert numero[1:].isdigit()


def test_criar_pedido_calcula_total_corretamente():
    from src import cardapio, pedidos

    produtos = cardapio.listar_produtos_ativos()
    x_bacon = next(p for p in produtos if p["nome"] == "X-Bacon")
    guarana = next(p for p in produtos if p["nome"] == "Guaraná Zero Açúcar")

    pedido = pedidos.criar_pedido(
        telefone="5547999998888",
        nome_cliente="Cleryton Chagas",
        itens=[
            {"produto_id": x_bacon["id"], "quantidade": 1},
            {"produto_id": guarana["id"], "quantidade": 1},
        ],
        forma_pagamento="VALE ALIMENTACAO (COOPCERTO CABAL)",
        forma_entrega="RETIRADA BALCAO",
    )

    assert pedido["total_itens"] == pytest.approx(31.00)
    assert pedido["total_pedido"] == pytest.approx(31.00)  # sem taxa: é retirada no balcão
    assert pedido["status"] == "RECEBIDO"
    assert len(pedido["itens"]) == 2


def test_pedido_com_entrega_soma_taxa_de_entrega():
    from src import cardapio, pedidos

    produtos = cardapio.listar_produtos_ativos()
    item = produtos[0]

    pedido = pedidos.criar_pedido(
        telefone="5547988887777",
        nome_cliente="Fulano",
        itens=[{"produto_id": item["id"], "quantidade": 1}],
        forma_pagamento="Pix",
        forma_entrega="ENTREGA",
    )

    assert pedido["total_pedido"] == pytest.approx(item["preco"] + config.TAXA_ENTREGA)


def test_link_de_pedido_e_de_uso_unico():
    from src.links import gerar_link_pedido, link_valido, marcar_link_usado
    from src import cardapio, pedidos

    link = gerar_link_pedido("5547999990000")
    token = link.rsplit("/", 1)[-1]

    ok, _, dados = link_valido(token)
    assert ok is True

    produto = cardapio.listar_produtos_ativos()[0]
    pedido = pedidos.criar_pedido(
        telefone="5547999990000",
        nome_cliente="Teste",
        itens=[{"produto_id": produto["id"], "quantidade": 1}],
        forma_pagamento="Dinheiro",
    )
    marcar_link_usado(token, pedido["id"])

    ok_depois, msg_depois, _ = link_valido(token)
    assert ok_depois is False
    assert "usado" in msg_depois.lower()


def test_link_inexistente_e_invalido():
    from src.links import link_valido
    ok, msg, dados = link_valido("token-que-nao-existe")
    assert ok is False
    assert dados is None


def test_fila_de_preparo_avanca_status_do_pedido():
    from src import cardapio, fila, pedidos

    produto = cardapio.listar_produtos_ativos()[0]
    pedido = pedidos.criar_pedido(
        telefone="5547977776666",
        nome_cliente="Cliente Fila",
        itens=[{"produto_id": produto["id"], "quantidade": 1}],
        forma_pagamento="Dinheiro",
    )

    fila_inicial = fila.listar_fila()
    assert any(f["pedido_id"] == pedido["id"] and f["status"] == "AGUARDANDO" for f in fila_inicial)

    pedido_atualizado = fila.avancar_status(pedido["id"])
    assert pedido_atualizado["status"] == "EM_PREPARO"

    pedido_atualizado = fila.avancar_status(pedido["id"])
    assert pedido_atualizado["status"] == "PRONTO"


def test_recibo_contem_documento_nao_fiscal_e_itens():
    from src import cardapio, pedidos, recibo

    produto = cardapio.listar_produtos_ativos()[0]
    pedido = pedidos.criar_pedido(
        telefone="5547966665555",
        nome_cliente="Cliente Recibo",
        itens=[{"produto_id": produto["id"], "quantidade": 2}],
        forma_pagamento="Pix",
    )

    texto = recibo.montar_recibo(pedido)
    assert "DOCUMENTO NAO FISCAL" in texto
    assert pedido["numero_pedido"] in texto
    assert produto["nome"] in texto
