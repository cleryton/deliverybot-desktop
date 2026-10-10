"""Segunda API do projeto: ViaCEP — usada para validar o endereço/área de
entrega informado pelo cliente a partir do CEP.
"""
import re

import requests

VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"


def limpar_cep(cep: str) -> str:
    return re.sub(r"\D", "", cep or "")


def consultar_cep(cep: str) -> dict | None:
    """Consulta a ViaCEP e devolve os dados do endereço, ou None se o CEP for
    inválido / inexistente / a API estiver fora do ar.
    """
    cep_limpo = limpar_cep(cep)
    if len(cep_limpo) != 8:
        return None

    try:
        resp = requests.get(VIACEP_URL.format(cep=cep_limpo), timeout=5)
        resp.raise_for_status()
        dados = resp.json()
    except (requests.RequestException, ValueError):
        return None

    if dados.get("erro"):
        return None

    return {
        "cep": dados.get("cep", cep_limpo),
        "logradouro": dados.get("logradouro", ""),
        "bairro": dados.get("bairro", ""),
        "cidade": dados.get("localidade", ""),
        "uf": dados.get("uf", ""),
    }


def endereco_formatado(dados_cep: dict) -> str:
    partes = [p for p in [dados_cep.get("logradouro"), dados_cep.get("bairro"),
                           f"{dados_cep.get('cidade', '')}/{dados_cep.get('uf', '')}"] if p]
    return ", ".join(partes)


def validar_area_entrega(cep: str, cidades_atendidas: list[str] | None = None) -> tuple[bool, str, dict | None]:
    """Valida se o CEP existe e (opcionalmente) se a cidade está na área
    atendida pelo restaurante. Retorna (ok, mensagem, dados_do_cep).
    """
    dados = consultar_cep(cep)
    if dados is None:
        return False, "Não consegui localizar esse CEP. Confira o número e tente novamente.", None

    if cidades_atendidas:
        cidade = dados.get("cidade", "").strip().lower()
        permitidas = {c.strip().lower() for c in cidades_atendidas}
        if cidade not in permitidas:
            return False, f"Infelizmente ainda não entregamos em {dados.get('cidade')}/{dados.get('uf')}.", dados

    return True, "Endereço dentro da área de entrega.", dados
