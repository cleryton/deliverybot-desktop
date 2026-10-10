"""Painel administrativo compartilhado pelo aplicativo e pelo servidor."""
import hmac
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import secrets
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for

from . import bot, cardapio, config, estoque, fila, pedidos, preferencias, recibo, whatsapp
from .db import get_conn
from . import conexoes, processamento

bp = Blueprint("gestao", __name__)


def _local():
    # Host também é verificado para impedir DNS rebinding contra o servidor local.
    return request.remote_addr in {"127.0.0.1", "::1"} and request.host.split(":")[0] in {"127.0.0.1", "localhost"}


def autorizado():
    from .app import _exigir_autenticacao_cozinha
    token = current_app.config.get("DESKTOP_TOKEN")
    if token:
        return _local() and hmac.compare_digest(session.get("desktop", ""), token)
    return _exigir_autenticacao_cozinha()


def protegido(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not autorizado():
            return jsonify(erro="Acesso restrito ao administrador."), 401
        if request.method != "GET":
            esperado = session.get("csrf", "")
            if not esperado or not hmac.compare_digest(request.headers.get("X-CSRF-Token", ""), esperado):
                return jsonify(erro="Sessão expirada. Reabra o painel."), 403
        return view(*args, **kwargs)
    return wrapper


def dados_json():
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ValueError("Envie os dados em formato válido.")
    return dados


@bp.errorhandler(ValueError)
def erro_validacao(exc):
    return jsonify(erro=str(exc)), 400


@bp.after_request
def cabecalhos(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@bp.route("/gestao")
def painel():
    token = current_app.config.get("DESKTOP_TOKEN")
    recebido = request.args.get("acesso", "")
    if token and _local() and recebido and hmac.compare_digest(recebido, token):
        session.clear()
        session["desktop"] = token
        session["csrf"] = secrets.token_urlsafe(32)
        return redirect(url_for("gestao.painel"))
    if not autorizado():
        return "Abra o aplicativo DeliveryBot ou entre com a conta administrativa.", 401, {"WWW-Authenticate": 'Basic realm="DeliveryBot"'}
    session.setdefault("csrf", secrets.token_urlsafe(32))
    return render_template("gestao.html", csrf=session["csrf"])


@bp.route("/gestao/api/resumo")
@protegido
def resumo():
    produtos = estoque.listar_produtos()
    with get_conn() as conn:
        total = dict(conn.execute(
            "SELECT COUNT(*) AS pedidos, COALESCE(SUM(total_pedido),0) AS vendas FROM pedidos WHERE status != 'CANCELADO'").fetchone())
    return jsonify(produtos=len(produtos), ativos=sum(p["ativo"] for p in produtos),
                   baixos=sum(p["ativo"] and p["estoque"] is not None and p["estoque"] <= p["estoque_minimo"] for p in produtos),
                   pendentes=len(fila.listar_fila()), **total, nome=config.NOME_RESTAURANTE,
                   modo_teste=config.MODO_TESTE, whatsapp=config.WHATSAPP_PROVIDER,
                   base_url=config.BASE_URL, pasta=str(Path(config.DATABASE_PATH).resolve().parent),
                   webhook_waha=_webhook_exibicao())


def _webhook_exibicao():
    try:
        return conexoes.url_webhook()
    except ValueError:
        return "Informe o endereço do aplicativo visto pelo WAHA em Configurações."


@bp.route("/gestao/api/produtos", methods=["GET", "POST"])
@protegido
def produtos():
    if request.method == "GET":
        return jsonify(estoque.listar_produtos())
    return jsonify(estoque.salvar_produto(dados_json())), 201


@bp.route("/gestao/api/produtos/<int:produto_id>", methods=["PUT"])
@protegido
def editar_produto(produto_id):
    return jsonify(estoque.salvar_produto(dados_json(), produto_id))


@bp.route("/gestao/api/produtos/<int:produto_id>/estoque", methods=["POST"])
@protegido
def movimentar(produto_id):
    dados = dados_json()
    estoque.ajustar_estoque(produto_id, dados.get("quantidade"), dados.get("motivo", ""))
    return jsonify(ok=True)


@bp.route("/gestao/api/movimentos")
@protegido
def movimentos():
    return jsonify(estoque.listar_movimentos())


@bp.route("/gestao/api/pedidos")
@protegido
def listar_pedidos():
    with get_conn() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM pedidos ORDER BY id DESC LIMIT 200")]
    return jsonify([pedidos.obter_pedido(i) for i in ids])


@bp.route("/gestao/api/pedidos/<int:pedido_id>/avancar", methods=["POST"])
@protegido
def avancar(pedido_id):
    return jsonify(fila.avancar_status(pedido_id))


@bp.route("/gestao/api/pedidos/<int:pedido_id>/cancelar", methods=["POST"])
@protegido
def cancelar(pedido_id):
    pedido = pedidos.cancelar_pedido(pedido_id)
    try:
        mensagem = recibo.montar_mensagem_status(pedido, "CANCELADO")
        whatsapp.enviar_mensagem(pedido["cliente_telefone"], mensagem)
        pedidos.registrar_mensagem(pedido["cliente_telefone"], "SAIDA", mensagem)
    except Exception:
        current_app.logger.exception("Cancelamento salvo; notificação falhou")
        pedido["aviso"] = "Cancelamento salvo. Não foi possível notificar o cliente pelo WhatsApp."
    return jsonify(pedido)


@bp.route("/gestao/api/configuracoes", methods=["GET", "PUT"])
@protegido
def configuracoes():
    resultado = preferencias.obter() if request.method == "GET" else preferencias.salvar(dados_json())
    if request.method == "PUT" and config.WHATSAPP_PROVIDER != "LOCAL":
        conexoes.whatsapp_local.encerrar()
    return jsonify(resultado)


@bp.route("/gestao/api/simular", methods=["POST"])
@protegido
def simular():
    dados = dados_json()
    telefone = whatsapp._numero_limpo(estoque.texto(dados.get("telefone", ""), "Telefone", 40, True))
    if not 10 <= len(telefone) <= 15:
        raise ValueError("Informe o telefone com DDI e DDD, por exemplo 5547999990000.")
    mensagem = estoque.texto(dados.get("texto", ""), "Mensagem", 2000, True)
    resposta = bot._processar_mensagem_menu_fixo(telefone, mensagem)
    return jsonify(resposta=resposta, caminho="/m/" + resposta.rsplit("/", 1)[-1] if mensagem == "2" else None)


def criar_backup():
    pasta = Path(config.DATABASE_PATH).resolve().parent / "backups"
    pasta.mkdir(exist_ok=True)
    destino = pasta / ("DeliveryBot-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".db")
    with get_conn() as origem:
        with closing(sqlite3.connect(destino)) as copia:
            origem.backup(copia)
    return str(destino)


@bp.route("/gestao/api/backup", methods=["POST"])
@protegido
def backup():
    return jsonify(caminho=criar_backup())


@bp.route("/gestao/api/conexoes")
@protegido
def status_conexoes():
    with ThreadPoolExecutor(max_workers=2) as executor:
        wa = executor.submit(conexoes.status_whatsapp)
        ol = executor.submit(conexoes.status_ollama)
        return jsonify(whatsapp=wa.result(), ollama=ol.result(), tarefas=conexoes.status_jobs(),
                       fila=processamento.situacao(), provedor=config.WHATSAPP_PROVIDER,
                       pode_iniciar_local=bool(_local() and current_app.config.get("DESKTOP_TOKEN")),
                       whatsapp_local=config.WHATSAPP_PROVIDER in {"TESTE", "LOCAL"},
                       endereco_publico=config.BASE_URL,
                       links_publicos=not conexoes.url_local(config.BASE_URL))


@bp.route("/gestao/api/conexoes/qr")
@protegido
def qr_conexao():
    return jsonify(conexoes.qr_whatsapp())


@bp.route("/gestao/api/conexoes/<acao>", methods=["POST"])
@protegido
def controlar_conexao(acao):
    acoes = {"whatsapp-iniciar": ("whatsapp", conexoes.iniciar_whatsapp_local),
             "whatsapp-conectar": ("whatsapp", conexoes.conectar_whatsapp),
             "ollama-iniciar": ("ollama", conexoes.iniciar_ollama),
             "ollama-baixar": ("ollama", conexoes.baixar_modelo)}
    if acao in {"whatsapp-iniciar", "ollama-iniciar"} and not (_local() and current_app.config.get("DESKTOP_TOKEN")):
        return jsonify(erro="Abra o aplicativo Desktop neste computador para iniciar um serviço local."), 403
    if acao == "whatsapp-pausar":
        if conexoes.status_jobs().get("whatsapp", {}).get("estado") == "EXECUTANDO":
            raise ValueError("Aguarde a preparação da conexão antes de pausar.")
        conexoes.pausar_whatsapp()
        return jsonify(ok=True)
    if acao not in acoes:
        raise ValueError("Ação de conexão inválida.")
    nome, funcao = acoes[acao]
    return jsonify(conexoes.iniciar_tarefa(nome, funcao)), 202


@bp.route("/gestao/api/conexoes/mensagens/<int:tarefa_id>/<acao>", methods=["POST"])
@protegido
def resolver_mensagem(tarefa_id, acao):
    if acao == "reenviar":
        processamento.reenviar(tarefa_id)
    elif acao == "ignorar":
        processamento.ignorar(tarefa_id)
    else:
        raise ValueError("Ação inválida.")
    return jsonify(ok=True)
