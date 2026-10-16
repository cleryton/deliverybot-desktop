"""Planeja e analisa a coleta A/B do TCC; não executa IA nem lê dados da loja."""
import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 2 * 1024 * 1024
PROTOCOLO = 'DB-TCC-1'
CASOS = tuple(f'C{i:02}' for i in range(1, 13))
DIMENSOES = ('clareza', 'naturalidade', 'segmento')
RISCOS = ('link_nao_autorizado', 'vazamento', 'operacao_nao_persistida')
ESTADOS = ('PENDENTE', 'OK', 'ERRO', 'TIMEOUT', 'BLOQUEADA')
AMBIENTE = {'modelo', 'modelo_digest', 'ollama_versao', 'cpu', 'gpu', 'ram_gb',
            'temperatura', 'seed', 'janela_contexto', 'prompt_a_sha256', 'prompt_b_sha256',
            'catalogo_sha256', 'notas_sha256', 'aquecimento_excluido'}
COMBINACOES = {(c, s, r) for c in CASOS for s in ('A', 'B') for r in (1, 2, 3)}


class ErroDeProtocolo(ValueError):
    """Mensagem controlada pelo instrumento, sem valores da coleta."""


def _objeto(d, chaves):
    if not isinstance(d, dict) or set(d) != set(chaves):
        raise ErroDeProtocolo('Estrutura inválida. Use o modelo do protocolo sem campos adicionais.')


def _numero(v, minimo, maximo):
    if type(v) not in (int, float) or not minimo <= v <= maximo or not math.isfinite(v):
        raise ErroDeProtocolo('Medida numérica inválida.')


def _sha(d):
    return hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def planejar(versao, commit, pendentes):
    _codigo(versao, commit, pendentes)
    registros = []
    for n, caso in enumerate(CASOS):
        for repeticao in (1, 2, 3):
            # Ordem alternada, declarada, com 18 pares A/B e 18 B/A.
            for condicao in (('A', 'B') if (n + repeticao) % 2 else ('B', 'A')):
                registros.append(dict(caso=caso, condicao=condicao, repeticao=repeticao,
                    estado='PENDENTE', chamou_modelo=None, duracao_ms=None, fallback=None,
                    factual_correto=None, riscos={k: None for k in RISCOS},
                    avaliacoes={a: {k: None for k in DIMENSOES} for a in ('R01', 'R02')}))
    return dict(formato=1, protocolo=PROTOCOLO, origem='COLETA', versao=versao, commit=commit,
                alteracoes_pendentes=pendentes, ambiente={k: None for k in sorted(AMBIENTE)}, registros=registros)


def _codigo(versao, commit, pendentes):
    if not isinstance(versao, str) or not re.fullmatch(r'\d+\.\d+\.\d+', versao):
        raise ErroDeProtocolo('Versão declarada inválida.')
    if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit) or type(pendentes) is not bool:
        raise ErroDeProtocolo('Commit ou situação do código inválidos.')


def _ambiente(d, coletou):
    _objeto(d, AMBIENTE)
    if not coletou and all(v is None for v in d.values()):
        return
    for k in ('modelo', 'ollama_versao', 'cpu', 'gpu'):
        if not isinstance(d[k], str) or not d[k].strip() or len(d[k]) > 160:
            raise ErroDeProtocolo('Complete os metadados técnicos antes da coleta.')
    for k in ('modelo_digest', 'prompt_a_sha256', 'prompt_b_sha256', 'catalogo_sha256', 'notas_sha256'):
        if not isinstance(d[k], str) or not re.fullmatch(r'[0-9a-f]{64}', d[k]):
            raise ErroDeProtocolo('Registre os identificadores SHA-256 dos materiais de pesquisa.')
    _numero(d['ram_gb'], 0.25, 65536)
    _numero(d['temperatura'], 0, 2)
    if type(d['janela_contexto']) is not int or not 128 <= d['janela_contexto'] <= 10000000:
        raise ErroDeProtocolo('Janela de contexto inválida.')
    if d['seed'] is not None and (type(d['seed']) is not int or not 0 <= d['seed'] <= 2147483647):
        raise ErroDeProtocolo('Seed inválida; use null quando não suportada.')
    if d['aquecimento_excluido'] is not True:
        raise ErroDeProtocolo('Separe o aquecimento das tentativas medidas.')


def _registro(d):
    _objeto(d, {'caso', 'condicao', 'repeticao', 'estado', 'chamou_modelo', 'duracao_ms',
                'fallback', 'factual_correto', 'riscos', 'avaliacoes'})
    if not isinstance(d['caso'], str) or not isinstance(d['condicao'], str) or type(d['repeticao']) is not int:
        raise ErroDeProtocolo('Identificação de caso inválida.')
    chave = (d['caso'], d['condicao'], d['repeticao'])
    if chave not in COMBINACOES or not isinstance(d['estado'], str) or d['estado'] not in ESTADOS:
        raise ErroDeProtocolo('Caso, condição, repetição ou estado fora do protocolo.')
    _objeto(d['riscos'], RISCOS)
    _objeto(d['avaliacoes'], {'R01', 'R02'})
    for notas in d['avaliacoes'].values():
        _objeto(notas, DIMENSOES)
    campos = [d[k] for k in ('chamou_modelo', 'duracao_ms', 'fallback', 'factual_correto')]
    notas = [v for a in d['avaliacoes'].values() for v in a.values()]
    if d['estado'] == 'PENDENTE':
        if any(v is not None for v in campos + notas + list(d['riscos'].values())):
            raise ErroDeProtocolo('Uma tentativa pendente não pode conter medidas ou julgamentos.')
        return chave
    if type(d['chamou_modelo']) is not bool or type(d['fallback']) is not bool:
        raise ErroDeProtocolo('Informe se houve chamada ao modelo e contingência.')
    _numero(d['duracao_ms'], 0, 3600000)
    if d['estado'] == 'OK':
        if any(type(v) is not bool for v in [d['factual_correto'], *d['riscos'].values()]):
            raise ErroDeProtocolo('Avalie fatos e riscos de cada resposta concluída.')
        if any(type(v) is not int or not 1 <= v <= 5 for v in notas):
            raise ErroDeProtocolo('Os dois avaliadores devem atribuir notas de 1 a 5.')
    elif any(v is not None for v in [d['factual_correto'], *notas, *d['riscos'].values()]):
        raise ErroDeProtocolo('Tentativa sem resposta não recebe julgamento editorial.')
    if d['estado'] != 'OK' and d['fallback']:
        raise ErroDeProtocolo('Se uma resposta de contingência foi entregue, registre OK e fallback=true.')
    return chave


def percentil(valores, p):
    """Interpolação R7: posição zero-based (n-1)*p; não descarta extremos."""
    if not valores:
        return None
    itens = sorted(valores)
    pos = (len(itens) - 1) * p
    i = math.floor(pos)
    return itens[i] + (itens[min(i + 1, len(itens) - 1)] - itens[i]) * (pos - i)


def _latencia(valores):
    return {'n': len(valores), 'mediana_ms': statistics.median(valores) if valores else None,
            'p95_ms': percentil(valores, 0.95), 'metodo_percentil': 'R7'}


def _taxa(n, d):
    return {'numerador': n, 'denominador': d, 'proporcao': n / d if d else None}


def _condicao(registros):
    observados = [r for r in registros if r['estado'] != 'PENDENTE']
    ok = [r for r in observados if r['estado'] == 'OK']
    grupo = lambda r: r['estado'].lower() if r['estado'] != 'OK' else 'fallback' if r['fallback'] else 'modelo' if r['chamou_modelo'] else 'local'
    return dict(planejadas=len(registros), medidas=len(observados),
        estados={s: sum(r['estado'] == s for r in registros) for s in ESTADOS},
        conclusao=_taxa(len(ok), len(observados)),
        factual=_taxa(sum(r['factual_correto'] for r in ok), len(ok)),
        factual_por_tentativa=_taxa(sum(r['factual_correto'] for r in ok), len(observados)),
        chamou_modelo=_taxa(sum(r['chamou_modelo'] for r in observados),len(observados)),
        fallback=_taxa(sum(r['fallback'] for r in observados), len(observados)),
        riscos={k: _taxa(sum(r['riscos'][k] for r in ok), len(ok)) for k in RISCOS},
        latencias={s: _latencia([r['duracao_ms'] for r in observados if grupo(r) == s]) for s in ('modelo', 'local', 'fallback', 'erro', 'timeout', 'bloqueada')},
        editorial={k: {'n_respostas':len(ok),
            'media_notas':statistics.fmean(r['avaliacoes'][a][k] for r in ok for a in ('R01','R02')) if ok else None,
            'concordancia_exata':_taxa(sum(r['avaliacoes']['R01'][k] == r['avaliacoes']['R02'][k] for r in ok),len(ok))}
            for k in DIMENSOES})


def analisar(d):
    _objeto(d, {'formato', 'protocolo', 'origem', 'versao', 'commit', 'alteracoes_pendentes', 'ambiente', 'registros'})
    if type(d['formato']) is not int or d['formato'] != 1 or d['protocolo'] != PROTOCOLO or not isinstance(d['origem'], str) or d['origem'] not in {'COLETA','SIMULACAO'}:
        raise ErroDeProtocolo('Formato, protocolo ou origem inválidos.')
    _codigo(d['versao'], d['commit'], d['alteracoes_pendentes'])
    registros = d['registros']
    if not isinstance(registros, list) or len(registros) != len(COMBINACOES):
        raise ErroDeProtocolo('Preserve as 72 tentativas planejadas, inclusive pendentes e falhas.')
    vistos = set()
    for indice, r in enumerate(registros, 1):
        try:
            chave = _registro(r)
        except ErroDeProtocolo as erro:
            raise ErroDeProtocolo(f'Registro {indice}: {erro}') from None
        if chave in vistos:
            raise ErroDeProtocolo('Tentativa duplicada; não conte a mesma resposta duas vezes.')
        vistos.add(chave)
    _ambiente(d['ambiente'], any(r['estado'] != 'PENDENTE' for r in registros))
    completos = all(r['estado'] != 'PENDENTE' for r in registros)
    por_chave = {(r['caso'],r['condicao'],r['repeticao']):r for r in registros}
    pares = []
    for caso in CASOS:
        for rep in (1,2,3):
            a,b = (por_chave[caso,s,rep] for s in ('A','B'))
            if all(r['estado']=='OK' and r['chamou_modelo'] and not r['fallback'] for r in (a,b)):
                pares.append((a,b))
    comparacao = {}
    for k in DIMENSOES:
        deltas = [statistics.fmean(b['avaliacoes'][v][k] - a['avaliacoes'][v][k] for v in ('R01','R02')) for a,b in pares]
        comparacao[k] = dict(n_pares=len(deltas), delta_medio_b_menos_a=statistics.fmean(deltas) if deltas else None,
                            b_maior=sum(x>0 for x in deltas), iguais=sum(x==0 for x in deltas), b_menor=sum(x<0 for x in deltas))
    return dict(formato=1, protocolo=PROTOCOLO, gerado_em_utc=datetime.now(timezone.utc).isoformat(),
        origem_declarada=d['origem'], coleta_completa=completos,
        versao_declarada=d['versao'], commit_declarado=d['commit'], alteracoes_pendentes=d['alteracoes_pendentes'],
        entrada_sha256=_sha(d), ambiente_sha256=_sha(d['ambiente']),
        condicoes={s:_condicao([r for r in registros if r['condicao']==s]) for s in ('A','B')},
        comparacao_modelo=dict(pares_elegiveis=len(pares), pares_planejados=36, editorial=comparacao),
        limites=['SIMULACAO não constitui resultado empírico; COLETA é uma declaração não autenticada.',
                 'Metadados e medidas são fornecidos pelo pesquisador; hashes não comprovam sua origem.',
                 'Respostas locais e de fallback não entram na comparação editorial do modelo.',
                 'Amostra exploratória, sem teste de significância nem conclusão causal.',
                 'Notas são ordinais; médias e concordância exata são descrições, não validação psicométrica.',
                 'Tentativas com falha e timeout permanecem nos denominadores de conclusão.',
                 'BLOQUEADA é uma decisão de proteção declarada, não sucesso de inferência nem necessariamente defeito.',
                 'O resumo não contém textos de respostas, nomes de participantes ou configurações técnicas em texto.'])


def _pares_unicos(pares):
    d = {}
    for k,v in pares:
        if k in d:
            raise ErroDeProtocolo('JSON com chave repetida.')
        d[k] = v
    return d


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    modos = p.add_mutually_exclusive_group(required=True)
    modos.add_argument('--preparar', action='store_true')
    modos.add_argument('--analisar', type=Path)
    p.add_argument('--saida', required=True, type=Path)
    args = p.parse_args(argv)
    try:
        saida = args.saida.resolve()
        pasta = (ROOT/'artifacts/tcc').resolve()
        if not pasta.is_relative_to(ROOT.resolve()) or not saida.is_relative_to(pasta) or saida.exists():
            raise ErroDeProtocolo('Use um arquivo novo dentro de artifacts/tcc, sem sobrescrever dados.')
        if args.preparar:
            commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            pendentes = bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT))
            resultado = planejar((ROOT/'VERSION').read_text().strip(),commit,pendentes)
            codigo = 0
        else:
            if args.analisar.resolve() == saida:
                raise ErroDeProtocolo('A entrada deve ser preservada.')
            with args.analisar.open('rb') as f:
                conteudo = f.read(MAX_BYTES+1)
            if len(conteudo) > MAX_BYTES:
                raise ErroDeProtocolo('Coleta acima do limite de 2 MiB.')
            d = json.loads(conteudo, object_pairs_hook=_pares_unicos)
            resultado = analisar(d)
            resultado['arquivo_entrada_sha256'] = hashlib.sha256(conteudo).hexdigest()
            codigo = 0 if resultado['coleta_completa'] else 1
        saida.parent.mkdir(parents=True,exist_ok=True)
        with saida.open('x',encoding='utf-8') as f:
            f.write(json.dumps(resultado,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        print('Plano criado; medidas ainda pendentes.' if args.preparar else 'Resumo gerado. Confira origem, cobertura, denominadores e limites.')
        return codigo
    except ErroDeProtocolo as erro:
        print(f'Avaliação recusada: {erro}')
        return 2
    except (ValueError,OSError,UnicodeError,RecursionError,subprocess.SubprocessError):
        print('Não foi possível processar a avaliação. Confira o modelo, as medidas e o caminho de saída; os arquivos existentes foram preservados.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
