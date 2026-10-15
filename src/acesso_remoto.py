"""Área remota isolada: convite único, conta vinculada e autorização no servidor."""
import hashlib
import secrets
import time

from flask import Blueprint, abort, g, jsonify, render_template, request, session
from werkzeug.security import check_password_hash

from . import config, fila, operadores, publicacao, seguranca
from .db import get_conn
from .politica_terminal import Limites

bp = Blueprint('remoto', __name__)
_limites = Limites()
INATIVIDADE = 15 * 60


def encerrar_ao_iniciar():
    # Reiniciar/atualizar a loja exige novos convites, inclusive após restaurar um backup.
    with get_conn() as c:
        c.execute('UPDATE acessos_remotos SET ativo=0,sessao_hash=NULL WHERE ativo=1')


def _hash(valor):
    return hashlib.sha256(valor.encode()).hexdigest()


def _responsavel(c):
    r = c.execute("SELECT id FROM operadores WHERE id=? AND versao=? AND ativo=1 AND perfil='ADMIN'",
                  (session.get('operador_id'), session.get('operador_versao'))).fetchone()
    if not r:
        raise ValueError('A autorização do responsável mudou. Entre novamente no aplicativo local.')
    return r['id']


def criar(d):
    uid, minutos = d.get('operador_id'), d.get('minutos')
    permissao = d.get('permissao')
    if type(uid) is not int or type(minutos) is not int or minutos not in {15, 60, 240, 1440} or not isinstance(permissao, str) or permissao not in {'CONSULTA', 'PEDIDOS'}:
        raise ValueError('Escolha a conta, a permissão e um prazo válido.')
    base = publicacao.validar_dominio(publicacao.endereco())
    chave = secrets.token_urlsafe(32)
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        ator = _responsavel(c)
        conta = c.execute("SELECT versao FROM operadores WHERE id=? AND ativo=1 AND perfil IN ('ADMIN','ATENDENTE')", (uid,)).fetchone()
        if not conta:
            raise ValueError('Escolha uma conta ativa de administrador ou atendente. Caixas usam o aplicativo da loja.')
        if c.execute('SELECT COUNT(*) FROM acessos_remotos WHERE ativo=1 AND expira_em>?', (time.time(),)).fetchone()[0] >= 20:
            raise ValueError('Revogue um acesso antes de criar outro. Limite de 20 convites ativos.')
        cur = c.execute('INSERT INTO acessos_remotos(operador_id,conta_versao,convite_hash,permissao,expira_em) VALUES(?,?,?,?,?)',
                        (uid, conta['versao'], _hash(chave), permissao, time.time() + minutos * 60))
        c.execute('INSERT INTO auditoria_operadores(operador_id,acao,objeto) VALUES(?,?,?)', (ator, 'REMOTO_CRIAR', str(cur.lastrowid)))
    return {'id': cur.lastrowid, 'link': base + '/remoto#' + chave}


def situacao():
    with get_conn() as c:
        rows = c.execute('SELECT r.id,r.permissao,r.expira_em,r.ativo,r.usado,r.ultimo,o.nome,o.login FROM acessos_remotos r JOIN operadores o ON o.id=r.operador_id ORDER BY r.id DESC LIMIT 100').fetchall()
    try:
        url = publicacao.validar_dominio(publicacao.endereco())
    except ValueError:
        url = ''
    return {'url': url, 'inatividade_minutos': 15, 'acessos': [dict(r) for r in rows]}


def revogar(uid=None):
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        ator = _responsavel(c)
        c.execute('UPDATE acessos_remotos SET ativo=0,sessao_hash=NULL' + (' WHERE id=?' if uid is not None else ''), (uid,) if uid is not None else ())
        c.execute('INSERT INTO auditoria_operadores(operador_id,acao,objeto) VALUES(?,?,?)', (ator, 'REMOTO_REVOGAR', str(uid) if uid is not None else 'TODOS'))


def _validar(c, operar=False):
    chave = session.get('remoto_sessao', '')
    if not isinstance(chave, str) or len(chave) != 64:
        abort(401)
    r = c.execute('SELECT r.*,o.versao,o.ativo AS conta_ativa,o.perfil,o.nome FROM acessos_remotos r JOIN operadores o ON o.id=r.operador_id WHERE r.sessao_hash=?', (_hash(chave),)).fetchone()
    agora = time.time()
    if (not r or not r['ativo'] or not r['conta_ativa'] or r['perfil'] not in {'ADMIN', 'ATENDENTE'}
            or r['conta_versao'] != r['versao'] or agora >= r['expira_em']
            or r['ultimo'] is None or agora >= r['ultimo'] + INATIVIDADE):
        abort(401)
    if operar and r['permissao'] != 'PEDIDOS':
        abort(403)
    return r


@bp.before_request
def proteger():
    # Somente a porta pública isolada pode marcar este ambiente WSGI.
    if not request.environ.get('deliverybot.remote_gateway') or not request.is_secure:
        abort(404)
    request.max_content_length = 4096
    if request.method != 'GET' and not seguranca.csrf_valido():
        abort(403)
    if request.endpoint not in {'remoto.pagina', 'remoto.entrar'}:
        with get_conn() as c:
            r = _validar(c)
            g.remoto_id = r['id']
        if not _limites.consumir(('sessao', r['id']), 120, 60):
            abort(429)


@bp.errorhandler(400)
@bp.errorhandler(401)
@bp.errorhandler(403)
@bp.errorhandler(404)
@bp.errorhandler(429)
def erro_http(exc):
    mensagens = {400: 'Envie dados válidos.', 401: 'Acesso inválido, encerrado ou expirado. Solicite um novo convite.',
                 403: 'Operação não permitida. Confira sua permissão e reabra esta página.', 404: 'Página não encontrada.',
                 429: 'Muitas tentativas. Aguarde alguns minutos.'}
    return jsonify(erro=mensagens[exc.code]), exc.code


@bp.errorhandler(ValueError)
def erro_validacao(exc):
    return jsonify(erro=str(exc)), 400


@bp.get('/remoto')
def pagina():
    return render_template('remoto.html', csrf=seguranca.csrf(), loja=config.NOME_RESTAURANTE)


@bp.post('/remoto/api/entrar')
def entrar():
    # IPs encaminhados não são usados: limites globais e por convite no servidor.
    if not _limites.consumir('entradas', 60, 300):
        abort(429)
    d = request.get_json()
    if not isinstance(d, dict):
        abort(400)
    chave, senha, login = d.get('convite'), d.get('senha'), d.get('login')
    if not isinstance(chave, str) or len(chave) != 43 or not isinstance(senha, str) or not 12 <= len(senha) <= 256 or not isinstance(login, str) or len(login) > 80:
        abort(401)
    digest = _hash(chave)
    if not _limites.consumir(('convite', digest), 10, 300):
        abort(429)
    with get_conn() as c:
        r = c.execute('SELECT r.*,o.senha_hash,o.login,o.versao,o.ativo AS conta_ativa,o.perfil FROM acessos_remotos r JOIN operadores o ON o.id=r.operador_id WHERE r.convite_hash=?', (digest,)).fetchone()
    hash_senha = r['senha_hash'] if r else operadores._HASH_FICTICIO
    correto = check_password_hash(hash_senha, senha)
    if not r or not correto or not seguranca.igual(r['login'], login.casefold()):
        abort(401)
    nova = secrets.token_hex(32)
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        # Revalida a conta após o cálculo do hash e consome o convite uma única vez.
        ok = c.execute("UPDATE acessos_remotos SET usado=1,sessao_hash=?,ultimo=? WHERE id=? AND usado=0 AND ativo=1 AND expira_em>? AND EXISTS(SELECT 1 FROM operadores o WHERE o.id=operador_id AND o.ativo=1 AND o.perfil IN ('ADMIN','ATENDENTE') AND o.versao=conta_versao AND o.senha_hash=?)",
                       (_hash(nova), time.time(), r['id'], time.time(), hash_senha)).rowcount
        if not ok:
            abort(401)
        c.execute('INSERT INTO auditoria_operadores(operador_id,acao,objeto) VALUES(?,?,?)', (r['operador_id'], 'REMOTO_ENTRAR', str(r['id'])))
    session.clear()
    session.update(remoto_sessao=nova, csrf=secrets.token_urlsafe(32))
    return jsonify(ok=True, csrf=session['csrf'])


@bp.get('/remoto/api/estado')
def estado():
    with get_conn() as c:
        r = _validar(c)
        # Atualizar é uma ação manual; não há polling que prolongue uma sessão abandonada.
        c.execute('UPDATE acessos_remotos SET ultimo=? WHERE id=?', (time.time(), r['id']))
        produtos = [dict(p) for p in c.execute('SELECT id,nome,categoria,preco,estoque,unidade FROM produtos WHERE ativo=1 ORDER BY nome LIMIT 500')]
    campos = {'pedido_id', 'numero_pedido', 'status', 'total_pedido', 'forma_entrega', 'pedido_criado_em', 'cliente_nome'}
    abertos = []
    for p in fila.listar_fila():
        abertos.append({**{k: v for k, v in p.items() if k in campos},
                        'itens': [{k: v for k, v in i.items() if k in {'quantidade', 'produto_nome', 'observacao'}} for i in p['itens']]})
    return jsonify(nome=r['nome'], permissao=r['permissao'], expira_em=r['expira_em'],
                   inatividade_minutos=15, pedidos=abertos, produtos=produtos)


@bp.post('/remoto/api/pedidos/<int:pid>/avancar')
def avancar(pid):
    d = request.get_json()
    if not isinstance(d, dict) or not isinstance(d.get('status'), str) or d['status'] not in {'AGUARDANDO', 'EM_PREPARO', 'PRONTO'} or d.get('confirmar') is not True:
        raise ValueError('Atualize os pedidos e confirme a mudança de etapa.')
    def autorizar(c):
        r = _validar(c, operar=True)
        c.execute('UPDATE acessos_remotos SET ultimo=? WHERE id=?', (time.time(), r['id']))
        c.execute('INSERT INTO auditoria_operadores(operador_id,acao,objeto) VALUES(?,?,?)', (r['operador_id'], 'REMOTO_AVANCAR', str(pid)))
    p = fila.avancar_status(pid, _autorizar=autorizar, status_esperado=d['status'])
    return jsonify(ok=True, aviso=p.get('aviso'))


@bp.post('/remoto/api/sair')
def sair():
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        r = _validar(c)
        c.execute('UPDATE acessos_remotos SET ativo=0,sessao_hash=NULL WHERE id=?', (r['id'],))
        c.execute('INSERT INTO auditoria_operadores(operador_id,acao,objeto) VALUES(?,?,?)', (r['operador_id'], 'REMOTO_SAIR', str(r['id'])))
    session.clear()
    return jsonify(ok=True)
