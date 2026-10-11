"""Reconexão de callback remoto com APIs simuladas, sem contas ou rede reais."""
import copy
from unittest.mock import Mock

import pytest

from src import config, conexoes


@pytest.fixture(autouse=True)
def remoto(monkeypatch):
    for chave, valor in {
        "WHATSAPP_PROVIDER": "WAHA",
        "WAHA_URL": "https://waha.example",
        "WAHA_SESSION": "vendas / loja",
        "WAHA_WEBHOOK_BASE_URL": "",
        "WEBHOOK_SECRET": "segredo-ficticio-da-loja",
    }.items():
        monkeypatch.setattr(config, chave, valor)
    monkeypatch.setattr(conexoes, "url_webhook", lambda: "https://novo.example/webhook/waha/segredo-ficticio-da-loja")


@pytest.mark.parametrize("campo,valor", [
    ("WHATSAPP_PROVIDER", "LOCAL"),
    ("WHATSAPP_PROVIDER", "META"),
    ("WHATSAPP_PROVIDER", "TESTE"),
    ("WAHA_WEBHOOK_BASE_URL", "https://manual.example"),
    ("WAHA_URL", "http://127.0.0.1:3000"),
    ("WAHA_URL", "http://localhost:3000"),
    ("WAHA_URL", "http://[::1]:3000"),
    ("WEBHOOK_SECRET", ""),
])
def test_ignora_configuracoes_sem_callback_automatico(monkeypatch, campo, valor):
    monkeypatch.setattr(config, campo, valor)
    chamada = Mock(side_effect=AssertionError("Não deve consultar ou modificar a sessão."))
    monkeypatch.setattr(conexoes, "_waha", chamada)
    assert conexoes.renovar_webhook_publico() is False
    chamada.assert_not_called()


def test_nao_cria_sessao_ausente(monkeypatch):
    chamada = Mock(return_value=None)
    monkeypatch.setattr(conexoes, "_waha", chamada)
    assert conexoes.renovar_webhook_publico() is False
    chamada.assert_called_once_with("GET", "/api/sessions/vendas%20%2F%20loja", aceitar_404=True)


def test_renova_uma_vez_preservando_configuracao_e_outros_webhooks(monkeypatch):
    original = {
        "status": "WORKING", "apps": [{"id": "integracao-ficticia"}],
        "config": {
            "custom": {"valor": 7}, "ignore": {"groups": False},
            "webhooks": [
                {"url": "https://integrador.example/hook", "events": ["message"]},
                {"url": "https://outra-loja.example/webhook/waha/outro-segredo", "events": ["message"]},
                {"url": "https://antigo.example/webhook/waha/segredo-ficticio-da-loja",
                 "events": ["message", "session.status"], "customHeaders": [{"name": "X-App", "value": "loja"}],
                 "retries": {"policy": "constant", "attempts": 8, "delaySeconds": 5}},
            ],
        },
    }
    antes = copy.deepcopy(original)
    atualizado = {}

    def fake(metodo, caminho, dados=None, aceitar_404=False):
        if metodo == "GET":
            return atualizado or original
        assert metodo == "PUT"
        atualizado.update(copy.deepcopy(dados))
        return {}

    chamada = Mock(side_effect=fake)
    monkeypatch.setattr(conexoes, "_waha", chamada)
    assert conexoes.renovar_webhook_publico() is True
    assert conexoes.renovar_webhook_publico() is False
    assert [c.args[0] for c in chamada.call_args_list] == ["GET", "PUT", "GET"]
    payload = chamada.call_args_list[1].args[2]
    assert payload["apps"] == original["apps"]
    assert payload["config"]["custom"] == original["config"]["custom"]
    assert payload["config"]["ignore"] == {"groups": False}
    assert payload["config"]["webhooks"][:2] == original["config"]["webhooks"][:2]
    esperado = copy.deepcopy(original["config"]["webhooks"][2])
    esperado["url"] = "https://novo.example/webhook/waha/segredo-ficticio-da-loja"
    assert payload["config"]["webhooks"][2] == esperado
    assert original == antes


@pytest.mark.parametrize("status", ["WORKING", "STOPPED", "FAILED", "SCAN_QR_CODE"])
def test_callback_ausente_atualiza_configuracao_sem_iniciar_sessao(monkeypatch, status):
    chamada = Mock(side_effect=[{"status": status, "config": {"custom": 7}}, {}])
    monkeypatch.setattr(conexoes, "_waha", chamada)
    assert conexoes.renovar_webhook_publico() is True
    assert [c.args[0] for c in chamada.call_args_list] == ["GET", "PUT"]
    dados = chamada.call_args_list[1].args[2]
    assert "start" not in dados and "apps" not in dados
    assert dados["config"]["custom"] == 7
    assert dados["config"]["webhooks"][0]["events"] == ["message"]


def test_falha_na_renovacao_permite_nova_tentativa(monkeypatch):
    info = {"config": {"webhooks": [{"url": "https://antigo.example/webhook/waha/segredo-ficticio-da-loja"}]}}
    chamada = Mock(side_effect=[info, ValueError("Serviço indisponível"), info, {}])
    monkeypatch.setattr(conexoes, "_waha", chamada)
    with pytest.raises(ValueError, match="indisponível"):
        conexoes.renovar_webhook_publico()
    assert conexoes.renovar_webhook_publico() is True
    assert [c.args[0] for c in chamada.call_args_list] == ["GET", "PUT", "GET", "PUT"]


def test_webhooks_duplicados_da_loja_nao_duplicam_apos_troca(monkeypatch):
    info = {"config": {"webhooks": [
        {"url": "https://antigo.example/webhook/waha/segredo-ficticio-da-loja"},
        {"url": "https://novo.example/webhook/waha/segredo-ficticio-da-loja", "events": ["message"]},
    ]}}
    chamada = Mock(side_effect=[info, {}])
    monkeypatch.setattr(conexoes, "_waha", chamada)
    assert conexoes.renovar_webhook_publico() is True
    assert chamada.call_args.args[2]["config"]["webhooks"] == [info["config"]["webhooks"][1]]
