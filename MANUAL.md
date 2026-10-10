# Manual do DeliveryBot (Barbaros Lanches)

Bot de atendimento e pedidos por WhatsApp. O cliente conversa em linguagem
natural (IA), recebe um link único para montar o pedido, recebe o cupom no
WhatsApp, e a cozinha acompanha tudo em um painel protegido por login.

---

## 1. Como o sistema funciona

```
Cliente (WhatsApp)
      │  manda mensagem
      ▼
WAHA (Docker, porta 3000)  ── webhook c/ segredo ──►  Flask (porta 5000)  ──► IA (Ollama ou Claude)
      ▲                                                     │
      └──────────────────── resposta do bot ◄───────────────┘
                                                             │
Cliente abre o link  https://xxxx.ngrok-free.dev/m/<token>  (ngrok expõe o Flask)
      │  escolhe itens, pagamento, CEP (ViaCEP)
      ▼
Pedido salvo ► cupom no WhatsApp ► painel da cozinha (/cozinha, com login) ► avisos de status
```

Peças:

| Peça | Para quê |
|---|---|
| **WAHA** | Conecta o seu número de WhatsApp (QR Code) e entrega/recebe mensagens |
| **Flask** (`src/app.py`) | Cérebro do bot, página do pedido e painel da cozinha |
| **IA** | Conversa de forma humana. **Ollama** (grátis, local) ou **Claude** (API paga) |
| **ngrok** | Deixa o link do pedido acessível pelo celular do cliente |
| **SQLite** (modo WAL) | Banco (`data/deliverybot.db`), criado e migrado sozinho |

Se a IA falhar por qualquer motivo, o bot cai no **menu numerado** e o
atendimento não para. Mensagens muito rápidas do mesmo número (flood) também
caem no menu fixo em vez de chamar a IA de novo (ver seção 12).

---

## 2. O que você precisa instalar (uma vez só)

1. **Python 3.11 ou mais novo**: https://www.python.org/downloads/ (marque "Add Python to PATH").
2. **Docker Desktop**: https://www.docker.com/products/docker-desktop/ (deixe aberto e rodando).
3. **ngrok**: https://ngrok.com/download. Crie conta grátis e rode uma vez
   `ngrok config add-authtoken SEU_TOKEN` (o token está no painel do ngrok).
4. **Ollama** (só se for usar IA grátis): https://ollama.com/download/windows

---

## 3. Instalação (primeira vez)

1. Extraia o zip. Você terá a pasta do projeto.
2. Dê **dois cliques** em **`Iniciar DeliveryBot.bat`**.

É só isso. Na primeira vez, esse arquivo:
- cria o `.env` (a partir do `.env.example`), se ainda não existir;
- cria a venv e instala tudo do `requirements.txt`, se ainda não existir
  (demora um pouco só nessa primeira vez);
- gera sozinho os segredos de segurança que estiverem vazios
  (`WEBHOOK_SECRET`, a senha da cozinha, `WAHA_DASHBOARD_PASSWORD`,
  `WAHA_API_KEY`) -- nunca aparecem na tela, ficam só dentro do `.env`;
- sobe o Docker/WAHA (se o Docker estiver instalado e aberto) e o ngrok
  (se estiver instalado) -- e segue sem eles, avisando, se não estiverem;
- abre o sistema (Flask) numa janela própria.

Se o Windows perguntar algo sobre "política de execução" na primeira vez,
responda com:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
(isso só precisa ser feito uma vez, e só libera scripts PowerShell para a
sua conta de usuário, não muda nada no resto do sistema.)

Depois disso, confira os dados do restaurante na seção 6, e configure a
IA na seção 4 se quiser.

> **Dica:** clique com o botão direito em `Iniciar DeliveryBot.bat` →
> "Enviar para" → "Área de trabalho (criar atalho)" para abrir o sistema
> direto da área de trabalho, como um programa normal.

---

## 4. Configurar a IA

### Opção A: Ollama (grátis, roda no seu PC)

```powershell
ollama pull llama3.2:3b
ollama list          # o modelo precisa aparecer na lista
```

Deixe o Ollama aberto (ícone na bandeja do Windows). Teste:
`http://localhost:11434` deve mostrar "Ollama is running".

No `.env`:
```
IA_PROVIDER=OLLAMA
OLLAMA_MODEL=llama3.2:3b
```
O nome do modelo precisa ser **igual** ao que aparece no `ollama list`.

Com `OLLAMA_AQUECER_AO_INICIAR=true` (padrão), o Flask já pede pro Ollama
carregar o modelo na memória assim que sobe, em segundo plano -- a primeira
mensagem de um cliente de verdade não paga mais o custo de 30-60s. Ainda
assim, a primeira chamada depois de ligar o PC pode demorar um pouco.

Outros ajustes finos (`OLLAMA_TEMPERATURE`, `OLLAMA_NUM_PREDICT`,
`OLLAMA_KEEP_ALIVE`, `OLLAMA_TIMEOUT_SEGUNDOS`) ficam no `.env`; os valores
padrão já funcionam bem.

### Opção B: Claude (mais rápido e mais confiável)

1. Crie uma chave em https://console.anthropic.com e adicione crédito
   (a API é paga por uso, separada da assinatura do Claude.ai).
2. No `.env`:
   ```
   IA_PROVIDER=ANTHROPIC
   ANTHROPIC_API_KEY=sua_chave
   ANTHROPIC_MODEL=claude-haiku-4-5-20251001
   ```
3. Com o venv ativo: `pip install anthropic` (já está no `requirements.txt`).

### Desligar a IA
Deixe `IA_PROVIDER=` vazio. O bot usa só o menu numerado.

### Testar a IA sem WhatsApp
```powershell
python testar_ia.py
```
Mostra o modelo lido do `.env`, os modelos instalados no Ollama e uma
resposta de teste. Se algo estiver errado, ele diz o quê.

---

## 5. Conectar o WhatsApp (WAHA)

1. Confirme que o `.env` já tem `WEBHOOK_SECRET`, `WAHA_API_KEY` e
   `WAHA_DASHBOARD_PASSWORD` preenchidos (seção 12) -- o `docker-compose.yml`
   lê essas variáveis do `.env`, não tem mais senha fixa no arquivo.
2. Suba o Docker:
   ```powershell
   docker compose up -d
   ```
3. Abra `http://localhost:3000/dashboard`. Login: usuário de
   `WAHA_DASHBOARD_USERNAME`, senha de `WAHA_DASHBOARD_PASSWORD` (ambos no
   seu `.env`).
4. Em **Sessions**, inicie a sessão (**Start New** ou o botão de play).
5. Clique no ícone de QR Code e escaneie com o WhatsApp do celular do
   restaurante: **WhatsApp > Aparelhos conectados > Conectar um aparelho**.
6. Espere o status ficar **WORKING** (verde).

O número escaneado é o **número do bot**. É nele que os clientes mandam mensagem.

> A sessão fica salva no Docker. Depois de reiniciar o PC ou o Docker, ela
> volta sozinha (`WHATSAPP_RESTART_ALL_SESSIONS=True`). Se aparecer o QR de
> novo, escaneie outra vez.

**Nome da sessão:** o `.env` usa `WAHA_SESSION=default`. O bot responde usando
o nome da sessão que vem em cada mensagem recebida, então normalmente não
precisa ajustar. Se aparecer o erro `Session "..." does not exist` ao enviar,
copie o nome exato da sessão no dashboard (coluna Name) e coloque em
`WAHA_SESSION` no `.env`.

**Webhook:** o endereço que o WAHA chama já inclui o `WEBHOOK_SECRET` do seu
`.env` embutido na URL (`WHATSAPP_HOOK_URL` no `docker-compose.yml`). Se você
trocar o `WEBHOOK_SECRET`, precisa recriar o container do WAHA
(`docker compose up -d --force-recreate waha`) para ele pegar a URL nova.

---

## 6. Dados do restaurante

No `.env`:

```
NOME_RESTAURANTE=Barbaros Lanches
TELEFONE_RESTAURANTE=(47) 3000-0000
ENDERECO_RESTAURANTE=Rua das Hamburguerias, 123 - Centro
HORARIO_FUNCIONAMENTO=Terça a Domingo, das 18h às 23h30
TAXA_ENTREGA=6.00
CEP_RESTAURANTE=89460-000
RAIO_ENTREGA_KM=6
TEMPO_PREPARO_MIN=40
VALIDADE_LINK_MIN=30
```

**Cardápio:** `data/cardapio.json`. É carregado **só quando o banco está
vazio**. Para trocar o cardápio depois de já ter usado: feche o Flask, apague
`data/deliverybot.db` (e os arquivos `-wal`/`-shm` ao lado, se existirem),
edite o JSON e inicie de novo (isso apaga pedidos e histórico).

**Fotos dos produtos (opcional):** salve a foto em
`web/static/produtos/` e adicione o campo `"imagem": "nome-do-arquivo.jpg"`
no item correspondente do `cardapio.json`. Itens sem foto aparecem com um
retrato ilustrado automático (ícone da categoria) em vez de ficar quebrado.
Veja `web/static/produtos/README.md` para detalhes e dica de tamanho.

Depois de mudar o `.env`, **reinicie o Flask**. Ele só lê o arquivo ao iniciar.

---

## 7. Iniciar tudo (dia a dia)

Abra o Docker Desktop e o Ollama (se for usar), e dê **dois cliques em
`Iniciar DeliveryBot.bat`**. Abrem **duas janelas novas** (`DeliveryBot -
ngrok` e `DeliveryBot - Sistema`) -- não feche enquanto estiver usando. A
janela principal (onde você clicou) mostra um resumo e pode ser fechada
sem problema; o sistema continua rodando nas outras duas.

Para **parar tudo de uma vez**: dê dois cliques em **`Parar DeliveryBot.bat`**
-- ele fecha as janelas do ngrok e do sistema e desliga o Docker.

Cada peça (Docker/WAHA, ngrok) é opcional do ponto de vista do script: se
alguma não estiver instalada ou aberta, ele avisa e segue sem ela (por
exemplo, sem ngrok o sistema funciona só na rede local, sem WAHA o bot só
responde no modo teste/console).

### Iniciar manualmente (se preferir, ou para depurar um problema)
```powershell
docker compose up -d
ngrok http 5000                       # janela 1: copie a URL https "Forwarding"
# cole a URL em BASE_URL no .env, salve
.\venv\Scripts\Activate.ps1           # janela 2
python -m src.app
```

> **Atenção:** se não usar plano pago do ngrok, a URL muda toda vez que o
> ngrok reinicia. O `iniciar.ps1` (chamado pelo `.bat`) atualiza o
> `BASE_URL` sozinho a cada execução. Links de pedidos antigos deixam de
> funcionar quando a URL muda.

---

## 8. Testar com outro usuário (passo a passo)

O bot **não responde a mensagens do próprio número conectado**. Você precisa
de **outro celular/número** para fazer o papel do cliente.

### Preparação
- [ ] Docker Desktop aberto
- [ ] Ollama aberto (se usar IA grátis)
- [ ] `.\iniciar.ps1` rodado, duas janelas abertas (ngrok e Flask)
- [ ] Dashboard `http://localhost:3000/dashboard`: sessão **WORKING**
- [ ] Salvou o número do bot (o que você escaneou) no celular do cliente de teste

### Roteiro de teste
O cliente de teste manda, do outro número, para o número do bot:

| # | Cliente escreve | Esperado |
|---|---|---|
| 1 | `oi` (ou `opa`, `boa noite`) | Cumprimento humano e pergunta como ajudar. **Sem** link e **sem** menu numerado |
| 2 | `vocês abrem hoje?` | Informa o horário real configurado |
| 3 | `quanto é a entrega?` | Informa a taxa e que na retirada é grátis |
| 4 | `o que tem no cardápio?` | Fala do cardápio real |
| 5 | `quero fazer um pedido` | Manda o **link** `https://xxxx.ngrok-free.dev/m/...` |
| 6 | Abre o link no celular | Página do cardápio. O ngrok grátis pode mostrar um aviso, toque em **Visit Site** |
| 7 | Escolhe itens, pagamento, retirada/entrega e CEP | Valida o CEP na ViaCEP e confirma |
| 8 | Finaliza o pedido | Recebe no WhatsApp "pedido #... realizado" e o cupom |
| 9 | (no PC) abre `http://localhost:5000/cozinha` (faz login) e clica para avançar o status | Cliente recebe "Pedido confirmado", depois "Pronto para retirada" |

O link é de **uso único** e vale `VALIDADE_LINK_MIN` minutos. Usado ou
expirado, mostra "link inválido" (HTTP 410). É esperado. Peça outro no chat.

### O que observar no terminal do Flask
- `POST /webhook/waha/... 200`: mensagem recebida e processada.
- **Não** deve aparecer `IA indisponível`. Se aparecer, a mensagem depois
  dos dois pontos diz o motivo (ver seção 13).
- `Erro ao enviar via WAHA ...`: falha ao responder (ver seção 13).
- `Rate limit: ... mandou mensagem rápido demais`: normal se você mandar
  várias mensagens em menos de `RATE_LIMIT_SEGUNDOS` seguidos -- a próxima
  mensagem do mesmo número, mais espaçada, volta a usar a IA.

### Testar sem WhatsApp (só a lógica)
```powershell
python -m src.main_teste        # simula um pedido de ponta a ponta no terminal
```
Com `FLASK_DEBUG=true` no `.env`, `http://localhost:5000/testar` gera um link
de pedido como se o cliente tivesse pedido, sem WhatsApp (esse endpoint fica
**bloqueado** quando `FLASK_DEBUG=false`, de propósito -- ver seção 12). Se
quiser desligar o envio real, `WHATSAPP_PROVIDER=TESTE` no `.env` (as
mensagens só aparecem no console).

### Rodar os testes automatizados
```powershell
pip install pytest
pytest
```
Cada teste usa um banco SQLite temporário isolado -- não afeta
`data/deliverybot.db`. O teste de fila de preparo (`test_fila_de_preparo...`)
só passa com o Docker/WAHA rodando (ele manda uma mensagem de verdade); os
demais não dependem de nada externo.

---

## 9. Painel da cozinha

`http://localhost:5000/cozinha` (ou `SUA_URL_NGROK/cozinha`) lista a fila de
preparo. Cada clique em avançar muda o status e **avisa o cliente
automaticamente** no WhatsApp:

`AGUARDANDO → EM_PREPARO → PRONTO → RETIRADO`

**Login obrigatório:** o navegador vai pedir usuário/senha (HTTP Basic
Auth). Tem dois jeitos de configurar (`COZINHA_AUTH_MODO` no `.env`):

- **`SENHA`** (padrão): usuário = `COZINHA_USUARIO`, senha = a que você
  definiu com `python definir_senha_cozinha.py` (ou a que apareceu na tela
  na primeira vez que rodou o `Iniciar DeliveryBot.bat`). A senha nunca
  fica salva em texto puro -- só o hash, em `COZINHA_SENHA_HASH`.
- **`WINDOWS`**: usa o usuário/senha da própria conta do Windows **desta
  máquina** (a que está rodando o sistema) -- não precisa inventar nem
  guardar senha nenhuma. Requer `pip install pywin32` na venv.

Sem nenhum dos dois configurado corretamente, o painel fica **bloqueado
para todo mundo**, de propósito (ver seção 12).

> O ngrok expõe o link do pedido (`/m/...`) e o painel da cozinha pela
> mesma URL pública. O login protege a cozinha; ainda assim, não divulgue a
> URL além de quem precisa, e troque a senha periodicamente se usar por
> muito tempo.

---

## 10. Eficiência / como o sistema foi otimizado

Para quem for ler o código ou dar manutenção, alguns pontos que foram
cuidados de propósito:

- **Banco em modo WAL** (`PRAGMA journal_mode=WAL`): permite o Flask ler e
  escrever no SQLite ao mesmo tempo (webhook chegando enquanto alguém abre
  a página do pedido) sem o clássico erro "database is locked".
- **Índice em `mensagens(telefone, id)`**: a IA consulta o histórico da
  conversa a cada mensagem recebida; sem índice, isso seria uma busca
  completa na tabela toda vez.
- **`init_db()` roda uma vez só**, não a cada requisição: antes, toda
  requisição HTTP reexecutava o schema inteiro e checava o cardápio no
  banco, sem necessidade.
- **Conexões HTTP reaproveitadas** (`requests.Session`) nas chamadas ao
  WAHA e ao Ollama, em vez de abrir uma conexão nova a cada mensagem.
- **Cache do prompt da IA** por 30 segundos: montar o texto do cardápio
  bate no banco; como o cardápio muda raramente, não precisa remontar a
  cada mensagem.
- **chatId/sessão do WAHA persistidos no banco** (colunas
  `clientes.chat_id` / `clientes.waha_session`), não só em memória -- um
  restart do Flask não volta a cair no erro de "LID" para clientes que já
  mandaram mensagem antes.
- **Logging estruturado** (`logging`, com nível configurável) em vez de
  `print()` espalhado pelo código.

---

## 11. Ajustar o jeito de a IA falar

Tudo está na função `_system_prompt()` em `src/ia.py`:

- **Estilo:** regras curtas (tamanho, emoji, sem menu numerado).
- **Exemplos:** o bloco "EXEMPLOS DE COMO RESPONDER". Modelos pequenos
  imitam exemplos melhor do que seguem instruções, então ajuste o tom
  editando as respostas de exemplo.
- **Quando mandar o link:** regra "REGRAS DE CONTEÚDO".

Se a IA errar um caso (ex.: mandou o link cedo demais), acrescente um
exemplo daquela situação com a resposta certa e reinicie o Flask. Se
precisar que a mudança apareça imediatamente (sem esperar os 30s do cache),
chame `ia.invalidar_cache_prompt()` ou simplesmente reinicie o Flask.

Promoções e formas de pagamento citadas pela IA estão fixas no mesmo
prompt. Edite lá se mudar.

---

## 12. Segurança

### 12.1 Os segredos já são gerados sozinhos

Isso tudo acontece automaticamente na primeira vez que você roda
`Iniciar DeliveryBot.bat` -- você não precisa fazer nada manualmente:

- `WEBHOOK_SECRET`, `WAHA_DASHBOARD_PASSWORD`, `WAHA_API_KEY`: gerados e
  salvos no `.env` sozinhos, nunca aparecem na tela (são usados por
  máquinas, não por uma pessoa digitando).
- Senha do painel da cozinha (`COZINHA_SENHA_HASH`): gerada e **mostrada
  na tela uma única vez**, com um aviso bem visível -- anote nessa hora.
  Só o hash (não a senha de verdade) fica salvo no `.env`.

Se quiser gerar de novo manualmente (ex.: depois de uma suspeita de
vazamento):

```powershell
python gerar_segredos.py              # WEBHOOK_SECRET, WAHA_API_KEY, senha do dashboard do WAHA
python definir_senha_cozinha.py       # senha do painel da cozinha
```

Depois de trocar `WAHA_API_KEY` ou `WAHA_DASHBOARD_PASSWORD`:
```powershell
docker compose down
docker compose up -d
```
(o WAHA precisa subir de novo para aplicar o valor novo.)

**Nunca cole esses valores em chats, prints de tela, grupos ou
repositórios públicos.** Qualquer segredo que apareça em texto em algum
lugar (inclusive numa conversa com uma IA de suporte) deve ser tratado como
exposto e trocado de novo.

### 12.2 O que cada proteção faz

| Proteção | Onde | Risco que evita |
|---|---|---|
| `FLASK_DEBUG=false` (padrão) | `src/app.py` | Com `debug=true` e o link do ngrok público, qualquer erro 500 abriria o console interativo do Werkzeug para a internet -- permite executar código no seu PC. Só ligue `true` testando localmente, nunca com o ngrok rodando |
| `WEBHOOK_SECRET` na URL (`/webhook/waha/<segredo>`, `/api/bot/mensagem/<segredo>`) | `src/app.py`, `docker-compose.yml` | Sem isso, qualquer pessoa que descubra a URL do ngrok pode forjar mensagens do WhatsApp, gerar pedidos falsos ou gastar seus créditos de IA mandando mensagens direto pro webhook |
| Login HTTP Basic em `/cozinha` (senha com hash, ou login do Windows) | `src/app.py`, `src/auth_windows.py` | Sem login, qualquer um com a URL veria todos os pedidos e poderia avançar/confundir o status da fila. A senha nunca é guardada em texto puro (só o hash) -- mesmo que o `.env` seja exposto por acidente, a senha de verdade não está nele |
| `/testar` bloqueado fora de `FLASK_DEBUG=true` | `src/app.py` | Era um atalho de desenvolvimento que gerava pedidos de teste sem senha nenhuma -- exposto, seria um jeito de qualquer um abusar do sistema |
| Segredos lidos do `.env` em vez de fixos no `docker-compose.yml` | `docker-compose.yml` | Evita duplicar/esquecer de trocar senha em dois lugares, e evita subir a senha for acidente num repositório Git junto com o compose |
| `.gitignore` incluindo `.env` | raiz do projeto | Se algum dia você usar Git/GitHub neste projeto, o `.env` (com todos os segredos) nunca é commitado por engano |
| Rate limit por telefone (`RATE_LIMIT_SEGUNDOS`) | `src/bot.py` | Reduz o custo de um flood de mensagens (de propósito ou um webhook reenviando em loop) que chamaria a IA repetidamente |
| `MAX_CONTENT_LENGTH` | `src/app.py` | Limita o tamanho de uma requisição HTTP, evitando payloads gigantes de propósito |
| Erros nunca expõem traceback ao público | `src/app.py` (todos os `try/except` nos webhooks) | Uma falha interna vira log no servidor, não uma página de erro com detalhes do código para quem está de fora |
| `COZINHA_AUTH_MODO=WINDOWS` (opcional) | `src/auth_windows.py` | Login da cozinha reaproveitando a própria conta do Windows da máquina -- nenhuma senha extra pra inventar, lembrar ou vazar |

### 12.3 Antes de usar "de verdade" (não só testes)

- Troque os valores padrão do `.env.example` que ainda estiverem como
  exemplo (ex.: `NOME_RESTAURANTE`, `WHATSAPP_VERIFY_TOKEN`).
- O servidor do Flask (`python -m src.app`) é de **desenvolvimento**. Para
  uso contínuo (não só testes), considere um servidor WSGI de produção
  (ex.: `waitress` no Windows) e, se possível, um domínio fixo em vez do
  ngrok gratuito.
- O WAHA usa o WhatsApp Web por baixo dos panos. Use o número com cuidado
  (evite disparos em massa, que podem causar bloqueio pela própria Meta).
- Revise periodicamente quem tem acesso ao `.env` e ao PC onde ele roda.

---

## 13. Problemas comuns

| Sintoma / log | Causa | Solução |
|---|---|---|
| Webhook retorna "não autorizado" (404) | `WEBHOOK_SECRET` vazio, errado, ou `WHATSAPP_HOOK_URL` do WAHA desatualizada | Confira `WEBHOOK_SECRET` no `.env`; se trocou, recrie o container: `docker compose up -d --force-recreate waha` |
| `/cozinha` pede usuário/senha e nada funciona | `COZINHA_USUARIO` vazio, ou `COZINHA_SENHA_HASH` nunca definido (modo SENHA), ou `pywin32` não instalado (modo WINDOWS) | Modo SENHA: rode `python definir_senha_cozinha.py`. Modo WINDOWS: `pip install pywin32`. Depois reinicie o Flask |
| `/testar` retorna 404 | `FLASK_DEBUG` não é `true` | Normal em "produção". Para testar localmente, ligue `FLASK_DEBUG=true` temporariamente |
| `Session "default" does not exist` (422) | Nome da sessão no `.env` diferente do WAHA, ou sessão parada | Dashboard do WAHA: sessão `WORKING`? Copie o nome exato para `WAHA_SESSION` e reinicie o Flask |
| Sessão do WAHA em `SCAN_QR_CODE` ou `STOPPED` | Desconectou do celular | Reinicie a sessão e escaneie o QR de novo |
| `Ollama inacessível ... WinError 10061` | Ollama não está rodando | Abra o app Ollama ou rode `ollama serve` |
| `Modelo '...' não encontrado` / 404 no Ollama | Modelo não baixado ou nome diferente | `ollama list`, depois `ollama pull llama3.2:3b` e ajuste `OLLAMA_MODEL` |
| `does not support tools` | Modelo sem suporte a ferramentas | Use `llama3.2:3b`, `llama3.1`, `qwen2.5` ou `mistral` |
| `IA desativada` | `IA_PROVIDER` vazio | Defina `OLLAMA` ou `ANTHROPIC` no `.env` e reinicie o Flask |
| `ANTHROPIC_API_KEY não configurada` / erro de crédito | Chave vazia ou sem saldo | Preencha a chave e verifique o crédito no console |
| Biblioteca 'anthropic' não instalada | Falta pacote | `pip install anthropic` com o venv ativo |
| Primeira resposta demora muito | Ollama carregando o modelo (o aquecimento automático ainda não terminou) | Normal na primeira vez após ligar o PC. Pode usar modelo menor ou a API do Claude |
| Alterei o `.env` e nada mudou | Flask antigo ainda aberto | Feche todas as janelas do Flask e inicie de novo |
| Porta 5000 em uso | Flask antigo aberto | Feche a janela antiga ou reinicie o terminal |
| Cliente não recebe resposta | Sessão fora do ar, webhook falhando ou Docker parado | Veja o dashboard e o log do Flask; `docker compose ps` |
| Link do pedido não abre no celular | ngrok fechado ou URL mudou | Rode `iniciar.ps1` de novo e peça um link novo |
| Link dá "inválido" (410) | Expirou ou já foi usado | Peça outro no chat |
| Mensagens de grupo ignoradas | Comportamento proposital | O bot só atende conversas privadas |
| `iniciar.ps1` bloqueado | Política de execução do PowerShell | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` |
| `docker compose` não encontrado | Docker Desktop fechado | Abra o Docker Desktop e espere iniciar |
| Script diz "Docker Desktop demorou demais pra iniciar" | PC lento, ou é a primeira vez que o Docker abre (mais lento) | Espere o ícone do Docker Desktop (bandeja do Windows) ficar fixo/"Running", depois clique no `.bat` de novo |
| QR Code nunca aparece / painel do WAHA não abre | O Docker/WAHA não chegou a subir (veja a mensagem anterior no terminal) | Confirme que o ícone do Docker Desktop está "Running", rode `docker compose up -d` manualmente e veja se dá erro |
| `docker compose up` falha com variável vazia (WAHA_DASHBOARD_PASSWORD etc.) | `.env` incompleto | Normalmente o `iniciar.ps1` já preenche sozinho; se ainda faltou algo, rode `python gerar_segredos.py` e cole os valores no `.env` |
| Duplo clique no `.bat` abre e fecha na hora, sem mostrar nada | Erro logo no início do script | Abra o PowerShell manualmente, rode `.\iniciar.ps1` e leia a mensagem de erro (o `.bat` normalmente pausa no final, mas um erro muito no começo pode fechar rápido) |
| Windows avisa "não é possível executar scripts" | Política de execução do PowerShell | Dentro de um PowerShell: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, depois clique no `.bat` de novo |
| `Parar DeliveryBot.bat` não fecha as janelas | As janelas foram renomeadas ou abertas manualmente (fora do `.bat`) | Feche manualmente pela barra de tarefas, ou pelo Gerenciador de Tarefas |

**Ver logs do WAHA:** `docker compose logs -f waha`

---

## 14. Estrutura de arquivos

```
projeto/
├── .env                  configuração + segredos (local, NUNCA compartilhar)
├── .env.example          modelo do .env, sem segredos reais
├── .gitignore            garante que .env/venv/banco nunca vão para um repositório
├── gerar_segredos.py       gera valores fortes para o .env (rode localmente)
├── definir_senha_cozinha.py  define/troca a senha do painel da cozinha (nunca mostra/guarda em texto puro)
├── MANUAL.md             este manual
├── Iniciar DeliveryBot.bat   clique duplo para ligar tudo (chama o iniciar.ps1)
├── Parar DeliveryBot.bat     clique duplo para desligar tudo
├── iniciar.ps1           lógica real: prepara o ambiente, sobe Docker + ngrok + Flask
├── testar_ia.py          diagnóstico da IA sem WhatsApp
├── docker-compose.yml    WAHA + n8n (n8n é opcional); credenciais vêm do .env
├── requirements.txt
├── data/cardapio.json    cardápio inicial
├── sql/schema.sql        tabelas + índices
├── src/
│   ├── app.py            rotas: webhook (c/ segredo), link do pedido, cozinha (c/ login)
│   ├── bot.py            IA primeiro (com rate limit), menu numerado como reserva
│   ├── ia.py             IA (Ollama/Claude), prompt de atendimento, aquecimento do Ollama
│   ├── whatsapp.py       envio/recebimento (WAHA/Meta), cache de chatId persistido
│   ├── auth_windows.py   login da cozinha usando a conta do Windows (modo opcional)
│   ├── pedidos.py, links.py, fila.py, recibo.py, cardapio.py, viacep.py
│   ├── config.py, db.py  configuração e acesso ao banco (modo WAL, migrações)
├── web/templates/        páginas do pedido e da cozinha
├── web/static/produtos/  fotos dos produtos (opcional)
└── tests/                testes automatizados (pytest)
```

O n8n do `docker-compose.yml` é opcional e não é necessário para este fluxo.
O webhook do WAHA aponta direto para o Flask.

---

## 15. Visual das páginas (pedido e cozinha)

As páginas do pedido (`/m/<token>`), confirmação, link inválido e o painel
da cozinha (`/cozinha`) usam a mesma identidade visual (tema "taverna
pirata": fundo escuro, dourado de destaque, cards em tom pergaminho),
coerente com o nome e os emojis que o bot já usa.

- **Fotos dos produtos**: ver seção 6. Sem foto, aparece um retrato
  ilustrado automático -- nunca uma imagem quebrada.
- **Seletor de quantidade** com botões `−`/`+` (em vez de uma caixinha de
  número) e uma **barra fixa no rodapé** mostrando a quantidade de itens e
  o total em tempo real (incluindo a taxa de entrega, se escolhida) --
  some embaixo até o cliente escolher algo.
- **Navegação por categoria** no topo da página do pedido: toca no nome da
  categoria e pula direto pra ela; a categoria visível na tela fica
  destacada automaticamente.
- **Painel da cozinha em formato quadro (kanban)**: três colunas --
  Aguardando, Em preparo, Pronto -- cada pedido mostra os itens pedidos
  (antes só aparecia o total em reais, sem dizer o quê) e há quanto tempo
  está naquele status. Atualiza sozinho a cada 15s **sem recarregar a
  página inteira** (sem o "flash" branco do refresh); o botão de avançar
  usa a mesma lógica.
- **Para ajustar cores/fontes**: cada template tem as variáveis de cor no
  topo do `<style>` (ex.: `--latao`, `--tinta`, `--mar`) -- troque os
  valores hexadecimais lá para mudar a paleta sem precisar editar o resto
  do CSS.

---

## 16. Resumo rápido (cola)

1. Dois cliques em **`Iniciar DeliveryBot.bat`** (primeira vez: ele se
   prepara sozinho -- venv, `.env`, segredos).
2. Se abrir o navegador pedindo QR Code: escaneie com o WhatsApp do
   restaurante.
3. De **outro** celular, mande "oi" para o número do bot.
4. Painel da cozinha: `http://localhost:5000/cozinha` (ou a URL do ngrok
   + `/cozinha`), login com `COZINHA_USUARIO` + a senha definida (ou a
   conta do Windows, se `COZINHA_AUTH_MODO=WINDOWS`).
5. Pra desligar tudo: dois cliques em **`Parar DeliveryBot.bat`**.
