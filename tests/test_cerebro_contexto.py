"""Memória editorial isolada: nenhum dado real, modelo ou serviço externo."""
from datetime import date, timedelta

import pytest

from src import cerebro, config


@pytest.fixture
def cofre(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path / 'ficticio.db'))
    cerebro.arquivo_inicio()
    return cerebro.diretorio()


def nota(cofre, nome, corpo, meta='atendimento: true'):
    caminho = cofre / 'Conhecimento' / (nome + '.md')
    caminho.write_text('---\n' + meta + '\n---\n# ' + nome + '\n\n' + corpo, encoding='utf-8')
    return caminho


def test_busca_assunto_sem_levar_notas_irrelevantes(cofre):
    nota(cofre, 'Trocas', 'Para trocar o tamanho, fale com a equipe da loja.')
    nota(cofre, 'Embalagem', 'Temos embalagem reciclável para presentes.')
    contexto = cerebro.instrucoes_contexto('Como funciona trocar o tamanho?')
    assert 'Para trocar o tamanho' in contexto
    assert 'embalagem reciclável' not in contexto
    assert 'Próxima, esperta' in contexto


def test_nota_relevante_apos_primeiras_quatorze_e_encontrada(cofre):
    for numero in range(20):
        nota(cofre, f'A {numero:02}', 'Embalagem de presente.')
    nota(cofre, 'Z Trocas', 'Política aprovada para trocas.')
    assert 'Política aprovada para trocas.' in cerebro.instrucoes_contexto('trocas')


def test_tags_acentos_prioridade_e_limite_de_notas(cofre):
    for numero in range(8):
        nota(cofre, f'Assunto {numero}', f'Referência editorial {numero}.',
             f'atendimento: true\ntags: garantia\nprioridade: {5 if numero == 7 else 1}')
    contexto = cerebro.instrucoes_contexto('GARANTÍA')
    assert 'Referência editorial 7.' in contexto
    assert contexto.index('Referência editorial 7.') < contexto.index('Referência editorial 0.')
    assert contexto.count('Referência editorial') == 6


@pytest.mark.parametrize('tags', ['tags: [garantia, troca]', 'tags:\n  - garantia\n  - troca', 'tags:\n- garantia\n- troca'])
def test_tags_da_interface_obsidian_tambem_selecionam_nota(cofre, tags):
    nota(cofre, 'Política', 'Instrução editorial revisada.', 'atendimento: true\n' + tags + '\nprioridade: 4')
    assert 'Instrução editorial revisada.' in cerebro.instrucoes_contexto('garantia')


@pytest.mark.parametrize('metadados', [
    'atendimento: false', 'atendimento: true\natendimento: false',
    'atendimento: true\nvalido_ate: data-invalida',
    'atendimento: true\nvalido_ate: 2000-01-01',
    'atendimento: true\nvalido_ate: 2999-01-01\nvalido_ate: 2000-01-01',
])
def test_ignora_rascunho_metadados_ambiguos_e_validade_invalida(cofre, metadados):
    nota(cofre, 'Garantia', 'Condição que não deve ser usada.', metadados)
    assert 'Condição que não deve ser usada.' not in cerebro.instrucoes_contexto('garantia')


def test_validade_inclusiva_e_atualizacao_sem_cache(cofre):
    caminho = nota(cofre, 'Garantia', 'Texto revisado hoje.', f'atendimento: true\nvalido_ate: {date.today().isoformat()}')
    assert 'Texto revisado hoje.' in cerebro.instrucoes_contexto('garantia')
    caminho.write_text('---\natendimento: true\nvalido_ate: ' + (date.today()-timedelta(days=1)).isoformat() + '\n---\nTexto expirado.', encoding='utf-8')
    assert 'Texto expirado.' not in cerebro.instrucoes_contexto('garantia')


def test_arquivo_grande_ou_invalido_nao_derruba_contexto(cofre):
    grande = nota(cofre, 'Grande', 'a' * (cerebro._MAX_LEITURA_NOTA + 1))
    binario = cofre / 'Conhecimento' / 'Binário.md'
    binario.write_bytes(b'---\natendimento: true\n---\n\xff\x00')
    assert cerebro._ler(grande) == ('', '')
    assert cerebro._ler(binario) == ('', '')
    assert cerebro.instrucoes_contexto('garantia')


def test_orcamento_inclui_cabecalhos_e_mantem_estilo(cofre):
    for numero in range(10):
        nota(cofre, f'Garantia {numero}', ('garantia revisão aprovada ' * 500))
    texto = cerebro.instrucoes_contexto('garantia')
    assert len(texto) <= cerebro._LIMITE_TOTAL
    assert texto.startswith('### Estilo de atendimento')


def test_leitura_de_estilo_nao_sai_do_cofre(cofre, tmp_path):
    fora = tmp_path / 'fora.md'
    fora.write_text('Conteúdo externo privado.', encoding='utf-8')
    assert cerebro._ler(fora) == ('', '')
    estilo = cofre / 'Estilo de atendimento.md'
    estilo.write_bytes(b'\xef\xbb\xbf# Minha voz\n\nUse o tom revisado por mim.\n')
    assert 'Use o tom revisado por mim.' in cerebro.instrucoes_estilo()


def test_cofre_existente_preserva_edicoes_e_nao_guarda_perguntas(cofre):
    estilo = cofre / 'Estilo de atendimento.md'
    estilo.write_text('# Voz da marca\n\nFale com calma e simplicidade.\n', encoding='utf-8')
    antes = {p.relative_to(cofre).as_posix(): p.read_bytes() for p in cofre.rglob('*') if p.is_file()}
    cerebro.instrucoes_contexto('Meu contato fictício é 5511999990022')
    assert antes == {p.relative_to(cofre).as_posix(): p.read_bytes() for p in cofre.rglob('*') if p.is_file()}
    assert cerebro.situacao()['consulta_por_assunto']


def test_revogacao_durante_a_consulta_nao_publica_rascunho(cofre, monkeypatch):
    caminho = nota(cofre, 'Garantia', 'Conteúdo anteriormente aprovado.')
    ler = cerebro._ler
    def editar_apos_leitura(arquivo):
        resultado = ler(arquivo)
        if arquivo == caminho and resultado[0].find('atendimento: true') >= 0:
            caminho.write_text('---\natendimento: false\n---\nRascunho privado.', encoding='utf-8')
        return resultado
    monkeypatch.setattr(cerebro, '_ler', editar_apos_leitura)
    assert 'Rascunho privado.' not in cerebro.instrucoes_contexto('garantia')


def test_ollama_recebe_apenas_notas_relevantes_sem_guardar_pergunta(cofre, monkeypatch):
    from src import ia
    nota(cofre, 'Trocas', 'Condições de troca revisadas.')
    nota(cofre, 'Presentes', 'Embalagens especiais.')
    monkeypatch.setattr(ia, '_system_prompt', lambda: 'Cadastro oficial e regras.')
    prompt = ia._system_prompt_ollama('Como são as trocas?')
    assert 'Condições de troca revisadas.' in prompt
    assert 'Embalagens especiais.' not in prompt
    assert 'Cadastro oficial e regras.' in prompt


def test_mapa_graph_liga_guias_e_so_conhecimento_revisado(cofre):
    nota(cofre, 'Trocas', 'Condições aprovadas para trocas.')
    nota(cofre, 'Rascunho', 'Texto ainda privado.', 'atendimento: false')
    nota(cofre, 'Vencida', 'Orientação vencida.', 'atendimento: true\nvalido_ate: 2000-01-01')
    cerebro.arquivo_inicio()
    mapa = (cofre / 'Mapa do atendimento.md').read_text(encoding='utf-8')
    for nome in ['Estilo de atendimento', 'Pedidos pelo WhatsApp', 'Conexão e página de pedidos', 'Conhecimento/Trocas', 'Modelos/Lista de estoque', 'Modelos/Conhecimento aprovado']:
        assert f'[[{nome}]]' in mapa
    assert 'Rascunho' not in mapa and 'Vencida' not in mapa
    assert 'atendimento: false' in mapa
    assert 'Mapa do atendimento.md' in [n['nome'] for n in cerebro.visualizacao()['notas']]
    assert 'Mapa atualizado pelo aplicativo' not in cerebro.instrucoes_contexto('trocas')
    (cofre / 'Conhecimento/Trocas.md').write_text('---\natendimento: false\n---\nEm revisão.', encoding='utf-8')
    cerebro.arquivo_inicio()
    assert 'Conhecimento/Trocas' not in (cofre / 'Mapa do atendimento.md').read_text(encoding='utf-8')


def test_mapa_preserva_index_e_edicao_manual_nao_reescreve_sem_mudanca(cofre):
    inicio = cofre / 'Início.md'
    inicio.write_text('# Meu índice\nTexto da equipe.', encoding='utf-8')
    mapa = cofre / 'Mapa do atendimento.md'
    antes = mapa.stat().st_mtime_ns
    cerebro.arquivo_inicio()
    assert mapa.stat().st_mtime_ns == antes
    assert inicio.read_text(encoding='utf-8') == '# Meu índice\nTexto da equipe.'
    mapa.write_text('# Mapa mantido pela equipe\n', encoding='utf-8')
    cerebro.arquivo_inicio()
    assert mapa.read_text(encoding='utf-8') == '# Mapa mantido pela equipe\n'


def test_mapa_nao_injeta_wikilinks_pelo_nome_da_nota(cofre):
    nota(cofre, 'Troca]] [[Rascunho', 'Condições de troca aprovadas.')
    cerebro.arquivo_inicio()
    assert 'Rascunho' not in (cofre / 'Mapa do atendimento.md').read_text(encoding='utf-8')
