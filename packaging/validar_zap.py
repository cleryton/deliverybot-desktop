"""Valida relatório passivo local e bloqueia riscos altos e controles essenciais."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

CONTROLES_ESSENCIAIS = {'10010', '10011', '10020', '10021', '10038'}


def validar(relatorio):
    sites = relatorio.get('site')
    if not isinstance(sites, list) or not sites:
        raise ValueError('ZAP não gerou resultados para o alvo local.')
    total = bloqueios = 0
    for site in sites:
        url = urlsplit(site.get('@name',''))
        if url.scheme not in {'http','https'} or url.hostname!='127.0.0.1' or url.port!=5030:
            raise ValueError('O relatório ZAP deve conter somente o alvo fictício local.')
        alerts = site.get('alerts')
        if not isinstance(alerts,list):
            raise ValueError('Relatório ZAP incompleto.')
        for alert in alerts:
            risk = int(alert['riskcode'])
            if risk not in range(4):
                raise ValueError('Risco ZAP inválido.')
            total += 1
            if risk>=3 or str(alert.get('pluginid')) in CONTROLES_ESSENCIAIS:
                bloqueios += 1
    return {'alertas':total,'bloqueios':bloqueios,'escopo':'loopback com dados fictícios'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('relatorio',type=Path)
    args=p.parse_args()
    try:
        result=validar(json.loads(args.relatorio.read_text(encoding='utf-8')))
        print(json.dumps(result, ensure_ascii=False))
        return int(bool(result['bloqueios']))
    except (OSError, ValueError, TypeError, KeyError):
        print('Falha na validação: relatório ausente, inválido ou fora do escopo permitido.')
        return 2


if __name__=='__main__':
    raise SystemExit(main())
