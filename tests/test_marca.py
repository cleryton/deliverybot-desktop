"""A marca deve continuar legível em ícones pequenos e disponível nos dois aplicativos."""
import importlib.util
from pathlib import Path

from PIL import Image
import pytest

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deliverybot_icone', RAIZ / 'packaging/criar_icone.py')
icone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(icone)


@pytest.mark.parametrize('tamanho', icone.TAMANHOS)
def test_icone_windows_tem_resolucao_transparencia_e_marca(tmp_path, tamanho):
    destino = icone.criar(tmp_path / 'marca.ico')
    with Image.open(destino) as arquivo:
        assert (tamanho, tamanho) in arquivo.ico.sizes()
        imagem = arquivo.ico.getimage((tamanho, tamanho)).convert('RGBA')
    alpha = imagem.getchannel('A')
    assert imagem.size == (tamanho, tamanho)
    assert alpha.getpixel((0, 0)) == 0
    # O espaço entre as faces não pode virar um fundo branco ao reduzir o ícone.
    # Em 16 px o vão ocupa menos de um pixel; considera a borda suavizada e o alinhamento.
    centro = range(round(tamanho * .45), round(tamanho * .54) + 1)
    assert min(alpha.getpixel((x, round(tamanho * .8))) for x in centro) < 128
    assert alpha.getpixel((round(tamanho * .3), round(tamanho * .65))) > 220
    assert alpha.getpixel((round(tamanho * .8), round(tamanho * .65))) > 220
    assert alpha.getbbox() is not None


def test_marca_incluida_no_terminal_corresponde_ao_original():
    assert (RAIZ / 'web/funcionario/marca.svg').read_bytes() == (RAIZ / 'web/static/marca.svg').read_bytes()


def test_icone_distribuido_nao_esta_desatualizado(tmp_path):
    with Image.open(icone.criar(tmp_path / 'atual.ico')) as atual, Image.open(RAIZ / 'packaging/DeliveryBot.ico') as distribuido:
        assert atual.ico.sizes() == distribuido.ico.sizes()
        # Compara pixels; a compressão PNG pode variar com a versão do zlib no computador.
        for tamanho in atual.ico.sizes():
            assert atual.ico.getimage(tamanho).tobytes() == distribuido.ico.getimage(tamanho).tobytes()


def test_marca_web_servida_como_imagem_sem_credenciais():
    from src.app import app
    resposta = app.test_client().get('/static/marca.svg')
    assert resposta.status_code == 200
    assert resposta.mimetype == 'image/svg+xml'
    assert b'<svg' in resposta.data
