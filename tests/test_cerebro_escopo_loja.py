"""Conhecimento categorizado acompanha o perfil ativo sem alterar notas da loja."""
import pytest

from src import cerebro, config


@pytest.fixture
def cofre(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'cofre-segmento.db'))
    monkeypatch.setattr(config, 'COMERCIO_CONFIGURADO', 'SIM')
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Lanchonete')
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', '')
    monkeypatch.setattr(config, 'COMERCIO_MODELO', 'PRODUCAO')
    cerebro.arquivo_inicio()
    return cerebro.diretorio()


def nota(cofre, nome, corpo, categoria=None):
    categoria = '' if categoria is None else '\ncategoria_atendimento: ' + categoria
    caminho = cofre / 'Conhecimento' / (nome + '.md')
    caminho.write_text('---\natendimento: true\ntags: [garantia]\n' + categoria +
                       '\n---\n' + corpo, encoding='utf-8')
    return caminho


def test_nota_de_outro_segmento_nao_entra_mesmo_com_tag_relevante(cofre):
    nota(cofre, 'Condição de oficina', 'CONTEUDO_EXCLUSIVO_OFICINA', 'OFICINA')
    nota(cofre, 'Condição de alimentos', 'CONTEUDO_EXCLUSIVO_ALIMENTACAO', 'ALIMENTACAO')
    contexto = cerebro.instrucoes_contexto('Qual a garantia?')
    assert 'CONTEUDO_EXCLUSIVO_ALIMENTACAO' in contexto
    assert 'CONTEUDO_EXCLUSIVO_OFICINA' not in contexto
    nomes = [n['nome'] for n in cerebro.visualizacao()['notas']]
    assert not any('Condição de oficina' in nome for nome in nomes)


@pytest.mark.parametrize('categoria', [
    '', 'DESCONHECIDO', 'ALIMENTACAO\ncategoria_atendimento: OFICINA',
    'ALIMENTACAO\ncategoria_atendimento: ALIMENTACAO',
])
def test_categoria_vazia_desconhecida_ou_repetida_nao_e_aprovada(cofre, categoria):
    nota(cofre, 'Revisão necessária', 'CONTEUDO_NAO_AUTORIZADO', categoria)
    assert 'CONTEUDO_NAO_AUTORIZADO' not in cerebro.instrucoes_contexto('garantia')


def test_nota_geral_e_estilo_permanecem_disponiveis(cofre):
    nota(cofre, 'Atendimento geral', 'REFERENCIA_GERAL_APROVADA')
    (cofre / 'Estilo de atendimento.md').write_text('# Estilo\nVOZ_GERAL_DA_EQUIPE', encoding='utf-8')
    contexto = cerebro.instrucoes_contexto('garantia')
    assert 'REFERENCIA_GERAL_APROVADA' in contexto
    assert 'VOZ_GERAL_DA_EQUIPE' in contexto


def test_mudanca_de_perfil_e_revogacao_refletem_na_proxima_leitura(cofre, monkeypatch):
    alimentos = nota(cofre, 'Alimentos', 'NOTA_DA_LANCHONETE', 'ALIMENTACAO')
    oficina = nota(cofre, 'Oficina', 'NOTA_DA_OFICINA', 'OFICINA')
    originais = {p: p.read_bytes() for p in (alimentos, oficina)}
    assert 'NOTA_DA_LANCHONETE' in cerebro.instrucoes_contexto('garantia')
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Oficina mecânica')
    contexto = cerebro.instrucoes_contexto('garantia')
    assert 'NOTA_DA_OFICINA' in contexto and 'NOTA_DA_LANCHONETE' not in contexto
    assert all(p.read_bytes() == conteudo for p, conteudo in originais.items())
    oficina.write_text(oficina.read_text(encoding='utf-8').replace('atendimento: true', 'atendimento: false'), encoding='utf-8')
    assert 'NOTA_DA_OFICINA' not in cerebro.instrucoes_contexto('garantia')


def test_categoria_revogada_entre_selecao_e_leitura_final_nao_entra(cofre, monkeypatch):
    caminho = nota(cofre, 'Condição', 'NOTA_REVOGADA_DURANTE_LEITURA', 'ALIMENTACAO')
    selecionar = cerebro._notas_aprovadas

    def revogar(pasta):
        candidatas = selecionar(pasta)
        caminho.write_text(caminho.read_text(encoding='utf-8').replace('ALIMENTACAO', 'OFICINA'), encoding='utf-8')
        return candidatas

    monkeypatch.setattr(cerebro, '_notas_aprovadas', revogar)
    assert 'NOTA_REVOGADA_DURANTE_LEITURA' not in cerebro.instrucoes_contexto('garantia')
