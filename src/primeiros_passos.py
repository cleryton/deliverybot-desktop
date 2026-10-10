"""Preparação da loja e confirmação de abertura de um endereço público."""
import hashlib
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, jsonify
from . import config, estoque
from .db import get_conn
from .gestao import protegido

bp = Blueprint("primeiros_passos", __name__)


def publico():
    partes = urlsplit(config.BASE_URL)
    return partes.scheme == "https" and bool(partes.hostname) and partes.hostname not in {"localhost", "127.0.0.1", "::1"}


@bp.get('/gestao/api/preparacao')
@protegido
def situacao():
    with get_conn() as conn:
        teste = conn.execute("SELECT 1 FROM testes_publicos WHERE base_url=? AND recebido_em IS NOT NULL AND expira_em>datetime('now')", (config.BASE_URL,)).fetchone()
    return jsonify(loja=bool(config.NOME_RESTAURANTE and config.NOME_RESTAURANTE != 'Minha loja' and config.TELEFONE_RESTAURANTE),
                   produtos=bool(estoque.listar_produtos()), privacidade=bool(config.LGPD_RESPONSAVEL and config.LGPD_CONTATO),
                   whatsapp=config.WHATSAPP_PROVIDER, ia=config.IA_PROVIDER or 'Menu sem IA',
                   endereco_publico=publico(), abertura_recebida=bool(teste), base_url=config.BASE_URL)


@bp.post('/gestao/api/preparacao/testar')
@protegido
def testar():
    if not publico():
        return jsonify(erro='Configure um endereço HTTPS público em Configurações antes de testar.'), 400
    token = secrets.token_urlsafe(32)
    with get_conn() as conn:
        conn.execute("DELETE FROM testes_publicos WHERE expira_em<=datetime('now')")
        conn.execute("INSERT INTO testes_publicos(token_hash,base_url,expira_em) VALUES(?,?,datetime('now','+30 minutes'))", (hashlib.sha256(token.encode()).hexdigest(), config.BASE_URL))
    return jsonify(url=config.BASE_URL + '/diagnostico/' + token)


@bp.get('/diagnostico/<token>')
def confirmar(token):
    if len(token) > 100:
        return 'Teste inválido.', 404
    with get_conn() as conn:
        cur = conn.execute("UPDATE testes_publicos SET recebido_em=datetime('now') WHERE token_hash=? AND base_url=? AND expira_em>datetime('now')", (hashlib.sha256(token.encode()).hexdigest(), config.BASE_URL))
    if not cur.rowcount:
        return 'Este teste expirou. Gere outro no aplicativo.', 410
    return 'DeliveryBot: endereço acessível neste aparelho. Volte ao aplicativo e clique em Verificar preparação.'
