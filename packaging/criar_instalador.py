"""Compila um instalador Windows por usuário, usando o compilador .NET do sistema."""
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent.parent
packaging = root / "packaging"
compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
if not compiler.exists():
    compiler = Path(os.environ.get("WINDIR", "C:/Windows")) / "Microsoft.NET/Framework/v4.0.30319/csc.exe"
if not compiler.exists():
    raise SystemExit("Compilador .NET Framework não encontrado. O executável portátil continua disponível.")
(root / "build").mkdir(exist_ok=True)
uninstaller = root / "build/Desinstalar.exe"
def compilar(source, output, resources=()):
    args = [str(compiler), "/nologo", "/target:winexe", "/platform:anycpu", "/optimize+",
            "/reference:System.Windows.Forms.dll", "/reference:System.Drawing.dll",
            "/win32icon:" + str(packaging / "DeliveryBot.ico"),
            "/win32manifest:" + str(packaging / "app.manifest"), "/out:" + str(output)]
    args.extend("/resource:"+str(path)+","+name for path,name in resources)
    subprocess.run(args+[str(source)],check=True,cwd=root)
compilar(packaging / "Desinstalador.cs", uninstaller)
compilar(packaging / "Instalador.cs",root / "dist/Instalar DeliveryBot.exe",
         [(root / "dist/DeliveryBot.exe","aplicativo"),(uninstaller,"desinstalador"),(packaging/"DeliveryBot.ico","icone")])
print("Instalador criado: dist/Instalar DeliveryBot.exe")
