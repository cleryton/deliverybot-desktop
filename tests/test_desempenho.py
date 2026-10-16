"""Correção, isolamento e quantidade limitada de consultas, sem tempos frágeis."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import builtins
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from src import config, db, pedidos, estoque, cerebro

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('benchmark_desempenho', ROOT/'packaging/benchmark_desempenho.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


@pytest.fixture
def loja(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATABASE_PATH', str(tmp_path/'ficticio.db'))
    monkeypatch.setattr(config, 'SEED_CATALOGO', False)
    monkeypatch.setattr(config, 'FORMAS_PAGAMENTO', 'Pix,Dinheiro')
    monkeypatch.setattr(config, 'WHATSAPP_PROVIDER', 'TESTE')
    monkeypatch.setattr(config, 'IA_PROVIDER', '')
    monkeypatch.setattr(config, 'COMERCIO_ESTOQUE_PADRAO', 'SIM')
    monkeypatch.setattr(config, 'MODO_TESTE', True)
    db.init_db()
    p = estoque.salvar_produto({'nome':'Produto fictício','categoria':'Teste','preco':10,'controlar_estoque':False})
    return p


@contextmanager
def rastrear(monkeypatch):
    conectar = db._connect
    registro = {'conexoes':0,'selects':0}
    def trace(sql):
        if sql.lstrip().upper().startswith('SELECT'):
            registro['selects'] += 1
    def abrir():
        registro['conexoes'] += 1
        conn = conectar()
        conn.set_trace_callback(trace)
        return conn
    with monkeypatch.context() as m:
        m.setattr(db, '_connect', abrir)
        yield registro


def comprar(produto, numero):
    return pedidos.criar_pedido(f'55119999{numero:04}', 'Cliente fictício',
        [{'produto_id':produto['id'],'quantidade':1}], 'Pix')


def test_lista_em_lote_preserva_recibos_ordem_e_custos(loja, monkeypatch):
    ids = [comprar(loja, i)['id'] for i in range(5)]
    anteriores = [pedidos.obter_pedido(i) for i in reversed(ids)]
    with rastrear(monkeypatch) as consultas:
        resultado = pedidos.listar_pedidos()
    assert resultado == anteriores
    assert consultas == {'conexoes':1,'selects':2}
    assert pedidos.listar_pedidos(2) == anteriores[:2]


def test_lista_vazia_e_limite_sao_controlados(loja, monkeypatch):
    with rastrear(monkeypatch) as consultas:
        assert pedidos.listar_pedidos() == []
    assert consultas == {'conexoes':1,'selects':1}
    for limite in [0,-1,201,True,1.5,'invalido']:
        with pytest.raises(ValueError):
            pedidos.listar_pedidos(limite)


def test_leitura_em_lote_usa_o_mesmo_snapshot(loja, monkeypatch):
    pid = comprar(loja, 1)['id']
    conectar = db._connect
    class Conexao:
        def __init__(self, conn):
            self.conn = conn
        def __getattr__(self, chave):
            return getattr(self.conn, chave)
        def execute(self, sql, *args):
            resultado = self.conn.execute(sql, *args)
            if 'JOIN clientes' in sql and 'LIMIT' in sql:
                class Resultado:
                    def fetchall(self):
                        linhas = resultado.fetchall()
                        outra = conectar()
                        try:
                            outra.execute('UPDATE itens_pedido SET nome_produto=? WHERE pedido_id=?', ('Nova edição concorrente',pid))
                            outra.commit()
                        finally:
                            outra.close()
                        return linhas
                return Resultado()
            return resultado
    monkeypatch.setattr(db,'_connect',lambda:Conexao(conectar()))
    assert pedidos.listar_pedidos()[0]['itens'][0]['produto_nome'] == 'Produto fictício'
    monkeypatch.setattr(db,'_connect',conectar)
    assert pedidos.listar_pedidos()[0]['itens'][0]['produto_nome'] == 'Nova edição concorrente'


def test_resumo_agrega_sem_carregar_catalogo_ou_itens(loja, monkeypatch):
    from src.app import app
    from src import gestao, fila
    a = comprar(loja, 1)
    b = comprar(loja, 2)
    pedidos.cancelar_pedido(b['id'])
    estoque.salvar_produto({'nome':'Sem saldo','categoria':'Teste','preco':2,'estoque':0})
    estoque.salvar_produto({'nome':'Inativo','categoria':'Teste','preco':2,'ativo':False,'estoque':0})
    def proibido():
        pytest.fail('Resumo deve contar no banco, sem materializar listas.')
    monkeypatch.setattr(estoque,'listar_produtos',proibido)
    monkeypatch.setattr(fila,'listar_fila',proibido)
    monkeypatch.setattr(gestao.operadores,'admin',lambda:True)
    with app.test_request_context():
        dados = gestao.resumo.__wrapped__().get_json()
    assert (dados['produtos'],dados['ativos'],dados['baixos'],dados['produtos_controlados']) == (3,2,1,2)
    assert (dados['pendentes'],dados['pedidos'],dados['vendas']) == (1,1,10)
    monkeypatch.setattr(gestao.operadores,'admin',lambda:False)
    with app.test_request_context():
        assert gestao.resumo.__wrapped__().get_json()['vendas'] == 0


def test_resumo_vazio_nao_retorna_contagens_nulas(loja,monkeypatch):
    from src.app import app
    from src import gestao
    with db.get_conn() as conn:
        conn.execute('DELETE FROM produtos')
    monkeypatch.setattr(gestao.operadores,'admin',lambda:True)
    with app.test_request_context():
        dados = gestao.resumo.__wrapped__().get_json()
    for campo in ['produtos','ativos','baixos','produtos_controlados','pedidos','vendas','pendentes']:
        assert dados[campo] == 0


def test_lista_administrativa_nao_expoe_custo_ao_funcionario(loja, monkeypatch):
    from src.app import app
    from src import gestao
    pedido = comprar(loja,1)
    with db.get_conn() as conn:
        conn.execute('UPDATE itens_pedido SET custo_unitario=3 WHERE pedido_id=?',(pedido['id'],))
        conn.execute("UPDATE produtos SET nome='Nome alterado',custo=8 WHERE id=?",(loja['id'],))
    monkeypatch.setattr(gestao.operadores,'admin',lambda:False)
    with app.test_request_context():
        dados = gestao.listar_pedidos.__wrapped__().get_json()
    assert 'custo_unitario' not in dados[0]['itens'][0]
    assert dados[0]['itens'][0]['produto_nome'] == 'Produto fictício'
    assert pedidos.obter_pedido(pedido['id'])['itens'][0]['custo_unitario'] == 3


def test_indices_instalam_em_banco_existente_preservando_dados(loja):
    pid = comprar(loja,1)['id']
    indices = ['idx_itens_pedido_pedido_id','idx_fila_posicao','idx_tarefas_telefone_estado']
    with db.get_conn() as conn:
        for indice in indices:
            conn.execute(f'DROP INDEX IF EXISTS {indice}')
    db.init_db(forcar=True)
    db.init_db(forcar=True)
    assert pedidos.obter_pedido(pid)['total_pedido'] == 10
    with db.get_conn() as conn:
        consultas = [
            ('SELECT * FROM itens_pedido WHERE pedido_id=1 ORDER BY id','idx_itens_pedido_pedido_id'),
            ('SELECT MAX(posicao) FROM fila_preparo','idx_fila_posicao'),
            ("SELECT 1 FROM tarefas_bot WHERE telefone='5511999990000' AND estado IN ('PROCESSANDO','ENVIANDO')",'idx_tarefas_telefone_estado'),
        ]
        for sql, indice in consultas:
            assert indice in ' '.join(str(tuple(r)) for r in conn.execute('EXPLAIN QUERY PLAN '+sql))


def test_contexto_nao_reconstroi_graph_a_cada_mensagem(loja, monkeypatch):
    pasta = cerebro.arquivo_inicio().parent
    mapa = pasta/'Mapa do atendimento.md'
    anterior = (mapa.read_bytes(), mapa.stat().st_mtime_ns)
    sincronizar = cerebro._sincronizar_mapa
    chamadas = []
    monkeypatch.setattr(cerebro, '_sincronizar_mapa', lambda p: chamadas.append(p))
    assert cerebro.instrucoes_contexto('quero conhecer os produtos')
    assert chamadas == []
    assert (mapa.read_bytes(),mapa.stat().st_mtime_ns) == anterior
    monkeypatch.setattr(cerebro, '_sincronizar_mapa', sincronizar)


def test_contexto_rele_nota_editada_e_graph_atualiza_na_visualizacao(loja):
    pasta = cerebro.arquivo_inicio().parent
    nota = pasta/'Conhecimento/Garantia.md'
    nota.write_text('---\natendimento: true\n---\n# Garantia\nInformação revisada.',encoding='utf-8')
    assert 'Informação revisada.' in cerebro.instrucoes_contexto('garantia')
    nota.write_text('---\natendimento: false\n---\nRascunho privado.',encoding='utf-8')
    assert 'Rascunho privado.' not in cerebro.instrucoes_contexto('garantia')
    cerebro.visualizacao()
    assert '[[Conhecimento/Garantia]]' not in (pasta/'Mapa do atendimento.md').read_text(encoding='utf-8')


def test_primeiro_contexto_ainda_prepara_graph(loja):
    assert not cerebro.diretorio().exists()
    assert cerebro.instrucoes_contexto('oi')
    assert (cerebro.diretorio()/'Mapa do atendimento.md').is_file()


def test_estado_do_cofre_sincroniza_graph_uma_vez(loja,monkeypatch):
    sincronizar = cerebro._sincronizar_mapa
    chamadas = []
    def registrar(pasta):
        chamadas.append(pasta)
        sincronizar(pasta)
    monkeypatch.setattr(cerebro,'_sincronizar_mapa',registrar)
    estado = cerebro.situacao()
    assert len(chamadas) == 1
    assert Path(estado['arquivo']).is_file()
    assert estado['notas_contexto'] > 0 and estado['consulta_por_assunto']


def test_sdk_opcional_nao_pesa_na_importacao_local(tmp_path):
    ambiente = {**{k:os.environ[k] for k in ('SYSTEMROOT','WINDIR','PATH','TEMP','TMP') if k in os.environ},
                'DELIVERYBOT_ENV_FILE':str(tmp_path/'vazio.env'),
                'DATABASE_PATH':str(tmp_path/'ficticio.db'),'IA_PROVIDER':'OLLAMA'}
    subprocess.run([sys.executable,'-c',"import sys; from src import ia; assert 'anthropic' not in sys.modules"],
                   cwd=ROOT,env=ambiente,check=True,timeout=30,capture_output=True)


def test_sdk_ausente_tem_fallback_e_sem_chave_nao_importa(loja, monkeypatch):
    from src import ia
    monkeypatch.setattr(ia,'anthropic',None)
    monkeypatch.setattr(config,'ANTHROPIC_API_KEY','chave-ficticia')
    importar = builtins.__import__
    chamadas = []
    def sem_sdk(nome,*args,**kwargs):
        if nome == 'anthropic':
            chamadas.append(nome)
            raise ImportError('Simulação sem SDK')
        return importar(nome,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',sem_sdk)
    with pytest.raises(ia.IAIndisponivel,match='não instalada'):
        ia._responder_anthropic('5511999990000','oi')
    assert chamadas == ['anthropic']
    chamadas.clear()
    monkeypatch.setattr(config,'ANTHROPIC_API_KEY','')
    with pytest.raises(ia.IAIndisponivel,match='não configurada'):
        ia._responder_anthropic('5511999990000','oi')
    assert chamadas == []


def test_sdk_carrega_na_primeira_chamada_e_reutiliza(loja,monkeypatch):
    from src import ia
    monkeypatch.setattr(ia,'anthropic',None)
    monkeypatch.setattr(config,'ANTHROPIC_API_KEY','chave-ficticia')
    resposta = SimpleNamespace(stop_reason='end_turn',content=[SimpleNamespace(type='text',text='Resposta fictícia.')])
    sdk = SimpleNamespace(Anthropic=lambda **kwargs:SimpleNamespace(messages=SimpleNamespace(create=lambda **kw:resposta)))
    monkeypatch.setitem(sys.modules,'anthropic',sdk)
    monkeypatch.setattr(ia,'_mensagens_atualizadas',lambda *a:[])
    monkeypatch.setattr(ia,'_system_prompt',lambda:'Regras fictícias')
    assert ia._responder_anthropic('5511999990000','oi') == 'Resposta fictícia.'
    assert ia.anthropic is sdk
    assert ia._responder_anthropic('5511999990000','oi') == 'Resposta fictícia.'


def test_benchmark_percentil_e_instrumentacao_sem_gravar_dados(loja):
    assert benchmark.percentil([1,2,3,4,5], .95) == pytest.approx(4.8)
    def ler():
        with db.get_conn() as conn:
            assert conn.execute('SELECT COUNT(*) FROM produtos').fetchone()[0] == 1
    resultado = benchmark.medir(ler, 5, db)
    assert resultado['amostras'] == 5
    assert resultado['conexoes'] == resultado['selects'] == 1
    assert resultado['p95_ms_r7'] >= resultado['min_ms'] >= 0


@pytest.mark.parametrize('nome',['VERSION','artifacts/desempenho/../../../VERSION','artifacts/desempenho/arquivo.txt'])
def test_benchmark_so_cria_json_na_pasta_de_medicao(nome):
    with pytest.raises(ValueError):
        benchmark.destino_seguro(ROOT/nome)


def test_benchmark_preserva_arquivos_e_recusa_processo_nao_isolado(tmp_path, monkeypatch):
    monkeypatch.setattr(benchmark, 'ROOT', tmp_path)
    destino = tmp_path/'artifacts/desempenho/existente.json'
    destino.parent.mkdir(parents=True)
    destino.write_text('{}')
    with pytest.raises(ValueError):
        benchmark.destino_seguro(destino)
    with pytest.raises(ValueError):
        with benchmark.ambiente_ficticio(tmp_path):
            pytest.fail('O aplicativo já foi importado neste processo.')
    assert destino.read_text() == '{}'
