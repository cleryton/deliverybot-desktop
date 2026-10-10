"""Contas locais com sessão revogável, permissões e auditoria operacional."""
import re
import secrets
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_conn
from .estoque import texto

_HASH_FICTICIO = generate_password_hash('credencial-ficticia-inexistente')


def existem():
    with get_conn() as c:
        return bool(c.execute('SELECT 1 FROM operadores LIMIT 1').fetchone())


def usuario(dados=None):
    s=session if dados is None else dados
    with get_conn() as c:
        r=c.execute('SELECT id,nome,login,perfil,versao FROM operadores WHERE id=? AND ativo=1',(s.get('operador_id'),)).fetchone()
    return dict(r) if r and secrets.compare_digest(r['versao'],s.get('operador_versao','')) else None


def admin():
    u=usuario()
    return not existem() or bool(u and u['perfil']=='ADMIN')


def permitido(caminho,metodo):
    if admin():
        return True
    if caminho.startswith('/gestao/api/humano'):
        return True
    if metodo=='GET' and caminho in {'/gestao/api/resumo','/gestao/api/produtos','/gestao/api/pedidos','/gestao/api/operadores/me'}:
        return True
    return bool(metodo=='POST' and re.fullmatch(r'/gestao/api/pedidos/\d+/avancar',caminho))


def auditar(acao, objeto=None, usuario_id=None):
    u=usuario() if usuario_id is None else None
    with get_conn() as c:
        c.execute('INSERT INTO auditoria_operadores(operador_id,acao,objeto) VALUES(?,?,?)',(usuario_id if usuario_id is not None else u['id'] if u else None,acao,str(objeto)[:80] if objeto is not None else None))


def senha_valida(senha):
    if not isinstance(senha,str) or not 12<=len(senha)<=256:
        raise ValueError('Use uma senha de 12 a 256 caracteres.')
    return generate_password_hash(senha)


def criar(d):
    login=texto(d.get('login',''),'Login',80,True).casefold()
    if not re.fullmatch(r'[a-z0-9._-]{3,80}',login):
        raise ValueError('Login: use de 3 a 80 letras sem acentos, números, ponto, hífen ou sublinhado.')
    nome=texto(d.get('nome',''),'Nome',160,True)
    perfil=d.get('perfil')
    if perfil not in {'ADMIN','ATENDENTE'}:
        raise ValueError('Perfil inválido.')
    senha=senha_valida(d.get('senha'))
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        primeiro=not c.execute('SELECT 1 FROM operadores LIMIT 1').fetchone()
        if primeiro and perfil!='ADMIN':
            raise ValueError('A primeira conta precisa ser administradora.')
        if c.execute('SELECT 1 FROM operadores WHERE login=?',(login,)).fetchone():
            raise ValueError('Este login já está cadastrado.')
        versao=secrets.token_hex(24)
        cur=c.execute('INSERT INTO operadores(nome,login,senha_hash,perfil,versao) VALUES(?,?,?,?,?)',(nome,login,senha,perfil,versao))
        uid=cur.lastrowid
    if primeiro:
        session['operador_id']=uid
        session['operador_versao']=versao
        session.permanent=True
    auditar('CRIAR_OPERADOR',uid)
    return {'id':uid,'nome':nome,'login':login,'perfil':perfil}


def alterar(uid,d):
    ator=usuario()
    senha=senha_valida(d['senha']) if d.get('senha') else None
    if not isinstance(d.get('ativo'),bool) or d.get('perfil') not in {'ADMIN','ATENDENTE'}:
        raise ValueError('Informe perfil e situação da conta.')
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        u=c.execute('SELECT * FROM operadores WHERE id=?',(uid,)).fetchone()
        if not u:
            raise ValueError('Conta não encontrada.')
        if u['ativo'] and u['perfil']=='ADMIN' and (not d['ativo'] or d['perfil']!='ADMIN') and not c.execute("SELECT 1 FROM operadores WHERE id!=? AND ativo=1 AND perfil='ADMIN'",(uid,)).fetchone():
            raise ValueError('Mantenha pelo menos um administrador ativo.')
        c.execute('UPDATE operadores SET ativo=?,perfil=?,senha_hash=?,versao=? WHERE id=?',(d['ativo'],d['perfil'],senha or u['senha_hash'],secrets.token_hex(24),uid))
    auditar('ALTERAR_OPERADOR',uid,usuario_id=ator['id'] if ator else None)


def entrar(login,senha):
    with get_conn() as c:
        u=c.execute('SELECT * FROM operadores WHERE login=? AND ativo=1',(str(login)[:80].casefold(),)).fetchone()
    # Hash fictício torna tentativas para logins inexistentes comparáveis em custo.
    alvo=u['senha_hash'] if u else _HASH_FICTICIO
    ok=isinstance(senha,str) and len(senha)<=256 and check_password_hash(alvo,senha)
    if not u or not ok:
        return False
    session['operador_id']=u['id'];session['operador_versao']=u['versao'];session.permanent=True
    auditar('ENTRAR',usuario_id=u['id'])
    return True


def listar():
    with get_conn() as c:
        return [dict(r) for r in c.execute('SELECT id,nome,login,perfil,ativo FROM operadores ORDER BY nome')]


def auditoria():
    with get_conn() as c:
        return [dict(r) for r in c.execute('SELECT a.*,COALESCE(o.nome,\'Responsável local\') AS operador FROM auditoria_operadores a LEFT JOIN operadores o ON o.id=a.operador_id ORDER BY a.id DESC LIMIT 100')]


def validar_sessao_nativa(app, janela, administrador=True):
    """Valida o cookie HttpOnly assinado, inclusive nas chamadas da ponte nativa."""
    from . import seguranca
    try:
        nome=app.config.get('SESSION_COOKIE_NAME','session')
        cookies=janela.get_cookies()
        valor=next(c[nome].value for c in cookies if nome in c)
        serializador=app.session_interface.get_signing_serializer(app)
        dados=serializador.loads(valor,max_age=int(app.permanent_session_lifetime.total_seconds()))
        valido=seguranca.igual(dados.get('desktop',''),app.config.get('DESKTOP_TOKEN',''))
        if administrador and existem():
            u=usuario(dados)
            valido=valido and bool(u and u['perfil']=='ADMIN')
        if valido:
            return
    except Exception:
        pass
    raise ValueError('Entre com uma conta administradora para realizar esta operação.')
