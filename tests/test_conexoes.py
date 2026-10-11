"""Serviços simulados: nenhuma conta real, envio ao WhatsApp ou download de modelo."""
import base64
from unittest.mock import Mock

import pytest
import requests

from src import config, conexoes, preferencias, processamento, bot, whatsapp
from src.db import init_db, get_conn


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "loja.db"))
    monkeypatch.setattr(config, "SEED_CATALOGO", False)
    for chave in preferencias.CAMPOS | {"MODO_TESTE", "WHATSAPP_API_URL"}:
        monkeypatch.setattr(config, chave, getattr(config, chave))
    config.WHATSAPP_PROVIDER = "WAHA"
    config.MODO_TESTE = False
    config.WAHA_URL = "http://localhost:3000"
    config.WAHA_WEBHOOK_BASE_URL = ""
    config.BASE_URL = "http://localhost:5000"
    config.WEBHOOK_SECRET = "segredo"
    config.OLLAMA_URL = "http://localhost:11434"
    config.OLLAMA_MODEL = "teste"
    config.IA_PROVIDER = ""
    processamento._parar.clear()
    monkeypatch.setattr(processamento, "_servico_pronto", lambda: True)
    init_db()


def entrada(chave="a", telefone="5547999990000"):
    return processamento.enfileirar({"telefone": telefone, "texto": "oi", "chat_id": telefone+"@lid", "session": "default"}, chave)


def test_deduplicacao_persistente_e_mensagens_iguais_distintas():
    assert not entrada()["duplicada"]
    assert entrada()["duplicada"]
    assert not entrada("b")["duplicada"]
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tarefas_bot").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM mensagens").fetchone()[0] == 0


def test_webhook_confirma_sem_esperar_ia(monkeypatch):
    from src.app import app
    gerar = Mock(side_effect=AssertionError("IA não deve executar na requisição"))
    monkeypatch.setattr(bot, "processar_mensagem", gerar)
    cliente = app.test_client()
    payload = {"event":"message", "session":"default", "payload":{"id":"msg-1", "from":"5547999990000@c.us", "body":"oi"}}
    r = cliente.post("/webhook/waha/segredo", json=payload)
    assert r.status_code == 200 and not r.json["duplicada"]
    assert cliente.post("/webhook/waha/segredo", json=payload).json["duplicada"]
    gerar.assert_not_called()
    assert cliente.post("/webhook/waha/errado", json=payload).status_code == 404


def test_falha_reenvia_resposta_sem_repetir_ia(monkeypatch):
    gerar = Mock(return_value="Resposta pronta")
    enviar = Mock(side_effect=[requests.Timeout(), {"id":"ok"}])
    monkeypatch.setattr(bot, "processar_mensagem", gerar)
    monkeypatch.setattr(whatsapp, "enviar_mensagem", enviar)
    tarefa = entrada()
    assert processamento.processar_proxima()
    assert processamento.situacao()["falhas"][0]["estado"] == "FALHOU"
    processamento.reenviar(tarefa["id"])
    assert processamento.processar_proxima()
    gerar.assert_called_once()
    assert enviar.call_count == 2
    assert enviar.call_args.kwargs == {"chat_id":"5547999990000@lid", "session":"default"}
    assert processamento.situacao()["falhas"] == []


def test_falha_bloqueia_apenas_conversa_afetada(monkeypatch):
    entrada("a"); entrada("b"); entrada("c", "5511999990000")
    monkeypatch.setattr(bot, "processar_mensagem", Mock(return_value="oi"))
    enviar = Mock(side_effect=[requests.Timeout(), {}])
    monkeypatch.setattr(whatsapp, "enviar_mensagem", enviar)
    assert processamento.processar_proxima()
    assert processamento.processar_proxima()
    assert enviar.call_args.args[0] == "5511999990000"
    assert not processamento.processar_proxima()
    processamento.ignorar(1)
    enviar.side_effect = None
    assert processamento.processar_proxima()


def test_reinicio_nao_reenvia_resultado_incerto():
    entrada()
    entrada("b", "5511999990000")
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET estado='ENVIANDO' WHERE id=1")
        conn.execute("UPDATE tarefas_bot SET estado='PROCESSANDO' WHERE id=2")
    processamento.recuperar_interrompidas()
    assert processamento.situacao()["falhas"][0]["estado"] == "VERIFICAR"
    assert processamento.situacao()["pendentes"] == 1


def test_sem_conexao_mensagem_continua_pendente(monkeypatch):
    entrada()
    monkeypatch.setattr(processamento, "_servico_pronto", lambda: False)
    assert not processamento.processar_proxima()
    assert processamento.situacao()["pendentes"] == 1


def test_ruido_emoji_e_repeticao_nao_chamam_bot(monkeypatch):
    assert not processamento._mensagem_ruido("?")
    assert not processamento._mensagem_ruido("4")
    ruido = processamento.enfileirar({"telefone":"5547999990000", "texto":"😂😂😂"}, "emoji")
    repetir = processamento.enfileirar({"telefone":"5547999990001", "texto":"aaaaaaaa"}, "repeticao")
    gerar = Mock(side_effect=AssertionError("mensagens sem conteúdo não devem chamar o bot"))
    monkeypatch.setattr(bot, "processar_mensagem", gerar)
    assert processamento.processar_proxima()
    assert processamento.processar_proxima()
    gerar.assert_not_called()
    with get_conn() as conn:
        for tarefa in (ruido, repetir):
            linha = conn.execute("SELECT estado, telefone, texto FROM tarefas_bot WHERE id=?", (tarefa["id"],)).fetchone()
            assert tuple(linha) == ("CONCLUIDA", "", "")
            assert not conn.execute("SELECT 1 FROM mensagens WHERE telefone=?", ("5547999990000" if tarefa["id"] == ruido["id"] else "5547999990001",)).fetchone()


def test_fila_descarta_mensagem_vencida_e_atende_nova(monkeypatch):
    antiga = entrada("antiga")
    entrada("nova")
    with get_conn() as conn:
        conn.execute("UPDATE tarefas_bot SET recebido_em=datetime('now','-10 minutes') WHERE id=?", (antiga["id"],))
    monkeypatch.setattr(bot, "processar_mensagem", Mock(return_value="Resposta recente"))
    monkeypatch.setattr(whatsapp, "enviar_mensagem", Mock(return_value={}))
    assert processamento.processar_proxima()
    assert whatsapp.enviar_mensagem.call_args.args == ("5547999990000", "Resposta recente")
    with get_conn() as conn:
        assert conn.execute("SELECT estado, telefone, texto FROM tarefas_bot WHERE id=?", (antiga["id"],)).fetchone()[0] == "CONCLUIDA"


def test_ia_nao_recebe_mensagens_futuras_na_fila(monkeypatch):
    from src import ia
    entrada("a")
    processamento.enfileirar({"telefone":"5547999990000", "texto":"segunda mensagem"}, "b")
    historicos = []
    def gerar(telefone, texto):
        historicos.append(ia._historico_mensagens(telefone))
        return "resposta"
    monkeypatch.setattr(bot, "processar_mensagem", gerar)
    monkeypatch.setattr(whatsapp, "enviar_mensagem", Mock(return_value={}))
    processamento.processar_proxima()
    processamento.processar_proxima()
    assert historicos[0] == [{"role":"user", "content":"oi"}]
    assert historicos[1] == [{"role":"user", "content":"oi"}, {"role":"assistant", "content":"resposta"}, {"role":"user", "content":"segunda mensagem"}]


def test_configura_waha_preserva_outros_recursos(monkeypatch):
    original = {"status":"STOPPED", "apps":[{"id":"outro"}], "config":{"custom":7, "ignore":None, "webhooks":[{"url":"https://outro/hook", "events":["message"]}, {"url":"http://antigo/webhook/waha/velho"}]}}
    chamada = Mock(side_effect=[original, {}, {}])
    monkeypatch.setattr(conexoes, "_waha", chamada)
    conexoes.conectar_whatsapp(lambda *args: None)
    dados = chamada.call_args_list[1].args[2]
    assert dados["apps"] == original["apps"]
    assert dados["config"]["custom"] == 7
    assert dados["config"]["webhooks"][0]["url"] == "https://outro/hook"
    assert len(dados["config"]["webhooks"]) == 2
    assert dados["config"]["webhooks"][1]["url"] == "http://host.docker.internal:5000/webhook/waha/segredo"
    assert chamada.call_args_list[2].args[1].endswith("/start")
    assert len(original["config"]["webhooks"]) == 2


def test_cria_sessao_nova_com_webhook(monkeypatch):
    chamada = Mock(side_effect=[None, {}])
    monkeypatch.setattr(conexoes, "_waha", chamada)
    conexoes.conectar_whatsapp(lambda *args: None)
    assert chamada.call_args.args[:2] == ("POST", "/api/sessions")
    assert chamada.call_args.args[2]["start"] is True


def test_inicializacao_integrada_nao_procura_docker(monkeypatch):
    executar = Mock(side_effect=AssertionError("Não deve procurar executáveis externos"))
    monkeypatch.setattr(conexoes, "_executable", executar)
    iniciar = Mock()
    monkeypatch.setattr(conexoes.whatsapp_local, "iniciar", iniciar)
    monkeypatch.setattr(conexoes, "conectar_whatsapp", Mock())
    conexoes.iniciar_whatsapp_local(Mock())
    iniciar.assert_called_once()
    assert config.WHATSAPP_PROVIDER == "LOCAL"
    executar.assert_not_called()


def test_waha_remoto_precisa_callback_acessivel():
    config.WAHA_URL = "https://waha.example"
    with pytest.raises(ValueError, match="remoto"):
        conexoes.url_webhook()
    config.WAHA_WEBHOOK_BASE_URL = "https://loja.example"
    assert conexoes.url_webhook().startswith("https://loja.example/webhook/waha/")


def test_qr_valida_formato_e_nao_expoe_outros_dados(monkeypatch):
    monkeypatch.setattr(conexoes, "_waha", lambda *args: {"mimetype":"image/png", "data":base64.b64encode(b'\x89PNG\r\n\x1a\nabc').decode()})
    assert conexoes.qr_whatsapp()["imagem"].startswith("data:image/png;base64,")
    monkeypatch.setattr(conexoes, "_waha", lambda *args: {"mimetype":"text/html", "data":"html"})
    with pytest.raises(ValueError):
        conexoes.qr_whatsapp()


def test_ollama_existente_reutiliza_e_ativa_so_apos_aquecer(monkeypatch):
    monkeypatch.setattr(conexoes, "_tags", lambda url: ["teste:latest"])
    processo = Mock(side_effect=AssertionError("Serviço já disponível"))
    monkeypatch.setattr(conexoes.subprocess, "Popen", processo)
    resposta = Mock(); resposta.json.return_value = {"done":True}
    sessao = Mock(); sessao.post.return_value = resposta
    monkeypatch.setattr(conexoes, "http", lambda: sessao)
    conexoes.iniciar_ollama(lambda *args: None)
    assert config.IA_PROVIDER == "OLLAMA"
    assert sessao.post.call_args.kwargs["json"]["prompt"] == ""
    processo.assert_not_called()


def test_ollama_sem_modelo_nao_ativa_ia(monkeypatch):
    monkeypatch.setattr(conexoes, "_tags", lambda url: [])
    progresso = Mock()
    conexoes.iniciar_ollama(progresso)
    assert config.IA_PROVIDER == ""
    assert "Baixar modelo" in progresso.call_args.args[0]


def test_download_interrompido_nao_ativa_ia(monkeypatch):
    monkeypatch.setattr(conexoes, "_tags", lambda url: [])
    resposta = Mock(); resposta.iter_lines.return_value = [b'{"status":"pulling","total":100,"completed":25}']
    resposta.__enter__ = Mock(return_value=resposta); resposta.__exit__ = Mock(return_value=False)
    sessao = Mock(); sessao.post.return_value = resposta
    monkeypatch.setattr(conexoes, "http", lambda: sessao)
    with pytest.raises(ValueError, match="não foi concluído"):
        conexoes.baixar_modelo(Mock())
    assert config.IA_PROVIDER == ""


def test_inicia_ollama_oculto_sem_terminal(monkeypatch):
    monkeypatch.setattr(conexoes, "_tags", Mock(side_effect=[ValueError("offline"), ["teste"]]))
    monkeypatch.setattr(conexoes, "_executable", lambda nome: "C:/Programas/Ollama/ollama.exe")
    processo = Mock()
    monkeypatch.setattr(conexoes.subprocess, "Popen", processo)
    monkeypatch.setattr(conexoes, "_aquecer_ativar", Mock())
    conexoes.iniciar_ollama(Mock())
    assert processo.call_args.args[0] == ["C:/Programas/Ollama/ollama.exe", "serve"]
    assert processo.call_args.kwargs["env"]["OLLAMA_HOST"] == "localhost:11434"
    assert processo.call_args.kwargs.get("shell", False) is False
    if conexoes.os.name == "nt":
        assert processo.call_args.kwargs["creationflags"] == conexoes.subprocess.CREATE_NO_WINDOW


def test_componente_integrado_autenticacao_qr_e_encerramento(monkeypatch):
    import time
    from src import whatsapp_local
    config.WHATSAPP_PROVIDER = "LOCAL"
    try:
        whatsapp_local.iniciar(teste=True)
        endereco, chave = whatsapp_local.credenciais()
        processo = whatsapp_local._processo
        assert requests.get(endereco+'/health', timeout=5).status_code == 401
        assert conexoes.status_whatsapp()["estado"] == "STOPPED"
        conexoes.conectar_whatsapp(Mock())
        assert config.WHATSAPP_PROVIDER == "LOCAL"
        for _ in range(50):
            if conexoes.status_whatsapp()["estado"] == "SCAN_QR_CODE":
                break
            time.sleep(.05)
        assert conexoes.qr_whatsapp()["imagem"].startswith('data:image/png;base64,')
        conexoes._waha('POST','/test/connect')
        assert conexoes.status_whatsapp()["conectado"]
        assert whatsapp.enviar_mensagem('5547999990000','Teste',chat_id='5547999990000@c.us')["id"] == 'TESTE'
        conexoes.pausar_whatsapp()
        assert conexoes.status_whatsapp()["estado"] == "STOPPED"
    finally:
        whatsapp_local.encerrar()
    assert processo.poll() == 0
    with pytest.raises(ValueError, match="desligada"):
        whatsapp_local.credenciais()


def test_lid_preserva_destino_e_usa_numero_alternativo():
    dados = whatsapp.extrair_mensagem_recebida_waha({"event":"message", "session":"default", "payload":{"from":"123456789012345@lid","telefone":"5547999990000","body":"Oi"}})
    assert dados["telefone"] == "5547999990000"
    assert dados["chat_id"] == "123456789012345@lid"


def test_modelo_alterado_durante_aquecimento_nao_ativa_ia(monkeypatch):
    resposta = Mock(); resposta.json.return_value = {"done":True}
    sessao = Mock(); sessao.post.return_value = resposta
    monkeypatch.setattr(conexoes, "http", lambda: sessao)
    with pytest.raises(ValueError, match="alterado"):
        conexoes._aquecer_ativar(config.OLLAMA_URL, "outro-modelo", Mock())
    assert config.IA_PROVIDER == ""


def test_api_conexoes_protegida_e_inicio_remoto_bloqueado(monkeypatch):
    from src.app import app
    monkeypatch.setitem(app.config, "DESKTOP_TOKEN", "segredo-local")
    cliente = app.test_client()
    assert cliente.get("/gestao/api/conexoes/qr").status_code == 401
    cliente.get("/gestao?acesso=segredo-local", follow_redirects=True)
    assert cliente.post("/gestao/api/conexoes/ollama-iniciar", json={}).status_code == 403
    with cliente.session_transaction() as s:
        csrf = s["csrf"]
    iniciar = Mock(return_value={"estado":"EXECUTANDO"})
    monkeypatch.setattr(conexoes, "iniciar_tarefa", iniciar)
    assert cliente.post("/gestao/api/conexoes/ollama-iniciar", json={}, headers={"X-CSRF-Token":csrf}).status_code == 202
    assert cliente.post("/gestao/api/conexoes/ollama-iniciar", json={}, headers={"X-CSRF-Token":csrf}, environ_overrides={"REMOTE_ADDR":"10.0.0.2"}).status_code == 401
