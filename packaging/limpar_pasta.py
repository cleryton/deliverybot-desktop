"""Remove somente distribuições antigas e caches reconhecidos; simula por padrão."""
import argparse
import re
import shutil
from pathlib import Path
from distribuicao import ROOT, GERADOS, verificar, versao, vinculo


def seguro(caminho, raiz):
    try:
        caminho.resolve().relative_to(raiz.resolve())
    except ValueError:
        return False
    if caminho == raiz:
        return False
    for parte in (caminho, *caminho.parents):
        if vinculo(parte):
            return False
        if parte == raiz:
            break
    if caminho.is_dir():
        return all(not vinculo(p) for p in caminho.rglob('*'))
    return True


def cache_reconhecido(pasta, extensoes):
    return all(not p.is_file() or p.suffix in extensoes or p.name in {'.gitignore', 'CACHEDIR.TAG', 'README.md', 'nodeids', 'lastfailed', 'stepwise'}
               for p in pasta.rglob('*'))


def planejar(raiz=ROOT):
    raiz = Path(raiz).absolute()
    if vinculo(raiz) or not all((raiz/p).is_file() for p in ('VERSION','desktop.py','.gitignore')):
        raise ValueError('Informe a raiz do projeto DeliveryBot.')
    atual = (raiz/'VERSION').read_text().strip()
    numero = versao(atual)
    vigente = raiz/'dist'/('v'+atual)
    if not seguro(vigente, raiz):
        raise ValueError('A distribuição atual deve estar dentro do projeto, sem vínculos.')
    verificar(vigente, completa=True, esperada=atual)
    antigas, candidatos = [], []
    for pasta in (raiz/'dist').iterdir():
        if not re.fullmatch(r'v\d+\.\d+\.\d+', pasta.name) or not pasta.is_dir() or not seguro(pasta, raiz):
            continue
        if versao(pasta.name[1:]) >= numero:
            continue
        arquivos = list(pasta.iterdir())
        if any(not p.is_file() or p.name not in GERADOS for p in arquivos):
            continue
        antigas.append(pasta)
    anterior = None
    for pasta in sorted(antigas, key=lambda p:versao(p.name[1:]), reverse=True):
        try:
            verificar(pasta)
        except (ValueError, OSError, UnicodeError):
            continue
        anterior = pasta
        break
    candidatos.extend(p for p in antigas if p != anterior)
    solto = raiz/'dist/DeliveryBot.exe'
    if solto.is_file() and seguro(solto, raiz):
        with solto.open('rb') as f:
            if f.read(2) == b'MZ':
                candidatos.append(solto)
    build = raiz/'build'
    if build.is_dir() and seguro(build, raiz):
        for p in build.iterdir():
            if p.is_dir() and (p.name == 'DeliveryBot' or re.fullmatch(r'pyinstaller-v\d+\.\d+\.\d+', p.name)):
                if cache_reconhecido(p, {'.toc','.zip','.pyc','.pyz','.pkg','.txt','.html'}):
                    candidatos.append(p)
            elif p.name == 'Desinstalar.exe' and p.is_file():
                candidatos.append(p)
    for base in ('', 'src', 'tests', 'packaging'):
        p = raiz/base/'__pycache__'
        if p.is_dir() and seguro(p, raiz) and cache_reconhecido(p, {'.pyc'}):
            candidatos.append(p)
    p = raiz/'.pytest_cache'
    if p.is_dir() and seguro(p, raiz) and cache_reconhecido(p, set()):
        candidatos.append(p)
    return {'atual':atual, 'anterior':anterior.name if anterior else None,
            'remover': [p.relative_to(raiz).as_posix() for p in candidatos if seguro(p, raiz)]}


def aplicar(raiz=ROOT):
    raiz = Path(raiz).absolute()
    plano = planejar(raiz)
    removidos, bloqueados, total = [], [], 0
    for relativo in plano['remover']:
        # Recalcula o plano e os limites antes de cada operação destrutiva.
        p = raiz/relativo
        if relativo not in planejar(raiz)['remover'] or not seguro(p, raiz):
            bloqueados.append(relativo)
            continue
        tamanho = sum(f.stat().st_size for f in p.rglob('*') if f.is_file()) if p.is_dir() else p.stat().st_size
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        except OSError:
            bloqueados.append(relativo)
        else:
            removidos.append(relativo)
            total += tamanho
    return {**plano, 'removidos':removidos, 'bloqueados':bloqueados, 'bytes_liberados':total}


if __name__ == '__main__':
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--aplicar', action='store_true')
    args = p.parse_args()
    print(json.dumps(aplicar() if args.aplicar else planejar(), ensure_ascii=False, indent=2))
