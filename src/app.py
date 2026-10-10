import hmac
import hashlib
import logging
import threading
import secrets
from functools import wraps

from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash

from . import auth_windows, bot, cardapio, config, fila, pedidos, recibo, viacep, whatsapp
from .db import init_db
from .ia import aquecer_ollama
from .links import link_valido
from . import preferencias, processamento
from . import seguranca, privacidade

logging.basicConfig(
    level=logging.DEBUG if config.FLASK_DEBUG else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    template_folder="../web/templates",
    static_folder="../web/static",
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.secret_key = secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")
seguranca.instalar(app)

# Banco e IA são inicializados UMA VEZ ao importar o módulo (não a cada
# requisição -- rodar o schema inteiro e checar o cardápio em todo request
# era um desperdício de I/O sem necessidade nenhuma).
init_db()
preferencias.carregar()
app.jinja_env.globals["icone_categoria"] = cardapio.icone_categoria


@app.context_processor
def dados_da_loja():
    return {"formas_pagamento": [p.strip() for p in config.FORMAS_PAGAMENTO.split(",") if p.strip()]}

if config.IA_PROVIDER == "OLLAMA" and config.OLLAMA_AQUECER_AO_INICIAR:
    threading.Thread(target=aquecer_ollama, daemon=True).start()


# ---------------------------------------------------------------------------
# Segurança: segredo embutido na URL dos webhooks + HTTP Basic Auth no painel
# da cozinha. Ver MANUAL.md, seção "Segurança", para como configurar.
# ---------------------------------------------------------------------------

def _segredo_valido(segredo_recebido: str) -> bool:
    if not config.WEBHOOK_SECRET:
        # Sem segredo configurado, o endpoint fica bloqueado por padrão --
        # é melhor "esquecer de configurar e nada funcionar" do que "esquecer
        # de configurar e o endpoint ficar aberto pra qualquer um".
        return False
    return seguranca.igual(segredo_recebido or "", config.WEBHOOK_SECRET)


def _exigir_autenticacao_cozinha():
    if not seguranca.acesso_administrativo() or seguranca.login_bloqueado():
        return False
    resultado = _validar_autenticacao_cozinha()
    if request.authorization:
        seguranca.registrar_login(resultado)
    return resultado


def _validar_autenticacao_cozinha():
    auth = request.authorization
    if not auth:
        return False

    if config.COZINHA_AUTH_MODO == "WINDOWS":
        return auth_windows.validar_credenciais_windows(auth.username, auth.password)

    # Modo padrão ("SENHA"): usuário comparado em texto (hmac evita timing
    # attack), senha comparada só pelo HASH -- o valor de verdade nunca é
    # guardado em lugar nenhum.
    if not (config.COZINHA_USUARIO and config.COZINHA_SENHA_HASH):
        logger.warning(
            "Acesso à cozinha bloqueado: configure COZINHA_USUARIO e rode "
            "'python definir_senha_cozinha.py' para definir a senha."
        )
        return False
    if not seguranca.igual(auth.username or "", config.COZINHA_USUARIO):
        return False
    return check_password_hash(config.COZINHA_SENHA_HASH, auth.password or "")


def requer_login_cozinha(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not seguranca.acesso_administrativo():
            return "Acesso administrativo remoto desativado.", 403
        if seguranca.login_bloqueado():
            return "Muitas tentativas. Aguarde cinco minutos.", 429
        if not _exigir_autenticacao_cozinha():
            return (
                "Login necessário.",
                401,
                {"WWW-Authenticate": 'Basic realm="Painel da cozinha"'},
            )
        if request.method != "GET" and not seguranca.csrf_valido():
            return "Sessão inválida. Reabra o painel.", 403
        return view(*args, **kwargs)

    return wrapper


def apenas_em_desenvolvimento(view):
    """Bloqueia o endpoint quando FLASK_DEBUG não está ligado -- usado nas
    rotas que existem só para testar localmente e que não devem ficar
    acessíveis quando o sistema está exposto publicamente (ngrok etc.)."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        if not config.FLASK_DEBUG or not seguranca.local():
            return jsonify({"erro": "endpoint disponível apenas com FLASK_DEBUG=true"}), 404
        return view(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Webhook do WhatsApp (Meta Cloud API)
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    modo = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    desafio = request.args.get("hub.challenge")

    if config.WHATSAPP_VERIFY_TOKEN not in {"", "trocar_por_uma_palavra_secreta"} and modo == "subscribe" and seguranca.igual(token or "", config.WHATSAPP_VERIFY_TOKEN):
        return desafio, 200
    return "Token de verificação inválido", 403


@app.route("/webhook", methods=["POST"])
def receber_webhook():
    if not config.WHATSAPP_APP_SECRET:
        return jsonify(status="não autorizado"), 403
    assinatura = "sha256=" + hmac.new(config.WHATSAPP_APP_SECRET.encode(), request.get_data(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get("X-Hub-Signature-256", ""), assinatura):
        return jsonify(status="não autorizado"), 403
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(status="dados inválidos"), 400
    dados = whatsapp.extrair_mensagem_recebida(payload)

    if dados is None:
        # Pode ser um evento de status (entregue/lido) ou payload vazio; apenas confirma o recebimento.
        return jsonify({"status": "ignorado"}), 200

    telefone, texto = dados["telefone"], dados["texto"]
    pedidos.registrar_mensagem(telefone, "ENTRADA", texto)

    try:
        resposta = bot.processar_mensagem(telefone, texto)
        if resposta is None:
            return jsonify(status='atendimento_humano'),200
        whatsapp.enviar_mensagem(telefone, resposta)
        pedidos.registrar_mensagem(telefone, "SAIDA", resposta)
    except Exception:
        # Nunca deixa uma exceção virar uma página de erro 500 pública --
        # loga internamente e confirma o recebimento mesmo assim (evita que
        # o provedor fique retransmitindo o mesmo webhook em loop).
        logger.error("Falha ao processar mensagem recebida da Meta")
        return jsonify({"status": "erro_interno"}), 200

    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# Webhook do WAHA (WhatsApp HTTP API self-hosted via Docker, login por QR)
#
# A URL inclui um segredo (<segredo>) como parte do caminho: só quem conhece
# WEBHOOK_SECRET (configurado no .env e usado no WHATSAPP_HOOK_URL do
# docker-compose.yml) consegue mandar requisições que o Flask aceita como
# vindas do WAHA de verdade. Ver MANUAL.md, seção "Segurança".
# ---------------------------------------------------------------------------

@app.route("/webhook/waha/<segredo>", methods=["POST"])
def receber_webhook_waha(segredo):
    if not _segredo_valido(segredo):
        logger.warning("Tentativa de acesso ao webhook do WAHA com segredo inválido")
        return jsonify({"status": "não autorizado"}), 404  # 404 em vez de 401: não revela que a rota existe

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify(status="dados inválidos"), 400
    dados = whatsapp.extrair_mensagem_recebida_waha(payload)

    if dados is None:
        return jsonify({"status": "ignorado"}), 200

    chave = (payload.get("payload") or {}).get("id") or payload.get("id")
    tarefa = processamento.enfileirar(dados, chave)
    return jsonify(status="recebido", **tarefa), 200


# ---------------------------------------------------------------------------
# API interna usada pelo workflow do N8N (veja n8n/deliverybot-waha.json).
# Também protegida pelo mesmo segredo do webhook -- sem isso, qualquer
# pessoa que descobrisse a URL pública poderia conversar com a IA de graça
# à sua custa, ou criar pedidos falsos.
# ---------------------------------------------------------------------------

@app.route("/api/bot/mensagem/<segredo>", methods=["POST"])
def api_processar_mensagem(segredo):
    if not _segredo_valido(segredo):
        return jsonify({"erro": "não autorizado"}), 404

    dados = request.get_json(silent=True) or {}
    if not isinstance(dados, dict) or not isinstance(dados.get("telefone", ""), str) or not isinstance(dados.get("texto", ""), str):
        return jsonify(erro="Dados inválidos."), 400
    telefone = whatsapp._numero_limpo(dados.get("telefone", ""))
    texto = (dados.get("texto") or "").strip()

    if not 10 <= len(telefone) <= 15 or not texto or len(texto) > 8000:
        return jsonify({"erro": "telefone é obrigatório"}), 400

    pedidos.registrar_mensagem(telefone, "ENTRADA", texto)
    try:
        resposta = bot.processar_mensagem(telefone, texto)
    except Exception:
        logger.error("Falha ao processar mensagem via API interna")
        return jsonify({"erro": "falha ao processar mensagem"}), 500
    if resposta is not None:
        pedidos.registrar_mensagem(telefone, "SAIDA", resposta)

    return jsonify({"telefone": telefone, "resposta": resposta})


# ---------------------------------------------------------------------------
# Atalho só para TESTE LOCAL: simula o cliente digitando "2" no WhatsApp,
# sem precisar de credenciais da Meta nem do webhook real. Bloqueado quando
# FLASK_DEBUG não está ligado (ver apenas_em_desenvolvimento), pra não virar
# uma forma de qualquer um gerar pedidos/custos quando o sistema está
# exposto publicamente.
# ---------------------------------------------------------------------------

@app.route("/testar", methods=["GET"])
@apenas_em_desenvolvimento
def testar_localmente():
    telefone_teste = request.args.get("telefone", "5547999990000")
    resposta = bot.processar_mensagem(telefone_teste, "2")
    if resposta is None:
        return 'Conversa em atendimento humano. Retome o bot antes de testar.',409
    pedidos.registrar_mensagem(telefone_teste, "SAIDA", resposta)
    link = resposta.replace("Faça o seu pedido em ", "").strip()
    token = link.rsplit("/", 1)[-1]
    return redirect(url_for("pagina_pedido", token=token))


# ---------------------------------------------------------------------------
# Link único de pedido: GET mostra o cardápio, POST cria o pedido
# ---------------------------------------------------------------------------

@app.route("/m/<token>", methods=["GET"])
def pagina_pedido(token):
    ok, mensagem, link = link_valido(token)
    if not ok:
        return render_template("link_invalido.html", mensagem=mensagem), 410

    produtos = cardapio.listar_produtos_ativos()
    grupos = cardapio.agrupar_por_categoria(produtos)
    return render_template(
        "pedido.html",
        token=token,
        grupos=grupos,
        nome_restaurante=config.NOME_RESTAURANTE,
        taxa_entrega=config.TAXA_ENTREGA,
    )


@app.route("/m/<token>", methods=["POST"])
def enviar_pedido(token):
    ok, mensagem, link = link_valido(token)
    if not ok:
        return render_template("link_invalido.html", mensagem=mensagem), 410

    if not seguranca.csrf_valido():
        return "A sessão do pedido expirou. Reabra seu link de compra.", 403

    telefone = link["telefone"]
    nome_cliente = request.form.get("nome", "Cliente").strip() or "Cliente"
    if len(nome_cliente) > 160:
        return "O nome deve ter no máximo 160 caracteres.", 400
    forma_pagamento = request.form.get("forma_pagamento", "Dinheiro")
    forma_entrega = request.form.get("forma_entrega", "RETIRADA BALCAO")
    cep = request.form.get("cep", "").strip()

    endereco = ""
    if forma_entrega == "ENTREGA":
        ok_cep, msg_cep, dados_cep = viacep.validar_area_entrega(cep)
        if not ok_cep:
            produtos = cardapio.listar_produtos_ativos()
            grupos = cardapio.agrupar_por_categoria(produtos)
            return render_template(
                "pedido.html",
                token=token,
                grupos=grupos,
                nome_restaurante=config.NOME_RESTAURANTE,
                taxa_entrega=config.TAXA_ENTREGA,
                erro=msg_cep,
            ), 400
        numero = request.form.get("numero", "").strip()[:30]
        complemento = request.form.get("complemento", "").strip()[:150]
        if not numero:
            return render_template("pedido.html", token=token, grupos=cardapio.agrupar_por_categoria(cardapio.listar_produtos_ativos()),
                                   nome_restaurante=config.NOME_RESTAURANTE, taxa_entrega=config.TAXA_ENTREGA,
                                   erro="Informe o número do endereço ou s/n."), 400
        endereco = viacep.endereco_formatado(dados_cep) + ", " + numero + (", " + complemento if complemento else "")

    itens = []
    for chave, valor in request.form.items():
        if chave.startswith("qtd_") and valor and len(valor) <= 10 and valor.isascii():
            produto_id_str = chave.replace("qtd_", "")
            if len(produto_id_str) <= 10 and produto_id_str.isascii() and produto_id_str.isdigit():
                if valor not in {'0','0.000','0.0',''}:
                    itens.append({"produto_id": int(produto_id_str), "quantidade": valor})

    if not itens:
        produtos = cardapio.listar_produtos_ativos()
        grupos = cardapio.agrupar_por_categoria(produtos)
        return render_template(
            "pedido.html",
            token=token,
            grupos=grupos,
            nome_restaurante=config.NOME_RESTAURANTE,
            taxa_entrega=config.TAXA_ENTREGA,
            erro="Selecione ao menos um item antes de enviar o pedido.",
        ), 400

    try:
        pedido = pedidos.criar_pedido(
            telefone=telefone,
            nome_cliente=nome_cliente,
            itens=itens,
            forma_pagamento=forma_pagamento,
            forma_entrega=forma_entrega,
            cep=cep,
            endereco=endereco,
            token=token,
        )
    except ValueError as exc:
        produtos = cardapio.listar_produtos_ativos()
        grupos = cardapio.agrupar_por_categoria(produtos)
        return render_template(
            "pedido.html",
            token=token,
            grupos=grupos,
            nome_restaurante=config.NOME_RESTAURANTE,
            taxa_entrega=config.TAXA_ENTREGA,
            erro=str(exc),
        ), 400

    mensagem_confirmacao = recibo.montar_mensagem_confirmacao(pedido)
    cupom = recibo.montar_recibo(pedido)
    notificacao_ok = False
    try:
        whatsapp.enviar_mensagem(telefone, mensagem_confirmacao)
        whatsapp.enviar_mensagem(telefone, cupom)
        pedidos.registrar_mensagem(telefone, "SAIDA", mensagem_confirmacao)
        pedidos.registrar_mensagem(telefone, "SAIDA", cupom)

        mensagem_status = recibo.montar_mensagem_status(pedido, "CONFIRMADO")
        whatsapp.enviar_mensagem(telefone, mensagem_status)
        pedidos.registrar_mensagem(telefone, "SAIDA", mensagem_status)
        notificacao_ok = True
    except Exception:
        # O pedido já foi salvo com sucesso -- uma falha ao notificar pelo
        # WhatsApp não deve impedir de mostrar a confirmação na tela.
        logger.error("Pedido criado; notificação WhatsApp não concluída")

    return render_template("pedido_sucesso.html", pedido=pedido, modo_teste=config.MODO_TESTE, notificacao_ok=notificacao_ok)


# ---------------------------------------------------------------------------
# Painel da cozinha / fila de preparo -- protegido por HTTP Basic Auth
# (COZINHA_USUARIO + senha com hash, ou conta do Windows -- ver config.py). Sem isso configurado,
# o painel fica bloqueado por padrão.
# ---------------------------------------------------------------------------

@app.route("/cozinha", methods=["GET"])
@requer_login_cozinha
def painel_cozinha():
    return render_template("cozinha.html", fila=fila.listar_fila(), csrf=seguranca.csrf())


@app.route("/cozinha/avancar/<int:pedido_id>", methods=["POST"])
@requer_login_cozinha
def avancar_pedido(pedido_id):
    try:
        fila.avancar_status(pedido_id)
    except ValueError as e:
        return str(e), 400
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"status": "ok"})
    return redirect(url_for("painel_cozinha"))


@app.route("/cozinha/api/fila", methods=["GET"])
@requer_login_cozinha
def api_fila():
    """Usado pelo JavaScript do painel da cozinha para atualizar a fila sem
    recarregar a página inteira (sem o 'flicker' do refresh completo)."""
    return jsonify(fila.listar_fila())


from .gestao import bp as gestao_bp
app.register_blueprint(gestao_bp)
from .primeiros_passos import bp as preparacao_bp
app.register_blueprint(preparacao_bp)


@app.route("/")
def inicio():
    return redirect(url_for("gestao.painel"))


@app.route("/privacidade")
def aviso_privacidade():
    return render_template("privacidade.html", aviso=privacidade.aviso())


@app.errorhandler(500)
def erro_interno(_erro):
    return jsonify(erro="Não foi possível concluir a operação. Tente novamente ou contate a loja."), 500


if __name__ == "__main__":
    # Sem reloader: evita iniciar dois grupos de consumidores da mesma fila.
    from . import whatsapp_local
    if config.WHATSAPP_PROVIDER == "LOCAL":
        whatsapp_local.iniciar()
    processamento.iniciar()
    try:
        app.run(host="0.0.0.0", port=5000, debug=config.FLASK_DEBUG, use_reloader=False)
    finally:
        processamento.encerrar()
        whatsapp_local.encerrar()
