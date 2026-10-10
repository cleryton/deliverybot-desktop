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
    "8 - Endereço 📍\n"
    "9 - Privacidade e seus dados 🔒\n"
    "10 - Falar com atendente ☏"
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
    if opcao == "9" or opcao.casefold() in {"privacidade", "lgpd", "meus dados"}:
        contato = config.LGPD_CONTATO or config.TELEFONE_RESTAURANTE or "esta conversa com a loja"
        return f"🔒 Usamos seus dados para atendimento e pedidos. Para acesso, correção ou remoção, fale com o responsável: {contato}. Aviso de privacidade: {config.BASE_URL}/privacidade"
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
    from . import humano
    comando=(texto or '').strip().casefold()
    privacidade=comando in {'9','privacidade','lgpd','meus dados'}
    if humano.pausado(telefone) and not privacidade:
        return None
    if comando in {'atendente','humano','falar com atendente','10'}:
        humano.solicitar(telefone)
        resposta='Recebemos seu pedido de atendimento humano. Aguarde a equipe; o bot ficará pausado nesta conversa.'
    else:
        resposta = _processar(telefone, texto)
    """Recebe o texto do cliente e devolve a resposta do bot."""
    from .db import get_conn
    with get_conn() as conn:
        novo = conn.execute("INSERT OR IGNORE INTO sessoes_bot (telefone, estado) VALUES (?, 'AVISO_PRIVACIDADE')", (telefone,)).rowcount
    if novo and (texto or "").strip().casefold() not in {"9", "privacidade", "lgpd", "meus dados"}:
        resposta += f"\n\n🔒 Para saber como usamos seus dados e falar com o responsável, digite PRIVACIDADE ou veja {config.BASE_URL}/privacidade"
    return resposta


def _processar(telefone: str, texto: str) -> str:
    texto_limpo = (texto or "").strip()
    if texto_limpo == "9" or texto_limpo.casefold() in {"privacidade", "lgpd", "meus dados"}:
        return _resposta_opcao(texto_limpo, telefone)

    if _dentro_do_rate_limit(telefone):
        logger.info("Limite de frequência aplicado ao atendimento")
        return _processar_mensagem_menu_fixo(telefone, texto_limpo)

    try:
        return ia.responder(telefone, texto_limpo)
    except ia.IAIndisponivel as exc:
        logger.warning("IA indisponível; atendimento continuará pelo menu")

    return _processar_mensagem_menu_fixo(telefone, texto_limpo)
