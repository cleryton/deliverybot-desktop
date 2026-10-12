"""Distribuição do terminal; sem WhatsApp, túnel, bancos ou credenciais de uso."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files,collect_submodules

root=Path(SPECPATH)
a=Analysis([str(root/'funcionario.py')],pathex=[str(root)],binaries=[],
    datas=[(str(root/'web/funcionario'),'web/funcionario'),(str(root/'VERSION'),'.')]+collect_data_files('webview'),
    hiddenimports=collect_submodules('webview')+['clr','pythonnet'],hookspath=[],hooksconfig={},runtime_hooks=[],
    excludes=['pytest','tkinter','PyQt5','PyQt6','PySide2','PySide6','webview.platforms.qt','webview.platforms.gtk','webview.platforms.cocoa'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,a.binaries,a.datas,[],name='DeliveryBot-Funcionario',debug=False,strip=False,upx=False,console=False,icon=str(root/'packaging/DeliveryBot.ico'))
