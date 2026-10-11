"""Verificações sem serviços ou dependências extras para a integração contínua."""
import json
import re
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent


def verificar():
    versao = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', versao):
        raise ValueError('VERSION deve conter uma versão X.Y.Z.')
    esperados = {
        'GUIA DO APLICATIVO.md': f'# DeliveryBot Desktop {versao}',
        'CHANGELOG.md': f'## {versao} — ',
        'packaging/Instalador.cs': f'key.SetValue("DisplayVersion","{versao}")',
        'packaging/preparar_whatsapp.py': f'DeliveryBot {versao} — componentes',
        'web/templates/gestao.html': f'DeliveryBot Desktop · {versao}</small>',
        'whatsapp-native/LICENCAS.txt': f'DeliveryBot {versao} — componentes',
    }
    for arquivo, texto in esperados.items():
        if texto not in (ROOT / arquivo).read_text(encoding='utf-8'):
            raise ValueError(f'Versão divergente em {arquivo}.')
    manifest = ET.parse(ROOT / 'packaging/app.manifest').getroot()
    identidade = manifest.find('{urn:schemas-microsoft-com:asm.v1}assemblyIdentity')
    if identidade is None or identidade.get('version') != versao + '.0':
        raise ValueError('Versão divergente no manifesto Windows.')
    pacote = json.loads((ROOT / 'whatsapp-native/package.json').read_text(encoding='utf-8'))
    lock = json.loads((ROOT / 'whatsapp-native/package-lock.json').read_text(encoding='utf-8'))
    if pacote['version'] != versao or lock['version'] != versao or lock['packages']['']['version'] != versao:
        raise ValueError('Versão divergente nos arquivos do componente WhatsApp.')
    if pacote['dependencies'] != lock['packages']['']['dependencies']:
        raise ValueError('Dependências WhatsApp divergentes do lockfile.')
    def dependencias(arquivo):
        return dict(re.findall(r'^([\w.-]+)==([^\s]+)\s*$', (ROOT / arquivo).read_text(encoding='utf-8'), re.MULTILINE))
    lock_python = dependencias('requirements-desktop.lock.txt')
    for arquivo in ('requirements.txt', 'requirements-desktop.txt'):
        for nome, pin in dependencias(arquivo).items():
            if lock_python.get(nome) != pin:
                raise ValueError(f'{nome} em {arquivo} diverge do lockfile desktop.')
    arquivos = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    proibidos = {'.venv', 'venv', 'node_modules', '__pycache__', 'build', 'dist', 'runtime'}
    extensoes = {'.exe', '.db', '.sqlite', '.sqlite3', '.dbot', '.dbot-local', '.log', '.key', '.pfx', '.p12'}
    for nome in filter(None, arquivos):
        p = Path(nome)
        if (proibidos.intersection(p.parts) or p.suffix.lower() in extensoes
                or (p.name.startswith('.env') and p.name != '.env.example')
                or p.name.endswith(('.db-wal', '.db-shm', '.sqlite3-wal', '.sqlite3-shm'))):
            raise ValueError(f'Arquivo privado ou gerado não deve ser versionado: {nome}')
        if p.suffix == '.py':
            compile((ROOT / p).read_text(encoding='utf-8-sig'), nome, 'exec', dont_inherit=True)
    print(f'Projeto v{versao}: versões, dependências, sintaxe Python e arquivos versionados conferidos.')


if __name__ == '__main__':
    verificar()
