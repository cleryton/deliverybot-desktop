"""Preparação da loja e confirmação de abertura de um endereço público."""
import hashlib
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, jsonify
from . import config, conexoes, estoque, processamento, publicacao, tutorial
from .db import get_conn
from .gestao import protegido

bp = Blueprint("primeiros_passos", __name__)


def publico():
    partes = urlsplit(publicacao.endereco())
    return partes.scheme == "https" and bool(partes.hostname) and partes.hostname not in {"localhost", "127.0.0.1", "::1"}


@bp.get('/gestao/api/preparacao')
@protegido
def situacao():
    tunnel = publicacao.situacao()
    if config.WHATSAPP_PROVIDER in {"LOCAL", "WAHA"}:
        status_wa = conexoes.status_whatsapp()
        whatsapp_estado = status_wa.get("estado", "INDISPONIVEL")
        whatsapp_ok = bool(status_wa.get("conectado"))
    elif config.WHATSAPP_PROVIDER == "META":
        whatsapp_ok = bool(config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID)
        whatsapp_estado = "CONFIGURADO" if whatsapp_ok else "INCOMPLETO"
    else:
        whatsapp_ok = False
        whatsapp_estado = "TESTE"
    if tunnel.get("estado") == "ONLINE":
        https_estado, https_ok = "ONLINE", True
    elif publico():
        https_estado, https_ok = "ENDERECO_CONFIGURADO", True
    else:
        https_estado, https_ok = tunnel.get("estado", "DESLIGADO"), False
    with get_conn() as conn:
        teste = conn.execute("SELECT 1 FROM testes_publicos WHERE base_url=? AND recebido_em IS NOT NULL AND expira_em>datetime('now')", (publicacao.endereco(),)).fetchone()
    dados = dict(loja=bool(config.NOME_RESTAURANTE and config.NOME_RESTAURANTE != 'Minha loja' and config.TELEFONE_RESTAURANTE),
                   perfil=config.COMERCIO_CONFIGURADO == 'SIM', modelo=config.COMERCIO_MODELO,
                   produtos=any(p['ativo'] and (p['estoque'] is None or p['estoque'] > 0) for p in estoque.listar_produtos()), privacidade=bool(config.LGPD_RESPONSAVEL and config.LGPD_CONTATO),
                   whatsapp=config.WHATSAPP_PROVIDER, ia=config.IA_PROVIDER or 'Menu sem IA',
                   endereco_publico=publico(), abertura_recebida=bool(teste), base_url=publicacao.endereco(),
                   operacao={"whatsapp_ok": whatsapp_ok, "whatsapp_estado": whatsapp_estado,
                             "https_ok": https_ok, "https_estado": https_estado,
                             "fila_ok": processamento.ativo(),
                             "whatsapp_tarefa": conexoes.status_jobs().get("whatsapp", {}).get("estado", "")})
    dados['tutorial'] = tutorial.etapas(dados)
    return jsonify(dados)


@bp.post('/gestao/api/preparacao/testar')
@protegido
def testar():
    if not publico():
        return jsonify(erro='Inicie a página pública ou configure seu domínio HTTPS antes de testar.'), 400
    token = secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute("DELETE FROM testes_publicos WHERE expira_em<=datetime('now')")
        conn.execute("INSERT INTO testes_publicos(token_hash,base_url,expira_em) VALUES(?,?,datetime('now','+30 minutes'))", (hashlib.sha256(token.encode()).hexdigest(), publicacao.endereco()))
    return jsonify(url=publicacao.endereco() + '/diagnostico/' + token)


@bp.get('/diagnostico/<token>')
def confirmar(token):
    if len(token) > 100:
        return 'Teste inválido.', 404
    with get_conn() as conn:
        cur = conn.execute("UPDATE testes_publicos SET recebido_em=datetime('now') WHERE token_hash=? AND base_url=? AND expira_em>datetime('now')", (hashlib.sha256(token.encode()).hexdigest(), publicacao.endereco()))
    if not cur.rowcount:
        return 'Este teste expirou. Gere outro no aplicativo.', 410
    return 'DeliveryBot: endereço acessível neste aparelho. Volte ao aplicativo e clique em Verificar preparação.'
