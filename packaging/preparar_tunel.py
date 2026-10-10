"""Baixa apenas na compilação o conector oficial, com versão e hash fixados."""
import hashlib
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def preparar():
    pin = json.loads((ROOT / 'packaging/cloudflared.json').read_text(encoding='utf-8'))
    pasta = ROOT / 'cloudflare/runtime'
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / 'cloudflared.exe'
    if not destino.exists() or hashlib.sha256(destino.read_bytes()).hexdigest() != pin['sha256']:
        temporario = destino.with_suffix('.tmp')
        try:
            with requests.get(pin['url'], stream=True, timeout=(15, 60)) as r:
                r.raise_for_status()
                tamanho = 0
                digest = hashlib.sha256()
                with temporario.open('wb') as f:
                    for bloco in r.iter_content(1024 * 1024):
                        tamanho += len(bloco)
                        if tamanho > pin['size']:
                            raise ValueError('Conector maior que a distribuição oficial fixada.')
                        digest.update(bloco)
                        f.write(bloco)
            if tamanho != pin['size'] or digest.hexdigest() != pin['sha256']:
                raise ValueError('A integridade do conector não corresponde à distribuição fixada.')
            temporario.replace(destino)
        finally:
            temporario.unlink(missing_ok=True)
    with requests.get(f"https://raw.githubusercontent.com/cloudflare/cloudflared/{pin['version']}/LICENSE", timeout=30) as r:
        r.raise_for_status()
        (pasta / 'LICENSE.txt').write_text(r.text, encoding='utf-8')
    print('Conector oficial Cloudflare preparado e SHA-256 conferido: ' + pin['version'])


if __name__ == '__main__':
    preparar()
