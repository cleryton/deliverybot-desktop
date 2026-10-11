"""Fotos do catálogo, normalizadas e armazenadas junto ao banco da loja."""
import hashlib
from io import BytesIO
import re
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

LIMITE_ARQUIVO = 5 * 1024 * 1024
LIMITE_PIXELS = 20_000_000


def normalizar(arquivo):
    dados = arquivo.read(LIMITE_ARQUIVO + 1)
    if not dados or len(dados) > LIMITE_ARQUIVO:
        raise ValueError('Escolha uma foto JPG, PNG ou WebP de até 5 MB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(dados), formats=['JPEG', 'PNG', 'WEBP']) as origem:
                if origem.width * origem.height > LIMITE_PIXELS:
                    raise ValueError('A foto deve ter no máximo 20 milhões de pixels.')
                if getattr(origem, 'n_frames', 1) != 1:
                    raise ValueError('Use uma foto estática, sem animação.')
                origem.load()
                foto = ImageOps.exif_transpose(origem)
                foto.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
                # Uma nova imagem recebe só pixels: EXIF, GPS e perfis não são copiados.
                limpa = Image.new('RGB', foto.size, 'white')
                rgba = foto.convert('RGBA')
                limpa.paste(rgba, mask=rgba.getchannel('A'))
                saida = BytesIO()
                limpa.save(saida, format='JPEG', quality=82, optimize=True)
                if saida.tell() > 512 * 1024:
                    limpa.thumbnail((960, 960), Image.Resampling.LANCZOS)
                    saida = BytesIO()
                    limpa.save(saida, format='JPEG', quality=75, optimize=True)
                return saida.getvalue()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValueError('Arquivo inválido. Escolha uma foto JPG, PNG ou WebP.') from None


def url(produto):
    chave = produto.get('foto_hash')
    return '/produtos/fotos/' + chave + '.jpg' if chave and re.fullmatch(r'[a-f0-9]{64}', chave) else None


def salvar(conn, produto_id, foto=None, remover=False):
    if foto is not None:
        chave = hashlib.sha256(foto).hexdigest()
        conn.execute('INSERT INTO fotos_produto(produto_id,hash,dados) VALUES(?,?,?) '
                     'ON CONFLICT(produto_id) DO UPDATE SET hash=excluded.hash,dados=excluded.dados',
                     (produto_id, chave, foto))
    elif remover:
        conn.execute('DELETE FROM fotos_produto WHERE produto_id=?', (produto_id,))
    if foto is not None or remover:
        conn.execute('UPDATE produtos SET imagem=NULL WHERE id=?', (produto_id,))
