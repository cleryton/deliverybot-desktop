"""Atendimento "humano" via IA.

Em vez do menu numerado fixo, o cliente conversa naturalmente pelo WhatsApp
e a IA decide o que fazer:

- Responder com informações REAIS do restaurante (horário, telefone,
  endereço, taxa de entrega, formas de pagamento, cardápio) -- tudo isso é
  passado pra IA no system prompt, então ela nunca inventa preço ou dado
  fora do que está configurado.
- Chamar a ferramenta `gerar_link_pedido` quando o cliente demonstrar
  intenção clara de fazer um pedido -- isso gera o mesmo link único
  (`/m/<token>`) que o sistema já usava antes.

Suporta DOIS provedores, escolhidos por IA_PROVIDER no .env:

- "ANTHROPIC" -> API paga da Anthropic (Claude). Melhor qualidade de
  conversa, custa uma fração de centavo por mensagem. Precisa de
  ANTHROPIC_API_KEY.
- "OLLAMA"    -> modelo rodando LOCAL na sua máquina via Ollama
  (https://ollama.com). Custo ZERO por mensagem (usa o processador/memória
  do seu PC), qualidade de conversa um pouco inferior, mais lento sem GPU.
- vazio / qualquer outro valor -> IA desativada, bot usa direto o menu fixo
  (sem custo nenhum, sem dependência externa).

Em qualquer provedor, se a chamada falhar por qualquer motivo (sem crédito,
sem internet, Ollama não rodando, chave inválida, etc.), `responder()`
levanta `IAIndisponivel` e o chamador (bot.py) cai de volta no menu fixo --
o atendimento NUNCA para de funcionar por causa de um problema com a IA.
"""
import json
import logging
import time

import requests

from . import cardapio, config
from .db import get_conn
from .links import gerar_link_pedido

logger = logging.getLogger(__name__)

try:
    import anthropic
except ImportError:  # biblioteca não instalada -- provedor ANTHROPIC fica indisponível
    anthropic = None


class IAIndisponivel(Exception):
    """Levantada quando a IA não está configurada ou falha ao responder."""


_MAX_HISTORICO = 12  # quantidade de linhas (entrada+saída) usadas como contexto da conversa
_CACHE_PROMPT_SEGUNDOS = 30  # evita remontar o texto do cardápio a cada mensagem

_NOME_FERRAMENTA = "gerar_link_pedido"
_DESCRICAO_FERRAMENTA = (
    "Gera um link único e pessoal para o cliente montar o pedido pelo "
    "catálogo de produtos (escolher itens, quantidade, forma de pagamento, entrega ou "
    "retirada no balcão). Use esta ferramenta quando o cliente demonstrar "
    "intenção clara de pedir/comprar algo agora -- não use só porque ele "
    "perguntou o catálogo por curiosidade."
)

_TOOLS_ANTHROPIC = [
    {
        "name": _NOME_FERRAMENTA,
        "description": _DESCRICAO_FERRAMENTA,
        "input_schema": {"type": "object", "properties": {}},
    },
]

_TOOLS_OLLAMA = [
    {
        "type": "function",
        "function": {
            "name": _NOME_FERRAMENTA,
            "description": _DESCRICAO_FERRAMENTA,
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# Sessão HTTP reaproveitada (keep-alive) para as chamadas ao Ollama local.
_http = requests.Session()

# Cache simples do system prompt: montar o texto do cardápio bate no banco
# a cada chamada; como o cardápio muda raramente, vale a pena reaproveitar
# por alguns segundos em vez de reconsultar a cada mensagem recebida.
_cache_prompt: dict = {"texto": None, "gerado_em": 0.0}


def _system_prompt() -> str:
    agora = time.monotonic()
    if _cache_prompt["texto"] is not None and (agora - _cache_prompt["gerado_em"]) < _CACHE_PROMPT_SEGUNDOS:
        return _cache_prompt["texto"]

    produtos = cardapio.listar_produtos_ativos()
    grupos = cardapio.agrupar_por_categoria(produtos)
    linhas_cardapio = []
    for categoria, itens in grupos.items():
        linhas_cardapio.append(f"{categoria}:")
        for item in itens:
            desc = f" — {item['descricao']}" if item.get("descricao") else ""
            linhas_cardapio.append(f"  - {item['nome']}{desc} (R$ {item['preco']:.2f})")
    cardapio_texto = "\n".join(linhas_cardapio)

    texto = (
        f"Você é a atendente virtual do {config.NOME_RESTAURANTE}, conversando "
        "pelo WhatsApp com um cliente. Fale em português do Brasil, de forma "
        "simpática, calorosa e natural, como uma pessoa atendendo no balcão.\n\n"
        "ESTILO:\n"
        "- Respostas CURTAS: 1 a 3 frases. Nada de textão.\n"
        "- Tom de WhatsApp: informal e educado. No máximo 1 emoji por mensagem.\n"
        "- NUNCA use menu numerado ('1 - 2 - 3') nem listas com números.\n"
        "- Varie as palavras; não repita sempre a mesma frase.\n"
        "- Responda só o que o cliente perguntou, sem despejar todas as informações.\n"
        "- Se o cliente perguntar sinceramente se fala com uma pessoa ou uma IA, "
        "diga a verdade: você é a assistente virtual da loja.\n\n"
        "SAUDAÇÃO:\n"
        "Se o cliente só cumprimentar (oi, olá, opa, bom dia, boa tarde, boa noite, "
        "e aí...), responda o cumprimento de volta, dê boas-vindas ao "
        f"{config.NOME_RESTAURANTE} e pergunte como pode ajudar. NÃO gere link "
        "de pedido numa saudação.\n\n"
        "EXEMPLOS DE COMO RESPONDER:\n"
        f"Cliente: oi\nVocê: Oi! Tudo bem? 😊 Aqui é do {config.NOME_RESTAURANTE}. Como posso te ajudar?\n\n"
        "Cliente: opa\nVocê: Opa, tudo certo? Em que posso te ajudar hoje?\n\n"
        "Cliente: boa noite\nVocê: Boa noite! Seja bem-vindo. O que você gostaria hoje?\n\n"
        "Cliente: vocês abrem hoje?\nVocê: Funcionamos "
        f"{config.HORARIO_FUNCIONAMENTO}. Quer já dar uma olhada no catálogo?\n\n"
        "Cliente: quanto é a entrega?\nVocê: A taxa de entrega é "
        f"R$ {config.TAXA_ENTREGA:.2f}. Se retirar aqui no balcão, não paga nada.\n\n"
        "Cliente: quero fazer um pedido\nVocê: [use a ferramenta gerar_link_pedido e envie o link com uma frase simpática]\n\n"
        "REGRAS DE CONTEÚDO:\n"
        "- Use SOMENTE as informações abaixo. Se não souber algo, diga que não tem "
        "essa informação e sugira ligar no telefone da loja.\n"
        "- Nunca invente preço, produto, promoção ou horário.\n"
        "- Use a ferramenta gerar_link_pedido APENAS quando o cliente disser que "
        "quer pedir/comprar/fazer pedido agora. Curiosidade sobre catálogo ou "
        "preço NÃO é pedido. Depois de gerar, mande o link numa frase natural, "
        "ex: 'Claro! Monte seu pedido por aqui: <link>'.\n\n"
        "INFORMAÇÕES REAIS DA LOJA:\n"
        f"- Horário de funcionamento: {config.HORARIO_FUNCIONAMENTO}\n"
        f"- Telefone: {config.TELEFONE_RESTAURANTE}\n"
        f"- Endereço: {config.ENDERECO_RESTAURANTE}\n"
        f"- Taxa de entrega: R$ {config.TAXA_ENTREGA:.2f} (grátis na retirada no balcão)\n"
        f"- Formas de pagamento: {config.FORMAS_PAGAMENTO}\n"
        "- Promoções ativas: nenhuma no momento\n\n"
        "CATÁLOGO DE PRODUTOS DISPONÍVEIS:\n"
        "Atenda compras de qualquer categoria cadastrada. Não ofereça produtos fora deste catálogo. "
        "A quantidade disponível e o preço são conferidos ao confirmar o pedido.\n"
        f"{cardapio_texto}\n"
    )

    _cache_prompt["texto"] = texto
    _cache_prompt["gerado_em"] = agora
    return texto


def _system_prompt_ollama() -> str:
    """Adapta o atendimento local para soar natural sem afrouxar os fatos."""
    return _system_prompt() + (
        "\n\nCONVERSA NATURAL (PRIORIZE ESTAS ORIENTAÇÕES DE ESTILO):\n"
        "- Converse como alguém atencioso da equipe da loja: caloroso, direto e espontâneo, sem parecer um formulário.\n"
        "- Considere o que a pessoa acabou de dizer e o contexto recente. Responda primeiro ao pedido dela, sem repetir a pergunta.\n"
        "- Varie a construção das frases conforme a conversa. Evite respostas prontas repetidas como 'Claro!', 'Posso ajudar?' e 'Se precisar, estou à disposição'.\n"
        "- Seja breve sem ser seco. Faça no máximo uma pergunta por vez e só quando ela ajudar a continuar o atendimento.\n"
        "- Use emoji apenas quando combinar com o momento; não coloque emoji em toda resposta. Não use listas ou linguagem formal quando uma frase simples resolver.\n"
        "- Não invente familiaridade, ações ou dados. Se não tiver certeza, explique com naturalidade e ofereça confirmar com a equipe.\n"
        "- Se gerar um link de pedido, apresente-o com uma frase curta e acolhedora. Deixe claro que a pessoa ainda precisa abrir o link e confirmar o pedido.\n"
        "- Mantenha as regras do catálogo, preços, disponibilidade, privacidade e uso da ferramenta descritas acima. Estas instruções mudam o tom, nunca os fatos.\n"
    )


def invalidar_cache_prompt() -> None:
    """Chame depois de alterar o cardápio em tempo real, se precisar que a
    próxima resposta já reflita a mudança sem esperar o cache expirar."""
    _cache_prompt["texto"] = None


def _historico_mensagens(telefone: str) -> list[dict]:
    """Monta o histórico da conversa no formato {"role", "content"}, a
    partir da tabela `mensagens` já usada pelo projeto para log de
    ENTRADA/SAIDA.

    Mensagens consecutivas do mesmo lado (ex: o bot manda 3 mensagens em
    seguida ao confirmar um pedido) são agrupadas em um único turno, porque
    tanto a API da Anthropic quanto a do Ollama esperam turnos alternando
    entre user e assistant.
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT direcao, conteudo FROM mensagens WHERE telefone = ? "
            "ORDER BY id DESC LIMIT ?",
            (telefone, _MAX_HISTORICO),
        ).fetchall()
    rows = list(reversed(rows))

    historico: list[dict] = []
    for row in rows:
        papel = "user" if row["direcao"] == "ENTRADA" else "assistant"
        if historico and historico[-1]["role"] == papel:
            historico[-1]["content"] += "\n" + row["conteudo"]
        else:
            historico.append({"role": papel, "content": row["conteudo"]})
    return historico


def _mensagens_atualizadas(telefone: str, texto: str) -> list[dict]:
    # O histórico já inclui a mensagem atual do cliente como último turno
    # "user", porque app.py grava a mensagem de ENTRADA no banco ANTES de
    # chamar bot.processar_mensagem (que é quem chama esta função).
    mensagens = _historico_mensagens(telefone)
    if not mensagens or mensagens[-1]["role"] != "user":
        mensagens.append({"role": "user", "content": texto})
    from .privacidade import reduzir_para_ia
    return [{"role": m["role"], "content": reduzir_para_ia(telefone, m["content"])} for m in mensagens]


# ---------------------------------------------------------------------------
# Provedor: Anthropic (Claude) -- pago, melhor qualidade
# ---------------------------------------------------------------------------

def _responder_anthropic(telefone: str, texto: str) -> str:
    if not anthropic:
        raise IAIndisponivel("Biblioteca 'anthropic' não instalada (pip install anthropic).")
    if not config.ANTHROPIC_API_KEY:
        raise IAIndisponivel("ANTHROPIC_API_KEY não configurada no .env.")

    cliente = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    mensagens = _mensagens_atualizadas(telefone, texto)
    links_privados = {}

    try:
        resposta = cliente.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=600,
            system=_system_prompt(),
            tools=_TOOLS_ANTHROPIC,
            messages=mensagens,
        )

        for _ in range(4):
            if resposta.stop_reason != "tool_use":
                break
            blocos_tool = [b for b in resposta.content if b.type == "tool_use"]
            resultados = []
            for bloco in blocos_tool:
                if bloco.name == _NOME_FERRAMENTA:
                    link = gerar_link_pedido(telefone)
                    marcador = f"[LINK_PEDIDO_{len(links_privados)+1}]"
                    links_privados[marcador] = link
                    resultado = {"link": marcador}
                else:
                    resultado = {"erro": f"ferramenta desconhecida: {bloco.name}"}
                resultados.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": bloco.id,
                        "content": json.dumps(resultado, ensure_ascii=False),
                    }
                )

            mensagens = mensagens + [
                {"role": "assistant", "content": resposta.content},
                {"role": "user", "content": resultados},
            ]
            resposta = cliente.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=600,
                system=_system_prompt(),
                tools=_TOOLS_ANTHROPIC,
                messages=mensagens,
            )

        texto_final = "".join(
            bloco.text for bloco in resposta.content if bloco.type == "text"
        ).strip()
        for marcador, link in links_privados.items():
            if marcador in texto_final:
                texto_final = texto_final.replace(marcador, link)
            else:
                texto_final += "\nFaça seu pedido: " + link
        return texto_final or "Desculpa, pode repetir? Não entendi bem."
    except IAIndisponivel:
        raise
    except Exception as exc:
        raise IAIndisponivel(str(exc)) from exc


# ---------------------------------------------------------------------------
# Provedor: Ollama (modelo local, gratuito)
# ---------------------------------------------------------------------------

def _chamar_ollama(payload_mensagens: list, tentativas: int = 2) -> dict:
    url = f"{config.OLLAMA_URL}/api/chat"
    corpo = {
        "model": config.OLLAMA_MODEL,
        "messages": payload_mensagens,
        "tools": _TOOLS_OLLAMA,
        "stream": False,
        "keep_alive": config.OLLAMA_KEEP_ALIVE,  # mantém o modelo na memória (evita recarregar a cada mensagem)
        "options": {
            "temperature": config.OLLAMA_TEMPERATURE,
            "num_predict": config.OLLAMA_NUM_PREDICT,
        },
    }

    ultimo_erro: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        try:
            resp = _http.post(url, json=corpo, timeout=config.OLLAMA_TIMEOUT_SEGUNDOS, allow_redirects=False)
            if resp.status_code == 404:
                raise IAIndisponivel(
                    f"Modelo '{config.OLLAMA_MODEL}' não encontrado no Ollama. "
                    f"Rode 'ollama list' e coloque o nome exato em OLLAMA_MODEL no .env "
                    f"(ou 'ollama pull {config.OLLAMA_MODEL}')."
                )
            resp.raise_for_status()
            return resp.json()
        except IAIndisponivel:
            raise  # erro de configuração (modelo errado) -- não adianta tentar de novo
        except requests.RequestException as exc:
            ultimo_erro = exc
            if tentativa < tentativas:
                logger.warning(
                    "Ollama falhou (tentativa %d/%d), tentando de novo: %s",
                    tentativa, tentativas, exc,
                )
                time.sleep(0.5 * tentativa)  # pequeno backoff -- útil logo após o modelo subir

    raise IAIndisponivel(
        f"Ollama inacessível em {config.OLLAMA_URL} após {tentativas} tentativas "
        f"(ele está rodando? 'ollama serve'): {ultimo_erro}"
    )


def _responder_ollama(telefone: str, texto: str) -> str:
    mensagens = _mensagens_atualizadas(telefone, texto)
    payload_mensagens = [{"role": "system", "content": _system_prompt_ollama()}] + mensagens

    dados = _chamar_ollama(payload_mensagens)
    msg = dados.get("message", {})
    tool_calls = msg.get("tool_calls") or []

    # evita loop infinito se o modelo ficar chamando ferramenta sem parar
    for _ in range(4):
        if not tool_calls:
            break

        payload_mensagens.append(msg)
        for chamada in tool_calls:
            nome_funcao = chamada.get("function", {}).get("name")
            if nome_funcao == _NOME_FERRAMENTA:
                link = gerar_link_pedido(telefone)
                resultado = {"link": link}
            else:
                resultado = {"erro": f"ferramenta desconhecida: {nome_funcao}"}
            payload_mensagens.append(
                {"role": "tool", "content": json.dumps(resultado, ensure_ascii=False)}
            )

        dados = _chamar_ollama(payload_mensagens)
        msg = dados.get("message", {})
        tool_calls = msg.get("tool_calls") or []

    texto_final = (msg.get("content") or "").strip()
    return texto_final or "Desculpa, pode repetir? Não entendi bem."


def aquecer_ollama() -> None:
    """Pré-carrega o modelo na memória do Ollama (chamada "vazia", sem
    ferramentas nem system prompt) para que a PRIMEIRA mensagem de um
    cliente de verdade não pague o custo de 30-60s de carregamento.
    Chamada em background na inicialização do Flask -- qualquer falha aqui
    é só logada, nunca derruba o servidor."""
    if config.IA_PROVIDER != "OLLAMA":
        return
    try:
        logger.info("Aquecendo o modelo '%s' no Ollama...", config.OLLAMA_MODEL)
        inicio = time.monotonic()
        resp = _http.post(
            f"{config.OLLAMA_URL}/api/generate",
            json={
                "model": config.OLLAMA_MODEL,
                "prompt": "",
                "stream": False,
                "keep_alive": config.OLLAMA_KEEP_ALIVE,
            },
            timeout=config.OLLAMA_TIMEOUT_SEGUNDOS,
            allow_redirects=False,
        )
        resp.raise_for_status()
        logger.info("Modelo aquecido em %.1fs.", time.monotonic() - inicio)
    except Exception as exc:
        logger.warning("Não foi possível pré-aquecer o Ollama (sem problema, só será mais lento na 1ª mensagem): %s", exc)


# ---------------------------------------------------------------------------
# Ponto de entrada único -- escolhe o provedor configurado no .env
# ---------------------------------------------------------------------------

def responder(telefone: str, texto: str) -> str:
    """Gera a resposta "humana" da IA para a mensagem do cliente.

    Levanta IAIndisponivel se não for possível usar a IA por qualquer
    motivo -- o chamador deve tratar isso caindo de volta no menu fixo.
    """
    provedor = config.IA_PROVIDER
    from .conexoes import url_local
    externo = provedor == "ANTHROPIC" or (provedor == "OLLAMA" and not url_local(config.OLLAMA_URL))
    if externo and config.LGPD_IA_EXTERNA != "SIM":
        raise IAIndisponivel("Envio a IA externa desativado. Revise as opções de privacidade.")
    if provedor == "OLLAMA" and externo and not config.OLLAMA_URL.startswith("https://"):
        raise IAIndisponivel("O servidor externo de IA precisa usar HTTPS.")

    if provedor == "ANTHROPIC":
        return _responder_anthropic(telefone, texto)
    if provedor == "OLLAMA":
        return _responder_ollama(telefone, texto)

    raise IAIndisponivel(
        "IA desativada (defina IA_PROVIDER=ANTHROPIC ou IA_PROVIDER=OLLAMA no .env para ativar)."
    )
