$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskVersion = (Get-Content -LiteralPath 'VERSION' -Raw).Trim()
if ($taskVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'Versão inválida em VERSION.' }
$taskDist = Join-Path $PSScriptRoot "dist\v$taskVersion"
$taskPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Instale o Python 3.12 para compilar.' }
}
& $taskPython -m pip install -r requirements-desktop.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências.' }
& $taskPython -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Os testes falharam.' }
& $taskPython packaging\criar_icone.py
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o ícone.' }
Push-Location -LiteralPath (Join-Path $PSScriptRoot 'whatsapp-native')
try {
    npm.cmd ci --omit=dev --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar a conexão integrada.' }
    npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw 'Os testes da conexão integrada falharam.' }
} finally { Pop-Location }
& $taskPython packaging\preparar_whatsapp.py
if ($LASTEXITCODE -ne 0) { throw 'Falha ao incluir o componente WhatsApp.' }
& $taskPython packaging\preparar_tunel.py
if ($LASTEXITCODE -ne 0) { throw 'Falha ao incluir o túnel da página de pedidos.' }
& $taskPython -m PyInstaller --clean --noconfirm --distpath $taskDist DeliveryBot.spec
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar o aplicativo.' }
& $taskPython packaging\criar_instalador.py --distpath $taskDist
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o instalador.' }
& $taskPython packaging\gerar_hashes.py --distpath $taskDist
if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar os hashes da distribuição.' }
Copy-Item -LiteralPath 'GUIA DO APLICATIVO.md' -Destination (Join-Path $taskDist 'Como usar o DeliveryBot.txt') -Force
Copy-Item -LiteralPath 'PRIVACIDADE E SEGURANÇA.md' -Destination (Join-Path $taskDist 'Privacidade e seguranca.txt') -Force
Copy-Item -LiteralPath 'whatsapp-native\LICENCAS.txt' -Destination (Join-Path $taskDist 'LICENCAS WhatsApp.txt') -Force
Copy-Item -LiteralPath 'cloudflare\runtime\LICENSE.txt' -Destination (Join-Path $taskDist 'LICENCA Cloudflare.txt') -Force
Write-Host "Aplicativo e instalador disponíveis em $taskDist."
