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
        from .protecao_ia import MOTIVOS
        registros=[dict(r) for r in c.execute("SELECT a.*,COALESCE(c.nome,'Cliente') AS nome,b.motivo AS bloqueio_ia,"
            "(SELECT COUNT(*) FROM tarefas_bot t WHERE t.telefone=a.telefone AND t.origem!='HUMANO' AND t.estado IN ('FALHOU','VERIFICAR')) AS envios_para_conferir "
            "FROM atendimentos_humanos a LEFT JOIN clientes c ON c.telefone=a.telefone LEFT JOIN bloqueios_ia b ON b.telefone=a.telefone ORDER BY a.solicitado_em")]
        for r in registros:
            r['motivo_bloqueio']=MOTIVOS.get(r['bloqueio_ia'],'')
        return registros


def conversa(t):
    t=telefone(t)
    with get_conn() as c:
        return [dict(r) for r in reversed(c.execute('SELECT direcao,conteudo,criado_em FROM mensagens WHERE telefone=? ORDER BY id DESC LIMIT 100',(t,)).fetchall())]


def controlar(t,acao):
    t=telefone(t)
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        estava_pausado=bool(c.execute('SELECT 1 FROM atendimentos_humanos WHERE telefone=?',(t,)).fetchone())
        if c.execute("SELECT 1 FROM tarefas_bot WHERE telefone=? AND estado IN ('PROCESSANDO','ENVIANDO')",(t,)).fetchone():
            raise ValueError('Aguarde o envio em andamento antes de mudar o atendimento.')
        if acao=='assumir':
            c.execute("INSERT INTO atendimentos_humanos(telefone,estado) VALUES(?,'ASSUMIDO') ON CONFLICT(telefone) DO UPDATE SET estado='ASSUMIDO'",(t,))
        elif acao=='retomar':
            if c.execute('SELECT 1 FROM bloqueios_ia WHERE telefone=?',(t,)).fetchone():
                raise ValueError('O responsável precisa revisar e liberar a proteção da IA antes de retomar o bot.')
            if c.execute("SELECT 1 FROM tarefas_bot WHERE telefone=? AND origem='HUMANO' AND estado!='CONCLUIDA'",(t,)).fetchone():
                raise ValueError('Conclua ou resolva os envios manuais antes de retomar o bot.')
            if c.execute("SELECT 1 FROM tarefas_bot WHERE telefone=? AND estado IN ('FALHOU','VERIFICAR')",(t,)).fetchone():
                raise ValueError('Confira os envios automáticos pendentes em WhatsApp e IA antes de retomar o bot.')
            c.execute('DELETE FROM atendimentos_humanos WHERE telefone=?',(t,))
        else:
            raise ValueError('Ação de atendimento inválida.')
        # Preserve entradas ainda na fila para a equipe, sem reproduzi-las na IA
        # quando o atendimento for retomado. Envios incertos exigem conferência.
        if acao=='retomar' and not estava_pausado:
            return
        from . import processamento, protecao_ia
        pendentes=c.execute("SELECT id,texto,entrada_registrada FROM tarefas_bot WHERE telefone=? AND origem!='HUMANO' AND estado='PENDENTE' ORDER BY id",(t,)).fetchall()
        for tarefa in pendentes:
            if protecao_ia.privacidade(tarefa['texto']):
                continue
            if not tarefa['entrada_registrada']:
                c.execute("INSERT INTO mensagens(telefone,direcao,conteudo,ia_permitida) VALUES(?,'ENTRADA',?,0)",(t,tarefa['texto']))
            else:
                c.execute("UPDATE mensagens SET ia_permitida=0 WHERE telefone=? AND direcao='ENTRADA' AND conteudo=?",(t,tarefa['texto']))
            processamento._concluir_sem_resposta(c,tarefa['id'],'transferência para atendimento humano')


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
