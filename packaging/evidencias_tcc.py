"""Resume JUnit de testes fictícios sem copiar nomes, mensagens ou dados pessoais."""
import argparse
import hashlib
import json
import math
import platform
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 20 * 1024 * 1024


def resumir_junit(conteudo):
    if not conteudo or len(conteudo) > MAX_BYTES:
        raise ValueError('Relatório ausente ou acima do limite de 20 MiB.')
    raiz = ElementTree.fromstring(conteudo, forbid_dtd=True)
    if raiz.tag not in {'testsuites', 'testsuite'}:
        raise ValueError('Formato JUnit não reconhecido.')
    casos = list(raiz.iter('testcase'))
    if not casos:
        raise ValueError('Relatório sem casos de teste; não comprova execução.')
    totais = dict(executados=len(casos), aprovados=0, falhas=0, erros=0, ignorados=0)
    tempos = []
    for caso in casos:
        tempo = float(caso.get('time', '0'))
        if not math.isfinite(tempo) or tempo < 0:
            raise ValueError('Duração de teste inválida.')
        tempos.append(tempo)
        estados = [nome for nome in ('failure', 'error', 'skipped') if caso.find(nome) is not None]
        if len(estados) > 1:
            raise ValueError('Resultado de teste ambíguo.')
        chave = {'failure': 'falhas', 'error': 'erros', 'skipped': 'ignorados'}.get(
            estados[0] if estados else '', 'aprovados')
        totais[chave] += 1
    try:
        duracao = math.fsum(tempos)
    except OverflowError as erro:
        raise ValueError('Duração total inválida.') from erro
    if not math.isfinite(duracao):
        raise ValueError('Duração total inválida.')
    return {**totais, 'soma_duracoes_casos_s': round(duracao, 6),
            'sem_falhas': totais['falhas'] == totais['erros'] == 0,
            'validacao_completa': totais['falhas'] == totais['erros'] == totais['ignorados'] == 0}


def consolidar(conteudos, versao, commit, alteracoes_pendentes):
    if not re.fullmatch(r'\d+\.\d+\.\d+', versao):
        raise ValueError('Versão inválida.')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Informe um commit Git completo.')
    if type(alteracoes_pendentes) is not bool:
        raise ValueError('Estado do código inválido.')
    if not conteudos:
        raise ValueError('Informe ao menos um relatório JUnit.')
    hashes = set()
    relatorios = []
    for conteudo in conteudos:
        sha = hashlib.sha256(conteudo).hexdigest()
        if sha in hashes:
            raise ValueError('Relatório repetido; não some a mesma execução duas vezes.')
        hashes.add(sha)
        relatorios.append({'sha256': sha, **resumir_junit(conteudo)})
    return {'formato': 1, 'gerado_em_utc': datetime.now(timezone.utc).isoformat(),
            'versao_declarada': versao, 'commit_do_checkout': commit,
            'alteracoes_versionadas_pendentes': alteracoes_pendentes,
            'ambiente_consolidacao': {'python': platform.python_version(), 'sistema': platform.system()},
            'relatorios': relatorios,
            'sem_falhas': all(r['sem_falhas'] for r in relatorios),
            'validacao_completa': all(r['validacao_completa'] for r in relatorios),
            'limites': ['Metadados identificam o checkout da consolidação, não autenticam a origem do JUnit.',
                       'Relatórios distintos podem conter casos sobrepostos; os totais permanecem separados.',
                       'Duração dos testes não mede latência de atendimento nem qualidade da IA.',
                       'Casos ignorados exigem justificativa; não são considerados aprovados.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('junit', nargs='+', type=Path)
    parser.add_argument('--saida', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        entradas = [p.resolve() for p in args.junit]
        saida = args.saida.resolve()
        # Aceita somente a pasta de evidências, sem sobrescrever fontes ou o relatório original.
        pasta = (ROOT / 'artifacts' / 'tcc').resolve()
        if (not pasta.is_relative_to(ROOT.resolve())
                or not saida.is_relative_to(pasta) or saida in entradas):
            raise ValueError('A saída deve ficar em artifacts/tcc e ser diferente das entradas.')
        conteudos = []
        for caminho in entradas:
            with caminho.open('rb') as arquivo:
                conteudos.append(arquivo.read(MAX_BYTES + 1))
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        pendentes = bool(subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT))
        dados = consolidar(conteudos, (ROOT / 'VERSION').read_text().strip(), commit, pendentes)
        saida.parent.mkdir(parents=True, exist_ok=True)
        saida.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Evidências consolidadas. Consulte os resultados e limites no JSON gerado.')
        return 0 if dados['sem_falhas'] else 1
    except (ValueError, OSError, subprocess.SubprocessError, ElementTree.ParseError) as erro:
        print(f'Não foi possível consolidar as evidências ({type(erro).__name__}).')
        return 2
    except DefusedXmlException:
        print('Não foi possível consolidar as evidências (XML inseguro).')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
