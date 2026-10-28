"""Compara a espera na fila com duas inferências fictícias ocupadas.

Não mede o WhatsApp nem a velocidade real do Ollama. Usa eventos, uma loja
temporária e transporte simulado; nenhuma conta ou serviço é iniciado.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from unittest.mock import patch

from benchmark_desempenho import ROOT, ambiente_ficticio, destino_seguro, percentil


def cenario(pasta, reservado, espera):
    from src import bot, config, processamento, publicacao, whatsapp
    from src.db import init_db

    config.DATABASE_PATH = str(pasta / 'loja.db')
    config.WHATSAPP_PROVIDER = 'LOCAL'
    config.MODO_TESTE = False
    init_db()
    iniciadas = [threading.Event(), threading.Event()]
    liberar = threading.Event()
    entregue = threading.Event()
    envios = []
    fim = []

    def responder(telefone, texto):
        if texto.startswith('Consulta complexa'):
            iniciadas[int(texto[-1])].set()
            if not liberar.wait(10):
                raise AssertionError('Simulação não liberou o atendimento.')
            return 'Informação fictícia sobre o produto'
        assert texto == 'oi'
        return 'Saudação fictícia'

    def enviar(telefone, texto, **kwargs):
        envios.append((telefone, texto))
        if telefone == '554799990002':
            fim.append(time.perf_counter_ns())
            entregue.set()
        return {}

    def entrada(indice, texto):
        return processamento.enfileirar({'telefone': f'554799990{indice:03}', 'texto': texto}, f'ficticia-{indice}')

    def consumir():
        while processamento.processar_proxima():
            pass

    # Nenhuma função de transporte original permanece acessível nesta medição.
    with patch.object(processamento, '_servico_pronto', return_value=True), \
            patch.object(processamento, '_parar', threading.Event()), \
            patch.object(processamento, '_acordar', threading.Event()), \
            patch.object(publicacao, 'endereco', return_value=''), \
            patch.object(bot, 'processar_mensagem', side_effect=responder), \
            patch.object(whatsapp, 'enviar_mensagem', side_effect=enviar):
        entrada(0, 'Consulta complexa 0')
        entrada(1, 'Consulta complexa 1')
        with ThreadPoolExecutor(max_workers=3) as executor:
            normais = [executor.submit(consumir) for _ in range(2)]
            temporizador = None
            try:
                assert all(evento.wait(10) for evento in iniciadas)
                inicio = time.perf_counter_ns()
                entrada(2, 'oi')
                temporizador = threading.Timer(espera, liberar.set)
                temporizador.start()
                rapido = executor.submit(processamento.processar_proxima, somente_rapidas=True) if reservado else None
                assert entregue.wait(10), 'Saudação fictícia não foi processada.'
                latencia = (fim[0] - inicio) / 1_000_000
                if rapido is not None:
                    assert rapido.result(timeout=10)
                assert entrada(2, 'oi')['duplicada']
            finally:
                liberar.set()
                if temporizador is not None:
                    temporizador.cancel()
                    temporizador.join()
            for futuro in normais:
                futuro.result(timeout=10)
        assert len(envios) == 3 and len(set(envios)) == 3
        assert processamento.situacao()['pendentes'] == 0
    return round(latencia, 3)


def executar(repeticoes, espera):
    if not 3 <= repeticoes <= 30 or not .1 <= espera <= 1:
        raise ValueError('Use de 3 a 30 pares e espera fictícia entre 0,1 e 1 segundo.')
    resultados = {'antes_ms': [], 'reservado_ms': []}
    with tempfile.TemporaryDirectory(prefix='deliverybot-respostas-') as temporario:
        pasta = Path(temporario)
        with ambiente_ficticio(pasta):
            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            # Primeiro par só aquece imports e caches do processo; não entra
            # na distribuição de tempos reportada.
            for rodada in range(-1, repeticoes):
                ordem = (False, True) if rodada % 2 == 0 else (True, False)
                for reservado in ordem:
                    ensaio = pasta / f'{rodada}-{reservado}'
                    ensaio.mkdir()
                    resultado = cenario(ensaio, reservado, espera)
                    if rodada >= 0:
                        resultados['reservado_ms' if reservado else 'antes_ms'].append(resultado)
    def git(*argumentos):
        return subprocess.run(['git', *argumentos], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    return {
        'versao': (ROOT / 'VERSION').read_text(encoding='utf-8').strip(),
        'commit': git('rev-parse', 'HEAD'), 'alteracoes_nao_comitadas': bool(git('status', '--porcelain')),
        'python': platform.python_version(), 'plataforma': platform.platform(),
        'comparacao': 'Mesmo código e função processar_proxima: dois consumidores gerais versus dois gerais e um reservado; não compara executáveis completos.',
        'aquecimento': 'Um par descartado antes das amostras; ordem AB/BA alternada.',
        'cenario': 'Saudação de terceira conversa; dois consumidores ocupados em inferências simuladas',
        'espera_simulada_segundos': espera, 'pares': repeticoes,
        'limitacoes': 'Não mede inferência real, rede, entrega no WhatsApp nem garante latência em produção.',
        'correcao': 'Três envios únicos, nenhuma tarefa pendente; FIFO e deduplicação preservados no cenário.',
        **{nome: {'amostras_ms': valores, 'p50_ms': round(statistics.median(valores), 3),
                  'p95_ms_r7': round(percentil(valores, .95), 3)} for nome, valores in resultados.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeticoes', type=int, default=3)
    parser.add_argument('--espera', type=float, default=.2)
    parser.add_argument('--saida', required=True)
    args = parser.parse_args()
    destino = destino_seguro(args.saida)
    resultado = executar(args.repeticoes, args.espera)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open('x', encoding='utf-8') as arquivo:
        json.dump(resultado, arquivo, ensure_ascii=False, indent=2)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
