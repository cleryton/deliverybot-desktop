# Execute somente depois de configurar assinatura.json e reconstruir o aplicativo.
param([Parameter(Mandatory=$true)][string]$Arquivo, [Parameter(Mandatory=$true)][string]$SignTool)
$ErrorActionPreference = 'Stop'
$pin = (Get-Content -LiteralPath "$PSScriptRoot/assinatura.json" -Raw | ConvertFrom-Json).thumbprint
if ($pin -notmatch '^[a-fA-F0-9]{40}$') { throw 'Configure o thumbprint do certificado de assinatura antes de gerar a distribuição.' }
if (-not (Test-Path -LiteralPath $Arquivo -PathType Leaf)) { throw 'Arquivo não encontrado.' }
if (-not (Test-Path -LiteralPath $SignTool -PathType Leaf)) { throw 'Informe o caminho do SignTool do Windows SDK.' }
& $SignTool sign /sha1 $pin /fd SHA256 /tr https://timestamp.digicert.com /td SHA256 $Arquivo
if ($LASTEXITCODE -ne 0) { throw 'Falha ao assinar.' }
& "$PSScriptRoot/verificar_assinatura.ps1" -Arquivo $Arquivo -Thumbprint $pin
if ($LASTEXITCODE -ne 0) { throw 'Assinatura sem cadeia de confiança válida.' }
