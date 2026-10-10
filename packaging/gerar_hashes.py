"""Gera o manifesto depois da compilação e eventual assinatura digital."""
import hashlib
import argparse
from pathlib import Path

root=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser()
parser.add_argument('--distpath',type=Path,default=root/'dist')
distribuicao=parser.parse_args().distpath.resolve()
arquivos=[distribuicao/'Instalar-DeliveryBot.exe',distribuicao/'DeliveryBot.exe']
linhas=[]
for arquivo in arquivos:
    with arquivo.open('rb') as f:
        linhas.append(hashlib.file_digest(f,'sha256').hexdigest()+'  '+arquivo.name)
(distribuicao/'SHA256SUMS.txt').write_text('\n'.join(linhas)+'\n',encoding='utf-8')
print('Manifesto SHA256SUMS.txt criado para instalador e aplicativo.')
