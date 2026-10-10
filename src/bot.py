"""Ponto de entrada da conversa do bot.

Por padrão, tenta responder com a IA (ia.responder -- conversa natural,
sem menu numerado). Se a IA não estiver configurada ou a chamada falhar por
qualquer motivo (sem internet, sem créditos, chave inválida, etc.), cai de
volta no menu fixo numerado original, para o atendimento nunca parar de
funcionar.

Também aplica um limite simples de taxa por telefone: mensagens do MESMO
número chegando mais rápido que RATE_LIMIT_SEGUNDOS não disparam uma nova
chamada de IA (que tem custo, seja em dinheiro no caso do Claude, seja em
CPU/memória no caso do Ollama) -- usam o menu fixo nesse meio tempo. Isso
protege contra flood (de propósito ou por um webhook retransmitindo em
loop) sem bloquear o cliente de verdade.
"""
import logging
import time

from . import cardapio, config, ia
from .links import gerar_link_pedido

logger = logging.getLogger(__name__)

MENU_TEXTO = (
    "Seja bem-vindo ao nosso autoatendimento 🤖 no que posso ajudar?\n\n"
    "Aqui vão algumas coisas em que eu consigo te ajudar! Digite o número para "
    "iniciar o atendimento:\n"
    "1 - Horário de funcionamento ⏰\n"
    "2 - Realizar pedidos 📝\n"
    "3 - Formas de pagamento 💵\n"
    "4 - Catálogo de produtos 📦\n"
    "5 - Telefone ☎️\n"
    "6 - Promoções 💰\n"
    "7 - Taxa de entrega 🛵\n"
    "8 - Endereço 📍"
)

_ultima_chamada_ia: dict[str, float] = {}


def _dentro_do_rate_limit(telefone: str) -> bool:
    """True se o telefone já chamou a IA há menos de RATE_LIMIT_SEGUNDOS."""
    if config.RATE_LIMIT_SEGUNDOS <= 0:
        return False
    agora = time.monotonic()
    ultima = _ultima_chamada_ia.get(telefone)
    if ultima is not None and (agora - ultima) < config.RATE_LIMIT_SEGUNDOS:
        return True
    _ultima_chamada_ia[telefone] = agora
    return False


def _resposta_opcao(opcao: str, telefone: str) -> str | None:
    if opcao == "1":
        return f"⏰ Nosso horário de funcionamento:\n{config.HORARIO_FUNCIONAMENTO}"
    if opcao == "2":
        link = gerar_link_pedido(telefone)
        return f"Faça o seu pedido em {link}"
    if opcao == "3":
        return "💵 Formas de pagamento aceitas:\n" + "\n".join("• " + p.strip() for p in config.FORMAS_PAGAMENTO.split(","))
    if opcao == "4":
        return cardapio.texto_cardapio()
    if opcao == "5":
        return f"☎️ Telefone: {config.TELEFONE_RESTAURANTE}"
    if opcao == "6":
        return "💰 Fique de olho por aqui! Assim que tivermos promoções ativas, avisamos você."
    if opcao == "7":
        return f"🛵 Taxa de entrega: R$ {config.TAXA_ENTREGA:.2f} (grátis na retirada no balcão)"
    if opcao == "8":
        return f"📍 Endereço: {config.ENDERECO_RESTAURANTE}"
    return None


def _processar_mensagem_menu_fixo(telefone: str, texto_limpo: str) -> str:
    """Comportamento de reserva: menu numerado fixo (sem custo, sem IA)."""
    resposta_opcao = _resposta_opcao(texto_limpo, telefone)
    if resposta_opcao is not None:
        return resposta_opcao

    # Qualquer outra mensagem (saudação, ou texto que não bate com o menu) volta pro menu.
    return MENU_TEXTO


def processar_mensagem(telefone: str, texto: str) -> str:
    """Recebe o texto do cliente e devolve a resposta do bot."""
    texto_limpo = (texto or "").strip()

    if _dentro_do_rate_limit(telefone):
        logger.info("Rate limit: %s mandou mensagem rápido demais, usando menu fixo", telefone)
        return _processar_mensagem_menu_fixo(telefone, texto_limpo)

    try:
        return ia.responder(telefone, texto_limpo)
    except ia.IAIndisponivel as exc:
        logger.warning("IA indisponível, usando menu fixo: %s", exc)

    return _processar_mensagem_menu_fixo(telefone, texto_limpo)
