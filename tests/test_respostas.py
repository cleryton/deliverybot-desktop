"""Atendimento com dados fictícios, sem Ollama, túnel ou WhatsApp reais."""
from unittest.mock import Mock

import pytest
import requests

from src import bot, cerebro, config, ia, privacidade, publicacao
from src.db import get_conn, init_db


TELEFONE = "5511999990077"


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "respostas.db"))
    monkeypatch.setattr(config, "SEED_CATALOGO", False)
    monkeypatch.setattr(config, "IA_PROVIDER", "OLLAMA")
    monkeypatch.setattr(config, "OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setattr(config, "MODO_TESTE", True)
    monkeypatch.setattr(config, "BASE_URL", "https://loja.example")
    monkeypatch.setattr(config, "NOME_RESTAURANTE", "Loja Exemplo")
    monkeypatch.setattr(config, "HORARIO_FUNCIONAMENTO", "Segunda a sexta, 9h às 18h")
    monkeypatch.setattr(config, "FORMAS_PAGAMENTO", "Pix,Dinheiro")
    monkeypatch.setattr(config, "RATE_LIMIT_SEGUNDOS", 0)
    monkeypatch.setattr(publicacao, "_gerente", None)
    monkeypatch.setattr(cerebro, "instrucoes_contexto", lambda pergunta='': "Tom acolhedor e objetivo.")
    bot._ultima_chamada_ia.clear()
    ia.invalidar_cache_prompt()
    init_db()
    yield
    ia.invalidar_cache_prompt()
    bot._ultima_chamada_ia.clear()


def registrar(direcao, conteudo, telefone=TELEFONE):
    with get_conn() as conn:
        conn.execute("INSERT INTO mensagens (telefone,direcao,conteudo) VALUES (?,?,?)", (telefone, direcao, conteudo))


@pytest.mark.parametrize("texto", ["oi", "bom dia", "qual o horário?", "quanto é a entrega?", "qual o catálogo?", "aceitam Pix?", "obrigado", "2"])
def test_perguntas_objetivas_resolvem_sem_ia(monkeypatch, texto):
    responder = Mock(side_effect=AssertionError("Resposta objetiva não precisa de inferência"))
    monkeypatch.setattr(ia, "responder", responder)
    resposta = bot.processar_mensagem(TELEFONE, texto)
    assert resposta and "1 - " not in resposta
    responder.assert_not_called()


def test_preco_do_produto_vem_do_cadastro(monkeypatch):
    from src import estoque
    estoque.salvar_produto({"nome": "Caderno", "categoria": "Papelaria", "preco": 12.35, "estoque": 5})
    responder = Mock(side_effect=AssertionError("Preço exato vem do cadastro"))
    monkeypatch.setattr(ia, "responder", responder)
    resposta = bot.processar_mensagem(TELEFONE, "quanto custa o caderno?")
    assert "12,35" in resposta and "Caderno" in resposta
    assert "ao confirmar" in resposta
    responder.assert_not_called()


@pytest.mark.parametrize("texto", ["quero fazer um pedido", "quero fazer meu pedido", "quero comprar", "gostaria de comprar um caderno", "manda o link do pedido", "quero 2 cadernos"])
def test_intencao_clara_de_pedido(texto):
    assert ia.intencao_pedido(texto)


@pytest.mark.parametrize("texto", ["oi", "quanto custa um caderno?", "não quero comprar", "quero cancelar meu pedido", "meu pedido chegou?", "sim", "me manda link de privacidade", "manda o link do pagamento", "envia link de rastreamento", "manda o catálogo"])
def test_pergunta_nao_vira_pedido(texto):
    assert not ia.intencao_pedido(texto)


def test_confirmacao_curta_depende_da_ultima_oferta():
    assert ia.intencao_pedido("sim", [{"role": "assistant", "content": "Quer o link pra montar seu pedido?"}])
    assert not ia.intencao_pedido("sim", [{"role": "assistant", "content": "Você prefere retirar na loja?"}])
    assert not ia.intencao_pedido("sim", [{"role": "assistant", "content": "Quer o link pra montar seu pedido?"}, {"role": "assistant", "content": "Você prefere retirar na loja?"}])


def test_confirmacao_contextual_gera_link_sem_modelo(monkeypatch):
    registrar("SAIDA", "Quer o link para montar seu pedido?")
    responder = Mock(side_effect=AssertionError("Consentimento contextual dispensa inferência"))
    monkeypatch.setattr(ia, "responder", responder)
    resposta = bot.processar_mensagem(TELEFONE, "pode sim")
    assert "https://loja.example/m/" in resposta and "confirm" in resposta
    responder.assert_not_called()


def test_pedido_composto_responde_taxa_e_link_sem_ia(monkeypatch):
    responder = Mock(side_effect=AssertionError("Taxa oficial e ação local dispensam inferência"))
    monkeypatch.setattr(ia, "responder", responder)
    resposta = bot.processar_mensagem(TELEFONE, "Quero fazer um pedido, quanto custa a entrega?")
    assert "taxa de entrega" in resposta and "https://loja.example/m/" in resposta
    responder.assert_not_called()


def test_pedido_com_pergunta_especifica_segue_para_ia(monkeypatch):
    responder = Mock(return_value="A equipe precisa confirmar se há entrega nessa região.")
    monkeypatch.setattr(ia, "responder", responder)
    bot.processar_mensagem(TELEFONE, "Quero fazer um pedido, entregam no meu bairro?")
    responder.assert_called_once()


def test_preco_considera_variacao_sem_escolher_produto_ambiguo(monkeypatch):
    from src import estoque
    estoque.salvar_produto({"nome": "Camiseta", "variacao": "Azul", "categoria": "Roupas", "preco": 30, "estoque": 5})
    estoque.salvar_produto({"nome": "Camiseta", "variacao": "Verde", "categoria": "Roupas", "preco": 35, "estoque": 5})
    responder = Mock(return_value="Qual cor você prefere?")
    monkeypatch.setattr(ia, "responder", responder)
    resposta = bot.processar_mensagem(TELEFONE, "Quanto custa a camiseta azul?")
    assert "30,00" in resposta and "Verde" not in resposta
    responder.assert_not_called()
    bot.processar_mensagem(TELEFONE, "Quanto custa a camiseta?")
    responder.assert_called_once()


def test_link_privacidade_nao_cria_link_pedido(monkeypatch):
    gerar = Mock(side_effect=AssertionError("Privacidade não é compra"))
    monkeypatch.setattr(bot, "gerar_link_pedido", gerar)
    resposta = bot.processar_mensagem(TELEFONE, "Me manda o link de privacidade?")
    assert "/privacidade" in resposta and "/m/" not in resposta
    gerar.assert_not_called()


def test_saudacao_em_continuacao_nao_reinicia_apresentacao(monkeypatch):
    registrar("SAIDA", "Oi! Boas-vindas à Loja Exemplo.")
    assert "Boas-vindas" not in bot.processar_mensagem(TELEFONE, "oi")


def test_historico_isola_cliente_e_descarta_conversa_antiga():
    registrar("ENTRADA", "conversa antiga")
    with get_conn() as conn:
        conn.execute("UPDATE mensagens SET criado_em=datetime('now','-2 days')")
    registrar("ENTRADA", "mensagem de outra pessoa", "5511999990088")
    registrar("ENTRADA", "nova conversa")
    assert ia._historico_mensagens(TELEFONE) == [{"role": "user", "content": "nova conversa"}]


def test_entrada_atual_nao_se_perde_em_chamada_direta(monkeypatch):
    monkeypatch.setattr(privacidade, "reduzir_para_ia", lambda telefone, texto: texto)
    registrar("ENTRADA", "primeira dúvida")
    mensagens = ia._mensagens_atualizadas(TELEFONE, "e como retiro?")
    assert mensagens[-1]["content"] == "primeira dúvida\ne como retiro?"


def test_contexto_grande_prioriza_entrada_atual(monkeypatch):
    monkeypatch.setattr(privacidade, "reduzir_para_ia", lambda telefone, texto: texto)
    for i in range(8):
        registrar("ENTRADA" if i % 2 == 0 else "SAIDA", "x" * 3000)
    atual = "Preciso de uma informação nova " + "z" * 7900
    mensagens = ia._mensagens_atualizadas(TELEFONE, atual)
    assert mensagens[-1]["content"] == atual
    assert sum(len(m["content"]) for m in mensagens) <= ia._MAX_CONTEXTO_CARACTERES
    assert mensagens[0]["role"] == "user"


def test_ferramenta_ollama_nao_repete_inferencia_nem_transmite_token(monkeypatch):
    chamada = Mock(return_value={"message": {"role": "assistant", "tool_calls": [{"function": {"name": "gerar_link_pedido"}}, {"function": {"name": "gerar_link_pedido"}}]}})
    gerar = Mock(return_value="https://loja.example/m/tokenprivado")
    monkeypatch.setattr(ia, "_chamar_ollama", chamada)
    monkeypatch.setattr(ia, "gerar_link_pedido", gerar)
    resposta = ia._responder_ollama(TELEFONE, "quero comprar")
    assert "tokenprivado" in resposta and "confirm" in resposta
    assert "tokenprivado" not in str(chamada.call_args_list)
    chamada.assert_called_once()
    gerar.assert_called_once()


def test_ferramenta_sem_intencao_nao_executa(monkeypatch):
    chamada = Mock(return_value={"message": {"tool_calls": [{"function": {"name": "gerar_link_pedido"}}]}})
    gerar = Mock(side_effect=AssertionError("Não há intenção de compra"))
    monkeypatch.setattr(ia, "_chamar_ollama", chamada)
    monkeypatch.setattr(ia, "gerar_link_pedido", gerar)
    with pytest.raises(ia.IAIndisponivel, match="sem intenção"):
        ia._responder_ollama(TELEFONE, "qual o preço?")
    assert chamada.call_args.kwargs["permitir_ferramentas"] is False
    gerar.assert_not_called()


def test_link_offline_nao_anuncia_pedido(monkeypatch):
    monkeypatch.setattr(ia, "_chamar_ollama", Mock(return_value={"message": {"tool_calls": [{"function": {"name": "gerar_link_pedido"}}]}}))
    monkeypatch.setattr(ia, "gerar_link_pedido", Mock(side_effect=ValueError("túnel offline")))
    resposta = ia._responder_ollama(TELEFONE, "quero comprar")
    assert resposta == ia.PEDIDO_INDISPONIVEL
    assert "http" not in resposta and "confirmado" not in resposta


def test_pedido_composto_preserva_explicacao_valida_do_modelo(monkeypatch):
    monkeypatch.setattr(ia, "_chamar_ollama", Mock(return_value={"message": {"content": "A equipe precisa confirmar a cobertura desse bairro.", "tool_calls": [{"function": {"name": "gerar_link_pedido"}}]}}))
    monkeypatch.setattr(ia, "gerar_link_pedido", Mock(return_value="https://loja.example/m/tokenprivado"))
    resposta = ia._responder_ollama(TELEFONE, "quero comprar, entregam no meu bairro?")
    assert "confirmar a cobertura" in resposta and "tokenprivado" in resposta


def test_registro_de_rate_limit_e_limitado_e_atomico(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(config, "RATE_LIMIT_SEGUNDOS", 2)
    for i in range(4096):
        bot._ultima_chamada_ia[str(i)] = 0
    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = list(executor.map(bot._dentro_do_rate_limit, [TELEFONE, TELEFONE]))
    assert sorted(resultados) == [False, True]
    assert len(bot._ultima_chamada_ia) <= 4096


def test_resposta_local_humana_quando_modelo_falha(monkeypatch):
    monkeypatch.setattr(ia, "responder", Mock(side_effect=ia.IAIndisponivel("timeout")))
    resposta = bot.processar_mensagem(TELEFONE, "me explique melhor")
    assert "Me conta" in resposta and "1 - " not in resposta


def test_status_nao_e_inventado_pelo_modelo(monkeypatch):
    responder = Mock(side_effect=AssertionError("Status precisa da equipe"))
    monkeypatch.setattr(ia, "responder", responder)
    assert "ATENDENTE" in bot.processar_mensagem(TELEFONE, "meu pedido já saiu?")
    responder.assert_not_called()


@pytest.mark.parametrize("resposta", ["Seu pedido foi confirmado!", "O pagamento está aprovado.", "Seu pedido cancelado com sucesso."])
def test_acao_operacional_inventada_e_rejeitada(resposta):
    with pytest.raises(ia.IAIndisponivel, match="sem confirmação"):
        ia._limpar_resposta(resposta)


def test_raciocinio_interno_e_papel_nao_saem_para_cliente():
    assert ia._limpar_resposta("<think>Raciocínio privado</think>\nAssistente: Temos essas opções.") == "Temos essas opções."
    assert ia._limpar_resposta("<think>Raciocínio sem fechar") == ""


def test_timeout_ollama_nao_duplica_espera(monkeypatch):
    post = Mock(side_effect=requests.Timeout("modelo lento"))
    monkeypatch.setattr(ia._http, "post", post)
    with pytest.raises(ia.IAIndisponivel):
        ia._chamar_ollama([{"role": "user", "content": "oi"}])
    post.assert_called_once()


def test_reconexao_ollama_tenta_so_falha_de_transporte(monkeypatch):
    resposta = Mock(status_code=200)
    resposta.json.return_value = {"message": {"content": "Tudo certo."}}
    post = Mock(side_effect=[requests.ConnectionError("iniciando"), resposta])
    monkeypatch.setattr(ia._http, "post", post)
    monkeypatch.setattr(ia.time, "sleep", lambda _: None)
    assert ia._chamar_ollama([], permitir_ferramentas=False)["message"]["content"] == "Tudo certo."
    assert post.call_count == 2
    assert "tools" not in post.call_args.kwargs["json"]


def test_resposta_malformada_do_modelo_e_rejeitada(monkeypatch):
    resposta = Mock(status_code=200)
    resposta.json.return_value = {"message": "texto no lugar de objeto"}
    monkeypatch.setattr(ia._http, "post", Mock(return_value=resposta))
    with pytest.raises(ia.IAIndisponivel, match="inválida"):
        ia._chamar_ollama([])


def test_json_invalido_vira_indisponibilidade_sem_erro_aberto(monkeypatch):
    resposta = Mock(status_code=200)
    resposta.json.side_effect = ValueError("Não é JSON")
    post = Mock(return_value=resposta)
    monkeypatch.setattr(ia._http, "post", post)
    with pytest.raises(ia.IAIndisponivel, match="JSON válido"):
        ia._chamar_ollama([])
    post.assert_called_once()


def test_ferramenta_malformada_e_rejeitada(monkeypatch):
    monkeypatch.setattr(ia, "_chamar_ollama", Mock(return_value={"message": {"tool_calls": ["ferramenta inválida"]}}))
    with pytest.raises(ia.IAIndisponivel, match="ferramenta inválida"):
        ia._responder_ollama(TELEFONE, "quero comprar")


def test_prompt_orienta_continuidade_privacidade_e_acoes_reais():
    prompt = ia._system_prompt_ollama()
    assert "CONTINUIDADE E ESCUTA" in prompt
    assert "não reinicie o atendimento" in prompt
    assert "Não peça CPF, senha" in prompt
    assert "Nunca invente ou reconstrua URL" in prompt
    assert "Você não consulta status de pedidos" in prompt
    assert "Tom acolhedor e objetivo." in prompt


def test_mensagem_vazia_nao_cria_resposta_ou_sessao():
    assert bot.processar_mensagem(TELEFONE, "   ") is None
    with get_conn() as conn:
        assert not conn.execute("SELECT 1 FROM sessoes_bot").fetchone()


def test_pedido_humano_em_linguagem_natural_pausa_bot():
    from src import humano
    assert "humano" in bot.processar_mensagem(TELEFONE, "quero falar com uma pessoa")
    assert humano.pausado(TELEFONE)


def test_guardrail_final_trata_link_nao_autorizado(monkeypatch):
    from src import links
    monkeypatch.setattr(ia, "responder", Mock(return_value="Compre em https://localhost/m/inventado"))
    monkeypatch.setattr(links, "atualizar_resposta", Mock(side_effect=ValueError("não autorizado")))
    resposta = bot.processar_mensagem(TELEFONE, "me sugira um produto")
    assert ia.PEDIDO_INDISPONIVEL in resposta
    assert "localhost" not in resposta and "inventado" not in resposta
