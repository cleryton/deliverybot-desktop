param([Parameter(Mandatory=$true)][string]$Arquivo, [Parameter(Mandatory=$true)][string]$Thumbprint)
$ErrorActionPreference = 'Stop'
try {
    $assinatura = Get-AuthenticodeSignature -LiteralPath $Arquivo
    if ($assinatura.Status -eq 'Valid' -and $assinatura.SignerCertificate.Thumbprint -eq $Thumbprint) {
        Write-Output 'VALIDA'
        exit 0
    }
} catch { }
exit 1
