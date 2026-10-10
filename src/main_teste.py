"""Simula um atendimento completo pelo bot sem precisar do WhatsApp real.
Rode com: python -m src.main_teste
"""
from . import bot, cardapio, pedidos, recibo
from .db import init_db
from .links import link_valido, marcar_link_usado

TELEFONE_TESTE = "5547999998888"


def main():
    init_db()

    print("== Simulando conversa no bot ==\n")
    print("Cliente: Opa")
    print("Bot:", bot.processar_mensagem(TELEFONE_TESTE, "Opa"))

    print("\nCliente: 2")
    resposta = bot.processar_mensagem(TELEFONE_TESTE, "2")
    print("Bot:", resposta)
    link = resposta.replace("Faça o seu pedido em ", "").strip()
    token = link.rsplit("/", 1)[-1]

    ok, msg, dados_link = link_valido(token)
    assert ok, msg

    print("\n== Cliente abre o link e monta o pedido ==")
    produtos = cardapio.listar_produtos_ativos()
    itens_escolhidos = [
        {"produto_id": produtos[0]["id"], "quantidade": 1},
        {"produto_id": produtos[4]["id"], "quantidade": 1},
    ]

    pedido = pedidos.criar_pedido(
        telefone=TELEFONE_TESTE,
        nome_cliente="Cleryton Chagas",
        itens=itens_escolhidos,
        forma_pagamento="VALE ALIMENTACAO (COOPCERTO CABAL)",
        forma_entrega="RETIRADA BALCAO",
    )
    marcar_link_usado(token, pedido["id"])

    print("\nBot:", recibo.montar_mensagem_confirmacao(pedido))
    print("\nBot:")
    print(recibo.montar_recibo(pedido))
    print("\nBot:", recibo.montar_mensagem_status(pedido, "CONFIRMADO"))

    print("\n== Tentando reusar o mesmo link (tem que falhar) ==")
    ok2, msg2, _ = link_valido(token)
    print(f"Link reutilizável? {ok2} — {msg2}")


if __name__ == "__main__":
    main()
