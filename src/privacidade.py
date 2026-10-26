"""Operações de titular, minimização e retenção, exclusivas do administrador."""
import json
import time
import re
import secrets

from . import config, pedidos
from .db import get_conn
from .estoque import texto


def aviso():
    from .conexoes import url_local
    from .publicacao import situacao
    externa = config.LGPD_IA_EXTERNA == "SIM" and (config.IA_PROVIDER == "ANTHROPIC" or (config.IA_PROVIDER == "OLLAMA" and not url_local(config.OLLAMA_URL)))
    return {"responsavel": config.LGPD_RESPONSAVEL or config.NOME_RESTAURANTE,
            "contato": config.LGPD_CONTATO or config.TELEFONE_RESTAURANTE,
            "mensagens_dias": config.LGPD_MENSAGENS_DIAS,
            "ia_externa": externa,
            "provedor_ia": config.IA_PROVIDER,
            "tunel_cloudflare": situacao()['ativo'],
            "retencao_pedidos": config.LGPD_RETENCAO_PEDIDOS}


def auditar(conn, acao, cliente_id=None):
    conn.execute("INSERT INTO auditoria_privacidade (acao, cliente_id) VALUES (?, ?)", (acao, cliente_id))


def _telefone(dados):
    if dados.get("identidade_confirmada") is not True:
        raise ValueError("Verifique a identidade do solicitante antes de acessar ou modificar seus dados.")
    telefone = re.sub(r"\D", "", texto(dados.get("telefone", ""), "Telefone", 40, True))
    if not 10 <= len(telefone) <= 20:
        raise ValueError("Informe o telefone com DDI e DDD.")
    return telefone


def exportar(dados):
    telefone = _telefone(dados)
    with get_conn() as conn:
        cliente = conn.execute("SELECT id, nome, telefone, cep, endereco, criado_em FROM clientes WHERE telefone=?", (telefone,)).fetchone()
        perfil = dict(cliente) if cliente else None
        ids = [r[0] for r in conn.execute("SELECT id FROM pedidos WHERE cliente_id=?", (perfil["id"],))] if perfil else []
        mensagens = [dict(r) for r in conn.execute("SELECT direcao, conteudo, criado_em FROM mensagens WHERE telefone=? ORDER BY id", (telefone,))]
        fila = [dict(r) for r in conn.execute("SELECT texto, resposta, estado, recebido_em FROM tarefas_bot WHERE telefone=? ORDER BY id", (telefone,))]
        rascunho = conn.execute('SELECT dados, atualizado_em FROM carrinhos_conversa WHERE telefone=? AND pedido_id IS NULL', (telefone,)).fetchone()
        bloqueio=conn.execute('SELECT motivo,criado_em FROM bloqueios_ia WHERE telefone=?',(telefone,)).fetchone()
        auditar(conn, "EXPORTAR", perfil["id"] if perfil else None)
    compras = [pedidos.obter_pedido(i) for i in ids]
    # Um link de pedido é uma credencial de compra: não deve sair no relatório.
    relatorio = {"cliente": perfil, "pedidos": compras, "mensagens": mensagens, "atendimentos": fila, "protecao_ia":dict(bloqueio) if bloqueio else None, "rascunho_pedido":{'dados':json.loads(rascunho['dados']), 'atualizado_em':rascunho['atualizado_em']} if rascunho else None, "aviso": aviso()}
    return json.loads(re.sub(r"(/m/)[A-Za-z0-9_-]+", r"\1[link removido]", json.dumps(relatorio, ensure_ascii=False)))


def corrigir(dados):
    telefone = _telefone(dados)
    nome = texto(dados.get("nome", ""), "Nome", 160, True)
    cep = texto(dados.get("cep", ""), "CEP", 9)
    endereco = texto(dados.get("endereco", ""), "Endereço", 400)
    with get_conn() as conn:
        cliente = conn.execute("SELECT id FROM clientes WHERE telefone=?", (telefone,)).fetchone()
        if not cliente:
            raise ValueError("Cliente não encontrado.")
        conn.execute("UPDATE clientes SET nome=?, cep=?, endereco=? WHERE id=?", (nome, cep, endereco, cliente["id"]))
        auditar(conn, "CORRIGIR", cliente["id"])
    return {"ok": True}


def remover_identificacao(dados):
    telefone = _telefone(dados)
    if dados.get("confirmar_remocao") is not True:
        raise ValueError("Confirme a remoção da identificação do cliente.")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cliente = conn.execute("SELECT id FROM clientes WHERE telefone=?", (telefone,)).fetchone()
        if cliente and conn.execute("SELECT 1 FROM pedidos WHERE cliente_id=? AND status NOT IN ('CANCELADO','ENTREGUE','RETIRADO')", (cliente["id"],)).fetchone():
            raise ValueError("Conclua ou cancele os pedidos em andamento antes de remover a identificação.")
        if conn.execute("SELECT 1 FROM tarefas_bot WHERE telefone=? AND estado IN ('PROCESSANDO','ENVIANDO')", (telefone,)).fetchone():
            raise ValueError("Aguarde o atendimento em processamento antes de remover os dados.")
        for tabela in ("mensagens", "links_pedido", "sessoes_bot", "tarefas_bot", "atendimentos_humanos", "carrinhos_conversa", "bloqueios_ia", "frequencia_ia", "versoes_protecao_ia"):
            conn.execute(f"DELETE FROM {tabela} WHERE telefone=?", (telefone,))
        if cliente:
            conn.execute("UPDATE clientes SET nome='Cliente sem identificação', telefone=?, cep='', endereco='', chat_id=NULL, waha_session=NULL WHERE id=?",
                         ("removido:" + secrets.token_hex(24), cliente["id"]))
            conn.execute("UPDATE itens_pedido SET observacao=NULL WHERE pedido_id IN (SELECT id FROM pedidos WHERE cliente_id=?)", (cliente["id"],))
        auditar(conn, "REMOVER_IDENTIFICACAO", cliente["id"] if cliente else None)
    from . import whatsapp, bot
    whatsapp._chat_id_cache.pop(telefone, None)
    whatsapp._sessao_cache.pop(telefone, None)
    bot._ultima_chamada_ia.pop(telefone, None)
    return {"ok": True, "aviso": "Identificação e conversas removidas do banco atual. Revise backups antigos e dados nos provedores. Os totais e itens dos pedidos foram preservados."}


def limpar_historico():
    dias = config.LGPD_MENSAGENS_DIAS
    if not 1 <= dias <= 365:
        raise ValueError("Configure o prazo de retenção de conversas entre 1 e 365 dias.")
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        # Não remove o histórico de clientes com atendimento pendente ou incerto.
        mensagens = conn.execute("DELETE FROM mensagens WHERE criado_em < datetime('now', ?) AND telefone NOT IN (SELECT telefone FROM tarefas_bot WHERE estado!='CONCLUIDA')", (f"-{dias} days",)).rowcount
        tarefas = conn.execute("UPDATE tarefas_bot SET telefone='', texto='', resposta=NULL, chat_id=NULL, sessao=NULL, erro=NULL WHERE estado='CONCLUIDA' AND telefone!='' AND atualizado_em < datetime('now', ?)", (f"-{dias} days",)).rowcount
        links = conn.execute("DELETE FROM links_pedido WHERE expira_em < datetime('now')").rowcount
        conn.execute("DELETE FROM carrinhos_conversa WHERE atualizado_em <= datetime('now','-30 minutes')")
        conn.execute('DELETE FROM frequencia_ia WHERE inicio<?',(time.time()-60,))
        auditar(conn, "LIMPAR_HISTORICO")
    return {"mensagens": mensagens, "atendimentos": tarefas, "links_expirados": links}


def situacao():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) FROM clientes WHERE telefone NOT LIKE 'removido:%'").fetchone()[0]
        registros = [dict(r) for r in conn.execute("SELECT acao, criado_em FROM auditoria_privacidade ORDER BY id DESC LIMIT 30")]
    return {"clientes": total, "auditoria": registros, "aviso": aviso()}


def reduzir_para_ia(telefone, conteudo):
    from .seguranca import reduzir_dados
    with get_conn() as conn:
        cliente = conn.execute("SELECT nome, cep, endereco FROM clientes WHERE telefone=?", (telefone,)).fetchone()
    resultado = str(conteudo)
    if cliente:
        for campo in ("endereco", "cep", "nome"):
            valor = cliente[campo]
            if valor and len(valor) >= 3 and valor != "Cliente":
                resultado = re.sub(re.escape(valor), "[dado do cliente]", resultado, flags=re.IGNORECASE)
    return reduzir_dados(resultado)
