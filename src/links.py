"""Gera e valida o link único de pedido.

Cada link (`/m/<token>`) enviado ao cliente serve para UM único pedido:
- ao ser gerado, fica associado ao telefone do cliente e com um prazo de validade;
- assim que o pedido é concluído com sucesso, o token é marcado como usado;
- qualquer acesso posterior ao mesmo link (reenvio, F5, print antigo, etc.)
  cai numa página de "link inválido/expirado" em vez de abrir outro pedido.
"""
import secrets
import ipaddress
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from . import config
from .db import get_conn

_FORMATO_DATA = "%Y-%m-%d %H:%M:%S"
_URL = re.compile(r'[a-z][a-z0-9+.-]*://[^\s<>"\']+', re.I)
_DOMINIO_SOLTO = re.compile(r'(?i)(?<![\w@.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:com|net|org|io|app|dev|br|shop|online|site|example)(?![\w.-])')


class PaginaIndisponivel(ValueError):
    """Validação anterior ao envio: é seguro aguardar a reconexão e tentar novamente."""


def _base_pedido():
    from .publicacao import endereco, validar_dominio
    base = endereco()
    if config.MODO_TESTE and base:
        return base.rstrip('/')
    try:
        return validar_dominio(base)
    except ValueError:
        raise PaginaIndisponivel('A página pública está desconectada. Aguarde a conexão antes de enviar o link.') from None


def _endereco_local(host):
    host = (host or '').lower().rstrip('.')
    if not host or '.' not in host and ':' not in host or host.endswith(('.localhost', '.local', '.internal', '.home', '.lan')):
        return True
    try:
        return not ipaddress.ip_address(host).is_global
    except ValueError:
        return all(parte.isdigit() for parte in host.split('.'))


def gerar_link_pedido(telefone: str) -> str:
    base = _base_pedido()
    token = secrets.token_urlsafe(32)
    expira_em = (datetime.now(timezone.utc) + timedelta(minutes=config.VALIDADE_LINK_MIN)).strftime(_FORMATO_DATA)

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO links_pedido (token, telefone, usado, expira_em) VALUES (?, ?, 0, ?)",
            (token, telefone, expira_em),
        )

    return f"{base}/m/{token}"


def obter_link(token: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM links_pedido WHERE token = ?", (token,)).fetchone()
    return dict(row) if row else None


def atualizar_resposta(resposta, telefone, *, permitir_externos=False):
    """Valida todos os links, em qualquer frase, antes de chegarem ao cliente."""
    renovados = {}
    # Links comerciais cadastrados pelo responsável são dados de referência.
    # A IA não pode criar novos sites; mensagens humanas podem trazer links externos.
    cadastrados = set()
    for campo in ('ENDERECO_RESTAURANTE', 'HORARIO_FUNCIONAMENTO', 'FORMAS_PAGAMENTO', 'LGPD_CONTATO'):
        cadastrados.update(m[0].rstrip('.,;!?)]}*') for m in _URL.finditer(getattr(config, campo, '')))

    def substituir(m):
        bruto = m[0]
        url = bruto.rstrip('.,;!?)]}*')
        sufixo = bruto[len(url):]
        try:
            partes = urlsplit(url)
            host = partes.hostname
            if partes.username or partes.password:
                raise ValueError('A resposta contém um endereço com credenciais.')
            token = re.fullmatch(r'/m/([A-Za-z0-9_-]{1,100})/?', partes.path)
            if partes.path.startswith('/m/'):
                if not token:
                    raise ValueError('O link de pedido da resposta é inválido.')
                ok, _, link = link_valido(token[1])
                if not link or link['telefone'] != telefone:
                    raise ValueError('O link da resposta não pertence a este atendimento.')
                base = _base_pedido()
                if not ok:
                    if token[1] not in renovados:
                        renovados[token[1]] = gerar_link_pedido(telefone)
                    return renovados[token[1]] + sufixo
                return base + '/m/' + token[1] + sufixo
            if partes.path.rstrip('/') == '/privacidade':
                return _base_pedido() + '/privacidade' + sufixo
            if not config.MODO_TESTE and (_endereco_local(host) or partes.scheme != 'https'):
                raise ValueError('A resposta contém um endereço local ou sem HTTPS, que não pode ser enviado ao cliente.')
            if not permitir_externos and url not in cadastrados:
                raise ValueError('O endereço da resposta não foi gerado pelo aplicativo nem cadastrado pela loja.')
            return bruto
        except (TypeError, AttributeError):
            raise ValueError('A resposta contém um endereço inválido.') from None

    resultado = _URL.sub(substituir, resposta)
    if not permitir_externos and _DOMINIO_SOLTO.search(_URL.sub('', resultado)):
        raise ValueError('A resposta contém um domínio sem link autorizado.')
    if not config.MODO_TESTE:
        local_nome = re.search(r'(?i)(?<![\w.-])(?:[\w.-]+\.)?localhost(?:\b|:)|\[::1\]', resultado)
        ips = re.findall(r'(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])', resultado)
        if local_nome or any(_endereco_local(ip) for ip in ips):
            raise ValueError('A resposta contém um endereço local, que não pode ser enviado ao cliente.')
    return resultado


def link_valido(token: str) -> tuple[bool, str, dict | None]:
    link = obter_link(token)
    if link is None:
        return False, "Este link de pedido não existe.", None
    if link["usado"]:
        return False, "Este link já foi usado para um pedido e não pode ser reutilizado.", link
    if datetime.now(timezone.utc) >= datetime.strptime(link["expira_em"], _FORMATO_DATA).replace(tzinfo=timezone.utc):
        return False, "Este link de pedido expirou. Volte ao WhatsApp e peça um novo link para comprar.", link
    return True, "ok", link


def marcar_link_usado(token: str, pedido_id: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE links_pedido SET usado = 1, pedido_id = ? WHERE token = ?",
            (pedido_id, token),
        )
