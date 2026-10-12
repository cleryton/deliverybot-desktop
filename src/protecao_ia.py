"""Pausa por conversa: regras explícitas, revisão humana e saídas verificadas."""
import hashlib
import re
import secrets
import threading
import time
import unicodedata
import weakref
from contextlib import contextmanager

from . import config
from .db import get_conn

MOTIVOS = {
    'REGRAS': 'Tentativa de alterar as regras do atendimento',
    'SEGREDOS': 'Pedido de credenciais ou informações internas',
    'COMANDO': 'Tentativa de executar comandos privilegiados',
    'FREQUENCIA': 'Excesso ou repetição de mensagens',
    'SAIDA_PRIVADA': 'Resposta da IA contém uma credencial configurada',
    'SAIDA_SUSPEITA': 'Resposta da IA contém instrução suspeita',
    'SAIDA_INTERNA': 'Resposta da IA reproduz a estrutura das instruções internas',
}
_travas = weakref.WeakValueDictionary()
_indice = threading.Lock()


class ConversaBloqueada(Exception):
    pass


@contextmanager
def trava(telefone):
    with _indice:
        t = _travas.get(telefone)
        if t is None:
            t = threading.RLock()
            _travas[telefone] = t
    with t:
        yield


def normalizar(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(texto))
                           if not unicodedata.combining(c) and unicodedata.category(c) != 'Cf').casefold().split())


def privacidade(texto):
    return normalizar(texto).strip('.!? ') in {'9','privacidade','lgpd','meus dados'}


def classificar(texto):
    t = normalizar(texto)
    alterar = r'\b(?:ignore|desconsidere|esqueca)\s+(?:(?:todas?\s+)?(?:as|suas)\s+)?(?:instrucoes anteriores|regras(?: do sistema| de seguranca)?|restricoes|prompt do sistema)\b'
    for m in re.finditer(alterar,t):
        if not re.search(r'\b(?:nao|nunca)\s+$',t[max(0,m.start()-12):m.start()]):
            return 'REGRAS'
    if re.search(r'\bignore\s+(?:all\s+)?(?:previous|system)\s+instructions\b|<\|im_start\|>\s*system|<\|start_header_id\|>\s*system',t):
        return 'REGRAS'
    if re.search(r'\b(?:aja|finja|atue)\b.{0,40}\b(?:administrador|root|sem restricoes|sem regras)\b',t):
        return 'REGRAS'
    if re.search(r'\b(?:mostre|envie|revele|liste|extraia|exiba|reveal|show)\b.{0,80}(?:\b(?:credenciais|senha (?:administradora|do administrador)|senhas (?:dos|de) (?:clientes|funcionarios)|tokens? de acesso|chaves? (?:da api|de acesso)|api key|system prompt|prompt (?:do sistema|interno)|notas internas|dados (?:de outros|dos outros|de todos os) clientes)\b|\.env\b)',t):
        return 'SEGREDOS'
    if re.search(r'\b(?:execute|rode|executar)\b.{0,40}\b(?:sudo|powershell|drop table|comando no servidor|script no servidor)\b',t):
        return 'COMANDO'
    return None


def _bloquear(c,telefone,motivo):
    novo=c.execute('INSERT OR IGNORE INTO bloqueios_ia(telefone,motivo) VALUES(?,?)',(telefone,motivo)).rowcount
    if novo:
        _nova_versao(c,telefone)
    c.execute("INSERT OR IGNORE INTO atendimentos_humanos(telefone,estado) VALUES(?,'AGUARDANDO')",(telefone,))
    # Envios já iniciados são incertos e precisam conservar a informação para conferência.
    c.execute("UPDATE tarefas_bot SET estado='CONCLUIDA',texto='',resposta=NULL,chat_id=NULL,sessao=NULL,erro=NULL,atualizado_em=datetime('now') WHERE telefone=? AND origem!='HUMANO' AND estado IN ('PENDENTE','PROCESSANDO')",(telefone,))


def avaliar(c,telefone,texto,contar=False):
    aviso=privacidade(texto)
    if aviso and not contar:
        return False
    if not aviso and c.execute('SELECT 1 FROM bloqueios_ia WHERE telefone=?',(telefone,)).fetchone():
        return True
    motivo = classificar(texto) if not aviso else None
    if contar and not motivo:
        agora = time.time()
        c.execute('DELETE FROM frequencia_ia WHERE inicio<?',(agora-60,))
        r=c.execute('SELECT * FROM frequencia_ia WHERE telefone=?',(telefone,)).fetchone()
        h=hashlib.sha256(normalizar(texto).encode()).hexdigest()
        n=r['quantidade']+1 if r else 1
        repetidas=r['repetidas']+1 if r and r['ultimo_hash']==h else 1
        c.execute('INSERT INTO frequencia_ia VALUES(?,?,?,?,?) ON CONFLICT(telefone) DO UPDATE SET quantidade=excluded.quantidade,ultimo_hash=excluded.ultimo_hash,repetidas=excluded.repetidas',
                  (telefone,r['inicio'] if r else agora,n,h,repetidas))
        if aviso:
            return n>30  # O aviso continua acessível, com limite para evitar spam de respostas locais.
        if n>30 or (repetidas>=6 and len(normalizar(texto))>=12):
            motivo='FREQUENCIA'
    if motivo:
        _bloquear(c,telefone,motivo)
        return True
    return False


def bloqueado(telefone):
    with get_conn() as c:
        return bool(c.execute('SELECT 1 FROM bloqueios_ia WHERE telefone=?',(telefone,)).fetchone())


def _nova_versao(c,telefone):
    c.execute('INSERT INTO versoes_protecao_ia VALUES(?,?) ON CONFLICT(telefone) DO UPDATE SET versao=excluded.versao',(telefone,secrets.token_hex(24)))


def versao(telefone,c=None):
    if c is None:
        with get_conn() as conn:
            return versao(telefone,conn)
    r=c.execute('SELECT versao FROM versoes_protecao_ia WHERE telefone=?',(telefone,)).fetchone()
    return r['versao'] if r else ''


def verificar(telefone,texto):
    with trava(telefone), get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        return avaliar(c,telefone,texto)


def validar_saida(telefone,resposta,geracao=None):
    if bloqueado(telefone) or (geracao is not None and geracao!=versao(telefone)):
        raise ConversaBloqueada()
    motivo='SAIDA_SUSPEITA' if classificar(resposta) else None
    normalizada=normalizar(resposta)
    if sum(t in normalizada for t in ('regras de conteudo:','personalidade da equipe','informacoes reais da loja:','continuidade e escuta:'))>=2:
        motivo='SAIDA_INTERNA'
    for nome in ('ANTHROPIC_API_KEY','WHATSAPP_TOKEN','WAHA_API_KEY','WEBHOOK_SECRET','WHATSAPP_APP_SECRET','TUNEL_TOKEN'):
        segredo=getattr(config,nome,'')
        if isinstance(segredo,str) and len(segredo)>=8 and segredo in str(resposta):
            motivo='SAIDA_PRIVADA'
            break
    if motivo:
        with trava(telefone),get_conn() as c:
            c.execute('BEGIN IMMEDIATE')
            _bloquear(c,telefone,motivo)
        raise ConversaBloqueada()
    return resposta


def liberar(telefone):
    from .humano import telefone as validar
    telefone=validar(telefone)
    with trava(telefone),get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM tarefas_bot WHERE telefone=? AND estado IN ('PROCESSANDO','ENVIANDO')",(telefone,)).fetchone():
            raise ValueError('Aguarde o processamento ou confira o envio em andamento antes de liberar.')
        c.execute('DELETE FROM bloqueios_ia WHERE telefone=?',(telefone,))
        _nova_versao(c,telefone)
        c.execute('DELETE FROM frequencia_ia WHERE telefone=?',(telefone,))
    # A liberação de segurança não retoma o bot: a equipe decide quando encerrar o atendimento humano.
