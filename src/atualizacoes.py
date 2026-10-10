"""Consulta de releases públicas e download limitado com verificação de integridade."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

import requests
from . import backups, config
from .db import get_conn

REPOSITORIO='https://github.com/cleryton/deliverybot-desktop'
API='https://api.github.com/repos/cleryton/deliverybot-desktop/releases/latest'
INSTALADOR='Instalar-DeliveryBot.exe'
NOMES_INSTALADOR={INSTALADOR,'Instalar DeliveryBot.exe','Instalar.DeliveryBot.exe'}
LIMITE=256*1024*1024
_raiz=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent.parent))
_lock=threading.RLock()
_estado={}
_baixado=None


def versao(valor):
    if not isinstance(valor,str) or not re.fullmatch(r'v?(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})\.(0|[1-9]\d{0,5})',valor):
        raise ValueError('A versão publicada tem formato inválido.')
    return tuple(int(v) for v in valor.lstrip('v').split('.'))


def atual():
    return (_raiz/'VERSION').read_text(encoding='utf-8').strip()


def _url_arquivo(url,tag,nome):
    from urllib.parse import quote
    esperado=REPOSITORIO+'/releases/download/'+tag+'/'+quote(nome)
    if not isinstance(url,str) or url!=esperado:
        raise ValueError('O arquivo não pertence à distribuição oficial.')
    return url


def _abrir(url):
    # Redirecionamentos de assets são restritos aos hosts HTTPS usados pelo GitHub.
    for _ in range(6):
        u=urlsplit(url)
        if u.scheme!='https' or u.hostname not in {'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'} or u.username or u.password or u.port not in {None,443}:
            raise ValueError('Endereço de download não permitido.')
        r=requests.get(url,timeout=(5,15),stream=True,allow_redirects=False)
        if r.status_code in {301,302,303,307,308}:
            novo=r.headers.get('Location','');r.close();url=novo
            continue
        r.raise_for_status()
        return r
    raise ValueError('O download excedeu o limite de redirecionamentos.')


def validar_release(r):
    if not isinstance(r,dict) or r.get('draft') or r.get('prerelease'):
        raise ValueError('Distribuição inválida.')
    tag=r.get('tag_name','')
    versao(tag)
    if tag!='v'+tag.lstrip('v') or r.get('html_url')!=REPOSITORIO+'/releases/tag/'+tag:
        raise ValueError('Origem da versão inválida.')
    assets=r.get('assets')
    if not isinstance(assets,list):
        raise ValueError('Distribuição sem arquivos válidos.')
    encontrados={}
    for nome in [INSTALADOR,'SHA256SUMS.txt']:
        permitidos=NOMES_INSTALADOR if nome==INSTALADOR else {nome}
        lista=[a for a in assets if isinstance(a,dict) and a.get('name') in permitidos]
        if len(lista)!=1:
            raise ValueError('A versão ainda não contém instalador e manifesto de integridade.')
        a=lista[0]
        limite=LIMITE if nome==INSTALADOR else 16384
        if type(a.get('size')) is not int or not 0<a['size']<=limite:
            raise ValueError('Tamanho do arquivo inválido.')
        encontrados[nome]={'url':_url_arquivo(a.get('browser_download_url'),tag,a['name']),'size':a['size']}
    return {'versao':tag[1:],'url':r['html_url'],'arquivos':encontrados,'nova':versao(tag)>versao(atual())}


def consultar(progresso=lambda *_:None):
    progresso('Consultando a distribuição pública no GitHub…')
    try:
        with requests.get(API,headers={'Accept':'application/vnd.github+json'},timeout=(5,10),stream=True,allow_redirects=False) as r:
            if r.status_code==404:
                resultado={'mensagem':'Ainda não há distribuição publicada.'}
            else:
                r.raise_for_status()
                dados=bytearray()
                for bloco in r.iter_content(65536):
                    dados.extend(bloco)
                    if len(dados)>1024*1024:
                        raise ValueError('Resposta de atualização acima do limite.')
                resultado=validar_release(json.loads(dados))
                resultado['mensagem']='Nova versão disponível.' if resultado['nova'] else 'Você está usando a versão mais recente disponível.'
        with _lock:
            _estado.clear();_estado.update(resultado)
        with get_conn() as c:
            c.execute('UPDATE atualizacoes SET ultima_consulta=? WHERE id=1',(time.time(),))
        progresso(resultado['mensagem'])
    except (requests.RequestException, json.JSONDecodeError):
        raise ValueError('Não foi possível consultar o GitHub. Confira a internet e tente novamente.') from None


def assinatura(caminho):
    try:
        pin=json.loads((_raiz/'packaging/assinatura.json').read_text(encoding='utf-8')).get('thumbprint','')
        if not re.fullmatch(r'[A-Fa-f0-9]{40}',pin or '') or os.name!='nt':
            return False
        # Caminho segue como argumento, sem interpolação em código PowerShell.
        opcoes={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        script=_raiz/'packaging/verificar_assinatura.ps1'
        r=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',str(script),'-Arquivo',str(caminho),'-Thumbprint',pin],capture_output=True,timeout=30,**opcoes)
        return r.returncode==0 and r.stdout.strip()==b'VALIDA'
    except (OSError,ValueError,subprocess.SubprocessError):
        return False


def _hash(caminho):
    with Path(caminho).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def baixar(senha,progresso=lambda *_:None):
    global _baixado
    backups._chave(senha,b'0'*16)
    with _lock:
        release=json.loads(json.dumps(_estado))
    if not release.get('nova') or 'arquivos' not in release:
        raise ValueError('Consulte uma nova versão antes de baixar.')
    pasta=Path(config.DATABASE_PATH).resolve().parent/'atualizacoes'
    pasta.mkdir(exist_ok=True)
    destino=pasta/('Instalar-DeliveryBot-'+release['versao']+'.exe')
    tmp=destino.with_suffix('.download')
    try:
        progresso('Conferindo manifesto de integridade…')
        manifest=bytearray()
        with _abrir(release['arquivos']['SHA256SUMS.txt']['url']) as r:
            for bloco in r.iter_content(4096):
                manifest.extend(bloco)
                if len(manifest)>16384:
                    raise ValueError('Manifesto acima do limite.')
        linhas=manifest.decode('utf-8').splitlines()
        hashes=[m.group(1).lower() for linha in linhas if (m:=re.fullmatch(r'([a-fA-F0-9]{64})  \*?Instalar(?:-|\.| )DeliveryBot\.exe',linha))]
        if len(hashes)!=1:
            raise ValueError('Manifesto sem hash único do instalador.')
        total=0;inicio=time.monotonic()
        with _abrir(release['arquivos'][INSTALADOR]['url']) as r, tmp.open('wb') as f:
            for bloco in r.iter_content(65536):
                total+=len(bloco)
                if total>LIMITE or time.monotonic()-inicio>600:
                    raise ValueError('O download excedeu os limites permitidos.')
                f.write(bloco)
                progresso('Baixando instalador…',min(99,round(total*100/release['arquivos'][INSTALADOR]['size'])))
        if total!=release['arquivos'][INSTALADOR]['size'] or _hash(tmp)!=hashes[0]:
            raise ValueError('Arquivo incompleto ou alterado. Instalação bloqueada.')
        progresso('Criando e verificando backup antes da atualização…')
        backup=backups.criar(senha)
        backups.verificar_arquivo(backup,senha)
        os.replace(tmp,destino)
        assinado=assinatura(destino)
        with _lock:
            _baixado={'caminho':str(destino),'sha256':hashes[0],'backup':backup,'versao':release['versao'],'assinatura_confiavel':assinado}
        progresso('Download e backup verificados. '+('Pronto para instalar.' if assinado else 'Sem assinatura confiável: instalação automática bloqueada. Use a distribuição manual.'),100)
    except requests.RequestException:
        raise ValueError('Download interrompido. Tente novamente; os dados da loja foram preservados.') from None
    finally:
        tmp.unlink(missing_ok=True)


def instalar():
    with _lock:
        b=dict(_baixado or {})
    if not b or not b['assinatura_confiavel'] or _hash(b['caminho'])!=b['sha256'] or not assinatura(b['caminho']):
        raise ValueError('Instalação automática exige arquivo íntegro e assinatura confiável do editor.')
    if not Path(b['backup']).is_file():
        raise ValueError('Backup anterior não encontrado. Baixe e verifique novamente.')
    subprocess.Popen([b['caminho']],close_fds=True)


def configurar(dados):
    if type(dados.get('automatica')) is not bool:
        raise ValueError('Informe se deseja consultas automáticas.')
    with get_conn() as c:
        c.execute('UPDATE atualizacoes SET automatica=? WHERE id=1',(dados['automatica'],))


def rotina():
    with get_conn() as c:
        r=c.execute('SELECT * FROM atualizacoes WHERE id=1').fetchone()
    if r['automatica'] and time.time()-r['ultima_consulta']>=86400:
        # Registra a tentativa para evitar insistir a cada minuto se estiver offline.
        with get_conn() as c:
            c.execute('UPDATE atualizacoes SET ultima_consulta=? WHERE id=1',(time.time(),))
        try:
            consultar()
        except ValueError:
            pass


def situacao():
    with get_conn() as c:
        r=dict(c.execute('SELECT * FROM atualizacoes WHERE id=1').fetchone())
    with _lock:
        return {**r,'atual':atual(),'release':dict(_estado),'download':dict(_baixado or {})}
