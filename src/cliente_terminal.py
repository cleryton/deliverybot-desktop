"""Cliente HTTPS pareado: certificado específico, credencial cifrada e retentativa idempotente."""
import ipaddress
import json
import os
import re
import secrets
import threading
from pathlib import Path
from urllib.parse import urlsplit

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from .protecao_terminal import dpapi


class FalhaTerminal(ValueError):
    pass


def validar_conexao(d,permitir_loopback=False):
    if not isinstance(d,dict) or d.get('formato')!=1 or not isinstance(d.get('url'),str):
        raise FalhaTerminal('Arquivo de acesso inválido.')
    try:
        if any(c.isspace() or ord(c)<32 or ord(c)==127 for c in d['url']):
            raise ValueError
        u=urlsplit(d['url'])
        ip=ipaddress.IPv4Address(u.hostname)
        redes=('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16')
        if (u.scheme!='https' or u.username is not None or u.password is not None or u.path or u.query or u.fragment
                or not 1024<=u.port<=65535 or not (any(ip in ipaddress.IPv4Network(r) for r in redes) or permitir_loopback and ip.is_loopback)):
            raise ValueError
        pem=d.get('certificado','')
        if not isinstance(pem,str) or len(pem)>16384:
            raise ValueError
        cert=x509.load_pem_x509_certificate(pem.encode('ascii'))
        if cert.fingerprint(hashes.SHA256()).hex()!=d.get('impressao_sha256'):
            raise ValueError
        if x509.IPAddress(ip) not in cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value:
            raise ValueError
        return d
    except (ValueError,TypeError,x509.ExtensionNotFound,UnicodeError):
        raise FalhaTerminal('Endereço ou certificado inválido. Solicite um arquivo de acesso atualizado ao responsável.') from None


class Cliente:
    def __init__(self,pasta,permitir_loopback=False):
        self.permitir_loopback=permitir_loopback
        self.pasta=Path(pasta)
        self.pasta.mkdir(parents=True,exist_ok=True)
        self.http=requests.Session()
        self.http.trust_env=False  # Sem proxies ou credenciais herdados da máquina.
        self.trava=threading.RLock()
        self.usuario=None
        self.conexao=self._ler('conexao.bin')
        self.pendente=self._ler('pendencia.bin')
        if self.conexao:
            validar_conexao(self.conexao,self.permitir_loopback)
            self._preparar(self.conexao)
    def _ler(self,nome):
        p=self.pasta/nome
        if not p.exists():
            return None
        if p.stat().st_size>256*1024:
            raise FalhaTerminal('Configuração local inválida. Peça ajuda ao responsável.')
        return json.loads(dpapi(p.read_bytes(),True))
    def _salvar(self,nome,dados):
        p=self.pasta/nome
        if dados is None:
            p.unlink(missing_ok=True)
            return
        temporario=self.pasta/(nome+'.novo')
        temporario.write_bytes(dpapi(json.dumps(dados,ensure_ascii=False,allow_nan=False).encode()))
        os.replace(temporario,p)
    def _preparar(self,d):
        cert=self.pasta/'certificado.pem'
        cert.write_text(d['certificado'],encoding='ascii')
        self.http.verify=str(cert)
        self.http.cookies.clear()
        self.http.headers.update({'Authorization':'Bearer '+d.get('chave','')})
        self.url=d['url']
    def _request(self,caminho,dados=None):
        try:
            with self.http.request('GET' if dados is None else 'POST',self.url+'/terminal/'+caminho,
                                   json=dados,timeout=(5,20),allow_redirects=False,stream=True) as r:
                partes=[]
                tamanho=0
                # iter_content converte erros de protocolo do urllib3 para Requests,
                # permitindo conservar a pendência sem expor detalhes de transporte.
                for parte in r.iter_content(chunk_size=65536):
                    tamanho+=len(parte)
                    if tamanho>2*1024*1024:
                        raise FalhaTerminal('Resposta inesperada. Confira a operação antes de continuar.')
                    partes.append(parte)
                corpo=b''.join(partes)
                d=json.loads(corpo)
                if not isinstance(d,(dict,list)):
                    raise ValueError
                if not r.ok:
                    erro=FalhaTerminal(d.get('erro','Operação não disponível.') if isinstance(d,dict) else 'Operação não disponível.')
                    erro.status=r.status_code
                    raise erro
                return d
        except requests.exceptions.SSLError:
            raise FalhaTerminal('A identidade HTTPS da loja não confere. Solicite um novo arquivo de acesso ao responsável.') from None
        except (requests.RequestException,ValueError) as exc:
            if isinstance(exc,FalhaTerminal):
                raise
            raise FalhaTerminal('Sem resposta da loja. Verifique a rede e se o aplicativo do responsável está aberto. Confira operações pendentes antes de repetir.') from None
    def parear(self,d):
        with self.trava:
            if self.pendente:
                raise FalhaTerminal('Resolva a operação pendente antes de trocar a conexão.')
            validar_conexao(d,self.permitir_loopback)
            anterior=self.conexao
            self.usuario=None
            try:
                self._preparar(d)
                r=self._request('parear',{'convite':d.get('convite'),'nome':'Terminal do funcionário'})
            except Exception:
                if anterior:
                    self._preparar(anterior)
                raise
            if not isinstance(r.get('chave'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{32,100}',r['chave']):
                raise FalhaTerminal('A loja retornou uma credencial inválida.')
            nova={k:d[k] for k in ('formato','url','certificado','impressao_sha256')}
            nova.update(chave=r['chave'],dispositivo=r['dispositivo'])
            self._salvar('conexao.bin',nova)
            self.conexao=nova
            self._preparar(nova)
            self.usuario=None
            self.http.cookies.clear()
            return {'ok':True}
    def entrar(self,login,senha):
        with self.trava:
            if not self.conexao:
                raise FalhaTerminal('Importe primeiro o arquivo de acesso fornecido pelo responsável.')
            self.usuario=None
            self.http.cookies.clear()
            r=self._request('entrar',{'login':login,'senha':senha})
            self.usuario=r['usuario']
            return r
    def consultar(self,acao):
        with self.trava:
            if acao not in {'estado','catalogo'}:
                raise FalhaTerminal('Consulta inválida.')
            return self._request(acao)
    def cotar(self,itens,entrega='RETIRADA BALCAO'):
        with self.trava:
            return self._request('cotacao',{'itens':itens,'entrega':entrega})
    def executar(self,acao,dados):
        with self.trava:
            if not self.usuario:
                raise FalhaTerminal('Entre com sua conta.')
            if acao not in {'abrir','vender','movimentar','fechar'} and not re.fullmatch(r'receber/[1-9][0-9]{0,8}',acao):
                raise FalhaTerminal('Operação inválida.')
            if self.pendente:
                raise FalhaTerminal('Confira a operação pendente antes de iniciar outra.')
            d={**dados,'chave':secrets.token_hex(24)}
            self.pendente={'usuario_id':self.usuario['id'],'acao':acao,'dados':d}
            self._salvar('pendencia.bin',self.pendente)
            return self._enviar_pendente()
    def _enviar_pendente(self):
        try:
            r=self._request(self.pendente['acao'],self.pendente['dados'])
        except FalhaTerminal as e:
            if getattr(e,'status',None)==400:
                self._salvar('pendencia.bin',None)
                self.pendente=None
            raise
        self._salvar('pendencia.bin',None)
        self.pendente=None
        return r
    def conferir(self,repetir=False):
        with self.trava:
            if not self.pendente:
                return {'pendente':False}
            if not self.usuario or self.usuario['id']!=self.pendente['usuario_id']:
                if self.usuario and self.usuario.get('perfil')=='ADMIN':
                    r=self._request('conferir-admin',{'operador_id':self.pendente['usuario_id'],'chave':self.pendente['dados']['chave']})
                    if r['resultado'] is not None or r['cancelada']:
                        self._salvar('pendencia.bin',None)
                        self.pendente=None
                        return {'pendente':False,**r}
                if not repetir:
                    return {'pendente':True,'outro_funcionario':True}
                raise FalhaTerminal('Entre com a conta que iniciou a operação pendente.')
            r=self._request('operacao/'+self.pendente['dados']['chave'])['resultado']
            if r is not None:
                self._salvar('pendencia.bin',None)
                self.pendente=None
                return {'pendente':False,'resultado':r}
            if repetir:
                self._salvar('pendencia.bin',self.pendente)
                return {'pendente':False,'resultado':self._enviar_pendente()}
            return {'pendente':True,'acao':self.pendente['acao']}
    def sair(self):
        with self.trava:
            try:
                self._request('sair',{})
            except FalhaTerminal:
                pass
            finally:
                self.http.cookies.clear()
                self.usuario=None
            return {'ok':True}
