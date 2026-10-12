"""Gateway exclusivo do caixa na rede privada: TLS, dispositivo pareado e conta revogável."""
import hashlib
import ipaddress
import json
import secrets
import socket
import ssl
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from flask import Flask, g, jsonify, request, session

from . import caixa, config, estoque, operadores, pedidos, seguranca
from .db import get_conn
from .validacao_http import JSONSeguro, parametros_unicos
from . import politica_terminal as politica

_servidor = None
_trava = threading.RLock()


def ip_rede(valor, permitir_loopback=False):
    try:
        ip = ipaddress.IPv4Address(valor)
        redes = ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')
        if not any(ip in ipaddress.IPv4Network(r) for r in redes) and not (permitir_loopback and ip.is_loopback):
            raise ValueError
        return str(ip)
    except (ValueError, TypeError):
        raise ValueError('Use o IPv4 privado deste computador na rede da loja (10.x, 172.16–31.x ou 192.168.x).') from None


def configuracao():
    with get_conn() as c:
        return dict(c.execute('SELECT * FROM terminal_config WHERE id=1').fetchone())


def _certificado(host, pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    cert, chave = pasta/'terminal-cert.pem', pasta/'terminal-chave.pem'
    if cert.exists() and chave.exists():
        atual = x509.load_pem_x509_certificate(cert.read_bytes())
        if x509.IPAddress(ipaddress.ip_address(host)) in atual.extensions.get_extension_for_class(x509.SubjectAlternativeName).value and atual.not_valid_after_utc > datetime.now(timezone.utc) + timedelta(days=1):
            return cert, chave
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'DeliveryBot - caixa da loja')])
    agora = datetime.now(timezone.utc)
    certificado = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(agora-timedelta(minutes=5)).not_valid_after(agora+timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(host))]),critical=False)
        .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
        .sign(key,hashes.SHA256()))
    chave.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    cert.write_bytes(certificado.public_bytes(serialization.Encoding.PEM))
    return cert, chave


def convite(d):
    uid, mover = politica.dados_autorizacao(d)
    with _trava:
        if not _servidor:
            raise ValueError('Ative a conexão dos funcionários antes de gerar o arquivo de acesso.')
        codigo = secrets.token_urlsafe(32)
        with get_conn() as c:
            c.execute('BEGIN IMMEDIATE')
            politica.conta_caixa(c, uid)
            c.execute('DELETE FROM terminal_convites_autorizacoes WHERE hash IN (SELECT hash FROM terminal_convites WHERE expira_em<? OR usado=1)', (time.time(),))
            c.execute('DELETE FROM terminal_convites WHERE expira_em<? OR usado=1',(time.time(),))
            c.execute('INSERT INTO terminal_convites(hash,expira_em) VALUES(?,?)',(hashlib.sha256(codigo.encode()).hexdigest(),time.time()+600))
            c.execute('INSERT INTO terminal_convites_autorizacoes VALUES(?,?,?)', (hashlib.sha256(codigo.encode()).hexdigest(),uid,int(mover)))
        return {'formato':1,'url':f'https://{_servidor.host}:{_servidor.porta}',
                'certificado':_servidor.cert.read_text(encoding='ascii'), 'convite':codigo,
                'impressao_sha256':x509.load_pem_x509_certificate(_servidor.cert.read_bytes()).fingerprint(hashes.SHA256()).hex()}


def parear(d):
    codigo=d.get('convite')
    if not isinstance(codigo,str) or not 32<=len(codigo)<=100:
        raise ValueError('Arquivo de acesso inválido ou expirado.')
    nome=estoque.texto(d.get('nome','Terminal do funcionário'),'Computador',80,True)
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        if not configuracao()['ativo']:
            raise ValueError('A conexão foi desativada pelo responsável.')
        conv=c.execute('SELECT * FROM terminal_convites WHERE hash=?',(hashlib.sha256(codigo.encode()).hexdigest(),)).fetchone()
        if not conv or conv['usado'] or conv['expira_em']<time.time():
            raise ValueError('Arquivo de acesso já utilizado ou expirado. Solicite um novo ao responsável.')
        autorizacao=c.execute('SELECT * FROM terminal_convites_autorizacoes WHERE hash=?', (conv['hash'],)).fetchone()
        if not autorizacao:
            raise ValueError('Este acesso antigo não tem uma conta vinculada. Solicite um novo ao responsável.')
        politica.conta_caixa(c, autorizacao['operador_id'])
        chave=secrets.token_urlsafe(48)
        uid=c.execute('INSERT INTO terminal_dispositivos(nome,hash) VALUES(?,?)',(nome,hashlib.sha256(chave.encode()).hexdigest())).lastrowid
        c.execute('INSERT INTO terminal_autorizacoes VALUES(?,?,?,?)', (uid,autorizacao['operador_id'],autorizacao['movimentar'],secrets.token_hex(24)))
        c.execute('UPDATE terminal_convites SET usado=1 WHERE hash=?',(conv['hash'],))
        return {'dispositivo':uid,'chave':chave}


def criar_api():
    app=Flask('deliverybot_terminal',static_folder=None)
    app.secret_key=secrets.token_hex(32)
    app.json=JSONSeguro(app)
    sessoes=politica.Sessoes()
    limites=politica.Limites()
    app.extensions.update(terminal_sessoes=sessoes,terminal_limites=limites)
    app.config.update(MAX_CONTENT_LENGTH=128*1024,SESSION_COOKIE_NAME='terminal_session',SESSION_COOKIE_SECURE=True,
                      SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    def registrar_recusa(motivo):
        did=g.get('dispositivo')
        if did and limites.consumir(('auditoria',did,motivo),1,300):
            with get_conn() as c:
                c.execute('INSERT INTO auditoria_operadores(operador_id,acao,objeto) VALUES(NULL,?,?)',('TERMINAL_RECUSA_'+motivo,str(did)))
    @app.before_request
    def autenticar():
        try:
            ip_rede(request.remote_addr,permitir_loopback=True)
        except ValueError:
            return jsonify(erro='Acesso restrito à rede privada.'),403
        if not limites.consumir(('rede',request.remote_addr),120,60):
            return jsonify(erro='Muitas solicitações. Aguarde um minuto.',nao_executada=True),429
        cfg=configuracao()
        host=app.config.get('TERMINAL_HOST') or app.config.get('SERVER_NAME') or f"{cfg['host']}:{cfg['porta']}"
        if not request.is_secure or not cfg['ativo'] or request.host!=host or request.headers.get('Origin') or request.headers.get('Sec-Fetch-Site') or request.args or not parametros_unicos(request.args):
            return jsonify(erro='Acesso restrito ao aplicativo de caixa da loja.'),403
        if request.method not in {'GET','POST'}:
            return jsonify(erro='Método indisponível.'),405
        if request.endpoint is None:
            return jsonify(erro='Operação indisponível.'),404
        if request.path=='/terminal/parear' and request.method=='POST':
            if not limites.consumir(('parear',request.remote_addr),10,60):
                return jsonify(erro='Muitas tentativas de pareamento. Aguarde um minuto.'),429
            return None
        token=request.headers.get('Authorization','').removeprefix('Bearer ')
        if not 32<=len(token)<=100:
            return jsonify(erro='Computador não autorizado.'),401
        with get_conn() as c:
            dispositivo=c.execute('SELECT d.id,a.operador_id,a.movimentar,a.versao FROM terminal_dispositivos d LEFT JOIN terminal_autorizacoes a ON a.dispositivo_id=d.id WHERE d.ativo=1 AND d.hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not dispositivo:
            return jsonify(erro='Computador revogado. Solicite novo acesso ao responsável.'),401
        g.dispositivo=dispositivo['id']
        if dispositivo['operador_id'] is None:
            registrar_recusa('SEM_VINCULO')
            return jsonify(erro='O responsável precisa vincular este computador a uma conta Caixa.'),401
        g.autorizacao=dict(dispositivo)
        if request.endpoint=='pendencia_bloqueada' and request.method=='POST':
            return None  # Apenas o resultado de uma operação conhecida da conta já bloqueada.
        if request.path=='/terminal/entrar' and request.method=='POST':
            return None
        u=operadores.usuario()
        if not u or u['perfil']!='CAIXA' or u['id']!=dispositivo['operador_id'] or session.get('terminal_dispositivo')!=g.dispositivo:
            registrar_recusa('CONTA')
            return jsonify(erro='Entre com uma conta de caixa autorizada.'),401
        prazo=sessoes.validar(session.get('terminal_sessao'),g.dispositivo,u['id'],dispositivo['versao'],request.method=='POST')
        if prazo is None:
            session.clear()
            return jsonify(erro='Sua sessão expirou ou a autorização mudou. Entre novamente com a conta vinculada.'),401
        g.operador=u
        g.terminal_autorizacao=dict(dispositivo_id=g.dispositivo,versao=dispositivo['versao'],conta_versao=u['versao'],prazo=prazo)
        if request.endpoint=='movimentar' and not dispositivo['movimentar']:
            registrar_recusa('MOVIMENTACAO')
            return jsonify(erro='Sangria e suprimento precisam da autorização do responsável.',nao_executada=True),403
    @app.after_request
    def headers(r):
        r.headers.update({'Cache-Control':'no-store','X-Frame-Options':'DENY','X-Content-Type-Options':'nosniff',
                          'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'",'Referrer-Policy':'no-referrer'})
        return r
    @app.errorhandler(ValueError)
    def invalido(exc):
        return jsonify(erro=str(exc)),400
    @app.errorhandler(politica.AcessoNegado)
    def negado(exc):
        registrar_recusa('TRANSACAO')
        return jsonify(erro=str(exc),nao_executada=True),403
    for codigo in (400,404,405,413,415,500):
        app.register_error_handler(codigo,lambda exc: (jsonify(erro='Operação indisponível. Confira os dados e a conexão.'),exc.code))
    def dados():
        d=request.get_json()
        if not isinstance(d,dict):
            raise ValueError('Envie um objeto com os dados da operação.')
        permitidos={
            'par':{'convite','nome'},'entrar':{'login','senha'},'sair':set(),
            'cotar':{'itens','entrega'},'abrir':{'chave','abertura'},
            'vender':{'chave','nome','itens','cotacao','pago','forma','recebido','entrega','endereco'},
            'movimentar':{'chave','tipo','valor','motivo'},'fechar':{'chave','contado'},
            'receber':{'chave','forma','recebido'},
            'pendencia_bloqueada':{'chave','operador_id'},
        }
        if request.endpoint not in permitidos or not set(d).issubset(permitidos[request.endpoint]):
            raise ValueError('Campos não permitidos nesta operação.')
        if 'itens' in d:
            if not isinstance(d['itens'],list) or not 1<=len(d['itens'])<=200 or any(not isinstance(i,dict) or not set(i).issubset({'produto_id','quantidade'}) for i in d['itens']):
                raise ValueError('Escolha de 1 a 200 itens com produto e quantidade, sem campos extras.')
        return d
    @app.post('/terminal/parear')
    def par():
        return jsonify(parear(dados()))
    @app.post('/terminal/entrar')
    def entrar():
        if seguranca.login_bloqueado() or not limites.consumir(('login',g.dispositivo),30,300):
            return jsonify(erro='Muitas tentativas. Aguarde cinco minutos.'),429
        d=dados()
        sessoes.sair(session.get('terminal_sessao'))
        session.clear()
        with get_conn() as c:
            alvo=c.execute("SELECT login FROM operadores WHERE id=? AND ativo=1 AND perfil='CAIXA'", (g.autorizacao['operador_id'],)).fetchone()
        # Outra conta usa o hash fictício; nunca valida a senha administradora pela rede fraca.
        login=d.get('login')
        autorizado=bool(alvo and isinstance(login,str) and login.casefold()==alvo['login'])
        ok=operadores.entrar(login if autorizado else '',d.get('senha'))
        u=operadores.usuario() if ok else None
        ok=bool(u and u['perfil']=='CAIXA' and u['id']==g.autorizacao['operador_id'])
        seguranca.registrar_login(ok)
        if not ok:
            registrar_recusa('LOGIN')
            session.clear()
            return jsonify(erro='Login, senha ou perfil de caixa inválidos.'),401
        session['terminal_dispositivo']=g.dispositivo
        session['terminal_sessao']=sessoes.criar(g.dispositivo,u['id'],g.autorizacao['versao'])
        return jsonify(usuario={k:u[k] for k in ('id','nome','perfil')},loja=config.NOME_RESTAURANTE,permissoes={'movimentar':bool(g.autorizacao['movimentar'])})
    @app.post('/terminal/sair')
    def sair():
        dados()
        sessoes.sair(session.get('terminal_sessao'))
        session.clear()
        return jsonify(ok=True)
    @app.get('/terminal/estado')
    def estado():
        return jsonify(usuario={k:g.operador[k] for k in ('id','nome','perfil')},caixas=caixa.consultar(g.operador['id'],detalhar=False),vendas=caixa.vendas(g.operador['id']),permissoes={'movimentar':bool(g.autorizacao['movimentar'])})
    @app.get('/terminal/catalogo')
    def catalogo():
        campos=('id','nome','categoria','variacao','preco','estoque','unidade','fracionado')
        return jsonify([{k:p[k] for k in campos} for p in estoque.listar_produtos() if p['ativo']])
    @app.post('/terminal/cotacao')
    def cotar():
        d=dados()
        if not isinstance(d.get('itens'),list) or not 1<=len(d['itens'])<=200:
            raise ValueError('Escolha de 1 a 200 itens.')
        entrega=d.get('entrega','RETIRADA BALCAO')
        if entrega not in {'RETIRADA BALCAO','ENTREGA'}:
            raise ValueError('Escolha retirada ou entrega.')
        return jsonify(pedidos.cotacao(d['itens'],entrega))
    for rota,funcao in [('abrir',caixa.abrir),('vender',caixa.vender),('movimentar',caixa.movimentar),('fechar',caixa.fechar)]:
        app.add_url_rule('/terminal/'+rota,rota,lambda f=funcao:jsonify(f(g.operador['id'],dados())),methods=['POST'])
    @app.post('/terminal/receber/<int:pid>')
    def receber(pid):
        return jsonify(caixa.receber(g.operador['id'],pid,dados()))
    @app.get('/terminal/operacao/<chave>')
    def operacao(chave):
        return jsonify(resultado=caixa.resultado(g.operador['id'],chave))
    @app.post('/terminal/pendencia-bloqueada')
    def pendencia_bloqueada():
        import re
        d=dados()
        key=d.get('chave')
        if type(d.get('operador_id')) is not int or d['operador_id']!=g.autorizacao['operador_id'] or not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}',key):
            return jsonify(erro='Pendência não disponível para este computador.'),401
        with get_conn() as c:
            c.execute('BEGIN IMMEDIATE')
            alvo=c.execute('SELECT ativo,perfil FROM operadores WHERE id=?',(g.autorizacao['operador_id'],)).fetchone()
            if alvo and alvo['ativo'] and alvo['perfil']=='CAIXA':
                return jsonify(erro='Entre com a conta vinculada para conferir a operação.'),401
            r=c.execute('SELECT resultado FROM operacoes_caixa WHERE operador_id=? AND chave=?',(g.autorizacao['operador_id'],key)).fetchone()
            return jsonify(resultado=json.loads(r['resultado']) if r else None,cancelada=not bool(r))
    return app


class _Handler(WSGIRequestHandler):
    def log_message(self,*args):
        pass
    def get_environ(self):
        e=super().get_environ()
        e['HTTPS']='on'
        e['wsgi.url_scheme']='https'
        return e


class _Servidor(ThreadingMixIn,WSGIServer):
    daemon_threads=True
    request_queue_size=16
    def __init__(self,*args,**kwargs):
        self.limite=threading.BoundedSemaphore(16)
        super().__init__(*args,**kwargs)
    def process_request(self,req,addr):
        if not self.limite.acquire(blocking=False):
            self.shutdown_request(req)
            return
        super().process_request(req,addr)
    def process_request_thread(self,req,addr):
        try:
            ip_rede(addr[0],permitir_loopback=True)
            req.settimeout(10)
            with self.tls.wrap_socket(req,server_side=True) as seguro:
                self.finish_request(seguro,addr)
                # close_notify entrega os registros TLS pendentes antes do FIN.
                # Um cliente que encerra sem responder não prende o servidor.
                seguro.settimeout(2)
                try:
                    cru=seguro.unwrap()
                    cru.close()
                except OSError:
                    pass
        except (OSError,ValueError):
            pass
        finally:
            self.shutdown_request(req)
            self.limite.release()


class ServidorTerminal:
    def __init__(self,host,porta,pasta,permitir_loopback=False):
        self.host=ip_rede(host,permitir_loopback)
        self.porta=porta
        self.cert,chave=_certificado(self.host,Path(pasta))
        app=criar_api()
        self.http=make_server(host,porta,app,server_class=_Servidor,handler_class=_Handler)
        self.http.tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.http.tls.minimum_version=ssl.TLSVersion.TLSv1_2
        self.http.tls.load_cert_chain(self.cert,chave)
        self.porta=self.http.server_port
        app.config['TERMINAL_HOST']=f'{self.host}:{self.porta}'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True,name='DeliveryBot-Caixa-TLS')
        self.thread.start()
    def close(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=3)


def encerrar():
    global _servidor
    with _trava:
        if _servidor:
            _servidor.close()
            _servidor=None


def iniciar():
    global _servidor
    with _trava:
        cfg=configuracao()
        if cfg['ativo'] and not _servidor:
            _servidor=ServidorTerminal(cfg['host'],cfg['porta'],Path(config.DATABASE_PATH).resolve().parent/'terminal-tls')


def configurar(d):
    if type(d.get('ativo')) is not bool:
        raise ValueError('Informe se a conexão dos funcionários deve ficar ativa.')
    host=ip_rede(d.get('host')) if d['ativo'] else configuracao()['host']
    porta=d.get('porta',5443)
    if type(porta) is not int or not 1024<=porta<=65535:
        raise ValueError('Use uma porta entre 1024 e 65535.')
    with _trava:
        encerrar()
        with get_conn() as c:
            c.execute('UPDATE terminal_config SET ativo=?,host=?,porta=? WHERE id=1',(int(d['ativo']),host,porta))
        try:
            iniciar()
        except OSError:
            with get_conn() as c:
                c.execute('UPDATE terminal_config SET ativo=0 WHERE id=1')
            raise ValueError('Não foi possível abrir a conexão. Confira o IP deste computador e se a porta está livre.') from None


def situacao():
    with get_conn() as c:
        dispositivos=[dict(r) for r in c.execute('SELECT d.id,d.nome,d.ativo,d.criado_em,a.operador_id,a.movimentar,o.nome AS funcionario FROM terminal_dispositivos d LEFT JOIN terminal_autorizacoes a ON a.dispositivo_id=d.id LEFT JOIN operadores o ON o.id=a.operador_id ORDER BY d.id DESC')]
    try:
        ips=sorted({r[4][0] for r in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET) if ipaddress.ip_address(r[4][0]).is_private and not ipaddress.ip_address(r[4][0]).is_loopback})
    except OSError:
        ips=[]
    return {'configuracao':configuracao(),'em_execucao':_servidor is not None,'ips_sugeridos':ips,'dispositivos':dispositivos}


def revogar(did):
    with get_conn() as c:
        c.execute('UPDATE terminal_dispositivos SET ativo=0 WHERE id=?',(did,))
