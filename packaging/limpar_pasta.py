"""Remove somente distribuições antigas e caches reconhecidos; simula por padrão."""
import argparse
import re
import shutil
from pathlib import Path
from distribuicao import ROOT, GERADOS, verificar, versao, vinculo


def seguro(caminho, raiz):
    try:
        caminho.resolve().relative_to(raiz.resolve())
        if caminho == raiz:
            return False
        for parte in (caminho, *caminho.parents):
            if vinculo(parte):
                return False
            if parte == raiz:
                break
        if caminho.is_dir():
            return all(not vinculo(p) for p in caminho.rglob('*'))
    except (OSError, ValueError):
        return False
    return True


def cache_reconhecido(pasta, extensoes, nomes=()):
    try:
        return all(not p.is_file() or p.suffix in extensoes or p.name in nomes
                   for p in pasta.rglob('*'))
    except OSError:
        return False


def _raiz_projeto(raiz):
    raiz = Path(raiz).absolute()
    if vinculo(raiz) or not all((raiz/p).is_file() and seguro(raiz/p, raiz)
                              for p in ('VERSION', 'desktop.py', '.gitignore')):
        raise ValueError('Informe a raiz do projeto DeliveryBot.')
    return raiz


def _caches_reconhecidos(raiz=ROOT):
    """Lista somente caches regeneráveis; não valida nem seleciona distribuições."""
    raiz = _raiz_projeto(raiz)
    candidatos = []
    build = raiz/'build'
    if build.is_dir() and seguro(build, raiz):
        documentos = {'warn-DeliveryBot.txt', 'xref-DeliveryBot.html',
                      'warn-Funcionario.txt', 'xref-Funcionario.html'}
        for p in build.iterdir():
            if p.is_dir() and (p.name in {'DeliveryBot', 'Funcionario'}
                               or re.fullmatch(r'pyinstaller-v\d+\.\d+\.\d+', p.name)):
                if cache_reconhecido(p, {'.toc', '.zip', '.pyc', '.pyz', '.pkg'}, documentos):
                    candidatos.append(p)
            elif p.name in {'Desinstalar.exe', 'Desinstalar-Funcionario.exe'} and p.is_file():
                with p.open('rb') as arquivo:
                    if arquivo.read(2) == b'MZ':
                        candidatos.append(p)
    for base in ('', 'src', 'tests', 'packaging'):
        p = raiz/base/'__pycache__'
        if p.is_dir() and seguro(p, raiz) and cache_reconhecido(p, {'.pyc'}):
            candidatos.append(p)
    p = raiz/'.pytest_cache'
    marcadores_pytest = {'.gitignore', 'CACHEDIR.TAG', 'README.md', 'nodeids', 'lastfailed', 'stepwise'}
    if p.is_dir() and seguro(p, raiz) and cache_reconhecido(p, set(), marcadores_pytest):
        candidatos.append(p)
    return [p for p in candidatos if seguro(p, raiz)]


def planejar(raiz=ROOT):
    raiz = _raiz_projeto(raiz)
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
    candidatos.extend(_caches_reconhecidos(raiz))
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
