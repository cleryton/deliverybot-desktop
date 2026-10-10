"""Sincroniza versões do aplicativo e prepara uma entrada no histórico."""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def versionar(versao, descricao):
    if not re.fullmatch(r'\d+\.\d+\.\d+', versao):
        raise ValueError('Versão inválida')
    anterior = (ROOT / 'VERSION').read_text().strip()
    (ROOT / 'VERSION').write_text(versao+'\n', encoding='utf-8')
    for arquivo in ('web/templates/gestao.html', 'packaging/Instalador.cs'):
        p = ROOT / arquivo
        p.write_text(p.read_text(encoding='utf-8').replace(anterior, versao), encoding='utf-8')
    for arquivo in ('GUIA DO APLICATIVO.md', 'whatsapp-native/LICENCAS.txt', 'packaging/preparar_whatsapp.py'):
        p = ROOT / arquivo
        p.write_text(p.read_text(encoding='utf-8').replace('.'.join(anterior.split('.')[:2]), '.'.join(versao.split('.')[:2])), encoding='utf-8')
    p = ROOT / 'packaging/app.manifest'
    p.write_text(p.read_text(encoding='utf-8').replace(anterior+'.0', versao+'.0'), encoding='utf-8')
    for arquivo in ('whatsapp-native/package.json', 'whatsapp-native/package-lock.json'):
        p = ROOT / arquivo
        dados = json.loads(p.read_text(encoding='utf-8'))
        dados['version'] = versao
        if 'packages' in dados:
            dados['packages']['']['version'] = versao
        p.write_text(json.dumps(dados, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    p = ROOT / 'CHANGELOG.md'
    linhas = p.read_text(encoding='utf-8').splitlines(keepends=True)
    linhas.insert(2, f'## {versao} — {date.today().isoformat()}\n\n{descricao}\n\n')
    p.write_text(''.join(linhas), encoding='utf-8')


if __name__ == '__main__':
    versionar(sys.argv[1], sys.argv[2])
