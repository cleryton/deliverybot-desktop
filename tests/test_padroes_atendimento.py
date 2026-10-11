"""Padrões editoriais isolados; sem modelos, contas ou dados reais."""
from pathlib import Path

import pytest

from src import cerebro, config, padroes_atendimento as padroes


@pytest.fixture
def loja(tmp_path, monkeypatch):
    for chave, valor in {'DATABASE_PATH': str(tmp_path/'ficticio.db'),
                         'COMERCIO_CONFIGURADO': 'SIM', 'COMERCIO_SEGMENTO': 'Pizzaria',
                         'COMERCIO_DESCRICAO': 'Alimentos preparados por encomenda.',
                         'COMERCIO_MODELO': 'PRODUCAO'}.items():
        monkeypatch.setattr(config, chave, valor)
    cerebro.arquivo_inicio()
    return cerebro.diretorio()


def arquivo(loja, nome='Perfil.md', categoria='ALIMENTACAO'):
    return loja/'Atendimentos'/padroes.PERFIS[categoria][0]/nome


@pytest.mark.parametrize('segmento,modelo,esperada', [
    ('Restaurante','PRODUCAO','ALIMENTACAO'), ('Pizzaria','REVENDA','ALIMENTACAO'),
    ('Moda e acessórios','REVENDA','MODA'), ('Informática','SERVICOS','ELETRONICOS'),
    ('Oficina mecânica','MISTO','OFICINA'), ('Auto peças','REVENDA','OFICINA'),
    ('Papelaria','REVENDA','REVENDA'), ('Artesanato','PRODUCAO','PRODUCAO'),
    ('Consultoria','SERVICOS','SERVICOS'), ('Comércio misto','MISTO','MISTO'),
    ('Moda e informática','REVENDA','MISTO'), ('Outro','INVALIDO','GERAL'),
])
def test_categoria_da_loja(segmento, modelo, esperada, monkeypatch):
    monkeypatch.setattr(config, 'COMERCIO_CONFIGURADO', 'SIM')
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', segmento)
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', '')
    monkeypatch.setattr(config, 'COMERCIO_MODELO', modelo)
    assert padroes.categoria() == esperada


def test_descricao_como_apoio_e_segmento_tem_preferencia(loja, monkeypatch):
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', 'Oficina e informática')
    assert padroes.categoria() == 'ALIMENTACAO'
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Outro')
    assert padroes.categoria() == 'MISTO'
    monkeypatch.setattr(config, 'COMERCIO_DESCRICAO', 'Oficina especializada')
    assert padroes.categoria() == 'OFICINA'
    monkeypatch.setattr(config, 'COMERCIO_CONFIGURADO', 'NAO')
    assert padroes.categoria() == 'GERAL'


@pytest.mark.parametrize('mensagem,esperada', [
    ('Olá!', 'recepcao'), ('bom dia', 'recepcao'), ('Oi, quero uma pizza', 'escolha'),
    ('Qual o horário de funcionamento?', 'duvidas'), ('Vocês fazem entrega?', 'duvidas'),
    ('Tem tamanho pequeno?', 'duvidas'), ('Quero conhecer as opções', 'escolha'),
    ('Orçamento', 'escolha'), ('Confirme, pagarei em dinheiro', 'fechamento'),
    ('Quero agendar', 'fechamento'), ('Meu pedido já saiu?', 'pos_venda'),
    ('Já paguei com Pix', 'pos_venda'), ('Quero trocar a peça', 'pos_venda'),
    ('Meu pedido está quebrado', 'humano'), ('Quero falar com alguém', 'humano'),
    ('Reclamação', 'humano'), ('', 'duvidas'),
])
def test_etapa_editorial(mensagem, esperada):
    assert padroes.etapa(mensagem) == esperada


@pytest.mark.parametrize('categoria', list(padroes.PERFIS))
def test_todos_modelos_tem_perfil_e_seis_etapas_identificadas(categoria):
    notas = padroes.arquivos(categoria)
    assert len(notas) == 7
    etapas = {'Perfil.md': 'perfil', **{v[0]: k for k, v in padroes.ETAPAS.items()}}
    for nome, texto in notas.items():
        meta, _ = cerebro._remover_frontmatter(texto)
        assert cerebro._aprovada(meta)
        assert cerebro._metadado(meta, 'categoria_atendimento') == categoria
        assert cerebro._metadado(meta, 'etapa_atendimento') == etapas[nome]
        assert Path(nome).name == nome


def test_so_cria_categoria_ativa_e_guia(loja):
    base = loja/'Atendimentos'
    assert {p.name for p in base.iterdir()} == {'Como personalizar.md','Restaurantes e alimentos'}
    assert len(list(arquivo(loja).parent.glob('*.md'))) == 7
    assert cerebro.situacao()['atendimento'] == {'categoria': 'ALIMENTACAO', 'titulo': 'Restaurantes e alimentos', 'padroes': 7}


def test_contexto_so_perfil_e_etapa_correspondente(loja):
    contexto = cerebro.instrucoes_contexto('Quero conhecer as opções')
    assert '### Atendimentos/Restaurantes e alimentos/Perfil.md' in contexto
    assert '### Atendimentos/Restaurantes e alimentos/03 Escolha.md' in contexto
    for slug, (nome, _, _) in padroes.ETAPAS.items():
        if slug != 'escolha':
            assert '### Atendimentos/Restaurantes e alimentos/' + nome not in contexto
    assert '### Estilo de atendimento' in contexto
    assert 'Mapa atualizado pelo aplicativo' not in contexto
    assert '## Uma nota para cada atendimento' not in contexto


def test_troca_de_segmento_preserva_edicoes_e_isola_categoria(loja, monkeypatch):
    original = arquivo(loja)
    original.write_text(original.read_text(encoding='utf-8') + '\nOrientação exclusiva da pizzaria.', encoding='utf-8')
    conteudo = original.read_bytes()
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Oficina mecânica')
    contexto = cerebro.instrucoes_contexto('Quero uma pizza')
    assert '### Atendimentos/Oficinas e peças/Perfil.md' in contexto
    assert 'Orientação exclusiva da pizzaria' not in contexto
    assert original.read_bytes() == conteudo
    assert arquivo(loja, categoria='OFICINA').is_file()
    notas = cerebro.visualizacao()['notas']
    assert not any('Restaurantes e alimentos/' in n['nome'] for n in notas)
    mapa = (loja/'Mapa do atendimento.md').read_text(encoding='utf-8')
    assert '[[Atendimentos/Oficinas e peças/Perfil]]' in mapa
    assert 'Atendimentos/Restaurantes e alimentos/' not in mapa
    monkeypatch.setattr(config, 'COMERCIO_SEGMENTO', 'Pizzaria')
    assert 'Orientação exclusiva da pizzaria' in cerebro.instrucoes_contexto('oi')


def test_edicao_refletida_sem_regravar_nem_copiar_mensagem(loja):
    caminho = arquivo(loja, '02 Dúvidas.md')
    caminho.write_text(caminho.read_text(encoding='utf-8') + '\nFale com calma e explique uma opção de cada vez.', encoding='utf-8')
    cerebro.arquivo_inicio()
    antes = {p.relative_to(loja).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns) for p in loja.rglob('*.md')}
    assert 'Fale com calma e explique uma opção de cada vez.' in cerebro.instrucoes_contexto('Meu contato fictício: 5511999990022')
    assert antes == {p.relative_to(loja).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns) for p in loja.rglob('*.md')}


@pytest.mark.parametrize('antigo,novo', [
    ('atendimento: true','atendimento: false'),
    ('atendimento: true','atendimento: true\natendimento: false'),
    ('atendimento: true','atendimento: true\nvalido_ate: 2000-01-01'),
    ('atendimento: true','atendimento: true\nvalido_ate: inválido'),
    ('categoria_atendimento: ALIMENTACAO','categoria_atendimento: OFICINA'),
    ('categoria_atendimento: ALIMENTACAO','categoria_atendimento: ALIMENTACAO\ncategoria_atendimento: OFICINA'),
    ('etapa_atendimento: duvidas','etapa_atendimento: fechamento'),
])
def test_padrao_invalido_fica_fora_do_contexto_leitor_e_mapa(loja, antigo, novo):
    caminho = arquivo(loja, '02 Dúvidas.md')
    texto = caminho.read_text(encoding='utf-8').replace(antigo, novo) + '\nORIENTACAO_SUSPENSA'
    caminho.write_text(texto, encoding='utf-8')
    assert 'ORIENTACAO_SUSPENSA' not in cerebro.instrucoes_contexto('Tem opções pequenas?')
    assert caminho.relative_to(loja).as_posix() not in [n['nome'] for n in cerebro.visualizacao()['notas']]
    assert '[[Atendimentos/Restaurantes e alimentos/02 Dúvidas]]' not in (loja/'Mapa do atendimento.md').read_text(encoding='utf-8')
    assert cerebro.situacao()['atendimento']['padroes'] == 6


def test_revogacao_entre_selecao_e_contexto(loja, monkeypatch):
    caminho = arquivo(loja, '02 Dúvidas.md')
    selecionar = cerebro._padroes_aprovados
    def revogar(pasta, etapa=None):
        notas = selecionar(pasta, etapa)
        if etapa:
            caminho.write_text('---\natendimento: false\n---\nSEGREDO_RASCUNHO', encoding='utf-8')
        return notas
    monkeypatch.setattr(cerebro, '_padroes_aprovados', revogar)
    assert 'SEGREDO_RASCUNHO' not in cerebro.instrucoes_contexto('Tem tamanho pequeno?')


def test_backup_restaura_personalizacao_aninhada(loja):
    caminho = arquivo(loja, '06 Atendimento humano.md')
    personalizado = caminho.read_text(encoding='utf-8') + '\nReconheça a dificuldade antes de orientar.'
    caminho.write_text(personalizado, encoding='utf-8')
    copia = cerebro.snapshot()
    relativo = caminho.relative_to(loja).as_posix()
    assert copia[relativo] == caminho.read_bytes()
    caminho.write_text('Texto alterado', encoding='utf-8')
    cerebro.restaurar_snapshot({relativo: copia[relativo]})
    assert caminho.read_text(encoding='utf-8') == personalizado


def test_ollama_recebe_categoria_e_etapa_ativas(loja, monkeypatch):
    from src import ia
    monkeypatch.setattr(ia, '_system_prompt', lambda: 'Cadastro oficial e regras de segurança.')
    prompt = ia._system_prompt_ollama('Meu pedido atrasou')
    assert '### Atendimentos/Restaurantes e alimentos/05 Pós-venda.md' in prompt
    assert '### Atendimentos/Restaurantes e alimentos/04 Fechamento.md' not in prompt
    assert 'Cadastro oficial e regras de segurança.' in prompt
    assert len(cerebro.instrucoes_contexto('Meu pedido atrasou')) <= cerebro._LIMITE_TOTAL


def test_recusa_pasta_de_padroes_redirecionada_sem_escrever_fora(loja, tmp_path, monkeypatch):
    externa = tmp_path/'externa'
    externa.mkdir()
    original = Path.is_symlink
    alvo = arquivo(loja).parent
    monkeypatch.setattr(Path, 'is_symlink', lambda p: p == alvo or original(p))
    with pytest.raises(ValueError, match='atalhos'):
        cerebro.arquivo_inicio()
    assert not list(externa.iterdir())
    assert cerebro._ler(alvo/'Perfil.md') == ('','')
