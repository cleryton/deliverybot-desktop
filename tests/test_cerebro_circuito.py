"""Envelope de notas revisadas: somente cofre fictício e nenhuma inferência real."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, timedelta

import pytest

from src import cerebro, config


@pytest.fixture
def cofre(tmp_path, monkeypatch):
    for chave, valor in {
        'DATABASE_PATH': str(tmp_path / 'loja-ficticia.db'),
        'COMERCIO_CONFIGURADO': 'SIM', 'COMERCIO_SEGMENTO': 'Lanchonete',
        'COMERCIO_DESCRICAO': '', 'COMERCIO_MODELO': 'PRODUCAO',
    }.items():
        monkeypatch.setattr(config, chave, valor)
    cerebro.arquivo_inicio()
    return cerebro.diretorio()


def nota(cofre, nome='Garantia', corpo='A equipe confere a embalagem na retirada.', meta=None):
    if meta is None:
        meta = 'atendimento: true\ncategoria_atendimento: ALIMENTACAO\ntags: [garantia]'
    caminho = cofre / 'Conhecimento' / (nome + '.md')
    caminho.write_text('---\n' + meta + '\n---\n' + corpo, encoding='utf-8')
    return caminho


def conhecimento(envelope):
    return [fonte for fonte in envelope.fontes if fonte.tipo == 'conhecimento']


@pytest.mark.parametrize('categoria', [None, '', 'OUTRA', 'OFICINA',
    'ALIMENTACAO\ncategoria_atendimento: ALIMENTACAO'])
def test_contexto_estrito_exige_categoria_explicita_valida_do_perfil(cofre, categoria):
    meta = 'atendimento: true\ntags: [garantia]'
    if categoria is not None:
        meta += '\ncategoria_atendimento: ' + categoria
    nota(cofre, corpo='REFERENCIA_FORA_DO_CIRCUITO', meta=meta)
    envelope = cerebro.contexto_revisado('Qual a garantia?')
    assert 'REFERENCIA_FORA_DO_CIRCUITO' not in envelope.texto
    assert not conhecimento(envelope)
    assert cerebro.contexto_valido(envelope)
    if categoria is None:
        assert 'REFERENCIA_FORA_DO_CIRCUITO' in cerebro.instrucoes_contexto('Qual a garantia?')


def test_fontes_identificam_somente_trecho_utilizado_e_nao_podem_ser_mutadas(cofre):
    caminho = nota(cofre)
    envelope = cerebro.contexto_revisado('garantia')
    fonte, = conhecimento(envelope)
    assert fonte.caminho == caminho.relative_to(cofre).as_posix()
    assert fonte.trecho == 'A equipe confere a embalagem na retirada.'
    assert fonte.trecho in envelope.texto
    assert len(fonte.assinatura) == 64
    assert isinstance(envelope.fontes, tuple)
    assert cerebro.contexto_valido(envelope)
    with pytest.raises(FrozenInstanceError):
        fonte.trecho = 'Outro texto.'


def test_callback_filtra_so_conhecimento_antes_do_ranking_e_do_limite(cofre):
    for numero in range(8):
        nota(cofre, f'A {numero}', f'RECUSAR {numero}',
             'atendimento: true\ncategoria_atendimento: ALIMENTACAO\ntags: [garantia]\nprioridade: 5')
    nota(cofre, 'Z Aceita', 'ACEITAR CONHECIMENTO')
    recebidas = []

    def aceita(corpo):
        recebidas.append(corpo)
        return corpo == 'ACEITAR CONHECIMENTO'

    envelope = cerebro.contexto_revisado('garantia', aceitar_conhecimento=aceita)
    assert len(recebidas) == 9
    assert all(corpo.startswith('RECUSAR') or corpo == 'ACEITAR CONHECIMENTO' for corpo in recebidas)
    assert [f.trecho for f in conhecimento(envelope)] == ['ACEITAR CONHECIMENTO']
    assert any(f.tipo == 'estilo' for f in envelope.fontes)
    assert any(f.tipo == 'padrao' for f in envelope.fontes)
    assert 'RECUSAR' not in envelope.texto


def test_orcamento_registra_so_fontes_realmente_enviadas(cofre, monkeypatch):
    (cofre / 'Estilo de atendimento.md').write_text('Voz.', encoding='utf-8')
    monkeypatch.setattr(cerebro, '_padroes_aprovados', lambda *_: [])
    monkeypatch.setattr(cerebro, '_LIMITE_TOTAL', 180)
    for nome in ('A', 'B'):
        nota(cofre, nome, nome * 80)
    nota(cofre, 'C', 'C' * 10)
    envelope = cerebro.contexto_revisado('garantia')
    assert len(envelope.texto) <= 180
    assert len(envelope.fontes) == 3
    assert [f.trecho for f in conhecimento(envelope)] == ['A' * 80, 'C' * 10]
    assert all(f.caminho != 'Conhecimento/B.md' for f in envelope.fontes)
    nota(cofre, 'B', 'A nota não enviada mudou.')
    assert cerebro.contexto_valido(envelope)


def test_conhecimento_acima_do_limite_da_nota_nao_perde_condicao_final(cofre):
    corpo = 'garantia ' * 500 + 'Somente com análise presencial da equipe.'
    assert len(corpo) > cerebro._LIMITE_NOTA
    nota(cofre, corpo=corpo)
    envelope = cerebro.contexto_revisado('garantia')
    assert not conhecimento(envelope)
    assert 'garantia garantia' in cerebro.instrucoes_contexto('garantia')


def test_assinatura_detecta_edicao_no_corpo_bruto_apos_limite_editorial(cofre):
    estilo = cofre / 'Estilo de atendimento.md'
    estilo.write_text('Voz da equipe. ' * 500, encoding='utf-8')
    nota(cofre, corpo='Condição revisada.\n<!-- ' + 'x' * 5000 + ' -->')
    envelope = cerebro.contexto_revisado('garantia')
    assert cerebro.contexto_valido(envelope)
    estilo.write_text(estilo.read_text(encoding='utf-8') + 'Alteração depois do corte.', encoding='utf-8')
    assert not cerebro.contexto_valido(envelope)


def test_assinatura_do_conhecimento_inclui_tambem_comentarios_nao_publicados(cofre):
    caminho = nota(cofre, corpo='Condição revisada.\n<!-- ' + 'x' * 5000 + ' -->')
    envelope = cerebro.contexto_revisado('garantia')
    assert [f.trecho for f in conhecimento(envelope)] == ['Condição revisada.']
    caminho.write_text(caminho.read_text(encoding='utf-8').replace('x -->', 'z -->'), encoding='utf-8')
    assert not cerebro.contexto_valido(envelope)


@pytest.mark.parametrize('antigo,novo', [
    ('embalagem', 'sacola'),
    ('atendimento: true', 'atendimento: false'),
    ('atendimento: true', 'atendimento: true\natendimento: true'),
    ('categoria_atendimento: ALIMENTACAO', 'categoria_atendimento: OFICINA'),
    ('categoria_atendimento: ALIMENTACAO', ''),
    ('atendimento: true', 'atendimento: true\nvalido_ate: 2000-01-01'),
    ('tags: [garantia]', 'tags: [revisao]'),
])
def test_edicao_ou_revogacao_apos_consulta_invalida_envelope(cofre, antigo, novo):
    caminho = nota(cofre)
    envelope = cerebro.contexto_revisado('garantia')
    caminho.write_text(caminho.read_text(encoding='utf-8').replace(antigo, novo), encoding='utf-8')
    assert not cerebro.contexto_valido(envelope)


def test_nota_removida_ou_ilegivel_invalida_envelope(cofre):
    caminho = nota(cofre)
    envelope = cerebro.contexto_revisado('garantia')
    caminho.write_bytes(b'\xff\x00')
    assert not cerebro.contexto_valido(envelope)
    caminho.unlink()
    assert not cerebro.contexto_valido(envelope)


def test_validade_e_reavaliada_mesmo_sem_edicao_do_arquivo(cofre, monkeypatch):
    hoje = date.today()
    nota(cofre, meta='atendimento: true\ncategoria_atendimento: ALIMENTACAO\ntags: [garantia]\nvalido_ate: ' + hoje.isoformat())
    envelope = cerebro.contexto_revisado('garantia')
    assert cerebro.contexto_valido(envelope)

    class Amanha(date):
        @classmethod
        def today(cls):
            return hoje + timedelta(days=1)

    monkeypatch.setattr(cerebro, 'date', Amanha)
    assert not cerebro.contexto_valido(envelope)


@pytest.mark.parametrize('chave,valor', [
    ('COMERCIO_CONFIGURADO', 'NAO'), ('COMERCIO_SEGMENTO', 'Oficina'),
    ('COMERCIO_DESCRICAO', 'Outra descrição'), ('COMERCIO_MODELO', 'SERVICOS'),
    ('NOME_RESTAURANTE', 'Outra loja'),
])
def test_troca_de_perfil_invalida_contexto_em_andamento(cofre, monkeypatch, chave, valor):
    nota(cofre)
    envelope = cerebro.contexto_revisado('garantia')
    monkeypatch.setattr(config, chave, valor)
    assert not cerebro.contexto_valido(envelope)


def test_mudanca_de_cofre_invalida_sem_preparar_outros_arquivos(cofre, monkeypatch, tmp_path):
    nota(cofre)
    envelope = cerebro.contexto_revisado('garantia')
    outra = tmp_path / 'outra' / 'loja.db'
    monkeypatch.setattr(config, 'DATABASE_PATH', str(outra))
    assert not cerebro.contexto_valido(envelope)
    assert not outra.parent.exists()


@pytest.mark.parametrize('campo,valor', [
    ('atendimento: true', 'atendimento: false'),
    ('categoria_atendimento: ALIMENTACAO', 'categoria_atendimento: MODA'),
    ('etapa_atendimento: duvidas', 'etapa_atendimento: fechamento'),
])
def test_padrao_editorial_revogado_tambem_invalida_a_consulta(cofre, campo, valor):
    envelope = cerebro.contexto_revisado('Qual a garantia?')
    fonte = next(f for f in envelope.fontes if f.tipo == 'padrao' and f.etapa == 'duvidas')
    caminho = cofre / fonte.caminho
    caminho.write_text(caminho.read_text(encoding='utf-8').replace(campo, valor), encoding='utf-8')
    assert not cerebro.contexto_valido(envelope)


@pytest.mark.parametrize('meta', ['atendimento: false',
    'valido_ate: 2000-01-01', 'categoria_atendimento: OFICINA'])
def test_estilo_com_restricao_explicita_respeita_contexto_estrito(cofre, meta):
    (cofre / 'Estilo de atendimento.md').write_text('---\n' + meta + '\n---\nVOZ_SUSPENSA', encoding='utf-8')
    envelope = cerebro.contexto_revisado('garantia')
    assert 'VOZ_SUSPENSA' not in envelope.texto
    assert 'VOZ_SUSPENSA' in cerebro.instrucoes_contexto('garantia')
    assert cerebro.contexto_valido(envelope)


def test_revalidacao_so_rele_fontes_enviadas_sem_gravar_pergunta(cofre, monkeypatch):
    nota(cofre)
    nota(cofre, 'Presentes', 'Conhecimento de embrulhos.',
         'atendimento: true\ncategoria_atendimento: ALIMENTACAO\ntags: [presentes]')
    pergunta = 'garantia CONTATO_FICTICIO_NUNCA_PERSISTIDO_123456'
    antes = {p.relative_to(cofre).as_posix(): p.read_bytes() for p in cofre.rglob('*') if p.is_file()}
    envelope = cerebro.contexto_revisado(pergunta)
    assert pergunta not in repr(envelope)
    original = cerebro._ler
    lidas = []

    def ler(caminho, **kwargs):
        lidas.append(caminho.relative_to(cofre).as_posix())
        return original(caminho, **kwargs)

    def sem_preparo(**kwargs):
        pytest.fail('Revalidar não deve preparar ou gravar o cofre.')

    monkeypatch.setattr(cerebro, '_ler', ler)
    monkeypatch.setattr(cerebro, '_preparar', sem_preparo)
    assert cerebro.contexto_valido(envelope)
    assert lidas == [f.caminho for f in envelope.fontes]
    assert antes == {p.relative_to(cofre).as_posix(): p.read_bytes() for p in cofre.rglob('*') if p.is_file()}


@pytest.mark.parametrize('alteracao', [
    {'caminho': '../externo.md'}, {'caminho': '/externo.md'},
    {'caminho': 'Conhecimento\\Garantia.md'}, {'tipo': 'guia'},
    {'tipo': 'estilo'}, {'trecho': 'Texto que não foi lido.'}, {'assinatura': '0' * 64},
])
def test_referencia_invalida_ou_trocada_nao_e_revalidada(cofre, alteracao):
    nota(cofre)
    envelope = cerebro.contexto_revisado('garantia')
    fonte, = conhecimento(envelope)
    fontes = tuple(replace(f, **alteracao) if f == fonte else f for f in envelope.fontes)
    assert not cerebro.contexto_valido(replace(envelope, fontes=fontes))


def test_envelope_de_outro_texto_ou_sem_proveniencia_nao_e_valido(cofre):
    nota(cofre)
    envelope = cerebro.contexto_revisado('garantia')
    assert not cerebro.contexto_valido(replace(envelope, texto=envelope.texto + '\nTexto extra.'))
    assert not cerebro.contexto_valido(cerebro.ContextoRevisado(envelope.texto, envelope.fontes))
    assert not cerebro.contexto_valido(None)


def test_notas_novas_explicam_circuito_e_identificam_categoria_sem_alterar_edicoes(cofre):
    for nome in ('Informações da loja.md', 'Perguntas frequentes.md', 'Modelos/Conhecimento aprovado.md'):
        meta, _ = cerebro._remover_frontmatter((cofre / nome).read_text(encoding='utf-8'))
        assert cerebro._metadado(meta, 'categoria_atendimento') == 'ALIMENTACAO'
    modelo_meta, modelo_corpo = cerebro._remover_frontmatter(
        (cofre / 'Modelos/Conhecimento aprovado.md').read_text(encoding='utf-8'))
    assert 'revisado_em:' in modelo_meta and 'responsavel:' in modelo_meta and 'fonte:' in modelo_meta
    assert '- Responsável:' not in modelo_corpo and '- Revisado em' not in modelo_corpo
    guia = cofre / 'Circuito comercial.md'
    meta, _ = cerebro._remover_frontmatter(guia.read_text(encoding='utf-8'))
    assert not cerebro._aprovada(meta)
    assert 'categoria_atendimento' in guia.read_text(encoding='utf-8')
    assert '[[Circuito comercial]]' in (cofre / 'Início.md').read_text(encoding='utf-8')
    assert '[[Circuito comercial]]' in (cofre / 'Mapa do atendimento.md').read_text(encoding='utf-8')
    visivel = next(n for n in cerebro.visualizacao()['notas'] if n['nome'] == 'Circuito comercial.md')
    assert visivel['uso'] == 'Guia; não enviado ao modelo'
    guia.write_text('Edição da equipe preservada.', encoding='utf-8')
    modelo = cofre / 'Modelos/Conhecimento aprovado.md'
    modelo.write_text('Modelo anterior preservado.', encoding='utf-8')
    cerebro.arquivo_inicio()
    assert guia.read_text(encoding='utf-8') == 'Edição da equipe preservada.'
    assert modelo.read_text(encoding='utf-8') == 'Modelo anterior preservado.'
    assert not any(f.caminho == 'Circuito comercial.md' for f in cerebro.contexto_revisado('garantia').fontes)


def test_leitor_mostra_nota_legada_preservada_e_pede_revisao_de_categoria(cofre):
    caminho = nota(cofre, corpo='Política legada para garantia.', meta='atendimento: true\ntags: [garantia]')
    anterior = caminho.read_bytes()
    visivel = next(n for n in cerebro.visualizacao()['notas'] if n['nome'] == 'Conhecimento/Garantia.md')
    assert visivel['conteudo'] == 'Política legada para garantia.'
    assert visivel['uso'] == 'Revisar categoria; fora do circuito Ollama'
    assert 'Política legada para garantia.' in cerebro.instrucoes_contexto('garantia')
    assert not conhecimento(cerebro.contexto_revisado('garantia'))
    assert caminho.read_bytes() == anterior
