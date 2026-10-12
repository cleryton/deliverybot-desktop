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
& $taskPython -m PyInstaller --clean --noconfirm --distpath $taskDist Funcionario.spec
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar o aplicativo do funcionário.' }
& $taskPython packaging\criar_instalador.py --distpath $taskDist
if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar o instalador.' }
& $taskPython packaging\distribuicao.py --distpath $taskDist
if ($LASTEXITCODE -ne 0) { throw 'A distribuição está incompleta ou falhou na conferência de integridade.' }
$taskSmoke = Join-Path $PSScriptRoot 'artifacts\executavel-local.json'
New-Item -ItemType Directory -Path (Split-Path $taskSmoke) -Force | Out-Null
$taskProcess = Start-Process -FilePath (Join-Path $taskDist 'DeliveryBot.exe') -ArgumentList @('--smoke-test', ('"'+$taskSmoke+'"')) -WindowStyle Hidden -PassThru
if (-not $taskProcess.WaitForExit(120000)) {
    Stop-Process -Id $taskProcess.Id -Force
    throw 'O teste do aplicativo excedeu dois minutos.'
}
if ($taskProcess.ExitCode -ne 0 -or -not (Get-Content -LiteralPath $taskSmoke -Raw | ConvertFrom-Json).ok) { throw 'O aplicativo compilado falhou no teste com dados fictícios.' }
Write-Host "Aplicativo e instalador testados disponíveis em $taskDist."
Write-Host 'Para simular a limpeza de versões e caches: python packaging\limpar_pasta.py'
