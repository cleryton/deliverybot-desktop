"""Pausa por conversa e resposta manual pela fila persistente."""
import re
import secrets
from .db import get_conn
from .estoque import texto


def telefone(valor):
    t=re.sub(r'\D','',texto(valor,'Telefone',40,True))
    if not 10<=len(t)<=20:
        raise ValueError('Informe o telefone completo do cliente.')
    return t


def pausado(t):
    with get_conn() as c:
        return bool(c.execute('SELECT 1 FROM atendimentos_humanos WHERE telefone=?',(t,)).fetchone())


def solicitar(t):
    with get_conn() as c:
        c.execute("INSERT OR IGNORE INTO atendimentos_humanos(telefone,estado) VALUES(?,'AGUARDANDO')",(t,))


def listar():
    with get_conn() as c:
        return [dict(r) for r in c.execute("SELECT a.*,COALESCE(c.nome,'Cliente') AS nome FROM atendimentos_humanos a LEFT JOIN clientes c ON c.telefone=a.telefone ORDER BY a.solicitado_em")]


def conversa(t):
    t=telefone(t)
    with get_conn() as c:
        return [dict(r) for r in reversed(c.execute('SELECT direcao,conteudo,criado_em FROM mensagens WHERE telefone=? ORDER BY id DESC LIMIT 100',(t,)).fetchall())]


def controlar(t,acao):
    t=telefone(t)
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute("SELECT 1 FROM tarefas_bot WHERE telefone=? AND estado IN ('PROCESSANDO','ENVIANDO')",(t,)).fetchone():
            raise ValueError('Aguarde o envio em andamento antes de mudar o atendimento.')
        if acao=='assumir':
            c.execute("INSERT INTO atendimentos_humanos(telefone,estado) VALUES(?,'ASSUMIDO') ON CONFLICT(telefone) DO UPDATE SET estado='ASSUMIDO'",(t,))
        elif acao=='retomar':
            if c.execute("SELECT 1 FROM tarefas_bot WHERE telefone=? AND origem='HUMANO' AND estado!='CONCLUIDA'",(t,)).fetchone():
                raise ValueError('Conclua ou resolva os envios manuais antes de retomar o bot.')
            c.execute('DELETE FROM atendimentos_humanos WHERE telefone=?',(t,))
        else:
            raise ValueError('Ação de atendimento inválida.')


def responder(d):
    t=telefone(d.get('telefone',''))
    msg=texto(d.get('mensagem',''),'Mensagem',8000,True)
    if d.get('confirmar_envio') is not True:
        raise ValueError('Confirme o envio da mensagem ao cliente.')
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        if not c.execute("SELECT 1 FROM atendimentos_humanos WHERE telefone=? AND estado='ASSUMIDO'",(t,)).fetchone():
            raise ValueError('Assuma a conversa antes de responder.')
        cur=c.execute("INSERT INTO tarefas_bot(origem,chave,telefone,texto,resposta,entrada_registrada) VALUES('HUMANO',?,?, '',?,1)",(secrets.token_hex(32),t,msg))
    from . import processamento
    processamento._acordar.set()
    return {'ok':True,'tarefa_id':cur.lastrowid,'aviso':'Resposta registrada na fila. Confira o envio no painel WhatsApp e IA.'}
