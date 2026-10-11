"""Gera o manifesto depois da compilação e eventual assinatura digital."""
import argparse
from pathlib import Path
from distribuicao import gerar_hashes, GERADOS

root=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--distpath',type=Path,default=root/'dist')
distribuicao=parser.parse_args().distpath.resolve()
nomes = sorted(p.name for p in distribuicao.iterdir() if p.name in GERADOS - {'SHA256SUMS.txt'})
gerar_hashes(distribuicao, nomes if 'VERSAO.json' in nomes else ('Instalar-DeliveryBot.exe', 'DeliveryBot.exe'))
print('Manifesto SHA256SUMS.txt criado para instalador e aplicativo.')
