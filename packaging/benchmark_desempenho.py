"""Mede caminhos locais com loja fictícia, sem serviços ou dados do usuário."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent


def percentil(valores, proporcao):
    valores = sorted(valores)
    posicao = (len(valores) - 1) * proporcao
    inferior = int(posicao)
    superior = min(inferior + 1, len(valores) - 1)
    return valores[inferior] + (valores[superior] - valores[inferior]) * (posicao - inferior)


def destino_seguro(nome):
    destino = Path(nome).resolve()
    destino.relative_to((ROOT / 'artifacts/desempenho').resolve())
    if destino.suffix != '.json' or destino.exists():
        raise ValueError('Use um arquivo JSON novo em artifacts/desempenho.')
    return destino


@contextmanager
def ambiente_ficticio(pasta):
    # O processo precisa nascer isolado antes de importar o aplicativo.
    if any(nome in sys.modules for nome in ('src.config', 'src.app', 'src.db')):
        raise ValueError('Execute em um processo separado, antes de importar o aplicativo.')
    anterior = os.environ.copy()
    os.environ.update(DELIVERYBOT_ENV_FILE=str(pasta / 'laboratorio.env'),
                      DATABASE_PATH=str(pasta / 'loja.db'), WHATSAPP_PROVIDER='TESTE',
                      IA_PROVIDER='', MODO_TESTE='true', TUNEL_AUTOMATICO='NAO',
                      SEED_CATALOGO='false', OLLAMA_AQUECER_AO_INICIAR='false',
                      NOME_RESTAURANTE='Loja fictícia', COMERCIO_MODELO='REVENDA')
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(anterior)


def medir(operacao, repeticoes, db):
    for _ in range(2):
        operacao()
    contagens = {'conexoes': 0, 'selects': 0}
    conectar = db._connect

    def consulta(sql):
        if sql.lstrip().upper().startswith('SELECT'):
            contagens['selects'] += 1

    def conectar_contando():
        contagens['conexoes'] += 1
        conn = conectar()
        conn.set_trace_callback(consulta)
        return conn

    db._connect = conectar_contando
    try:
        operacao()
    finally:
        db._connect = conectar
    tempos = []
    for _ in range(repeticoes):
        inicio = time.perf_counter_ns()
        operacao()
        tempos.append((time.perf_counter_ns() - inicio) / 1_000_000)
    return {'amostras': repeticoes, 'p50_ms': round(statistics.median(tempos), 3),
            'p95_ms_r7': round(percentil(tempos, .95), 3),
            'min_ms': round(min(tempos), 3), **contagens}


def executar(repeticoes):
    with tempfile.TemporaryDirectory(prefix='deliverybot-desempenho-') as temporario:
        pasta = Path(temporario)
        with ambiente_ficticio(pasta):
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from src import db, cerebro, config, pedidos as repo_pedidos
            from src.app import app
            # Nenhum canal real é configurado, iniciado ou utilizado.
            assert config.WHATSAPP_PROVIDER == 'TESTE' and not config.IA_PROVIDER
            with db.get_conn() as conn:
                conn.executemany('INSERT INTO produtos(nome,categoria,preco,estoque,estoque_minimo,ativo) VALUES(?,?,?,?,?,?)',
                    [(f'Produto {i:04}', 'Categoria fictícia', 10, i % 25, 2, i % 4 != 0) for i in range(1500)])
                conn.execute("INSERT INTO clientes(nome,telefone) VALUES('Cliente fictício','5511999990000')")
                conn.executemany('INSERT INTO pedidos(numero_pedido,cliente_id,forma_entrega,tempo_estimado_min,forma_pagamento,total_itens,total_pedido,status) VALUES(?,1,?,40,?,50,50,?)',
                    [(f'#{i:08}', 'RETIRADA BALCAO', 'Pix', 'RECEBIDO' if i > 2700 else 'RETIRADO') for i in range(1,3001)])
                conn.executemany('INSERT INTO itens_pedido(pedido_id,produto_id,quantidade,preco_unitario,nome_produto,custo_unitario) VALUES(?,?,1,10,?,4)',
                    [(i, j+1, f'Nome histórico {j}') for i in range(1,3001) for j in range(5)])
                conn.executemany('INSERT INTO fila_preparo(pedido_id,posicao,status) VALUES(?,?,?)',
                    [(i,i,'AGUARDANDO' if i>2700 else 'RETIRADO') for i in range(1,3001)])
                conn.execute('UPDATE produtos SET estoque=999999 WHERE id=1500')
            cofre = cerebro.arquivo_inicio().parent
            for i in range(80):
                (cofre / 'Conhecimento' / f'Garantia {i:03}.md').write_text(
                    '---\natendimento: true\ntags: garantia\n---\n# Garantia\n\n' +
                    'Condição fictícia revisada para a garantia de produtos. ' * 20, encoding='utf-8')
            cerebro.arquivo_inicio()
            app.config['DESKTOP_TOKEN'] = 'benchmark-ficticio'
            app.config['TESTING'] = True
            cliente = app.test_client()
            assert cliente.get('/gestao?acesso=benchmark-ficticio').status_code == 302

            def pedidos():
                resposta = cliente.get('/gestao/api/pedidos')
                assert resposta.status_code == 200
                dados = json.loads(resposta.data)
                assert [p['id'] for p in dados] == list(range(3000, 2800, -1))
                assert all(len(p['itens']) == 5 and p['total_pedido'] == 50 for p in dados)
                assert dados[0]['itens'][0]['produto_nome'] == 'Nome histórico 0'
                assert dados[0]['itens'][0]['custo_unitario'] == 4

            def resumo():
                resposta = cliente.get('/gestao/api/resumo')
                assert resposta.status_code == 200
                dados = json.loads(resposta.data)
                assert (dados['produtos'], dados['ativos'], dados['pendentes'], dados['pedidos'], dados['vendas']) == (1500, 1125, 300, 3000, 150000)
                assert dados['baixos'] == sum(i % 4 != 0 and i % 25 <= 2 for i in range(1500))

            def contexto():
                texto = cerebro.instrucoes_contexto('Como funciona a garantia dos produtos?')
                assert 'Condição fictícia revisada' in texto and len(texto) <= cerebro._LIMITE_TOTAL

            def criar():
                pedido = repo_pedidos.criar_pedido('5511999990000', 'Cliente fictício',
                    [{'produto_id':1500,'quantidade':1}], 'Pix')
                assert pedido['total_pedido'] == 10 and len(pedido['itens']) == 1

            return {nome: medir(operacao, repeticoes, db) for nome, operacao in
                    [('pedidos_200', pedidos), ('resumo', resumo), ('contexto_80_notas', contexto), ('criar_pedido', criar)]}


def inicializacao_filho():
    with tempfile.TemporaryDirectory(prefix='deliverybot-inicializacao-') as temporario:
        with ambiente_ficticio(Path(temporario)):
            sys.path.insert(0, str(ROOT))
            inicio = time.perf_counter_ns()
            from src.app import app
            assert app is not None
            return {'ms': (time.perf_counter_ns()-inicio)/1_000_000,
                    'sdk_anthropic_carregado': 'anthropic' in sys.modules}


def medir_inicializacao(repeticoes):
    codigo = "import runpy,json; m=runpy.run_path('packaging/benchmark_desempenho.py'); print(json.dumps(m['inicializacao_filho']()))"
    registros = []
    for _ in range(repeticoes):
        processo = subprocess.run([sys.executable, '-c', codigo], cwd=ROOT,
            capture_output=True, text=True, check=True, timeout=60)
        registros.append(json.loads(processo.stdout))
    tempos = [r['ms'] for r in registros]
    return {'importacao_backend_banco_novo': {'amostras':repeticoes,
            'p50_ms':round(statistics.median(tempos),3), 'p95_ms_r7':round(percentil(tempos,.95),3),
            'min_ms':round(min(tempos),3),
            'sdk_anthropic_carregado':any(r['sdk_anthropic_carregado'] for r in registros)}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida', required=True)
    parser.add_argument('--repeticoes', type=int, default=15, choices=range(5,101))
    parser.add_argument('--inicializacao', action='store_true', help='Mede importação do backend em processos novos, sem janela ou serviços.')
    args = parser.parse_args(argv)
    try:
        destino = destino_seguro(args.saida)
        resultado = medir_inicializacao(args.repeticoes) if args.inicializacao else executar(args.repeticoes)
        registro = {'formato': 1, 'versao': (ROOT/'VERSION').read_text().strip(),
                    'commit': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    'alteracoes_versionadas': bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT)),
                    'python': platform.python_version(), 'sistema': platform.system(),
                    'dados': {'banco':'novo e vazio'} if args.inicializacao else {'produtos':1500,'pedidos':3000,'itens':15000,'notas':80},
                    'medidas': resultado,
                    'limites': 'Dados fictícios. Consultas aquecidas incluem leitura e verificação das respostas; importação usa processos novos e banco vazio. Não mede inferência, rede, abertura completa do executável ou renderização do navegador.'}
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open('x', encoding='utf-8') as arquivo:
            json.dump(registro, arquivo, ensure_ascii=False, indent=2)
        print(json.dumps(resultado, ensure_ascii=False))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError):
        print('Não foi possível concluir a medição. Use um processo isolado e um arquivo novo em artifacts/desempenho.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
