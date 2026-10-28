"""Perguntas compostas respondidas pelo cadastro, sem inferência ou serviços."""
from unittest.mock import Mock

import pytest

from src import bot, config, ia
from src.db import init_db


@pytest.mark.parametrize('pergunta,esperado', [
    ('qual o horario e o endereco', ['1', '8']),
    ('oi, qual o horario e quais as formas de pagamento', ['1', '3']),
    ('qual e a taxa de entrega; onde fica a loja', ['7', '8']),
    ('qual o catalogo? qual o telefone', ['4', '5']),
    ('o horario e o horario', ['1']),
    ('qual o horario no feriado e o endereco', []),
    ('qual o horario e quem ganhou o jogo', []),
    ('o endereco e quanto tempo demora', []),
])
def test_pergunta_so_e_direta_quando_todos_os_trechos_sao_conhecidos(pergunta, esperado):
    assert bot._perguntas_diretas(pergunta) == esperado


def test_duas_informacoes_da_loja_saem_sem_modelo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticia.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    monkeypatch.setattr(config, 'MODO_TESTE', True)
    monkeypatch.setattr(config, 'HORARIO_FUNCIONAMENTO', '18h às 22h')
    monkeypatch.setattr(config, 'ENDERECO_RESTAURANTE', 'Rua Fictícia, 123')
    init_db(seed_cardapio=False)
    modelo = Mock(side_effect=AssertionError('Pergunta direta dispensa modelo'))
    monkeypatch.setattr(ia, 'responder', modelo)
    resposta = bot.processar_mensagem('5511999991234', 'Oi, qual o horário e o endereço?')
    assert '18h às 22h' in resposta and 'Rua Fictícia, 123' in resposta
    modelo.assert_not_called()
