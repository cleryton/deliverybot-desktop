"""Relatório operacional para suporte, sem informações de clientes ou segredos."""
from datetime import datetime, timezone
from pathlib import Path
import platform
import sys

from . import config, conexoes, processamento, publicacao, rotinas
from .db import get_conn


def coletar():
    try:
        with get_conn() as conn:
            conn.execute("SELECT 1").fetchone()
        banco_ok = True
    except Exception:
        banco_ok = False

    try:
        if config.WHATSAPP_PROVIDER in {"LOCAL", "WAHA", "META"}:
            wa = conexoes.status_whatsapp()
            whatsapp = {"estado": wa.get("estado", "INDISPONIVEL"),
                        "servico": bool(wa.get("servico")),
                        "conectado": bool(wa.get("conectado"))}
        else:
            whatsapp = {"estado": "TESTE", "servico": True, "conectado": False}
    except Exception:
        whatsapp = {"estado": "INDISPONIVEL", "servico": False, "conectado": False}

    try:
        tunnel = publicacao.situacao()
        https = {"estado": tunnel.get("estado", "INDISPONIVEL"),
                 "ativo": bool(tunnel.get("ativo")),
                 "disponivel": bool(tunnel.get("disponivel"))}
    except Exception:
        https = {"estado": "INDISPONIVEL", "ativo": False, "disponivel": False}

    try:
        fila = processamento.situacao()
        fila_info = {"consumidores_ativos": processamento.ativo(),
                     "pendentes": int(fila.get("pendentes", 0)),
                     "falhas": len(fila.get("falhas", []))}
    except Exception:
        fila_info = {"consumidores_ativos": False, "pendentes": 0, "falhas": 0}

    try:
        ollama_status = conexoes.status_ollama() if config.IA_PROVIDER == "OLLAMA" else {}
        ollama = {"selecionado": config.IA_PROVIDER == "OLLAMA",
                  "online": bool(ollama_status.get("online")),
                  "modelo_instalado": bool(ollama_status.get("modelo_instalado"))}
    except Exception:
        ollama = {"selecionado": config.IA_PROVIDER == "OLLAMA",
                  "online": False, "modelo_instalado": False}

    try:
        rotina = rotinas.situacao()
        backup = {"automatico": bool(rotina.get("backup_ativo")),
                  "atrasado": bool(rotina.get("atrasado")),
                  "ultima_copia": rotina.get("ultima_copia"),
                  "falha": bool(rotina.get("erro"))}
    except Exception:
        backup = {"automatico": False, "atrasado": False,
                  "ultima_copia": None, "falha": True}

    raiz = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    try:
        versao = (raiz / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        versao = "desconhecida"
    return {
        "produto": "DeliveryBot",
        "versao": versao,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "sistema": {"nome": platform.system(), "versao": platform.release(),
                    "arquitetura": platform.machine()},
        "servicos": {
            "banco": {"online": banco_ok},
            "whatsapp": {"provedor": config.WHATSAPP_PROVIDER, **whatsapp},
            "https": https,
            "fila": fila_info,
            "ollama": ollama,
            "backup": backup,
        },
        "privacidade": "Este relatório não inclui nomes, telefones, mensagens, pedidos, URLs, caminhos locais ou credenciais.",
    }
