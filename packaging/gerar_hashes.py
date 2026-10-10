"""Gera o manifesto depois da compilação e eventual assinatura digital."""
import hashlib
from pathlib import Path

root=Path(__file__).resolve().parent.parent
arquivos=[root/'dist/Instalar-DeliveryBot.exe',root/'dist/DeliveryBot.exe']
linhas=[]
for arquivo in arquivos:
    with arquivo.open('rb') as f:
        linhas.append(hashlib.file_digest(f,'sha256').hexdigest()+'  '+arquivo.name)
(root/'dist/SHA256SUMS.txt').write_text('\n'.join(linhas)+'\n',encoding='utf-8')
print('Manifesto SHA256SUMS.txt criado para instalador e aplicativo.')
