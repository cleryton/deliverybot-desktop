$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
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
& $taskPython -m PyInstaller --noconfirm DeliveryBot.spec
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar o aplicativo.' }
& $taskPython packaging\criar_instalador.py
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o instalador.' }
Write-Host 'Aplicativo e instalador disponíveis na pasta dist.'
