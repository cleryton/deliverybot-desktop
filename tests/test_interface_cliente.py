"""Interface de compra com dados fictícios, sem serviços ou mensagens reais."""
from html.parser import HTMLParser
from unittest.mock import Mock

import pytest

from src import config, estoque, publicacao, viacep, whatsapp
from src.db import init_db
from src.links import gerar_link_pedido


class Elementos(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elementos = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elementos.append((tag, dict(attrs)))

    def por_id(self, identificador):
        return next(attrs for _, attrs in self.elementos if attrs.get('id') == identificador)

    def tags(self, tag):
        return [attrs for nome, attrs in self.elementos if nome == tag]


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'loja-ficticia.db'))
    for chave, valor in {'SEED_CATALOGO': False, 'MODO_TESTE': True, 'WHATSAPP_PROVIDER': 'TESTE',
                         'IA_PROVIDER': '', 'BASE_URL': 'http://localhost:5000',
                         'FORMAS_PAGAMENTO': 'Pix,Dinheiro', 'TAXA_ENTREGA': 7.5}.items():
        monkeypatch.setattr(config, chave, valor)
    monkeypatch.setattr(publicacao, '_gerente', None)
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', Mock())
    init_db(seed_cardapio=False)
    from src.app import app
    return app.test_client()


def pagina(cliente, **dados):
    produto = estoque.salvar_produto({'nome': 'Café especial', 'categoria': 'Mercearia',
                                     'preco': 10.01, 'estoque': 2.75, 'unidade': 'kg',
                                     'fracionado': True, **dados})
    caminho = '/m/' + gerar_link_pedido('5511999990011').rsplit('/', 1)[-1]
    resposta = cliente.get(caminho)
    html = resposta.get_data(as_text=True)
    csrf = next(input['value'] for input in Elementos(html).tags('input') if input.get('name') == 'csrf_token')
    return produto, caminho, csrf, html


def test_catalogo_generico_acessivel_e_funcional_sem_javascript(cliente):
    produto, _, _, html = pagina(cliente)
    elementos = Elementos(html)
    quantidade = elementos.por_id('qtd-' + str(produto['id']))
    assert quantidade['name'] == 'qtd_' + str(produto['id'])
    assert quantidade['step'] == '0.001' and quantidade['max'] == '2.75'
    assert 'hidden' not in quantidade and quantidade['aria-describedby'].startswith('dica-qtd-')
    assert any(label.get('for') == quantidade['id'] for label in elementos.tags('label'))
    assert 'disabled' not in elementos.por_id('botao-confirmar')
    assert elementos.por_id('nome')['autocomplete'] == 'given-name'
    assert [script['src'] for script in elementos.tags('script')] == ['/static/pedido.js']
    assert any(link.get('href') == '/static/pedido.css' for link in elementos.tags('link'))
    assert 'aviso de privacidade' in html and 'data-taxa-entrega="7.5"' in html
    assert 'csrf_token' in html and 'fonts.googleapis.com' not in html


def test_erro_de_entrega_preserva_selecao_e_dados_sem_injetar_html(cliente, monkeypatch):
    produto, caminho, csrf, _ = pagina(cliente)
    monkeypatch.setattr(viacep, 'validar_area_entrega', lambda cep: (False, 'CEP fora da área de entrega.', None))
    dados = {'csrf_token': csrf, 'nome': '<script>alert(1)</script>', 'forma_entrega': 'ENTREGA',
             'forma_pagamento': 'Dinheiro', 'cep': '12345-678', 'numero': '42',
             'complemento': 'Bloco "A"', 'qtd_' + str(produto['id']): '0.5'}
    resposta = cliente.post(caminho, data=dados)
    assert resposta.status_code == 400
    html = resposta.get_data(as_text=True)
    elementos = Elementos(html)
    assert elementos.por_id('qtd-' + str(produto['id']))['value'] == '0.5'
    for identificador in ['nome', 'cep', 'numero', 'complemento']:
        assert elementos.por_id(identificador)['value'] == dados[identificador]
    assert elementos.por_id('erro-pedido')['role'] == 'alert'
    selecionadas = [option['value'] for option in elementos.tags('option') if 'selected' in option]
    assert 'ENTREGA' in selecionadas and 'Dinheiro' in selecionadas
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html
    assert all(script.get('src') == '/static/pedido.js' for script in elementos.tags('script'))


def test_pedido_fracionado_csrf_confirmacao_e_link_unico(cliente, monkeypatch):
    produto, caminho, csrf, _ = pagina(cliente)
    envio = Mock(side_effect=RuntimeError('Falha fictícia'))
    monkeypatch.setattr(whatsapp, 'enviar_mensagem', envio)
    monkeypatch.setattr(config, 'MODO_TESTE', False)
    dados = {'nome': 'Pessoa fictícia', 'forma_entrega': 'RETIRADA BALCAO', 'forma_pagamento': 'Pix',
             'qtd_' + str(produto['id']): '0.5'}
    assert cliente.post(caminho, data=dados).status_code == 403
    resposta = cliente.post(caminho, data={**dados, 'csrf_token': csrf})
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert 'Seu pedido foi recebido!' in html and 'R$ 5,01' in html
    assert '0,5 × Café especial' in html and 'Pix' in html and 'Retirada na loja' in html
    assert html.count('R$ 5,01') == 2  # O subtotal e o total usam o mesmo arredondamento do servidor.
    assert 'Seu pedido está salvo.' in html and '5511999990011' not in html
    assert estoque.listar_produtos()[0]['estoque'] == 2.25
    assert cliente.post(caminho, data={**dados, 'csrf_token': csrf}).status_code == 410
    assert cliente.get(caminho).status_code == 410
    assert envio.call_count == 1


def test_produtos_e_campos_com_html_sao_escapados(cliente):
    _, _, _, html = pagina(cliente, nome='<img src=x onerror=alert(1)>', descricao='<script>malicioso()</script>')
    elementos = Elementos(html)
    assert '<img src=x onerror=alert(1)>' not in html
    assert '<script>malicioso()</script>' not in html
    assert elementos.tags('img') == []
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert all('onerror' not in attrs for _, attrs in elementos.elementos)


def test_estados_vazios_links_indisponiveis_e_privacidade(cliente):
    caminho = '/m/' + gerar_link_pedido('5511999990022').rsplit('/', 1)[-1]
    html = cliente.get(caminho).get_data(as_text=True)
    assert 'Nenhum produto está disponível agora' in html
    assert 'disabled' in Elementos(html).por_id('botao-confirmar')
    indisponivel = cliente.get('/m/token-inexistente')
    assert indisponivel.status_code == 410 and 'Você precisa de um novo link' in indisponivel.get_data(as_text=True)
    aviso = cliente.get('/privacidade')
    assert aviso.status_code == 200
    texto = aviso.get_data(as_text=True)
    assert all(titulo in texto for titulo in ['uso-dados', 'servicos', 'retencao', 'direitos', 'protecao'])
    assert 'Este pedido não autoriza campanhas de marketing.' in texto
    assert 'frame-ancestors' in aviso.headers['Content-Security-Policy']


def test_assets_locais_sao_servidos_sem_dependencias_externas(cliente):
    assert cliente.get('/static/pedido.css').status_code == 200
    script = cliente.get('/static/pedido.js')
    assert script.status_code == 200
    codigo = script.get_data(as_text=True)
    assert 'localStorage' not in codigo and 'sessionStorage' not in codigo and 'innerHTML' not in codigo
