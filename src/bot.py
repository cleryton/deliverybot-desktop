"""Conversa natural: respostas locais rápidas, IA com contexto e links validados."""
import logging
import re
import threading
import time

from . import cardapio, config, ia, protecao_ia
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
_trava_rate_limit = threading.Lock()


def _dentro_do_rate_limit(telefone: str) -> bool:
    """True se o telefone já chamou a IA há menos de RATE_LIMIT_SEGUNDOS."""
    if config.RATE_LIMIT_SEGUNDOS <= 0:
        return False
    agora = time.monotonic()
    with _trava_rate_limit:
        if len(_ultima_chamada_ia) >= 4096:
            for chave, instante in list(_ultima_chamada_ia.items()):
                if agora - instante >= max(config.RATE_LIMIT_SEGUNDOS, 60):
                    _ultima_chamada_ia.pop(chave, None)
            if len(_ultima_chamada_ia) >= 4096:
                _ultima_chamada_ia.pop(next(iter(_ultima_chamada_ia)), None)
        ultima = _ultima_chamada_ia.get(telefone)
        if ultima is not None and (agora - ultima) < config.RATE_LIMIT_SEGUNDOS:
            return True
        _ultima_chamada_ia[telefone] = agora
        return False


def _resposta_opcao(opcao: str, telefone: str) -> str | None:
    from .publicacao import endereco
    if opcao == "9" or opcao.casefold() in {"privacidade", "lgpd", "meus dados"}:
        contato = config.LGPD_CONTATO or config.TELEFONE_RESTAURANTE or "esta conversa com a loja"
        aviso = f" Aviso de privacidade: {endereco()}/privacidade" if endereco() else ''
        return f"🔒 Usamos seus dados para atendimento e pedidos. Para acesso, correção ou remoção, fale com o responsável: {contato}." + aviso
    if opcao == "1":
        return f"Nosso horário informado é {config.HORARIO_FUNCIONAMENTO}." if config.HORARIO_FUNCIONAMENTO else "Ainda não tenho o horário cadastrado. Digite ATENDENTE para confirmar com a equipe."
    if opcao == "2":
        try:
            link = gerar_link_pedido(telefone)
        except ValueError:
            return ia.PEDIDO_INDISPONIVEL
        return ia.resposta_link(link, ia._historico_mensagens(telefone))
    if opcao == "3":
        formas = [p.strip() for p in config.FORMAS_PAGAMENTO.split(",") if p.strip()]
        return "Você pode pagar com " + ", ".join(formas) + "." if formas else "As formas de pagamento ainda não foram cadastradas. Digite ATENDENTE para confirmar com a equipe."
    if opcao == "4":
        return cardapio.texto_cardapio()
    if opcao == "5":
        return f"O telefone da loja é {config.TELEFONE_RESTAURANTE}." if config.TELEFONE_RESTAURANTE else "Para falar com a equipe por aqui, digite ATENDENTE."
    if opcao == "6":
        return "Não tenho nenhuma promoção cadastrada agora. Os preços atuais estão no catálogo."
    if opcao == "7":
        taxa = f"{config.TAXA_ENTREGA:.2f}".replace(".", ",")
        return f"A taxa de entrega é R$ {taxa}. Se preferir retirar na loja, não há taxa de entrega."
    if opcao == "8":
        return f"A loja fica em {config.ENDERECO_RESTAURANTE}." if config.ENDERECO_RESTAURANTE else "O endereço ainda não foi cadastrado. Digite ATENDENTE para confirmar com a equipe."
    return None


def _resposta_rapida(telefone: str, texto: str) -> str | None:
    """Resolve perguntas objetivas com o cadastro, sem esperar uma inferência."""
    opcao = _resposta_opcao(texto, telefone)
    if opcao is not None:
        return opcao
    comando = ia.normalizar_texto(texto).strip(".!? ")
    if re.search(r"\b(privacidade|lgpd|meus dados|dados pessoais)\b", comando):
        return _resposta_opcao("9", telefone)
    if comando in {"menu", "ajuda", "opcoes"}:
        return MENU_TEXTO
    if comando in {"oi", "ola", "opa", "bom dia", "boa tarde", "boa noite", "e ai", "oie", "oii", "oiii", "hello"}:
        historico = ia._historico_mensagens(telefone)
        anteriores = [m["content"] for m in historico if m["role"] == "assistant"]
        saudacao = texto.strip(".!? ")
        if anteriores:
            return f"{saudacao[:1].upper() + saudacao[1:]}! Me conta, em que posso te ajudar?"
        return f"{saudacao[:1].upper() + saudacao[1:]}! Boas-vindas! Aqui é {config.NOME_RESTAURANTE}. Como posso te ajudar?"
    if comando in {"obrigado", "obrigada", "valeu", "muito obrigado", "muito obrigada", "obg", "agradeco"}:
        return "Por nada! Foi um prazer ajudar 😊"
    quer_pedido = ia.intencao_pedido(texto)
    if not quer_pedido and re.search(r"\b(meu pedido|status do pedido|pedido chegou|nao chegou|paguei|estorno|reembolso|cancelar pedido|cancelar meu pedido)\b", comando):
        return "A equipe precisa conferir os detalhes do seu pedido. Digite ATENDENTE para falar com uma pessoa por aqui."
    if comando in {"sim", "pode", "pode sim", "manda", "quero", "quero sim", "pode mandar"}:
        if ia.intencao_pedido(texto, ia._historico_mensagens(telefone)):
            return _resposta_opcao("2", telefone)
        return None
    opcoes = []
    for numero, padrao in (
        ("1", r"\b(horario|que horas|abre|abrem|fecha|fecham|funcionamento)\b"),
        ("3", r"\b(formas? de pagamento|como (?:eu )?pago|aceita[m]? pix|aceita[m]? cartao)\b"),
        ("4", r"\b(catalogo|cardapio)\b"),
        ("5", r"\b(telefone|numero da loja|contato da loja)\b"),
        ("6", r"\b(promocao|promocoes|desconto)\b"),
        ("7", r"\b(taxa de entrega|valor (?:da|do) (?:entrega|frete)|quanto (?:e|custa|fica) (?:a |o )?(?:entrega|frete))\b"),
        ("8", r"\b(endereco da loja|onde fica|onde voces ficam|localizacao|endereco de voces)\b"),
    ):
        if re.search(padrao, comando):
            opcoes.append(numero)
    # Perguntas sobre feriados, cobertura, pagamento específico ou exceções
    # precisam de contexto: o cadastro geral não confirma essas condições.
    excepcao = re.search(r"\b(hoje|agora|feriado|amanha|domingo|bairro|gratis|gratuito|parcel|prazo)\w*\b", comando)
    if quer_pedido:
        if excepcao:
            return None
        complemento = " ".join(_resposta_opcao(o, telefone) for o in opcoes)
        if not complemento and re.search(r"\b(quanto|preco|valor|custa|qual|quais|como|onde|quando|prazo)\b", comando):
            return None  # A pergunta adicional precisa de contexto do modelo.
        link = _resposta_opcao("2", telefone)
        return complemento + "\n\n" + link if complemento else link
    if len(opcoes) == 1 and not excepcao:
        if opcoes[0] == "3" and re.search(r"\baceita[m]?\b", comando):
            meio = "pix" if "pix" in comando else "cartao"
            cadastro = ia.normalizar_texto(config.FORMAS_PAGAMENTO)
            if meio not in cadastro:
                return f"Os pagamentos cadastrados são {config.FORMAS_PAGAMENTO or 'ainda não informados'}. Para confirmar outra forma, digite ATENDENTE."
        return _resposta_opcao(opcoes[0], telefone)
    if not opcoes and re.search(r"\b(quanto|preco|valor|custa|custam)\b", comando):
        consulta = " ".join(re.sub(r"[^\w]+", " ", comando).split())
        produtos = []
        for produto in cardapio.listar_produtos_ativos():
            nome = " ".join(re.sub(r"[^\w]+", " ", ia.normalizar_texto(produto["nome"])).split())
            if nome and re.search(r"(?<!\w)" + re.escape(nome) + r"(?!\w)", consulta):
                produtos.append(produto)
        if len(produtos) == 1:
            produto = produtos[0]
            preco = f"{produto['preco']:.2f}".replace(".", ",")
            unidade = produto.get("unidade") or "un"
            return f"{produto['nome']} custa R$ {preco}/{unidade}. Você confere o valor e a disponibilidade ao confirmar o pedido."
    return None


def _processar_mensagem_menu_fixo(telefone: str, texto_limpo: str) -> str:
    """Reserva natural: o atendimento continua mesmo quando a IA falha."""
    resposta_opcao = _resposta_rapida(telefone, texto_limpo)
    if resposta_opcao is not None:
        return resposta_opcao

    return "Me conta um pouco mais: você quer saber sobre um produto, entrega ou fazer um pedido? Se preferir uma pessoa da equipe, digite ATENDENTE."


def processar_mensagem(telefone: str, texto: str) -> str | None:
    """Recebe o texto do cliente e devolve uma resposta pronta para envio."""
    from . import humano
    if not (texto or '').strip():
        return None
    comando=(texto or '').strip().casefold()
    privacidade=protecao_ia.privacidade(texto)
    if privacidade:
        texto='PRIVACIDADE'
        comando='privacidade'
    with protecao_ia.trava(telefone):
        if not privacidade and protecao_ia.verificar(telefone,texto):
            return None
        geracao=protecao_ia.versao(telefone)
    if humano.pausado(telefone) and not privacidade:
        return None
    pedido_humano = comando in {'atendente','humano','falar com atendente','10'} or bool(re.search(r"\b(?:quero |preciso |posso )?falar com (?:um |uma |o |a )?(?:atendente|humano|humana|pessoa|alguem)\b", ia.normalizar_texto(texto)))
    if pedido_humano:
        humano.solicitar(telefone)
        resposta='Recebemos seu pedido de atendimento humano. Aguarde a equipe; o bot ficará pausado nesta conversa.'
    else:
        resposta = _processar(telefone, texto)
    if resposta is None:
        return None
    if not privacidade:
        try:
            protecao_ia.validar_saida(telefone,resposta,geracao)
        except protecao_ia.ConversaBloqueada:
            return None
    from .links import atualizar_resposta
    try:
        resposta = atualizar_resposta(resposta, telefone)
    except ValueError:
        logger.warning("Resposta com link indisponível ou não autorizado; atendimento seguro aplicado")
        resposta = (_resposta_opcao('2', telefone) if ia.intencao_pedido(texto, ia._historico_mensagens(telefone)) else ia.PEDIDO_INDISPONIVEL)
    from .db import get_conn
    with get_conn() as conn:
        novo = conn.execute("INSERT OR IGNORE INTO sessoes_bot (telefone, estado) VALUES (?, 'AVISO_PRIVACIDADE')", (telefone,)).rowcount
    if novo and (texto or "").strip().casefold() not in {"9", "privacidade", "lgpd", "meus dados"}:
        from .publicacao import endereco
        aviso = f" ou veja {endereco()}/privacidade" if endereco() else ''
        resposta += "\n\n🔒 Para saber como usamos seus dados e falar com o responsável, digite PRIVACIDADE" + aviso
    return resposta


def _processar(telefone: str, texto: str) -> str | None:
    texto_limpo = (texto or "").strip()
    if texto_limpo == "9" or texto_limpo.casefold() in {"privacidade", "lgpd", "meus dados"}:
        return _resposta_opcao(texto_limpo, telefone)

    from . import conversa_pedido
    resposta_conversa = conversa_pedido.responder(telefone, texto_limpo)
    if resposta_conversa is not None:
        return resposta_conversa

    resposta_local = _resposta_rapida(telefone, texto_limpo)
    if resposta_local is not None:
        return resposta_local

    if _dentro_do_rate_limit(telefone):
        logger.info("Limite de frequência aplicado ao atendimento")
        return _processar_mensagem_menu_fixo(telefone, texto_limpo)

    try:
        return ia.responder(telefone, texto_limpo)
    except protecao_ia.ConversaBloqueada:
        return None
    except ia.IAIndisponivel:
        logger.warning("IA indisponível; atendimento continuará com resposta local")

    return _processar_mensagem_menu_fixo(telefone, texto_limpo)
