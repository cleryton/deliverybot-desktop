"""Finaliza e confere uma distribuição sem incluir dados de uso do aplicativo."""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BINARIOS = ('Instalar-DeliveryBot.exe', 'DeliveryBot.exe', 'Instalar-DeliveryBot-Funcionario.exe', 'DeliveryBot-Funcionario.exe')
DOCUMENTOS = {
    'GUIA DO APLICATIVO.md': 'Como usar o DeliveryBot.txt',
    'PRIVACIDADE E SEGURANÇA.md': 'Privacidade e seguranca.txt',
    'whatsapp-native/LICENCAS.txt': 'LICENCAS WhatsApp.txt',
    'cloudflare/runtime/LICENSE.txt': 'LICENCA Cloudflare.txt',
    'packaging/LICENCA Pillow.txt': 'LICENCA Pillow.txt',
    'packaging/LICENCAS documentos.txt': 'LICENCAS documentos.txt',
    'GUIA DO FUNCIONARIO.md': 'Como usar o DeliveryBot Funcionario.txt',
}
GERADOS = frozenset((*BINARIOS, *DOCUMENTOS.values(), 'VERSAO.json', 'SHA256SUMS.txt'))


def versao(valor):
    if not re.fullmatch(r'\d+\.\d+\.\d+', valor):
        raise ValueError('Versão inválida: use X.Y.Z.')
    return tuple(map(int, valor.split('.')))


def vinculo(p):
    return p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())


def conferir_arquivo(pasta, nome):
    arquivo = pasta / nome
    if vinculo(pasta) or vinculo(arquivo) or not arquivo.is_file():
        raise ValueError(f'Arquivo regular obrigatório ausente: {nome}')
    if nome in BINARIOS:
        with arquivo.open('rb') as f:
            if f.read(2) != b'MZ':
                raise ValueError(f'Executável Windows inválido: {nome}')
    return arquivo


def gerar_hashes(pasta, nomes=BINARIOS):
    pasta = Path(pasta)
    if not set(BINARIOS).issubset(nomes) or any(nome not in GERADOS - {'SHA256SUMS.txt'} for nome in nomes):
        raise ValueError('Inclua os quatro executáveis e apenas arquivos da distribuição.')
    if vinculo(pasta/'SHA256SUMS.txt'):
        raise ValueError('O manifesto não pode ser um vínculo.')
    arquivos = [conferir_arquivo(pasta, nome) for nome in nomes]
    linhas = []
    for arquivo in arquivos:
        with arquivo.open('rb') as f:
            linhas.append(hashlib.file_digest(f, 'sha256').hexdigest() + '  ' + arquivo.name)
    (pasta / 'SHA256SUMS.txt').write_text('\n'.join(linhas)+'\n', encoding='utf-8')


def verificar(pasta, completa=False, esperada=None):
    pasta = Path(pasta)
    manifesto = conferir_arquivo(pasta, 'SHA256SUMS.txt')
    if manifesto.stat().st_size > 16384:
        raise ValueError('Manifesto acima do limite.')
    hashes = {}
    for linha in manifesto.read_text(encoding='utf-8').splitlines():
        m = re.fullmatch(r'([a-f0-9]{64})  (.+)', linha)
        if not m or m[2] not in GERADOS - {'SHA256SUMS.txt'} or m[2] in hashes:
            raise ValueError('Manifesto contém entrada inválida ou repetida.')
        hashes[m[2]] = m[1]
    legado=False
    if completa:
        metadados=conferir_arquivo(pasta,'VERSAO.json')
        legado=versao(json.loads(metadados.read_text(encoding='utf-8'))['versao']) < (2,34,0)
    exigidos = (GERADOS - {'SHA256SUMS.txt'} if not legado else (GERADOS-{'SHA256SUMS.txt',BINARIOS[2],BINARIOS[3],'Como usar o DeliveryBot Funcionario.txt'})) if completa else set(BINARIOS[:2])
    if not exigidos.issubset(hashes):
        raise ValueError('Distribuição incompleta.')
    for nome, esperado in hashes.items():
        with conferir_arquivo(pasta, nome).open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != esperado:
                raise ValueError(f'Integridade divergente: {nome}')
    if completa:
        dados = json.loads((pasta/'VERSAO.json').read_text(encoding='utf-8'))
        versao(dados['versao'])
        if esperada is not None and dados['versao'] != esperada:
            raise ValueError('A distribuição não corresponde à versão atual.')
    return True


def finalizar(pasta, raiz=ROOT):
    pasta, raiz = Path(pasta), Path(raiz)
    atual = (raiz/'VERSION').read_text(encoding='utf-8').strip()
    versao(atual)
    for nome in BINARIOS:
        conferir_arquivo(pasta, nome)
    fontes = [(conferir_arquivo(raiz, origem), destino) for origem, destino in DOCUMENTOS.items()]
    for _, destino in fontes:
        if vinculo(pasta/destino):
            raise ValueError('Documento de saída não pode ser um vínculo.')
    for nome in ('VERSAO.json', 'SHA256SUMS.txt'):
        if vinculo(pasta/nome):
            raise ValueError('Manifesto de saída não pode ser um vínculo.')
    for origem, destino in fontes:
        shutil.copyfile(origem, pasta/destino)
    (pasta/'VERSAO.json').write_text(json.dumps({'versao':atual, 'instalador':BINARIOS[0], 'aplicativo':BINARIOS[1], 'instalador_funcionario':BINARIOS[2], 'aplicativo_funcionario':BINARIOS[3]}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    gerar_hashes(pasta, sorted(GERADOS - {'SHA256SUMS.txt'}))
    verificar(pasta, completa=True, esperada=atual)
    if pasta.parent == raiz/'dist' and pasta.name == 'v'+atual:
        aviso = raiz/'dist/LEIA-ME.txt'
        if vinculo(aviso):
            raise ValueError('O indicador da versão não pode ser um vínculo.')
        aviso.write_text(f'DeliveryBot {atual}\n\nAbra v{atual}\\{BINARIOS[0]} para instalar ou atualizar.\nO aplicativo portátil está na mesma pasta: {BINARIOS[1]}.\nNão são necessários Docker, Python ou Node.js no computador do cliente.\n\nOs dados de uso ficam em %LOCALAPPDATA%\\DeliveryBot.\nAs pastas antigas em dist são apenas distribuições; o histórico está no Git e em CHANGELOG.md.\n', encoding='utf-8')
    return atual


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--distpath', type=Path)
    p.add_argument('--verificar', action='store_true')
    args = p.parse_args()
    atual = (ROOT/'VERSION').read_text().strip()
    destino = args.distpath or ROOT/'dist'/('v'+atual)
    if args.verificar:
        verificar(destino, completa=True, esperada=atual)
    else:
        finalizar(destino)
    print(f'Distribuição v{atual}: instalador, aplicativo, guias, licenças e hashes conferidos.')
