"""Fila persistente: webhooks rápidos, mensagens duplicadas sem repetir IA/envio."""
import logging
import hashlib
import threading
import time
import uuid

from . import bot, whatsapp, config
from .db import get_conn

logger = logging.getLogger(__name__)
_parar = threading.Event()
_acordar = threading.Event()
_threads = []
_status_lock = threading.Lock()
_status_ate = 0
_pronto = False


def invalidar_conexao():
    global _status_ate
    with _status_lock:
        _status_ate = 0
    _acordar.set()


def _servico_pronto():
    global _status_ate, _pronto
    with _status_lock:
        if time.monotonic() >= _status_ate:
            from .conexoes import status_whatsapp
            _pronto = status_whatsapp()["conectado"]
            _status_ate = time.monotonic() + 3
        return _pronto


def enfileirar(dados, chave=None):
    # WhatsApp pode fornecer um LID numérico quando o número alternativo não está disponível.
    if not isinstance(dados.get("telefone"), str) or not dados["telefone"].isascii() or not dados["telefone"].isdigit() or not 10 <= len(dados["telefone"]) <= 20:
        raise ValueError("Telefone de atendimento inválido.")
    if not isinstance(dados.get("texto"), str) or not 1 <= len(dados["texto"]) <= 8000:
        raise ValueError("Mensagem de atendimento inválida.")
    origem = ("LOCAL:" if config.WHATSAPP_PROVIDER == "LOCAL" else "WAHA:") + (dados.get("session") or "default")
    chave = "sha256:" + hashlib.sha256(str(chave or uuid.uuid4()).encode()).hexdigest()
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "INSERT OR IGNORE INTO tarefas_bot (origem, chave, telefone, texto, chat_id, sessao) VALUES (?, ?, ?, ?, ?, ?)",
            (origem, chave, dados["telefone"], dados["texto"], dados.get("chat_id"), dados.get("session")),
        )
        tarefa = dict(conn.execute("SELECT id, estado FROM tarefas_bot WHERE origem=? AND chave=?", (origem, chave)).fetchone())
        tarefa["duplicada"] = cur.rowcount == 0
    _acordar.set()
    return tarefa


def recuperar_interrompidas():
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='PENDENTE', atualizado_em=datetime('now') WHERE estado='PROCESSANDO'")
        # O envio pode ter sido aceito pelo WhatsApp antes de um encerramento inesperado.
        conn.execute("UPDATE tarefas_bot SET estado='VERIFICAR', erro='Confira se a resposta já chegou ao cliente antes de reenviar.' WHERE estado='ENVIANDO'")


def processar_proxima():
    if config.WHATSAPP_PROVIDER not in {"WAHA", "LOCAL"} or config.MODO_TESTE:
        return False
    if not _servico_pronto():
        return False
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM tarefas_bot t WHERE estado='PENDENTE' AND NOT EXISTS "
            "(SELECT 1 FROM tarefas_bot ativas WHERE ativas.telefone=t.telefone AND ativas.estado IN ('PROCESSANDO','ENVIANDO')) "
            "AND NOT EXISTS (SELECT 1 FROM tarefas_bot anteriores WHERE anteriores.telefone=t.telefone "
            "AND anteriores.id<t.id AND anteriores.estado IN ('PENDENTE','FALHOU','VERIFICAR')) ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None:
            return False
        tarefa = dict(row)
        # O histórico da IA inclui somente entradas que chegaram à sua vez.
        # Entradas futuras já estão preservadas na fila, mas não antecipam a conversa.
        if not tarefa["entrada_registrada"]:
            conn.execute("INSERT INTO mensagens (telefone, direcao, conteudo) VALUES (?, 'ENTRADA', ?)", (tarefa["telefone"], tarefa["texto"]))
            conn.execute("UPDATE tarefas_bot SET entrada_registrada=1 WHERE id=?", (tarefa["id"],))
        conn.execute("UPDATE tarefas_bot SET estado='PROCESSANDO', tentativas=tentativas+1, atualizado_em=datetime('now') WHERE id=?", (tarefa["id"],))
    try:
        resposta = tarefa["resposta"]
        if resposta is None:
            resposta = bot.processar_mensagem(tarefa["telefone"], tarefa["texto"])
            with get_conn() as conn:
                conn.execute("UPDATE tarefas_bot SET resposta=? WHERE id=?", (resposta, tarefa["id"]))
        if _parar.is_set():
            with get_conn() as conn:
                conn.execute("UPDATE tarefas_bot SET estado='PENDENTE' WHERE id=?", (tarefa["id"],))
            return True
        with get_conn() as conn:
            conn.execute("UPDATE tarefas_bot SET estado='ENVIANDO', atualizado_em=datetime('now') WHERE id=?", (tarefa["id"],))
        whatsapp.enviar_mensagem(tarefa["telefone"], resposta, chat_id=tarefa["chat_id"], session=tarefa["sessao"])
        with get_conn() as conn:
            conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA', erro=NULL, atualizado_em=datetime('now') WHERE id=?", (tarefa["id"],))
            conn.execute("INSERT INTO mensagens (telefone, direcao, conteudo) VALUES (?, 'SAIDA', ?)", (tarefa["telefone"], resposta))
    except Exception:
        logger.exception("Falha na tarefa de atendimento %s", tarefa["id"])
        with get_conn() as conn:
            conn.execute("UPDATE tarefas_bot SET estado='FALHOU', erro='Não foi possível concluir. Confira a conexão e se o cliente recebeu a resposta antes de tentar novamente.', atualizado_em=datetime('now') WHERE id=?", (tarefa["id"],))
    return True


def _executar():
    while not _parar.is_set():
        try:
            if processar_proxima():
                continue
        except Exception:
            logger.exception("Falha ao consultar fila do bot")
        _acordar.wait(3)
        _acordar.clear()


def iniciar():
    if any(t.is_alive() for t in _threads):
        return
    _parar.clear()
    recuperar_interrompidas()
    _threads[:] = [threading.Thread(target=_executar, name=f"Atendimento-{i}", daemon=True) for i in range(2)]
    for t in _threads:
        t.start()


def encerrar():
    _parar.set()
    _acordar.set()
    for t in _threads:
        t.join(timeout=2)


def situacao():
    with get_conn() as conn:
        ultima = conn.execute("SELECT MAX(recebido_em) FROM tarefas_bot").fetchone()[0]
        pendentes = conn.execute("SELECT COUNT(*) FROM tarefas_bot WHERE estado IN ('PENDENTE','PROCESSANDO','ENVIANDO')").fetchone()[0]
        falhas = [dict(r) for r in conn.execute("SELECT id, telefone, erro, estado, recebido_em FROM tarefas_bot WHERE estado IN ('FALHOU','VERIFICAR') ORDER BY id DESC LIMIT 20")]
    return {"ultima_mensagem": ultima, "pendentes": pendentes, "falhas": falhas}


def reenviar(tarefa_id):
    with get_conn() as conn:
        cur = conn.execute("UPDATE tarefas_bot SET estado='PENDENTE', erro=NULL, atualizado_em=datetime('now') WHERE id=? AND estado IN ('FALHOU','VERIFICAR')", (tarefa_id,))
        if not cur.rowcount:
            raise ValueError("Esta mensagem não está aguardando uma nova tentativa.")
    _acordar.set()


def ignorar(tarefa_id):
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA', atualizado_em=datetime('now') WHERE id=? AND estado IN ('FALHOU','VERIFICAR')", (tarefa_id,))
    _acordar.set()
