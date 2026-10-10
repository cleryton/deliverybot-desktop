# ============================================================================
# iniciar.ps1
#
# Script de inicializacao automatizada e auto-suficiente do deliverybot.
# Normalmente voce NAO roda este arquivo direto -- de um duplo clique em
# "Iniciar DeliveryBot.bat" (mesma pasta), que chama este script por voce.
#
# Na PRIMEIRA vez que roda, ele tambem se prepara sozinho:
#   - cria a venv e instala as dependencias, se ainda nao existirem;
#   - copia .env.example para .env, se o .env ainda nao existir;
#   - gera sozinho qualquer segredo de seguranca que esteja vazio no .env
#     (WEBHOOK_SECRET, COZINHA_SENHA, WAHA_DASHBOARD_PASSWORD, WAHA_API_KEY) --
#     os valores gerados NUNCA aparecem na tela, por seguranca.
#
# Depois disso, a cada execucao ele: sobe o WAHA (se o Docker estiver
# disponivel), confere a sessao, abre o ngrok (se instalado), pega a URL
# publica, atualiza o BASE_URL do .env, e abre o Flask -- tudo pulando
# graciosamente qualquer peca que nao esteja instalada/disponivel, em vez
# de travar com um erro confuso.
# ============================================================================

$ErrorActionPreference = "Stop"
$pastaProjeto = $PSScriptRoot
Set-Location $pastaProjeto

function Escrever($texto, $cor = "White") {
    Write-Host $texto -ForegroundColor $cor
}

function Gerar-Segredo([int]$tamanho = 28) {
    $caracteres = (48..57) + (65..90) + (97..122)  # 0-9, A-Z, a-z
    -join (1..$tamanho | ForEach-Object { [char]($caracteres | Get-Random) })
}

function Ler-VariavelEnv($nome, $conteudoEnv) {
    if ($conteudoEnv -match "(?m)^$nome=(.*)$") {
        return $matches[1].Trim()
    }
    return ""
}

function Atualizar-VariavelEnv($conteudoEnv, $nome, $valor) {
    if ($conteudoEnv -match "(?m)^$nome=.*$") {
        return ($conteudoEnv -replace "(?m)^$nome=.*$", "$nome=$valor")
    }
    return ($conteudoEnv.TrimEnd("`r", "`n") + "`r`n$nome=$valor`r`n")
}

function Comando-Existe($nome) {
    return [bool](Get-Command $nome -ErrorAction SilentlyContinue)
}

Escrever ""
Escrever "=======================================================" "DarkYellow"
Escrever "   DeliveryBot -- iniciando" "Yellow"
Escrever "=======================================================" "DarkYellow"

# ---------------------------------------------------------------------------
# 0. Preparacao de primeira execucao: .env e venv
# ---------------------------------------------------------------------------

$envPath = Join-Path $pastaProjeto ".env"
if (-not (Test-Path $envPath)) {
    Escrever ""
    Escrever "Primeira vez por aqui: criando o .env a partir do .env.example..." "Cyan"
    Copy-Item (Join-Path $pastaProjeto ".env.example") $envPath
}

# ---------------------------------------------------------------------------
# 0.1 Cadastro da empresa (só na primeira vez desta instância/pasta --
# controlado pela variável EMPRESA_CONFIGURADA, não pelo nome em si, pra
# nunca perguntar de novo mesmo que o restaurante continue com o mesmo
# nome de exemplo por coincidência).
# ---------------------------------------------------------------------------

$conteudoEnv = Get-Content $envPath -Raw
$empresaConfigurada = Ler-VariavelEnv "EMPRESA_CONFIGURADA" $conteudoEnv

if ($empresaConfigurada -ne "true") {
    Escrever ""
    Escrever "=======================================================" "DarkYellow"
    Escrever "   Bem-vindo! Vamos cadastrar o seu restaurante." "Yellow"
    Escrever "=======================================================" "DarkYellow"
    Escrever "(isso só é perguntado uma vez; depois dá pra editar no .env)" "DarkGray"
    Escrever ""

    $nomeEmpresa = ""
    while (-not $nomeEmpresa) {
        $nomeEmpresa = Read-Host "Nome do restaurante/lanchonete"
        if (-not $nomeEmpresa) { Escrever "Não pode ficar em branco." "Red" }
    }

    $telefoneEmpresa = ""
    while (-not $telefoneEmpresa) {
        $telefoneEmpresa = Read-Host "Telefone de contato (ex: (47) 99999-9999)"
        if (-not $telefoneEmpresa) { Escrever "Não pode ficar em branco." "Red" }
    }

    $conteudoEnv = Atualizar-VariavelEnv $conteudoEnv "NOME_RESTAURANTE" $nomeEmpresa
    $conteudoEnv = Atualizar-VariavelEnv $conteudoEnv "TELEFONE_RESTAURANTE" $telefoneEmpresa
    $conteudoEnv = Atualizar-VariavelEnv $conteudoEnv "EMPRESA_CONFIGURADA" "true"
    Set-Content -Path $envPath -Value $conteudoEnv -NoNewline

    Escrever ""
    Escrever "Cadastrado: $nomeEmpresa — $telefoneEmpresa" "Green"
    Escrever "Outros dados (endereço, horário, taxa de entrega, cardápio...)" "DarkGray"
    Escrever "ficam no .env e no data/cardapio.json -- edite quando quiser." "DarkGray"
    Escrever ""
}

$venvPython = Join-Path $pastaProjeto "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Escrever ""
    Escrever "Primeira vez por aqui: preparando o ambiente Python (isso demora" "Cyan"
    Escrever "só nesta primeira vez)..." "Cyan"
    python -m venv venv
    & (Join-Path $pastaProjeto "venv\Scripts\pip.exe") install -r requirements.txt --quiet
    Escrever "Ambiente Python pronto." "Green"
}

# ---------------------------------------------------------------------------
# 1. Preencher sozinho qualquer segredo vazio no .env (sem nunca exibi-lo)
# ---------------------------------------------------------------------------

$conteudoEnv = Get-Content $envPath -Raw
$segredosObrigatorios = @("WEBHOOK_SECRET", "WAHA_DASHBOARD_PASSWORD", "WAHA_API_KEY")
$gerouAlgum = $false

foreach ($nomeVar in $segredosObrigatorios) {
    $valorAtual = Ler-VariavelEnv $nomeVar $conteudoEnv
    if (-not $valorAtual) {
        $conteudoEnv = Atualizar-VariavelEnv $conteudoEnv $nomeVar (Gerar-Segredo)
        $gerouAlgum = $true
    }
}

if ($gerouAlgum) {
    Set-Content -Path $envPath -Value $conteudoEnv -NoNewline
    Escrever ""
    Escrever "Gerei sozinho os segredos de segurança que ainda estavam vazios no" "Cyan"
    Escrever ".env (não exibidos aqui, por segurança -- abra o .env se quiser ver)." "Cyan"
    $conteudoEnv = Get-Content $envPath -Raw  # relê com os valores novos
}

$cozinhaUsuario = Ler-VariavelEnv "COZINHA_USUARIO" $conteudoEnv
if (-not $cozinhaUsuario) { $cozinhaUsuario = "admin" }
$cozinhaAuthModo = (Ler-VariavelEnv "COZINHA_AUTH_MODO" $conteudoEnv).ToUpper()
if (-not $cozinhaAuthModo) { $cozinhaAuthModo = "SENHA" }

# ---------------------------------------------------------------------------
# 1.1 Senha do painel da cozinha: só gera se o modo for "SENHA" (padrão) e
# ainda não existir um hash salvo. A senha em texto puro é mostrada UMA
# VEZ na tela (precisa, senão ninguém saberia qual senha digitar) e nunca
# é salva em lugar nenhum -- só o hash fica no .env. Pra trocar depois sem
# passar por aqui de novo: python definir_senha_cozinha.py
# ---------------------------------------------------------------------------

if ($cozinhaAuthModo -eq "SENHA") {
    $hashAtual = Ler-VariavelEnv "COZINHA_SENHA_HASH" $conteudoEnv
    if (-not $hashAtual) {
        Escrever ""
        Escrever "Gerando a senha de login do painel da cozinha (primeira vez)..." "Cyan"
        $saidaPython = & $venvPython -c "from werkzeug.security import generate_password_hash; import secrets; p = secrets.token_urlsafe(9); print(p); print(generate_password_hash(p))"
        $linhasSaida = $saidaPython -split "`r?`n" | Where-Object { $_ }
        $senhaGerada = $linhasSaida[0]
        $hashGerado = $linhasSaida[1]

        $conteudoEnv = Atualizar-VariavelEnv $conteudoEnv "COZINHA_SENHA_HASH" $hashGerado
        Set-Content -Path $envPath -Value $conteudoEnv -NoNewline

        Escrever ""
        Escrever "=======================================================" "Red"
        Escrever "  SENHA DO PAINEL DA COZINHA -- ANOTE AGORA:" "Red"
        Escrever "  Usuário: $cozinhaUsuario" "White"
        Escrever "  Senha:   $senhaGerada" "White"
        Escrever "  (não aparece de novo; pra trocar depois: python definir_senha_cozinha.py)" "Red"
        Escrever "=======================================================" "Red"
        Escrever ""
    }
} elseif ($cozinhaAuthModo -eq "WINDOWS") {
    Escrever ""
    Escrever "Login da cozinha no modo WINDOWS: use seu usuário/senha do Windows" "DarkGray"
    Escrever "desta máquina (precisa de 'pip install pywin32' na venv)." "DarkGray"
}

$whatsappProvider = (Ler-VariavelEnv "WHATSAPP_PROVIDER" $conteudoEnv).ToUpper()
$dashboardUsuario = Ler-VariavelEnv "WAHA_DASHBOARD_USERNAME" $conteudoEnv
if (-not $dashboardUsuario) { $dashboardUsuario = "admin" }

# ---------------------------------------------------------------------------
# 2. Docker / WAHA -- só se este projeto estiver configurado para usar WAHA
# ---------------------------------------------------------------------------

function Docker-Rodando {
    docker info > $null 2>&1
    return $LASTEXITCODE -eq 0
}

function Garantir-DockerDesktopAberto {
    if (Docker-Rodando) {
        return $true
    }

    Escrever "Docker Desktop não está aberto -- tentando abrir sozinho..." "Yellow"

    $caminhosPossiveis = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    )
    $exeDocker = $caminhosPossiveis | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $exeDocker) {
        Escrever "Não encontrei o Docker Desktop instalado nos locais padrão." "Red"
        Escrever "Abra o Docker Desktop manualmente e rode este script de novo." "Red"
        return $false
    }

    Start-Process $exeDocker
    Escrever "Abrindo o Docker Desktop... isso pode levar 30-60s na primeira vez." "Yellow"

    $tentativas = 0
    while (-not (Docker-Rodando) -and $tentativas -lt 60) {
        Start-Sleep -Seconds 2
        $tentativas++
        if ($tentativas % 5 -eq 0) {
            Escrever "  ainda esperando o Docker iniciar... ($($tentativas * 2)s)" "DarkGray"
        }
    }

    if (Docker-Rodando) {
        Escrever "Docker Desktop iniciado." "Green"
        return $true
    } else {
        Escrever "O Docker Desktop demorou demais pra iniciar. Abra-o manualmente," "Red"
        Escrever "espere ele terminar de carregar, e rode este script de novo." "Red"
        return $false
    }
}

$sessaoOk = $false

if ($whatsappProvider -ne "WAHA") {
    Escrever ""
    Escrever "WHATSAPP_PROVIDER não é WAHA (está '$whatsappProvider') -- pulando Docker/WAHA." "DarkGray"
} elseif (-not (Comando-Existe "docker")) {
    Escrever ""
    Escrever "Docker não encontrado. Instale o Docker Desktop (docker.com/products/docker-desktop)" "Red"
    Escrever "e abra-o antes de conectar o WhatsApp de verdade. Continuando sem ele..." "Red"
} elseif (-not (Garantir-DockerDesktopAberto)) {
    Escrever "Continuando sem o Docker por enquanto (o WhatsApp não vai conectar)." "Red"
} else {
    Escrever ""
    Escrever "=== Subindo o WAHA (Docker) ===" "Cyan"
    docker compose up -d 2>&1 | Out-String | Write-Host
    if ($LASTEXITCODE -ne 0) {
        Escrever "O 'docker compose up' retornou um erro (veja acima). Continuando" "Red"
        Escrever "sem o WAHA por enquanto." "Red"
    }

    Start-Sleep -Seconds 3

    $wahaApiKey = Ler-VariavelEnv "WAHA_API_KEY" $conteudoEnv
    $headers = @{}
    if ($wahaApiKey) { $headers["X-Api-Key"] = $wahaApiKey }

    try {
        $sessao = Invoke-RestMethod -Uri "http://localhost:3000/api/sessions/default" -Method GET -Headers $headers -ErrorAction Stop
        if ($sessao.status -eq "WORKING") {
            Escrever "Sessão do WhatsApp já está conectada (WORKING)." "Green"
            $sessaoOk = $true
        } else {
            Escrever "Sessão existe, mas o status é: $($sessao.status)" "Yellow"
        }
    } catch {
        Escrever "Sessão do WhatsApp ainda não está conectada." "Yellow"
    }

    if (-not $sessaoOk) {
        Escrever ""
        Escrever "Abrindo o painel do WhatsApp pra você escanear o QR Code..." "Yellow"
        Escrever "Login: usuário '$dashboardUsuario', senha em WAHA_DASHBOARD_PASSWORD no seu .env" "Yellow"
        Start-Process "http://localhost:3000/dashboard"
    }
}

# ---------------------------------------------------------------------------
# 3. ngrok -- só se estiver instalado
# ---------------------------------------------------------------------------

$ngrokUrl = $null

if (-not (Comando-Existe "ngrok")) {
    Escrever ""
    Escrever "ngrok não encontrado -- o link do pedido vai funcionar só na sua" "Yellow"
    Escrever "rede local (http://localhost:5000), não fora dela. Instale em" "Yellow"
    Escrever "https://ngrok.com/download se quiser link público." "Yellow"
} else {
    Escrever ""
    Escrever "=== Abrindo o ngrok (porta 5000) ===" "Cyan"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'DeliveryBot - ngrok'; ngrok http 5000"

    Escrever "Esperando o ngrok ficar pronto..." "Cyan"
    $tentativas = 0
    while (-not $ngrokUrl -and $tentativas -lt 20) {
        Start-Sleep -Seconds 1
        $tentativas++
        try {
            $tuneis = Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels" -Method GET -ErrorAction Stop
            $tunelHttps = $tuneis.tunnels | Where-Object { $_.proto -eq "https" } | Select-Object -First 1
            if ($tunelHttps) { $ngrokUrl = $tunelHttps.public_url }
        } catch { }
    }

    if ($ngrokUrl) {
        Escrever "URL pública: $ngrokUrl" "Green"
        $conteudoEnv = Get-Content $envPath -Raw
        $conteudoEnv = Atualizar-VariavelEnv $conteudoEnv "BASE_URL" $ngrokUrl
        Set-Content -Path $envPath -Value $conteudoEnv -NoNewline
    } else {
        Escrever "Não consegui pegar a URL do ngrok automaticamente -- confira a" "Red"
        Escrever "janela do ngrok e cole a URL manualmente em BASE_URL no .env." "Red"
    }
}

# ---------------------------------------------------------------------------
# 4. Flask
# ---------------------------------------------------------------------------

Escrever ""
Escrever "=== Iniciando o sistema (Flask) ===" "Cyan"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle = 'DeliveryBot - Sistema'; cd '$pastaProjeto'; venv\Scripts\Activate.ps1; python -m src.app"

Start-Sleep -Seconds 2

Escrever ""
Escrever "=======================================================" "DarkYellow"
Escrever "   Tudo pronto!" "Green"
Escrever "=======================================================" "DarkYellow"
if ($ngrokUrl) {
    Escrever "Link do pedido (exemplo): $ngrokUrl/m/<token>" "White"
    Escrever "Painel da cozinha:        $ngrokUrl/cozinha" "White"
} else {
    Escrever "Painel da cozinha (rede local): http://localhost:5000/cozinha" "White"
}
if ($cozinhaAuthModo -eq "WINDOWS") {
    Escrever "Login da cozinha: use seu usuário/senha do Windows desta máquina" "White"
} else {
    Escrever "Login da cozinha: usuário '$cozinhaUsuario' (a senha foi mostrada na" "White"
    Escrever "primeira vez que você rodou; pra trocar: python definir_senha_cozinha.py)" "White"
}
if ($whatsappProvider -eq "WAHA" -and -not $sessaoOk) {
    Escrever ""
    Escrever "Lembre de escanear o QR Code na aba que abriu no navegador." "Yellow"
}
Escrever ""
Escrever "Duas janelas novas foram abertas (ngrok e Sistema) -- não feche" "DarkGray"
Escrever "enquanto estiver usando. Para parar tudo, use 'Parar DeliveryBot.bat'." "DarkGray"
Escrever ""
