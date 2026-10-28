"""Fronteira do segmento no roteador real, sem modelos ou contas externas."""
from unittest.mock import Mock

import pytest

from src import bot, cerebro, config, estoque, ia, publicacao
from src.db import get_conn, init_db


TELEFONE = '5500000007722'


@pytest.fixture(autouse=True)
def loja(tmp_path, monkeypatch):
    for chave, valor in {
        'DATABASE_PATH': str(tmp_path / 'escopo-loja-fluxo.db'),
        'SEED_CATALOGO': False, 'WHATSAPP_PROVIDER': 'TESTE', 'MODO_TESTE': True,
        'IA_PROVIDER': 'OLLAMA', 'RATE_LIMIT_SEGUNDOS': 0,
        'COMERCIO_CONFIGURADO': 'SIM', 'COMERCIO_SEGMENTO': 'Lanchonete',
        'COMERCIO_DESCRICAO': 'Lanches preparados sob pedido e bebidas',
        'COMERCIO_MODELO': 'PRODUCAO', 'FORMAS_PAGAMENTO': 'Pix,Dinheiro',
        'BASE_URL': 'https://loja-ficticia.example', 'TAXA_ENTREGA': 5.0,
        'HORARIO_FUNCIONAMENTO': 'Das 18h às 22h',
        'ENDERECO_RESTAURANTE': 'Rua Fictícia, 123',
    }.items():
        monkeypatch.setattr(config, chave, valor)
    monkeypatch.setattr(publicacao, '_gerente', None)
    init_db(seed_cardapio=False)
    estoque.salvar_produto({'nome': 'X-Salada', 'categoria': 'Lanches',
                           'preco': 22, 'controlar_estoque': False})
    estoque.salvar_produto({'nome': 'Refrigerante lata', 'categoria': 'Bebidas',
                           'preco': 6, 'estoque': 10})
    bot._ultima_chamada_ia.clear()
    ia.invalidar_cache_prompt()
    yield
    bot._ultima_chamada_ia.clear()
    ia.invalidar_cache_prompt()


def impedir_inferencia(monkeypatch):
    modelo = Mock(side_effect=AssertionError('Não chamar modelo neste fluxo'))
    notas = Mock(side_effect=AssertionError('Não ler cofre neste fluxo'))
    monkeypatch.setattr(ia, 'responder', modelo)
    monkeypatch.setattr(cerebro, 'instrucoes_contexto', notas)
    return modelo, notas


@pytest.mark.parametrize('segmento,texto', [
    ('Lanchonete', 'Vocês fazem troca de pneu?'),
    ('Lanchonete', 'Qual o preço da revisão do motor?'),
    ('Lanchonete', 'Vocês vendem ração?'),
    ('Lanchonete', 'Qual o tamanho da camiseta?'),
    ('Oficina mecânica', 'Vocês têm hambúrguer sem lactose?'),
    ('Oficina mecânica', 'Quais ingredientes da pizza?'),
    ('Loja de roupas', 'Como agendo troca de óleo?'),
])
def test_outro_segmento_nao_chega_ao_modelo_ou_cofre(monkeypatch, segmento, texto):
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', segmento)
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', segmento)
    # Cada cenário usa somente o catálogo coerente com seu próprio segmento.
    if segmento != 'Lanchonete':
        with get_conn() as conn:
            conn.execute('UPDATE produtos SET ativo=0')
    modelo, notas = impedir_inferencia(monkeypatch)
    resposta = bot.processar_mensagem(TELEFONE, texto)
    assert resposta.startswith(ia.RESPOSTA_FORA_ESCOPO)
    modelo.assert_not_called()
    notas.assert_not_called()
    with get_conn() as conn:
        assert conn.execute('SELECT count(*) FROM pedidos').fetchone()[0] == 0


@pytest.mark.parametrize('texto', [
    'Qual o preço da troca de pneus e o horário da loja?',
    'Vocês vendem ração e aceitam Pix?',
    'Quero saber os ingredientes da pizza e como fazer um código Python',
])
def test_uma_pergunta_comercial_nao_libera_outro_assunto(monkeypatch, texto):
    modelo, notas = impedir_inferencia(monkeypatch)
    atalho = Mock(side_effect=AssertionError('Triar antes de responder atalhos'))
    monkeypatch.setattr(bot, '_resposta_rapida', atalho)
    resposta = bot.processar_mensagem(TELEFONE, texto)
    assert resposta.startswith(ia.RESPOSTA_FORA_ESCOPO)
    atalho.assert_not_called()
    modelo.assert_not_called()
    notas.assert_not_called()


@pytest.mark.parametrize('texto,esperado', [
    ('qual o horário?', '18h'), ('onde fica?', 'Rua Fictícia'),
    ('aceitam Pix?', 'Pix'), ('privacidade', 'Usamos seus dados'),
    ('atendente', 'atendimento humano'), ('oi', 'Boas-vindas'),
    ('quanto custa o X-Salada?', '22,00'),
])
def test_informacoes_da_loja_continuam_locais_e_rapidas(monkeypatch, texto, esperado):
    modelo, notas = impedir_inferencia(monkeypatch)
    assert esperado in bot.processar_mensagem(TELEFONE, texto)
    modelo.assert_not_called()
    notas.assert_not_called()


def test_compra_na_conversa_preserva_campos_livres_e_confirmacao(monkeypatch):
    modelo, notas = impedir_inferencia(monkeypatch)
    def enviar(texto):
        return bot.processar_mensagem(TELEFONE, texto)

    assert 'produtos' in enviar('pedido pelo WhatsApp')
    assert 'chamar' in enviar('2 X-Salada e 1 Refrigerante lata')
    assert 'entrega ou retirada' in enviar('Cliente Fictício')
    assert 'endereço' in enviar('entrega')
    # Nome de rua pode mencionar outro comércio: continua sendo um campo do
    # pedido validado localmente, sem ampliar o contexto do modelo.
    assert 'pagar' in enviar('Rua da Oficina, 123, Centro')
    assert 'CONFIRMAR' in enviar('Dinheiro')
    assert 'realizado com sucesso' in enviar('confirmar')
    with get_conn() as conn:
        pedido = conn.execute('SELECT * FROM pedidos').fetchone()
        assert pedido['total_pedido'] == 55
        assert conn.execute('SELECT count(*) FROM pedidos').fetchone()[0] == 1
        assert conn.execute("SELECT estoque FROM produtos WHERE nome='Refrigerante lata'").fetchone()[0] == 9
    modelo.assert_not_called()
    notas.assert_not_called()
