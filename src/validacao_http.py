"""Limites de parsing e dados inequívocos, conforme orientações OWASP."""
import json
import math
from flask.json.provider import DefaultJSONProvider

PROFUNDIDADE_MAXIMA = 32
NOS_MAXIMOS = 25000


def _profundidade(texto):
    nivel = 0
    string = escape = False
    for caractere in texto:
        if string:
            if escape:
                escape = False
            elif caractere == '\\':
                escape = True
            elif caractere == '"':
                string = False
        elif caractere == '"':
            string = True
        elif caractere in '[{':
            nivel += 1
            if nivel > PROFUNDIDADE_MAXIMA:
                raise ValueError('JSON excede o limite de profundidade.')
        elif caractere in ']}':
            nivel -= 1


def _objeto(pares):
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError('JSON contém campos duplicados.')
        resultado[chave] = valor
    return resultado


def _inteiro(valor):
    if len(valor.lstrip('-')) > 128:
        raise ValueError('Número JSON excede o limite.')
    return int(valor)


def _real(valor):
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError('Número JSON deve ser finito.')
    return numero


def _constante(_valor):
    raise ValueError('Constante JSON inválida.')


def ler_json(dados):
    if isinstance(dados, (bytes, bytearray)):
        dados = bytes(dados).decode('utf-8', errors='strict')
    if not isinstance(dados, str):
        raise ValueError('JSON deve ser texto UTF-8.')
    _profundidade(dados)
    resultado = json.loads(dados, object_pairs_hook=_objeto, parse_int=_inteiro,
                           parse_float=_real, parse_constant=_constante)
    pendentes, total = [resultado], 0
    while pendentes:
        valor = pendentes.pop()
        total += 1
        if total > NOS_MAXIMOS:
            raise ValueError('JSON excede o limite de itens.')
        if isinstance(valor, dict):
            pendentes.extend(valor.keys())
            pendentes.extend(valor.values())
        elif isinstance(valor, list):
            pendentes.extend(valor)
        elif isinstance(valor, str) and ('\0' in valor or any(0xD800 <= ord(c) <= 0xDFFF for c in valor)):
            raise ValueError('Texto JSON contém caracteres inválidos.')
    return resultado


class JSONSeguro(DefaultJSONProvider):
    def loads(self, s, **kwargs):
        # Mesmas regras para requisições e leitura de respostas no cliente de teste.
        return ler_json(s)


def parametros_unicos(parametros):
    return all(len(valores) == 1 for _, valores in parametros.lists())
