"""Segunda API do projeto: ViaCEP — usada para validar o endereço/área de
entrega informado pelo cliente a partir do CEP.
"""
import re
import threading
import time
from collections import OrderedDict

import requests

VIACEP_URL = "https://viacep.com.br/ws/{cep}/json/"
CACHE_TTL = 300
CACHE_LIMITE = 256
_cache = OrderedDict()
_trava = threading.Lock()
_UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())


def limpar_cep(cep: str) -> str:
    return re.sub(r"\D", "", cep) if isinstance(cep, str) else ''


def consultar_cep(cep: str) -> dict | None:
    """Consulta a ViaCEP e devolve os dados do endereço, ou None se o CEP for
    inválido / inexistente / a API estiver fora do ar.
    """
    cep_limpo = limpar_cep(cep)
    if not re.fullmatch(r'[0-9]{8}', cep_limpo):
        return None

    # Somente endereços públicos por CEP; nunca nome, número ou complemento.
    with _trava:
        anterior = _cache.get(cep_limpo)
        if anterior and time.monotonic() < anterior[0]:
            _cache.move_to_end(cep_limpo)
            return dict(anterior[1])
        _cache.pop(cep_limpo, None)

    try:
        resp = requests.get(VIACEP_URL.format(cep=cep_limpo), timeout=(2, 4), allow_redirects=False)
        resp.raise_for_status()
        if resp.status_code != 200:
            return None
        dados = resp.json()
    except (requests.RequestException, ValueError):
        return None

    if not isinstance(dados, dict) or dados.get("erro"):
        return None
    cep_resposta = dados.get('cep', cep_limpo)
    if not isinstance(cep_resposta, str) or limpar_cep(cep_resposta) != cep_limpo:
        return None
    resultado = {
        "cep": cep_limpo[:5]+'-'+cep_limpo[5:],
        "logradouro": dados.get("logradouro", ""),
        "bairro": dados.get("bairro", ""),
        "cidade": dados.get("localidade", ""),
        "uf": dados.get("uf", ""),
    }
    for campo in ('logradouro','bairro','cidade','uf'):
        valor = resultado[campo]
        if not isinstance(valor,str) or len(valor)>160 or any(ord(c)<32 for c in valor):
            return None
        resultado[campo] = valor.strip()
    if not resultado['cidade'] or resultado['uf'] not in _UFS:
        return None
    with _trava:
        agora = time.monotonic()
        for chave in list(_cache):
            if _cache[chave][0] <= agora:_cache.pop(chave)
        _cache[cep_limpo] = (agora+CACHE_TTL, dict(resultado))
        _cache.move_to_end(cep_limpo)
        while len(_cache)>CACHE_LIMITE:_cache.popitem(last=False)
    return resultado


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
