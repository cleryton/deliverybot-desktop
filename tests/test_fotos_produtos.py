from contextlib import closing
from io import BytesIO
import json
import sqlite3

from PIL import Image
import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

from src import config, fotos, estoque, backups
from src.db import init_db, get_conn


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'loja.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    monkeypatch.setattr(config, 'MODO_TESTE', True)
    init_db()
    from src.app import app
    monkeypatch.setitem(app.config, 'DESKTOP_TOKEN', 'teste-fotos')
    cliente = app.test_client()
    cliente.get('/gestao?acesso=teste-fotos', follow_redirects=True)
    with cliente.session_transaction() as sessao:
        csrf = sessao['csrf']
    return app, cliente, {'X-CSRF-Token': csrf}


def foto(formato='PNG', cor='red', tamanho=(120, 80), exif=None):
    saida = BytesIO()
    opcoes = {'exif': exif} if exif else {}
    Image.new('RGB', tamanho, cor).save(saida, format=formato, **opcoes)
    return saida.getvalue()


def dados(**campos):
    return {'nome': 'Camiseta', 'categoria': 'Roupas', 'preco': 39.90, 'estoque': 5, **campos}


def enviar(cliente, headers, campos=None, imagem=None, caminho='/gestao/api/produtos', metodo='POST'):
    envio = {'dados': json.dumps(campos or dados())}
    if imagem is not None:
        envio['foto'] = (BytesIO(imagem), '../../foto.png')
    return cliente.open(caminho, method=metodo, data=envio, headers=headers)


def test_foto_upload_catalogo_https_e_admin_bloqueado(loja):
    app, cliente, headers = loja
    r = enviar(cliente, headers, imagem=foto())
    assert r.status_code == 201
    produto = r.json
    caminho = produto['foto_url']
    assert caminho.startswith('/produtos/fotos/') and caminho.endswith('.jpg')
    from src.links import gerar_link_pedido
    pedido = gerar_link_pedido('5511999990000').rsplit('/', 1)[-1]
    pagina = cliente.get('/m/' + pedido)
    assert caminho.encode() in pagina.data
    from src.publicacao import PaginaPublica
    publico = Client(PaginaPublica(app, lambda: 'https://loja.example'), Response)
    imagem = publico.get(caminho)
    assert imagem.status_code == 200 and imagem.mimetype == 'image/jpeg'
    assert Image.open(BytesIO(imagem.data)).size == (120, 80)
    assert imagem.headers['X-Content-Type-Options'] == 'nosniff'
    assert publico.get('/gestao/api/produtos').status_code == 404
    assert publico.post('/gestao/api/produtos', data={}).status_code == 404
    assert publico.get('/produtos/fotos/../../.env.jpg').status_code == 404


def test_alterar_produto_preserva_foto_e_estoque_remover_trocar(loja):
    app, cliente, headers = loja
    produto = enviar(cliente, headers, imagem=foto()).json
    caminho = '/gestao/api/produtos/' + str(produto['id'])
    estoque.ajustar_estoque(produto['id'], -1, 'Venda anterior')
    atualizado = cliente.put(caminho, json=dados(nome='Camiseta azul', estoque=500), headers=headers).json
    assert atualizado['foto_url'] == produto['foto_url'] and atualizado['estoque'] == 4
    novo = enviar(cliente, headers, dados(), foto(cor='blue'), caminho, 'PUT').json
    assert novo['foto_url'] != produto['foto_url']
    assert cliente.get(produto['foto_url']).status_code == 404
    removido = cliente.put(caminho, json=dados(remover_foto=True), headers=headers).json
    assert removido['foto_url'] is None and removido['imagem'] is None
    assert cliente.get(novo['foto_url']).status_code == 404


def test_foto_inativo_so_no_painel(loja):
    app, cliente, headers = loja
    p = enviar(cliente, headers, dados(ativo=False), foto()).json
    assert cliente.get(p['foto_url']).status_code == 200
    from src.publicacao import PaginaPublica
    publico = Client(PaginaPublica(app, lambda: 'https://loja.example'), Response)
    assert publico.get(p['foto_url']).status_code == 404


@pytest.mark.parametrize('conteudo', [b'', b'<svg onload="alert(1)"></svg>', b'GIF89a', b'\xff\xd8\xffinvalid', b'x' * (fotos.LIMITE_ARQUIVO + 1)], ids=['vazio', 'svg', 'gif', 'jpeg-corrompido', 'grande'])
def test_arquivo_invalido_nao_cria_produto(loja, conteudo):
    app, cliente, headers = loja
    assert enviar(cliente, headers, imagem=conteudo).status_code == 400
    assert estoque.listar_produtos() == []


def test_foto_exige_login_csrf_e_limite_requisicao(loja):
    app, cliente, headers = loja
    assert enviar(app.test_client(), headers, imagem=foto()).status_code == 401
    assert enviar(cliente, {}, imagem=foto()).status_code == 403
    r = enviar(cliente, headers, imagem=b'x' * (6 * 1024 * 1024 + 1))
    assert r.status_code == 413 and '5 MB' in r.json['erro']
    assert estoque.listar_produtos() == []


def test_imagem_tamanho_rotacao_e_metadados():
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = 'Dado pessoal da câmera'
    normal = fotos.normalizar(BytesIO(foto('JPEG', tamanho=(2400, 1200), exif=exif)))
    with Image.open(BytesIO(normal)) as img:
        assert img.size == (640, 1280)
        assert not img.getexif()
        assert 'icc_profile' not in img.info


def test_imagem_pixels_excessivos_e_animada(monkeypatch):
    monkeypatch.setattr(fotos, 'LIMITE_PIXELS', 100)
    with pytest.raises(ValueError, match='pixels'):
        fotos.normalizar(BytesIO(foto()))
    monkeypatch.setattr(fotos, 'LIMITE_PIXELS', 20_000_000)
    saida = BytesIO()
    Image.new('RGB', (10, 10), 'red').save(saida, format='PNG', save_all=True,
        append_images=[Image.new('RGB', (10, 10), 'blue')], duration=100)
    with pytest.raises(ValueError, match='animação'):
        fotos.normalizar(BytesIO(saida.getvalue()))


def test_foto_acompanha_backup_portatil_e_reabertura(loja):
    app, cliente, headers = loja
    p = enviar(cliente, headers, imagem=foto('WEBP')).json
    senha = 'senha-backup-fotos-teste'
    copia = backups.criar(senha)
    with closing(sqlite3.connect(':memory:')) as restaurado:
        restaurado.deserialize(backups.abrir_arquivo(copia, senha))
        registro = restaurado.execute('SELECT hash,dados FROM fotos_produto WHERE produto_id=?', (p['id'],)).fetchone()
        assert registro[0] == p['foto_hash'] and Image.open(BytesIO(registro[1])).format == 'JPEG'
    init_db(forcar=True)
    assert estoque.listar_produtos()[0]['foto_url'] == p['foto_url']


def test_falha_no_produto_nao_substitui_foto(loja):
    app, cliente, headers = loja
    p = enviar(cliente, headers, imagem=foto()).json
    caminho = '/gestao/api/produtos/' + str(p['id'])
    assert enviar(cliente, headers, dados(preco=-1), foto(cor='blue'), caminho, 'PUT').status_code == 400
    assert estoque.listar_produtos()[0]['foto_url'] == p['foto_url']
    assert enviar(cliente, headers, dados(remover_foto=True), foto(), caminho, 'PUT').status_code == 400
    assert estoque.listar_produtos()[0]['foto_url'] == p['foto_url']
