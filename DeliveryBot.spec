# Apenas recursos de distribuição: não inclui banco, .env ou dados pessoais.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH)
native = root / 'whatsapp-native'
conector = root / 'cloudflare/runtime'
if not (conector / 'cloudflared.exe').exists():
    raise RuntimeError('Prepare o túnel integrado: python packaging/preparar_tunel.py.')
if not (native / 'runtime/node.exe').exists() or not (native / 'node_modules/@whiskeysockets/baileys/package.json').exists():
    raise RuntimeError('Prepare o componente integrado: npm ci em whatsapp-native e python packaging/preparar_whatsapp.py.')
a = Analysis(
    [str(root / 'desktop.py')], pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'web'), 'web'), (str(root / 'sql'), 'sql'), (str(root / 'packaging' / 'DeliveryBot.ico'), 'packaging'),
           (str(root / 'VERSION'), '.'),
           (str(conector), 'cloudflare/runtime'),
           (str(root / 'packaging/cloudflared.json'), 'packaging'),
           (str(root / 'packaging' / 'assinatura.json'), 'packaging'),
           (str(root / 'packaging' / 'verificar_assinatura.ps1'), 'packaging'),
           (str(root / 'data' / 'cardapio.json'), 'data'),
           (str(native / 'runtime'), 'whatsapp-native/runtime'),
           (str(native / 'node_modules'), 'whatsapp-native/node_modules'),
           *[(str(native / name), 'whatsapp-native') for name in ('bridge.mjs','server.mjs','self-test.mjs','package.json','LICENCAS.txt')]] + collect_data_files('webview'),
    hiddenimports=collect_submodules('webview') + ['clr', 'pythonnet'],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['pytest', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'webview.platforms.qt', 'webview.platforms.gtk', 'webview.platforms.cocoa'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='DeliveryBot',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, icon=str(root / 'packaging' / 'DeliveryBot.ico'))
