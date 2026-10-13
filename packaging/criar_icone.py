"""Gera o ícone Windows em várias resoluções a partir da marca vetorial comum."""
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parents[1]
TAMANHOS = (16, 24, 32, 48, 64, 128, 256)


def renderizar(fonte, tamanho=256):
    """Rasteriza os polígonos da marca local, preservando os espaços transparentes."""
    svg = ET.parse(fonte).getroot()
    _, _, largura, altura = map(float, svg.attrib['viewBox'].split())
    fator = tamanho * 4 / max(largura, altura)
    imagem = Image.new('RGBA', (tamanho * 4, tamanho * 4))
    desenho = ImageDraw.Draw(imagem)
    for poligono in svg.iter('{http://www.w3.org/2000/svg}polygon'):
        pontos = [tuple(float(n) * fator for n in ponto.split(','))
                  for ponto in poligono.attrib['points'].split()]
        desenho.polygon(pontos, fill=poligono.attrib['fill'])
        desenho.line(pontos + pontos[:1], fill=poligono.attrib['fill'],
                     width=max(1, round(2 * fator)), joint='curve')
    return imagem.resize((tamanho, tamanho), Image.Resampling.LANCZOS)


def criar(destino=None, fonte=None):
    fonte = Path(fonte or RAIZ / 'web/static/marca.svg')
    destino = Path(destino or RAIZ / 'packaging/DeliveryBot.ico')
    destino.parent.mkdir(parents=True, exist_ok=True)
    imagem = renderizar(fonte)
    imagem.save(destino, format='ICO', sizes=[(n, n) for n in TAMANHOS])
    return destino


if __name__ == '__main__':
    criar()
    # O terminal abre uma página local independente; inclui a mesma marca no seu diretório.
    shutil.copyfile(RAIZ / 'web/static/marca.svg', RAIZ / 'web/funcionario/marca.svg')
