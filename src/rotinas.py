"""Backups portáteis agendados e retenção, executados somente no Desktop."""
import os
import logging
import shutil
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import backups, seguranca, privacidade
from .db import get_conn
from .estoque import inteiro

_lock = threading.Lock()
_parar = threading.Event()
_thread = None
logger = logging.getLogger(__name__)


def _instante_utc(valor):
    """Datas antigas sem fuso já eram UTC; datas com fuso são normalizadas."""
    if not isinstance(valor, str) or not valor or len(valor) > 64:
        return None
    try:
        instante = datetime.fromisoformat(valor)
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone.utc)
        return instante.astimezone(timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError):
        return None


def _cfg():
    with get_conn() as c:
        return dict(c.execute('SELECT * FROM rotinas WHERE id=1').fetchone())


def situacao():
    r=_cfg()
    r['senha_configurada']=bool(r.pop('senha'))
    r['executando']=_lock.locked()
    ultima = _instante_utc(r['ultima_copia'])
    r['atrasado']=bool(r['backup_ativo'] and (not ultima or ultima < datetime.now(timezone.utc).replace(tzinfo=None)-timedelta(hours=r['horas']*2)))
    return r


def configurar(d):
    r=_cfg()
    for k in ('backup_ativo','limpar'):
        if not isinstance(d.get(k),bool):
            raise ValueError('Informe as opções das rotinas.')
    horas=inteiro(d.get('horas'), 'Intervalo', 1)
    quantidade=inteiro(d.get('quantidade'), 'Cópias', 2)
    if horas>168 or quantidade>90:
        raise ValueError('Use intervalo de 1 a 168 horas e 2 a 90 cópias.')
    pasta=d.get('pasta','').strip()
    if pasta and (not Path(pasta).is_absolute() or len(pasta)>1000):
        raise ValueError('Informe uma pasta absoluta para os backups.')
    senha=d.get('senha','')
    if senha:
        backups._chave(senha,b'0'*16)
        r['senha']=seguranca.proteger_segredo(senha)
    if d['backup_ativo'] and (not r['senha'] or os.name!='nt'):
        raise ValueError('Configure uma senha no Windows para habilitar os backups automáticos.')
    with get_conn() as c:
        c.execute('UPDATE rotinas SET backup_ativo=?,horas=?,quantidade=?,senha=?,pasta=?,limpar=? WHERE id=1',
                  (d['backup_ativo'],horas,quantidade,r['senha'],pasta,d['limpar']))
    return situacao()


def verificar_arquivo(arquivo,senha):
    backups.verificar_arquivo(arquivo,senha)


def executar(forcar=False):
    if not _lock.acquire(blocking=False):
        return False
    try:
        r=_cfg()
        agora=datetime.now(timezone.utc).replace(tzinfo=None)
        ultima_copia = _instante_utc(r['ultima_copia'])
        ultima_limpeza = _instante_utc(r['ultima_limpeza']) if r['limpar'] else None
        if r['backup_ativo'] and (forcar or not ultima_copia or agora-ultima_copia>=timedelta(hours=r['horas'])):
            senha=seguranca.revelar_segredo(r['senha'])
            origem=Path(backups.criar(senha))
            verificar_arquivo(origem,senha)
            pasta=Path(r['pasta']) if r['pasta'] else origem.parent
            pasta.mkdir(parents=True,exist_ok=True)
            destino=pasta/('automatico-'+origem.name)
            if origem.parent.resolve()==pasta.resolve():
                os.replace(origem,destino)
            else:
                temp=destino.with_suffix('.novo')
                try:
                    shutil.copyfile(origem,temp)
                    # Valide os bytes no destino antes de publicar a cópia ou
                    # descartar a origem: discos externos/redes podem falhar.
                    with temp.open('rb+') as arquivo:
                        arquivo.flush()
                        os.fsync(arquivo.fileno())
                    verificar_arquivo(temp,senha)
                    os.replace(temp,destino)
                    origem.unlink()
                finally:
                    temp.unlink(missing_ok=True)
            with get_conn() as c:
                c.execute('UPDATE rotinas SET ultima_copia=?,erro=NULL WHERE id=1',(agora.isoformat(),))
            # Apenas arquivos criados pela rotina; preserva backups manuais e antigos.
            copias=sorted(pasta.glob('automatico-DeliveryBot-*.dbot'),key=lambda p:p.stat().st_mtime,reverse=True)
            for antigo in copias[r['quantidade']:]:
                if not antigo.is_symlink():
                    antigo.unlink()
        if r['limpar'] and (forcar or not ultima_limpeza or agora-ultima_limpeza>=timedelta(days=1)):
            privacidade.limpar_historico()
            with get_conn() as c:
                c.execute('UPDATE rotinas SET ultima_limpeza=? WHERE id=1',(agora.isoformat(),))
        return True
    except Exception:
        with get_conn() as c:
            c.execute("UPDATE rotinas SET erro='A rotina falhou. Confira a senha, a pasta, o espaço disponível e as permissões.' WHERE id=1")
        return False
    finally:
        _lock.release()


def iniciar():
    global _thread
    if _thread and _thread.is_alive():
        return
    _parar.clear()
    def rotina():
        while not _parar.is_set():
            try:
                executar()
            except Exception:
                # Nem a indisponibilidade do banco ao registrar uma falha deve
                # matar o agendador. Não exponha dados do erro de terceiros.
                logger.warning('Rotina de proteção indisponível; nova tentativa no próximo ciclo.')
            try:
                from . import atualizacoes
                atualizacoes.rotina()
            except Exception:
                logger.warning('Consulta de atualização indisponível; rotinas de proteção mantidas.')
            _parar.wait(60)
    _thread=threading.Thread(target=rotina,name='Rotinas-DeliveryBot',daemon=True)
    _thread.start()


def encerrar():
    _parar.set()
    if _thread:
        _thread.join(timeout=10)
