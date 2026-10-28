"""Escopo por loja com modelos e catálogo fictícios, sem transportes reais."""
from unittest.mock import Mock

import pytest

from src import cardapio, cerebro, config, ia, protecao_ia
from src.db import get_conn, init_db


TELEFONE = '5500000007744'
LANCHES = [{'nome': 'X-Salada', 'categoria': 'Lanches', 'preco': 22},
           {'nome': 'Refrigerante lata', 'categoria': 'Bebidas', 'preco': 6}]
PECAS = [{'nome': 'Pneu urbano', 'categoria': 'Oficina', 'preco': 120}]


@pytest.fixture(autouse=True)
def loja(tmp_path, monkeypatch):
    for chave, valor in {
        'DATABASE_PATH': str(tmp_path / 'escopo-por-loja.db'),
        'SEED_CATALOGO': False, 'WHATSAPP_PROVIDER': 'TESTE', 'MODO_TESTE': True,
        'IA_PROVIDER': 'OLLAMA', 'OLLAMA_URL': 'http://localhost:11434',
        'LGPD_IA_EXTERNA': 'SIM', 'ANTHROPIC_API_KEY': '',
        'COMERCIO_CONFIGURADO': 'SIM', 'COMERCIO_SEGMENTO': 'Lanchonete',
        'COMERCIO_DESCRICAO': 'Lanches preparados sob pedido e bebidas',
        'COMERCIO_MODELO': 'PRODUCAO', 'NOME_RESTAURANTE': 'Loja fictícia',
    }.items():
        monkeypatch.setattr(config, chave, valor)
    produtos = Mock(return_value=[dict(p) for p in LANCHES])
    monkeypatch.setattr(cardapio, 'listar_produtos_ativos', produtos)
    init_db(seed_cardapio=False)
    ia.invalidar_cache_prompt()
    yield produtos
    ia.invalidar_cache_prompt()


@pytest.mark.parametrize('segmento,pergunta', [
    ('Lanchonete', 'Vocês vendem peças para carro?'),
    ('Lanchonete', 'Qual o preço para reparar o motor?'),
    ('Lanchonete', 'Quero 2 pneus'),
    ('Lanchonete', 'Vocês têm ração para gato?'),
    ('Lanchonete', 'Qual tamanho da camiseta?'),
    ('Oficina mecânica', 'Tem opção sem lactose?'),
    ('Oficina mecânica', 'Quais ingredientes do hambúrguer?'),
    ('Loja de roupas', 'Vocês fazem balanceamento do carro?'),
    ('Pet shop', 'Qual sabor da pizza?'),
    ('Papelaria', 'Vocês consertam celular?'),
])
def test_assunto_de_outro_segmento_nao_chama_modelo_nem_cofre(monkeypatch, segmento, pergunta):
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', segmento)
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', segmento)
    modelo = Mock(side_effect=AssertionError('Não iniciar inferência alheia à loja'))
    notas = Mock(side_effect=AssertionError('Não ler Obsidian para outro segmento'))
    monkeypatch.setattr(ia, '_responder_ollama', modelo)
    monkeypatch.setattr(cerebro, 'instrucoes_contexto', notas)
    assert ia.responder(TELEFONE, pergunta) == ia.RESPOSTA_FORA_ESCOPO
    modelo.assert_not_called()
    notas.assert_not_called()
    assert not protecao_ia.bloqueado(TELEFONE)


@pytest.mark.parametrize('segmento,pergunta', [
    ('Lanchonete', 'Tem opção sem lactose?'),
    ('Lanchonete', 'Quais ingredientes do X-Salada?'),
    ('Lanchonete', 'Tem cachorro-quente?'),
    ('Lanchonete', 'Vocês aceitam vale refeição?'),
    ('Oficina mecânica', 'Esse filtro serve em qual veículo?'),
    ('Oficina mecânica', 'Quanto custa a troca de pneus?'),
    ('Loja de roupas', 'Quais cores de camiseta vocês têm?'),
    ('Loja de roupas', 'Como escolher o tamanho do vestido?'),
    ('Pet shop', 'Vocês vendem ração para gatos?'),
    ('Pet shop', 'Como agendo banho e tosa?'),
])
def test_duvidas_do_segmento_configurado_seguem_para_ia(monkeypatch, segmento, pergunta):
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', segmento)
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', segmento)
    modelo = Mock(return_value='A equipe pode confirmar esse detalhe do cadastro.')
    monkeypatch.setattr(ia, '_responder_ollama', modelo)
    assert ia.responder(TELEFONE, pergunta) == modelo.return_value
    modelo.assert_called_once_with(TELEFONE, pergunta)


def test_item_antigo_de_outra_atividade_nao_muda_o_perfil(loja):
    loja.return_value += PECAS
    assert not ia.assunto_negocio('Vocês vendem pneu urbano?')
    assert ia.assunto_negocio('Quais ingredientes do X-Salada?')


def test_perfil_misto_permite_so_atividades_cadastradas(monkeypatch, loja):
    monkeypatch.setattr(config, 'COMERCIO_MODELO', 'MISTO')
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Lanchonete e oficina')
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', 'Lanches e peças automotivas')
    loja.return_value += PECAS
    assert ia.assunto_negocio('Quero saber os ingredientes do lanche')
    assert ia.assunto_negocio('Qual o preço do pneu urbano?')
    assert not ia.assunto_negocio('Vocês vendem ração para gato?')


def test_catalogo_amplia_atividade_somente_quando_operacao_e_mista(monkeypatch, loja):
    loja.return_value += PECAS
    assert not ia.assunto_negocio('Qual pneu vocês vendem?')
    monkeypatch.setattr(config, 'COMERCIO_MODELO', 'MISTO')
    assert ia.assunto_negocio('Qual pneu vocês vendem?')


@pytest.mark.parametrize('pergunta', ['produto', 'loja', 'serviço',
                                   'Me fale qualquer coisa sobre a loja'])
def test_assunto_vago_pede_esclarecimento_sem_inferencia(monkeypatch, pergunta):
    modelo = Mock(side_effect=AssertionError('Não inferir um tema não indicado'))
    monkeypatch.setattr(ia, '_responder_ollama', modelo)
    assert ia.responder(TELEFONE, pergunta) == ia.RESPOSTA_FORA_ESCOPO
    modelo.assert_not_called()
    assert not protecao_ia.bloqueado(TELEFONE)


@pytest.mark.parametrize('pergunta', ['Qual o horário e o que é um qubit?',
                                   'Quero um X-Salada e explique fotossíntese',
                                   'Qual o horário e qual o preço da troca de pneus?'])
def test_parte_comercial_nao_autoriza_pergunta_externa(pergunta):
    assert not ia.assunto_negocio(pergunta)


@pytest.mark.parametrize('segmento,permitido', [('Lanchonete', True), ('Oficina mecânica', False)])
def test_oleo_alimentar_nao_e_confundido_com_manutencao(monkeypatch, segmento, permitido):
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', segmento)
    assert ia.assunto_negocio('Qual óleo vocês usam na fritura?') is permitido
    assert ia.assunto_negocio('A troca de óleo da fritura é diária?') is permitido


@pytest.mark.parametrize('pergunta', ['qual o horário?', 'aceitam Pix?', 'onde fica?',
                                   'quais produtos vocês têm?', 'quero comprar', 'me sugira um produto'])
def test_consulta_operacional_fechada_nao_percorre_catalogo(loja, pergunta):
    loja.reset_mock()
    assert ia.assunto_negocio(pergunta)
    loja.assert_not_called()


def test_prompt_nao_guarda_catalogo_invalidado_durante_a_montagem(monkeypatch, loja):
    def consultar():
        ia.invalidar_cache_prompt()
        return LANCHES
    loja.side_effect = consultar
    assert 'X-Salada' in ia._system_prompt()
    assert ia._cache_prompt['texto'] is None


def test_tipo_desconhecido_usa_catalogo_atual_e_operacao(monkeypatch, loja):
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Ateliê de vitrais')
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', 'Criação artesanal sob pedido')
    loja.return_value = [{'nome': 'Vitral Aurora', 'categoria': 'Arte', 'preco': 100}]
    assert ia.assunto_negocio('Qual o preço do Vitral Aurora?')
    assert ia.assunto_negocio('Como pago?')
    assert not ia.assunto_negocio('Quais ingredientes da pizza?')
    loja.return_value = []
    assert not ia.assunto_negocio('Tem Vitral Aurora?')


def test_perfil_vazio_sem_catalogo_nao_se_torna_assistente_geral(monkeypatch, loja):
    monkeypatch.setattr(config, 'COMERCIO_CONFIGURADO', 'NAO')
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', '')
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', '')
    loja.return_value = []
    assert ia.assunto_negocio('Como pago?')
    assert ia.assunto_negocio('Preciso de um atendente')
    assert not ia.assunto_negocio('Quais ingredientes do lanche?')
    assert not ia.assunto_negocio('Quem inventou o avião?')


def test_mudanca_de_perfil_vale_na_proxima_mensagem(monkeypatch):
    assert not ia.assunto_negocio('Qual o preço do pneu?')
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Oficina mecânica')
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', 'Manutenção automotiva')
    assert ia.assunto_negocio('Qual o preço do pneu?')
    assert not ia.assunto_negocio('Tem hambúrguer sem lactose?')


def test_continuacao_curta_exige_referencia_compativel_com_loja():
    assert not ia.assunto_negocio('sim', mensagens=[
        {'role': 'assistant', 'content': 'Qual pneu você quer para seu carro?'}])
    assert ia.assunto_negocio('sim', mensagens=[
        {'role': 'assistant', 'content': 'Quer conhecer os ingredientes do lanche?'}])


def test_historico_de_ambos_os_lados_filtra_segmento_anterior(monkeypatch):
    mensagens = [('ENTRADA', 'Quais pneus vocês vendem?'),
                ('SAIDA', 'Oferecemos pneus para carros.'),
                ('ENTRADA', 'Quais ingredientes do X-Salada?'),
                ('SAIDA', 'A equipe pode confirmar os ingredientes.')]
    with get_conn() as c:
        c.executemany('INSERT INTO mensagens(telefone,direcao,conteudo) VALUES(?,?,?)',
                      [(TELEFONE, d, t) for d, t in mensagens])
    historico = ia._historico_mensagens(TELEFONE)
    assert [m['content'] for m in historico] == [t for _, t in mensagens[2:]]
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Oficina')
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', 'Manutenção automotiva')
    assert [m['content'] for m in ia._historico_mensagens(TELEFONE)] == [t for _, t in mensagens[:2]]


@pytest.mark.parametrize('provedor,metodo', [('OLLAMA', '_responder_ollama'),
                                         ('ANTHROPIC', '_responder_anthropic')])
@pytest.mark.parametrize('resposta', ['Nossa oficina faz balanceamento e troca de pneus.',
                                   'A fotossíntese transforma energia luminosa em energia química.'])
def test_saida_fora_do_segmento_e_descartada_sem_segunda_inferencia(monkeypatch, provedor, metodo, resposta):
    monkeypatch.setattr(config, 'IA_PROVIDER', provedor)
    modelo = Mock(return_value=resposta)
    monkeypatch.setattr(ia, metodo, modelo)
    assert ia.responder(TELEFONE, 'Quais ingredientes do X-Salada?') == ia.RESPOSTA_FORA_ESCOPO
    modelo.assert_called_once()
    assert not protecao_ia.bloqueado(TELEFONE)


def test_resposta_legitima_com_pergunta_curta_nao_e_descartada(monkeypatch):
    resposta = 'Posso ajudar a escolher. Qual sabor de hambúrguer você prefere?'
    monkeypatch.setattr(ia, '_responder_ollama', Mock(return_value=resposta))
    assert ia.responder(TELEFONE, 'Quais lanches vocês têm?') == resposta


def test_mudanca_de_perfil_durante_geracao_descarta_contexto_anterior(monkeypatch):
    def gerar(*_):
        monkeypatch.setattr(config, 'NOME_RESTAURANTE', 'Outra loja fictícia')
        return 'A equipe pode confirmar esse detalhe.'
    modelo = Mock(side_effect=gerar)
    monkeypatch.setattr(ia, '_responder_ollama', modelo)
    assert ia.responder(TELEFONE, 'Quais ingredientes do X-Salada?') == ia.RESPOSTA_FORA_ESCOPO
    modelo.assert_called_once()


def test_mudanca_de_catalogo_durante_geracao_descarta_contexto_anterior(monkeypatch, loja):
    def gerar(*_):
        loja.return_value = []
        ia.invalidar_cache_prompt()
        return 'O catálogo oferece esse item.'
    modelo = Mock(side_effect=gerar)
    monkeypatch.setattr(ia, '_responder_ollama', modelo)
    assert ia.responder(TELEFONE, 'Quais ingredientes do X-Salada?') == ia.RESPOSTA_FORA_ESCOPO
    modelo.assert_called_once()


def test_prompt_muda_imediatamente_com_perfil_sem_aguardar_cache(monkeypatch):
    monkeypatch.setattr(ia.time, 'monotonic', lambda: 100.0)
    antes = ia._system_prompt()
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Oficina mecânica')
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', 'Manutenção automotiva')
    depois = ia._system_prompt()
    assert antes != depois
    assert 'ESCOPO ESPECÍFICO DESTA LOJA' in depois
    assert 'Oficina mecânica' in depois


def test_prompt_nao_oferece_item_legado_de_outro_segmento(loja):
    loja.return_value += PECAS + [{'nome': 'Filtro de óleo', 'categoria': 'Peças', 'preco': 40}]
    prompt = ia._system_prompt()
    assert 'X-Salada' in prompt
    assert 'Pneu urbano' not in prompt
    assert 'Filtro de óleo' not in prompt
