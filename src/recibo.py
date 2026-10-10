"""Monta o cupom de confirmação do pedido no mesmo estilo do print
'**** DOCUMENTO NAO FISCAL ****'. É enviado como mensagem de texto (bloco de
código do WhatsApp, com três crases) logo depois da confirmação do pedido.
"""
from . import config

_LARGURA = 42


def _linha(char="-"):
    return char * _LARGURA


def _centralizar(texto: str) -> str:
    return texto.center(_LARGURA)


def montar_recibo(pedido: dict) -> str:
    linhas = []
    linhas.append(_centralizar("**** DOCUMENTO NAO FISCAL ****"))
    linhas.append("")
    linhas.append(_centralizar(config.NOME_RESTAURANTE.upper()))
    linhas.append("")
    linhas.append(f"N. Pedido: {pedido['numero_pedido']}")
    linhas.append(f"Origem:    {pedido.get('origem', 'Bot Atendimento')}")
    linhas.append(f"Data/Hora: {pedido['criado_em']}")
    linhas.append(_linha())
    linhas.append(f"Cliente:   {pedido['cliente_nome']}")
    linhas.append(f"Fone:      {pedido['cliente_telefone']}")
    linhas.append(_linha())

    if pedido["forma_entrega"] == "ENTREGA":
        linhas.append(f"F. ENTREGA: ENTREGA ({pedido['tempo_estimado_min']}m)")
        if pedido.get("cliente_endereco"):
            linhas.append(f"Endereco:  {pedido['cliente_endereco']}")
    else:
        linhas.append(f"F. ENTREGA: RETIRADA BALCAO ({pedido['tempo_estimado_min']}m)")

    linhas.append(_linha())
    linhas.append(f"{'Qtd':<4}{'Descricao':<24}{'V.Uni':>6}{'V.Total':>8}")
    linhas.append(_linha())
    for item in pedido["itens"]:
        subtotal = item["quantidade"] * item["preco_unitario"]
        linhas.append(
            f"{item['quantidade']:<4}{item['produto_nome']:<24}"
            f"{item['preco_unitario']:>6.2f}{subtotal:>8.2f}"
        )
    linhas.append(_linha())
    linhas.append(f"{'Total Itens:':<34}{pedido['total_itens']:>8.2f}")
    linhas.append(f"{'TOTAL PEDIDO:':<34}{pedido['total_pedido']:>8.2f}")
    linhas.append(_linha(" "))
    linhas.append(f"{'TOTAL PAGO:':<34}{pedido['total_pago']:>8.2f}")
    linhas.append(f"{'TOTAL A PAGAR:':<34}{(pedido['total_pedido'] - pedido['total_pago']):>8.2f}")
    linhas.append(f"{'TROCO:':<34}{0.0:>8.2f}")
    linhas.append("")
    linhas.append(f"F. PAGAMENTO.: {pedido['forma_pagamento']}")

    corpo = "\n".join(linhas)
    return f"```\n{corpo}\n```"


def montar_mensagem_confirmacao(pedido: dict) -> str:
    return (
        f"Seu pedido {pedido['numero_pedido']} foi realizado com sucesso. "
        f"Vou te atualizando sobre o processo do seu pedido por aqui."
    )


_TEXTOS_STATUS = {
    "CONFIRMADO": (
        "Pedido confirmado.\nRecebemos o seu pedido. "
        "Você pode retirar seu pedido em aproximadamente {tempo} minutos..."
    ),
    "EM_PREPARO": "Estamos separando os produtos do seu pedido. 📦",
    "PRONTO": "Pronto para retirada.\nPode vir, seu pedido já está lhe aguardando...",
    "ENTREGUE": "Pedido entregue. Obrigado pela sua compra!",
    "RETIRADO": "Pedido retirado. Obrigado pela preferência, volte sempre!",
    "CANCELADO": "Seu pedido foi cancelado. Qualquer dúvida, é só chamar por aqui.",
}


def montar_mensagem_status(pedido: dict, novo_status: str) -> str:
    modelo = _TEXTOS_STATUS.get(novo_status, f"Status do pedido atualizado: {novo_status}")
    texto = modelo.format(tempo=pedido["tempo_estimado_min"])
    return f"Atualização Pedido {pedido['numero_pedido']}\n{texto}"
