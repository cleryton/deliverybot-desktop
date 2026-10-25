"""Fila persistente: webhooks rápidos, mensagens duplicadas sem repetir IA/envio."""
import logging
import hashlib
import threading
import time
import uuid
import unicodedata

from . import bot, whatsapp, config
from .db import get_conn
from .links import PaginaIndisponivel

logger = logging.getLogger(__name__)
_parar = threading.Event()
_acordar = threading.Event()
_threads = []
_status_lock = threading.Lock()
_status_ate = 0
_pronto = False
_ERRO_HTTPS = 'Aguardando a reconexão da página HTTPS.'


def _mensagem_ruido(texto):
    """Ignora reações sem texto e repetições claramente acidentais."""
    normalizada = unicodedata.normalize("NFKC", texto or "").strip()
    if not any(caractere.isalnum() for caractere in normalizada):
        return normalizada not in {"?", "??", "???"}
    compacta = "".join(normalizada.split()).casefold()
    return compacta.isalpha() and len(compacta) >= 8 and len(set(compacta)) == 1


def _concluir_sem_resposta(conn, tarefa_id, motivo):
    # Não coloca ruído no histórico do cliente e apaga o conteúdo sem utilidade.
    conn.execute(
        "UPDATE tarefas_bot SET estado='CONCLUIDA', telefone='', texto='', resposta=NULL, "
        "chat_id=NULL, sessao=NULL, erro=NULL, atualizado_em=datetime('now') WHERE id=?",
        (tarefa_id,),
    )
    logger.info("Mensagem ignorada automaticamente (tarefa=%s, motivo=%s)", tarefa_id, motivo)


def ativo():
    """Indica se os consumidores da fila estão ativos neste processo."""
    return bool(_threads) and all(thread.is_alive() for thread in _threads)


def invalidar_conexao():
    global _status_ate
    with _status_lock:
        _status_ate = 0
    _acordar.set()


def _servico_pronto():
    if config.WHATSAPP_PROVIDER=='META':
        return bool(config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID)
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
    origem = ({'LOCAL':'LOCAL:','META':'META:'}.get(config.WHATSAPP_PROVIDER,'WAHA:')) + (dados.get("session") or "default")
    chave = "sha256:" + hashlib.sha256(str(chave or uuid.uuid4()).encode()).hexdigest()
    from . import protecao_ia
    with protecao_ia.trava(dados['telefone']),get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "INSERT OR IGNORE INTO tarefas_bot (origem, chave, telefone, texto, chat_id, sessao) VALUES (?, ?, ?, ?, ?, ?)",
            (origem, chave, dados["telefone"], dados["texto"], dados.get("chat_id"), dados.get("session")),
        )
        tarefa = dict(conn.execute("SELECT id, estado FROM tarefas_bot WHERE origem=? AND chave=?", (origem, chave)).fetchone())
        tarefa["duplicada"] = cur.rowcount == 0
        protegida = not tarefa['duplicada'] and protecao_ia.avaliar(conn,dados['telefone'],dados['texto'],contar=True)
        humana = (not protecao_ia.privacidade(dados['texto']) and conn.execute(
            'SELECT 1 FROM atendimentos_humanos WHERE telefone=?', (dados['telefone'],)
        ).fetchone())
        if not tarefa['duplicada'] and (protegida or humana):
            conn.execute("INSERT INTO mensagens(telefone,direcao,conteudo,ia_permitida) VALUES(?,'ENTRADA',?,0)",(dados['telefone'],dados['texto']))
            _concluir_sem_resposta(conn,tarefa['id'],'proteção ou atendimento humano')
            tarefa['estado']='CONCLUIDA'
    _acordar.set()
    return tarefa


def recuperar_interrompidas():
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='PENDENTE', atualizado_em=datetime('now') WHERE estado='PROCESSANDO'")
        # O envio pode ter sido aceito pelo WhatsApp antes de um encerramento inesperado.
        conn.execute("UPDATE tarefas_bot SET estado='VERIFICAR', erro='Confira se a resposta já chegou ao cliente antes de reenviar.' WHERE estado='ENVIANDO'")


def processar_proxima():
    if config.WHATSAPP_PROVIDER not in {"WAHA", "LOCAL", "META"} or config.MODO_TESTE:
        return False
    if not _servico_pronto():
        return False
    from .publicacao import endereco
    aguardando_https = not bool(endereco())
    ordem = 'CASE WHEN t.erro=? THEN 1 ELSE 0 END, id' if aguardando_https else 'id'
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        idade_maxima = max(60, int(config.BOT_FILA_MAX_IDADE_SEGUNDOS))
        vencidas = conn.execute(
            "SELECT id FROM tarefas_bot WHERE estado='PENDENTE' AND origem!='HUMANO' "
            "AND recebido_em < datetime('now', ?)",
            (f"-{idade_maxima} seconds",),
        ).fetchall()
        for vencida in vencidas:
            _concluir_sem_resposta(conn, vencida["id"], "fila expirada")
        row = conn.execute(
            "SELECT * FROM tarefas_bot t WHERE estado='PENDENTE' AND NOT EXISTS "
            "(SELECT 1 FROM tarefas_bot ativas WHERE ativas.telefone=t.telefone AND ativas.estado IN ('PROCESSANDO','ENVIANDO')) "
            "AND NOT EXISTS (SELECT 1 FROM tarefas_bot anteriores WHERE anteriores.telefone=t.telefone "
            "AND anteriores.id<t.id AND anteriores.estado IN ('PENDENTE','FALHOU','VERIFICAR') "
            "AND (t.origem!='HUMANO' OR anteriores.origem='HUMANO')) "
            # Enquanto o HTTPS estiver fora, atenda outras conversas prontas.
            # Ao voltar, a ordem original é retomada, sem atrasar pedidos antigos.
            f"ORDER BY {ordem} LIMIT 1",
            (_ERRO_HTTPS,) if aguardando_https else (),
        ).fetchone()
        if row is None:
            return False
        tarefa = dict(row)
        from . import protecao_ia
        geracao=protecao_ia.versao(tarefa['telefone'],conn)
        if tarefa["origem"] != "HUMANO" and _mensagem_ruido(tarefa["texto"]):
            _concluir_sem_resposta(conn, tarefa["id"], "sem conteúdo textual útil")
            return True
        # O histórico da IA inclui somente entradas que chegaram à sua vez.
        # Entradas futuras já estão preservadas na fila, mas não antecipam a conversa.
        if not tarefa["entrada_registrada"]:
            conn.execute("INSERT INTO mensagens (telefone, direcao, conteudo) VALUES (?, 'ENTRADA', ?)", (tarefa["telefone"], tarefa["texto"]))
            conn.execute("UPDATE tarefas_bot SET entrada_registrada=1 WHERE id=?", (tarefa["id"],))
        conn.execute("UPDATE tarefas_bot SET estado='PROCESSANDO', tentativas=tentativas+1, atualizado_em=datetime('now') WHERE id=?", (tarefa["id"],))
    try:
        # Uma resposta automática preparada antes da pausa não pode atravessar
        # um atendimento humano ao ser reenviada após uma falha.
        from . import humano
        from . import protecao_ia
        if tarefa['origem']!='HUMANO' and protecao_ia.verificar(tarefa['telefone'],tarefa['texto']):
            with get_conn() as conn:
                conn.execute("UPDATE mensagens SET ia_permitida=0 WHERE telefone=? AND direcao='ENTRADA' AND conteudo=?",(tarefa['telefone'],tarefa['texto']))
                _concluir_sem_resposta(conn,tarefa['id'],'proteção do atendimento')
            return True
        if tarefa['origem']!='HUMANO' and tarefa['resposta'] is not None and humano.pausado(tarefa['telefone']):
            with get_conn() as conn:
                conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA', atualizado_em=datetime('now') WHERE id=?",(tarefa['id'],))
            return True
        resposta = tarefa["resposta"]
        if resposta is None:
            resposta = bot.processar_mensagem(tarefa["telefone"], tarefa["texto"])
            if resposta is None:
                with get_conn() as conn:
                    conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA', atualizado_em=datetime('now') WHERE id=?", (tarefa['id'],))
                return True
            with get_conn() as conn:
                conn.execute("UPDATE tarefas_bot SET resposta=? WHERE id=?", (resposta, tarefa["id"]))
        if _parar.is_set():
            with get_conn() as conn:
                conn.execute("UPDATE tarefas_bot SET estado='PENDENTE' WHERE id=?", (tarefa["id"],))
            return True
        # Um aviso preparado enquanto o HTTPS reconectava não deve ser enviado
        # como resposta definitiva quando o cliente pediu o acesso à compra.
        # Também recupera avisos já persistidos por versões anteriores.
        if tarefa['origem'] != 'HUMANO':
            from . import ia
            if resposta.startswith(ia.PEDIDO_INDISPONIVEL):
                historico = ia._historico_mensagens(tarefa['telefone'])
                if tarefa['texto'].strip() == '2' or ia.intencao_pedido(tarefa['texto'], historico):
                    from .links import gerar_link_pedido
                    resposta = (ia.resposta_link(gerar_link_pedido(tarefa['telefone']), historico)
                                + resposta[len(ia.PEDIDO_INDISPONIVEL):])
        from .links import atualizar_resposta
        humano_externo = tarefa['origem'] == 'HUMANO'
        try:
            resposta = atualizar_resposta(resposta, tarefa['telefone'], permitir_externos=humano_externo)
        except PaginaIndisponivel:
            raise
        except ValueError:
            if humano_externo:
                raise
            # Respostas automáticas antigas também passam pela correção, sem
            # pedir outra inferência nem reaproveitar um endereço inventado.
            from . import ia
            from .links import gerar_link_pedido
            historico = ia._historico_mensagens(tarefa['telefone'])
            resposta = (ia.resposta_link(gerar_link_pedido(tarefa['telefone']), historico)
                        if ia.intencao_pedido(tarefa['texto'], historico) else ia.PEDIDO_INDISPONIVEL)
            resposta = atualizar_resposta(resposta, tarefa['telefone'])
        with protecao_ia.trava(tarefa['telefone']):
            if not humano_externo and not protecao_ia.privacidade(tarefa['texto']):
                protecao_ia.validar_saida(tarefa['telefone'],resposta,geracao)
            with get_conn() as conn:
                conn.execute('BEGIN IMMEDIATE')
                atual=conn.execute('SELECT estado FROM tarefas_bot WHERE id=?',(tarefa['id'],)).fetchone()
                if not atual or atual['estado']!='PROCESSANDO':
                    raise protecao_ia.ConversaBloqueada()
                conn.execute("UPDATE tarefas_bot SET resposta=?, estado='ENVIANDO', atualizado_em=datetime('now') WHERE id=?", (resposta, tarefa['id']))
            whatsapp.enviar_mensagem(tarefa["telefone"], resposta, chat_id=tarefa["chat_id"], session=tarefa["sessao"], permitir_externos=humano_externo)
        with get_conn() as conn:
            conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA', erro=NULL, atualizado_em=datetime('now') WHERE id=?", (tarefa["id"],))
            conn.execute("INSERT INTO mensagens (telefone, direcao, conteudo) VALUES (?, 'SAIDA', ?)", (tarefa["telefone"], resposta))
    except protecao_ia.ConversaBloqueada:
        with get_conn() as conn:
            _concluir_sem_resposta(conn,tarefa['id'],'proteção antes do envio')
    except PaginaIndisponivel:
        # Falha na validação anterior ao transporte: nenhum envio foi iniciado.
        # Mantém a resposta pronta e o token para retomar sem chamar a IA outra vez.
        with get_conn() as conn:
            conn.execute("UPDATE tarefas_bot SET estado='PENDENTE', erro=?, atualizado_em=datetime('now') WHERE id=?", (_ERRO_HTTPS, tarefa['id']))
        return False
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
        aguardando_https = conn.execute("SELECT COUNT(*) FROM tarefas_bot WHERE estado='PENDENTE' AND erro=?", (_ERRO_HTTPS,)).fetchone()[0]
        falhas = [dict(r) for r in conn.execute("SELECT id, telefone, erro, estado, recebido_em FROM tarefas_bot WHERE estado IN ('FALHOU','VERIFICAR') ORDER BY id DESC LIMIT 20")]
    return {"ultima_mensagem": ultima, "pendentes": pendentes, "aguardando_https": aguardando_https, "falhas": falhas}


def reenviar(tarefa_id):
    with get_conn() as conn:
        cur = conn.execute("UPDATE tarefas_bot SET estado='PENDENTE', erro=NULL, recebido_em=datetime('now'), atualizado_em=datetime('now') WHERE id=? AND estado IN ('FALHOU','VERIFICAR')", (tarefa_id,))
        if not cur.rowcount:
            raise ValueError("Esta mensagem não está aguardando uma nova tentativa.")
    _acordar.set()


def ignorar(tarefa_id):
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='CONCLUIDA', atualizado_em=datetime('now') WHERE id=? AND estado IN ('FALHOU','VERIFICAR')", (tarefa_id,))
    _acordar.set()
