"""Inclui runtime, licenças e conexão direta no instalador Windows."""
import json
from pathlib import Path
import shutil
import subprocess

import requests

root = Path(__file__).resolve().parent.parent
native = root / "whatsapp-native"
runtime = native / "runtime"
runtime.mkdir(exist_ok=True)
node = shutil.which("node")
if not node:
    raise SystemExit("Instale Node.js 20 ou mais recente apenas na máquina de compilação.")
version = subprocess.check_output([node, "--version"], text=True).strip()
if int(version.removeprefix("v").split(".")[0]) < 20:
    raise SystemExit("O componente integrado precisa de Node.js 20 ou mais recente para compilar.")
shutil.copy2(node, runtime / "node.exe")
license_file = runtime / "NODE-LICENSE.txt"
if not license_file.exists() or not (runtime / "version.txt").exists() or (runtime / "version.txt").read_text().strip() != version:
    response = requests.get(f"https://raw.githubusercontent.com/nodejs/node/{version}/LICENSE", timeout=30)
    response.raise_for_status()
    license_file.write_text(response.text, encoding="utf-8")
(runtime / "version.txt").write_text(version, encoding="utf-8")
notices = ["DeliveryBot 2.32.0 — componentes da conexão integrada", "Runtime Node.js: " + version,
           "Biblioteca de conexão: https://github.com/WhiskeySockets/Baileys (7.0.0-rc14)",
           "As licenças e os arquivos distribuídos de cada dependência estão incluídos em node_modules.",
           "A conexão por QR Code usa uma biblioteca comunitária de WhatsApp Web. A API oficial da Meta continua disponível em Configurações.", ""]
for package in sorted((native / "node_modules").glob("**/package.json")):
    try:
        data = json.loads(package.read_text(encoding="utf-8"))
        if data.get("name"):
            notices.append(f"{data['name']} {data.get('version','')} — {data.get('license','Consultar licença no pacote')}")
    except (ValueError, OSError):
        continue
(native / "LICENCAS.txt").write_text("\n".join(notices), encoding="utf-8")
print("Componente integrado preparado com " + version)
