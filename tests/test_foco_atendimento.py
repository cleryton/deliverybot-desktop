"""Foco local com catálogo fictício, sem modelo, banco, configurações ou serviços."""
from dataclasses import FrozenInstanceError
import re

import pytest

from src.foco_atendimento import resolver
from src import foco_atendimento


PRODUTOS = [
    {'nome': 'TESTE - X-Salada', 'preco': 22},
    {'nome': 'Refrigerante lata', 'preco': 6},
    {'nome': 'X-Salada família', 'preco': 35},
]


def cliente(texto):
    return {'role': 'user', 'content': texto}


def assistente(texto):
    return {'role': 'assistant', 'content': texto}


@pytest.mark.parametrize('nome', ['XSalada', 'X-Salada', 'X Salada', 'X_Salada', 'TESTE - X-Salada'])
def test_nome_equivalente_identifica_mesmo_produto(nome):
    foco = resolver(f'Quanto custa {nome}?', PRODUTOS)
    assert foco.produto_ids == (1,)
    assert foco.assunto == 'produto'
    assert foco.aspectos == frozenset({'preco'})
    assert not foco.esclarecer and not foco.retomada


def test_nome_com_variacao_nao_seleciona_tambem_o_item_base():
    foco = resolver('Quais ingredientes do X-Salada família?', PRODUTOS)
    assert foco.produto_ids == (3,)
    assert foco.aspectos == frozenset({'descricao'})


@pytest.mark.parametrize('pergunta,aspecto', [('e o preço?', 'preco'),
                                          ('Qual o preço?', 'preco'),
                                          ('Qual é o preço do produto?', 'preco'),
                                          ('e os ingredientes?', 'descricao'),
                                          ('e a garantia?', 'garantia')])
def test_continuacao_retoma_so_produto_escolhido_pelo_cliente(pergunta, aspecto):
    mensagens = [cliente('Quero saber sobre X-Salada'), assistente('Também temos Refrigerante lata.')]
    foco = resolver(pergunta, PRODUTOS, mensagens)
    assert foco.produto_ids == (1,) and foco.retomada
    assert foco.aspectos == frozenset({aspecto})
    assert 'TESTE - X-Salada' in foco.consulta
    assert foco.historico(mensagens) == [cliente('Quero saber sobre X-Salada')]


def test_oferta_do_assistente_nao_identifica_escolha_do_cliente():
    mensagens = [cliente('Olá'), assistente('Quer X-Salada?')]
    foco = resolver('e o preço?', PRODUTOS, mensagens)
    assert not foco.produto_ids and not foco.retomada
    assert foco.esclarecer and foco.historico(mensagens) == []


def test_cliente_muda_produto_e_referencia_mais_antiga_nao_e_retornada():
    foco = resolver('e os ingredientes?', PRODUTOS, [cliente('Quero X-Salada'),
                     assistente('Posso ajudar'), cliente('E Refrigerante lata?')])
    assert foco.produto_ids == (2,) and foco.retomada


@pytest.mark.parametrize('ultimo', ['Qual o horário?', 'Qual o endereço?',
                                  'Vamos falar sobre astronomia', 'Quero um pneu de carro'])
def test_mudanca_de_assunto_interrompe_busca_por_produto_antigo(ultimo):
    foco = resolver('e o preço?', PRODUTOS, [cliente('Quero X-Salada'), cliente(ultimo)])
    assert not foco.produto_ids and not foco.retomada
    assert foco.esclarecer


@pytest.mark.parametrize('pergunta,assunto,aspectos', [
    ('Qual o horário?', 'horario', {'horario'}),
    ('Qual o endereço?', 'endereco', {'endereco'}),
    ('Qual o telefone?', 'contato', {'contato'}),
    ('Aceitam Pix?', 'pagamento', {'pagamento'}),
    ('Qual a taxa de entrega?', 'entrega', {'entrega', 'preco'}),
    ('Quanto custa a entrega?', 'entrega', {'entrega', 'preco'}),
    ('Quero fazer um pedido, quanto custa a entrega?', 'entrega', {'entrega', 'preco', 'pedido'}),
    ('Qual o horário de entrega?', 'entrega', {'entrega', 'prazo'}),
    ('Qual o horário de retirada?', 'entrega', {'entrega', 'prazo'}),
    ('Qual o horário e endereço?', 'geral', {'horario', 'endereco'}),
])
def test_operacional_atual_nao_herda_produto(pergunta, assunto, aspectos):
    mensagens = [cliente('Quero X-Salada')]
    foco = resolver(pergunta, PRODUTOS, mensagens)
    assert foco.assunto == assunto and foco.aspectos == frozenset(aspectos)
    assert not foco.produto_ids and not foco.retomada and not foco.esclarecer
    assert foco.historico(mensagens) == []


def test_operacao_e_produto_compostos_preservam_todos_os_campos_pedidos():
    foco = resolver('Qual o preço do X-Salada e o horário?', PRODUTOS)
    assert foco.produto_ids == (1,)
    assert foco.aspectos == frozenset({'preco', 'horario'})


@pytest.mark.parametrize('pergunta', [
    'Não quero X-Salada, e Refrigerante lata?',
    'Não quero X-Salada, quero Refrigerante lata',
    'Quero Refrigerante lata, não X-Salada',
])
def test_produto_negado_nao_e_selecionado(pergunta):
    assert resolver(pergunta, PRODUTOS).produto_ids == (2,)


def test_negacao_de_disponibilidade_nao_e_recusa_de_produto():
    foco = resolver('Não tem X-Salada?', PRODUTOS)
    assert foco.produto_ids == (1,) and not foco.esclarecer


def test_negacao_sem_alternativa_pede_esclarecimento_sem_retomar():
    foco = resolver('Não quero X-Salada', PRODUTOS, [cliente('Quero X-Salada')])
    assert not foco.produto_ids and not foco.retomada and foco.esclarecer


def test_negacao_de_dois_itens_na_mesma_oracao_nao_escolhe_o_segundo():
    foco = resolver('Não quero X-Salada e Refrigerante lata', PRODUTOS)
    assert not foco.produto_ids and foco.esclarecer


def test_continuacao_apos_multiplos_produtos_nao_escolhe_um_aleatoriamente():
    mensagens = [cliente('Quero X-Salada e Refrigerante lata')]
    foco = resolver('e o preço?', PRODUTOS, mensagens)
    assert foco.produto_ids == () and not foco.retomada and foco.esclarecer


def test_consulta_explicitamente_composta_pode_conter_os_dois_produtos():
    foco = resolver('Quanto custa X-Salada e Refrigerante lata?', PRODUTOS)
    assert foco.produto_ids == (1, 2) and not foco.esclarecer


def test_produtos_com_mesmo_nome_pedem_variacao():
    foco = resolver('Quanto custa lanche?', [{'nome': 'Lanche'}, {'nome': 'Lanche'}])
    assert foco.produto_ids == (1, 2) and foco.esclarecer


def test_nomes_equivalentes_na_mesma_posicao_nao_perdem_um_id():
    foco = resolver('Quanto custa XSalada?', [{'nome': 'X-Salada'}, {'nome': 'XSalada'}])
    assert foco.produto_ids == (1, 2) and foco.esclarecer


def test_nomes_duplicados_sao_buscados_uma_vez_sem_esconder_ambiguidade():
    class Padrao:
        pattern = r'\blanche\b'
        chamadas = 0

        def finditer(self, texto):
            self.chamadas += 1
            return re.finditer(self.pattern, texto)

    padrao = Padrao()
    nomes = tuple((i, 'Lanche', ('lanche',), padrao) for i in range(1, 1001))
    ids, mencionados = foco_atendimento._produtos_citados('Quero lanche', nomes)
    assert ids == tuple(range(1, 1001)) and mencionados
    assert padrao.chamadas == 1


def test_atual_incluida_no_historico_e_removida_antes_de_resolver():
    mensagens = [cliente('Quero X-Salada'), assistente('Pode perguntar.'), cliente('e o preço?')]
    foco = resolver('e o preço?', PRODUTOS, mensagens)
    assert foco.retomada and foco.produto_ids == (1,)
    assert foco.historico(mensagens) == [cliente('Quero X-Salada')]


def test_entradas_agrupadas_respeitam_ultimo_assunto():
    mensagens = [cliente('Quero X-Salada\nQual o horário?\ne o preço?')]
    foco = resolver('e o preço?', PRODUTOS, mensagens)
    assert not foco.retomada and foco.esclarecer


def test_entradas_agrupadas_podem_retomar_o_ultimo_produto():
    mensagens = [cliente('Quero X-Salada\nQuero Refrigerante lata\ne o preço?')]
    foco = resolver('e o preço?', PRODUTOS, mensagens)
    assert foco.retomada and foco.produto_ids == (2,)
    assert foco.historico(mensagens) == [cliente('Quero Refrigerante lata')]


def test_historico_limitado_mantem_ancora_e_nao_inclui_atual():
    mensagens = ([cliente('Quero X-Salada')]
                 + [cliente('e os ingredientes?'), cliente('e a garantia?')] * 3
                 + [cliente('e o preço?')])
    foco = resolver('e o preço?', PRODUTOS, mensagens)
    historico = foco.historico(mensagens)
    assert foco.retomada and len(historico) == 4
    assert historico[0] == cliente('Quero X-Salada')
    assert all(m['content'] != 'e o preço?' for m in historico)


@pytest.mark.parametrize('resposta', ['sim', 'esse', 'isso', 'pode sim'])
def test_confirmacao_ambigua_nao_retorna_a_produto_mais_antigo(resposta):
    mensagens = [cliente('Quero X-Salada'), assistente('Quer Refrigerante lata?'), cliente(resposta)]
    foco = resolver('e o preço?', PRODUTOS, mensagens)
    assert not foco.produto_ids and not foco.retomada
    assert foco.esclarecer and foco.historico(mensagens) == []


@pytest.mark.parametrize('mensagens', [[], [assistente('Quer X-Salada?')],
                                     [cliente('Quero X-Salada e Refrigerante lata')]])
def test_preco_de_produto_nao_identificado_pede_uma_pergunta_dirigida(mensagens):
    foco = resolver('Quanto custa esse produto?', PRODUTOS, mensagens)
    assert foco.assunto == 'produto' and foco.aspectos == frozenset({'preco'})
    assert foco.produto_ids == () and foco.esclarecer == 'De qual produto você quer saber?'


def test_catalogo_do_retrato_atual_nao_retoma_produto_removido():
    foco = resolver('e o preço?', PRODUTOS[1:], [cliente('Quero X-Salada')])
    assert not foco.produto_ids and not foco.retomada and foco.esclarecer


def test_historico_de_outra_consulta_nao_herda_referencia():
    foco = resolver('e o preço?', PRODUTOS, [cliente('Quero X-Salada')])
    assert foco.historico([cliente('Qual o horário?')]) == []


def test_retrato_e_imutavel_e_nao_altera_entradas():
    produtos = [dict(p) for p in PRODUTOS]
    mensagens = [cliente('Quero X-Salada')]
    foco = resolver('e o preço?', produtos, mensagens)
    with pytest.raises(FrozenInstanceError):
        foco.assunto = 'outro'
    assert produtos == PRODUTOS and mensagens == [cliente('Quero X-Salada')]


def test_catalogo_generico_nao_e_um_pedido_confirmado():
    foco = resolver('Quero ver o cardápio', PRODUTOS)
    assert foco.assunto == 'catalogo' and foco.aspectos == frozenset({'catalogo'})
    assert not foco.produto_ids and not foco.esclarecer
