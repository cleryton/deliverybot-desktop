> **Aplicativo Windows:** comece pelo [GUIA DO APLICATIVO.md](GUIA%20DO%20APLICATIVO.md). Abra `dist/Instalar DeliveryBot.exe` para instalar ou `dist/DeliveryBot.exe` para usar diretamente. O novo painel permite cadastrar produtos de qualquer categoria e controlar estoque.
>
> **Versão 2.2:** conecte o WhatsApp pelo QR Code em **WhatsApp e IA**, sem instalar Docker ou Node.js. O componente integrado já vem no executável, salva a sessão e mantém uma fila persistente para evitar eventos duplicados. Inicie o Ollama e baixe o modelo pelos botões desse painel; apenas o Ollama precisa de instalação separada para usar IA local.
>
> O [MANUAL.md](MANUAL.md) abaixo documenta o modo servidor e as integrações originais para desenvolvedores.

> **Versão 2.3:** configure o responsável e o contato em **Privacidade e LGPD**. O app oferece aviso aos clientes, exportação e correção de dados, remoção da identificação e limpeza do histórico. Backups novos são criptografados por senha. Veja [PRIVACIDADE E SEGURANÇA.md](PRIVACIDADE%20E%20SEGURAN%C3%87A.md) para procedimentos, retenção e limites das medidas.

## Versões e histórico

A versão atual está em [VERSION](VERSION), e as alterações são registradas em [CHANGELOG.md](CHANGELOG.md). Cada pedido que modificar o projeto gera um commit identificado por versão e uma tag `vX.Y.Z`, conforme [AGENTS.md](AGENTS.md). Os executáveis são gerados localmente e não fazem parte do histórico Git.

Repositório do aplicativo: [cleryton/deliverybot-desktop](https://github.com/cleryton/deliverybot-desktop).

# DeliveryBot 🤖🍔 — Bot de Pedidos para Restaurante via WhatsApp

> Tema 09 — DeliveryBot: Pedidos de restaurante
> Cenário: restaurantes confirmam pedidos manualmente um a um.
> O sistema deve: cadastro de cardápio e pedidos; enviar confirmação do pedido,
> tempo estimado e aviso de "saiu para entrega"; fila de preparo visível para a cozinha.
> Segunda API: ViaCEP — validar área de entrega pelo CEP.
> Entidades mínimas do banco: clientes, produtos, pedidos, itens_pedido, fila_preparo, mensagens.

Inspirado no fluxo do projeto [Pirata-dos-Hamburguer](https://github.com/Kennedy-Mariano/Pirata-dos-Hamburguer)
(automação com Flask + WhatsApp Business Cloud API) e nos prints de atendimento
anexados (menu numerado, link de pedido único, confirmação com número de pedido,
atualizações de status e um cupom "DOCUMENTO NÃO FISCAL").

## Como o fluxo funciona (igual aos prints)

1. Cliente manda qualquer mensagem no WhatsApp → bot responde com o menu:
   ```
   1 - Horário de funcionamento
   2 - Realizar pedidos
   3 - Formas de pagamento
   4 - Cardápio
   5 - Telefone
   6 - Promoções
   7 - Taxa de entrega
   8 - Endereço
   ```
2. Cliente digita **2** → o bot gera um **link único de pedido**
   (`/m/<token>`), válido para **um único pedido** — depois de usado ou expirado
   o link não abre outro pedido.
3. Cliente escolhe os itens na página do link, informa forma de pagamento e
   CEP (validado na hora com a **ViaCEP**).
4. Ao confirmar, o bot manda no WhatsApp:
   *"Seu pedido #21535858 foi realizado com sucesso. Vou te atualizando sobre
   o processo do seu pedido por aqui."* + o **cupom formatado** (igual ao print
   "DOCUMENTO NÃO FISCAL").
5. O pedido entra na **fila de preparo** (visível para a cozinha em
   `/cozinha`). Cada mudança de status dispara uma mensagem automática:
   - `Pedido confirmado. Recebemos o seu pedido. Você pode retirar seu pedido em
     aproximadamente 40 minutos...`
   - `Pronto para retirada. Pode vir, seu pedido já está lhe aguardando...`

## Estrutura de pastas

```
deliverybot/
├── requirements.txt
├── docker-compose.yml       -> sobe WAHA + N8N (WhatsApp real via QR Code)
├── .env.example
├── n8n/
│   └── deliverybot-waha.json -> workflow pronto pra importar no N8N
├── sql/schema.sql          -> clientes, produtos, pedidos, itens_pedido, fila_preparo, mensagens
├── data/cardapio.json      -> cardápio inicial (usado no seed do banco)
├── src/
│   ├── config.py           -> lê variáveis do .env
│   ├── db.py                -> conexão SQLite + criação/seed do banco
│   ├── viacep.py             -> valida CEP / área de entrega (API ViaCEP)
│   ├── cardapio.py           -> consultas de produtos/cardápio
│   ├── pedidos.py            -> regra de negócio: criar pedido, gerar nº, calcular total
│   ├── links.py               -> geração/validação do link único de pedido (token de uso único)
│   ├── recibo.py               -> monta o cupom "DOCUMENTO NÃO FISCAL" (texto)
│   ├── fila.py                  -> fila de preparo da cozinha + mudança de status
│   ├── whatsapp.py               -> envio de mensagens via WhatsApp Business Cloud API (Meta)
│   ├── bot.py                     -> máquina de estados da conversa (o menu 1-8)
│   └── app.py                      -> servidor Flask: webhook do WhatsApp + página do link + painel da cozinha
├── web/templates/
│   ├── pedido.html                 -> formulário de pedido (o link único abre isso)
│   ├── pedido_sucesso.html
│   ├── link_invalido.html
│   └── cozinha.html                 -> painel da fila de preparo (para o restaurante)
└── tests/
    └── test_pedidos.py
```

## 1. Instalação

```bash
cd deliverybot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Rodando sem preencher nada no `.env`, o sistema funciona em **modo teste**:
o banco (SQLite) é criado sozinho em `data/deliverybot.db` e as mensagens que
seriam enviadas ao WhatsApp aparecem só no console, com o prefixo
`[MODO TESTE] enviaria para 5547...:`. Isso permite testar toda a lógica do
bot e do cardápio antes de ter as credenciais da Meta.

Simule um pedido de ponta a ponta sem precisar do WhatsApp real:

```bash
python -m src.main_teste
```

## 2. Conectando no WhatsApp de verdade — duas opções

### Opção A (recomendada para testar rápido): WAHA + Docker, login por QR Code

Essa é a forma mais rápida de testar com o **seu próprio número de WhatsApp**,
sem precisar de conta comercial verificada nem esperar aprovação da Meta —
é o mesmo [WAHA](https://waha.devlike.pro/) usado por trás do N8N no vídeo
[N8N + WhatsApp GRÁTIS](https://www.youtube.com/watch?v=KkKlfAb3TSI), só que
aqui chamado direto do Python, sem precisar do N8N.

1. Instale o [Docker Desktop](https://docker.com).
2. No `.env`, defina `WHATSAPP_PROVIDER=WAHA`.
3. Rode o servidor Flask: `python -m src.app` (deixe essa janela aberta).
4. Em outro terminal, suba o WAHA: `docker compose up`.
5. Abra `http://localhost:3000` no navegador — é o Swagger/Dashboard do WAHA.
   Vá em `GET /api/screenshot` (ou na aba Dashboard) para ver o **QR Code** e
   escaneie com o WhatsApp do seu celular, em **Aparelhos conectados → Conectar
   um aparelho**.
6. Pronto — assim que a sessão ficar `WORKING`, qualquer mensagem que
   alguém mandar pro **seu número de WhatsApp** cai automaticamente no
   webhook `http://localhost:5000/webhook/waha` (o `docker-compose.yml` já
   configura isso sozinho) e o bot responde na hora.

> Atenção: o WAHA usa o WhatsApp Web por baixo dos panos. Use um número que
> você não se importe de conectar a um "aparelho" extra (dá pra usar seu
> WhatsApp normal mesmo, ele só aparece na lista de aparelhos conectados).

### Opção C: WAHA + N8N (o mesmo arranjo do vídeo, orquestrado visualmente)

Aqui o **N8N** vira o "cérebro" que liga o WAHA no Flask: ele recebe o evento
do WAHA, manda o texto pro Flask decidir a resposta (reaproveitando a mesma
lógica de `bot.py`, sem duplicar nada), e manda a resposta de volta pro WAHA.
É útil se você quiser mostrar visualmente o fluxo no trabalho, ou plugar
outras automações (IA, planilhas, etc.) depois sem mexer no Python.

1. Instale o [Docker Desktop](https://docker.com).
2. Rode o Flask fora do Docker: `python -m src.app` (deixe aberto).
3. Suba o WAHA **e** o N8N juntos: `docker compose up`.
4. Abra `http://localhost:3000` (WAHA) e escaneie o QR Code com o WhatsApp
   do seu celular, em **Aparelhos conectados → Conectar um aparelho**. O
   webhook do WAHA já sai configurado sozinho apontando pro N8N (variável
   `WHATSAPP_HOOK_URL` no `docker-compose.yml`).
5. Abra `http://localhost:5678` (N8N), crie sua conta local (é só local,
   fica na sua máquina) e importe o workflow pronto:
   **Menu (⋯) → Import from File → `n8n/deliverybot-waha.json`**.
6. **Ative o workflow** (toggle no canto superior direito do editor).
7. Pronto: mande uma mensagem pro seu número de WhatsApp. O caminho é
   `WhatsApp real → WAHA → N8N (decide) → Flask /api/bot/mensagem (aplica a
   regra de negócio) → N8N manda a resposta de volta pro WAHA → WhatsApp`.

O workflow importado tem 6 nós:
- **Webhook WAHA** — recebe o evento cru do WAHA.
- **É mensagem de cliente?** — filtra eventos que não são `message` ou que
  foram enviados pelo próprio bot (`fromMe`).
- **Processar no Bot (Flask)** — `POST /api/bot/mensagem` com
  `{telefone, texto, nome}`, recebe `{resposta}`.
- **Enviar resposta (WAHA)** — `POST /api/sendText` com a resposta.
- **Responder 200** (dois nós) — confirma o recebimento do webhook pro WAHA
  não ficar reenviando o mesmo evento.

> Se preferir mexer no fluxo dentro do N8N (textos, novas opções de menu,
> etc.) em vez de editar `bot.py`, dá pra trocar o nó **Processar no Bot** por
> nós de lógica do próprio N8N (Switch/Set) — só que aí o link único de
> pedido (`/m/<token>`) e o cardápio continuam vindo do Flask, porque
> precisam do banco de dados.

### Opção D: WhatsApp Business Cloud API (Meta) — oficial

Essa é a forma **oficial** de um bot Python conversar com o WhatsApp real
(é o mesmo caminho usado no projeto de referência Pirata-dos-Hamburguer):

1. Crie uma conta em [developers.facebook.com](https://developers.facebook.com/)
   e um **App do tipo "Business"**.
2. No app, adicione o produto **WhatsApp**. A Meta te dá automaticamente um
   número de teste, um **Phone Number ID** e um **token de acesso temporário**
   (24h) — dá para testar tudo com eles antes de ter um número comercial
   definitivo.
3. Copie para o `.env`:
   ```
   WHATSAPP_TOKEN=seu_token_de_acesso
   WHATSAPP_PHONE_NUMBER_ID=id_do_numero
   WHATSAPP_VERIFY_TOKEN=uma_palavra_secreta_que_voce_escolhe
   BASE_URL=https://SEU-DOMINIO-PUBLICO
   ```
4. Rode o servidor:
   ```bash
   python -m src.app
   ```
5. Deixe a porta 5000 pública (em desenvolvimento, use o
   [ngrok](https://ngrok.com/): `ngrok http 5000`) e copie a URL https gerada
   para `BASE_URL` no `.env` — é esse domínio que vira o link
   `https://SEU-DOMINIO/m/<token>` mandado ao cliente.
6. No painel do app da Meta, em **WhatsApp → Configuração → Webhooks**,
   cadastre:
   - Callback URL: `https://SEU-DOMINIO/webhook`
   - Verify Token: o mesmo valor de `WHATSAPP_VERIFY_TOKEN`
   - Inscreva-se no campo `messages`.
7. No seu celular, mande qualquer mensagem para o número de teste da Meta —
   o bot já responde com o menu.

> Para usar em produção com o **seu próprio número comercial** (não o número
> de teste da Meta), é preciso verificar o WhatsApp Business Account e trocar
> o token temporário por um **token permanente de usuário do sistema**, mas o
> código não muda — só as credenciais no `.env`.

## 3. Painel da cozinha (fila de preparo)

Acesse `http://localhost:5000/cozinha` (ou o seu domínio) para ver a fila de
preparo em tempo real e clicar para avançar o status de cada pedido
("Confirmado" → "Em preparo" → "Pronto para retirada" → "Entregue"). Cada
clique dispara automaticamente a mensagem correspondente no WhatsApp do
cliente.

## 4. Testes automatizados

```bash
pip install -r requirements-dev.txt   # já incluso em requirements.txt (pytest)
pytest -v
```

Os testes cobrem: geração de número de pedido, cálculo de total, geração e
invalidação do link único, validação de CEP e montagem do cupom.
