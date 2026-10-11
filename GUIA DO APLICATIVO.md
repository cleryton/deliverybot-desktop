# DeliveryBot Desktop 2.18.2

Aplicativo para Windows 10/11 de 64 bits, com uma janela própria, catálogo de produtos, controle de estoque e pedidos pelo WhatsApp.

## Instalar e abrir

1. Dentro de **dist**, abra a pasta da versão atual (indicada em **VERSION**), execute **Instalar-DeliveryBot.exe** e clique em **Instalar**.
2. Use o atalho **DeliveryBot** na área de trabalho ou no menu Iniciar.
3. Em **Configurações**, informe o nome da loja, contato, horário, formas de pagamento, taxa de entrega e tempo estimado.
4. Em **Produtos e estoque**, clique em **Cadastrar produto**. Cadastre nome, código opcional, categoria, descrição, preço, unidade, saldo inicial e alerta de estoque mínimo.
5. Experimente **Testar atendimento**. Envie `4` para ver o catálogo ou `2` para abrir uma compra de teste.

Também pode abrir **DeliveryBot.exe** nessa pasta diretamente, sem instalar. O usuário final não precisa instalar Python, Node.js ou Docker nem abrir um terminal. O componente de conexão do WhatsApp já está incluído no executável.

A janela usa o Microsoft Edge WebView2 Runtime, normalmente presente no Windows. Se faltar, instale pelo [site da Microsoft](https://developer.microsoft.com/microsoft-edge/webview2/). Os arquivos gerados ainda não possuem assinatura digital de um editor comercial.

## Aparência

No seletor **Tema** no topo do painel, escolha **Claro**, **Escuro** ou **Seguir o Windows**. A opção do Windows acompanha o tema do sistema e é o padrão inicial. A escolha fica salva na instalação, continua após reabrir o aplicativo e é compartilhada entre os funcionários deste computador. A tela de login usa a mesma preferência e também permite alterá-la. O QR Code mantém o fundo branco para facilitar a leitura pelo celular.

## Produtos de qualquer categoria

Na Visão geral, **Prepare sua loja, passo a passo** reúne os atalhos das configurações essenciais. Para validar o endereço público, inicie o túnel em **Página de pedidos**, gere o teste e abra o endereço no celular pelos dados móveis. Volte ao app e clique em **Verificar preparação**. O teste expira em 30 minutos; uma abertura recebida só é evidência do aparelho que o abriu, não uma garantia de disponibilidade permanente. O teste não envia mensagens pelo WhatsApp nem cria pedidos.

Cadastre roupas, acessórios, alimentos, eletrônicos, materiais, cosméticos ou outros produtos. Cada tamanho, cor ou embalagem pode ter seu próprio código e saldo. As categorias são livres.

As quantidades são inteiras por padrão. Habilite **Permitir quantidades fracionadas** para vender por peso, volume ou comprimento, com até três casas decimais. Preço e custo são por unidade cadastrada: 0,250 kg de um produto a R$ 20/kg custa R$ 5. Não há conversão automática entre kg, g, litros e embalagens. Os produtos antigos continuam inteiros. Use **Família** para agrupar produtos e **Variação** para tamanho/cor; cada variação mantém seu SKU e saldo próprios e aparece identificada ao cliente.

Em **Importar catálogo CSV**, selecione um arquivo, confira a prévia e confirme. O limite é 1000 produtos/500 KB. A importação cria novos cadastros e é transacional: erro ou SKU duplicado cancela o arquivo inteiro. Modelo: `nome;categoria;preco;sku;unidade;estoque;estoque_minimo;fracionado;familia;variacao;custo`. Nome, categoria e preço são obrigatórios; use `sim`/`nao` para as opções. Um leitor de códigos que funciona como teclado pode preencher o SKU ou a busca.

Em **Relatórios**, consulte vendas por período (datas UTC), produtos vendidos, custos registrados e margem parcial. O custo é opcional e fica congelado nos itens dos novos pedidos; pedidos antigos sem custo são indicados. Cancelados ficam fora do relatório. Margem parcial não é lucro líquido: faltam despesas, impostos, taxas e custos não cadastrados.

- **Movimentar** registra reposições e perdas com motivo, sem sobrescrever compras simultâneas.
- Produtos inativos ou com saldo zero ficam fora do catálogo público e das ofertas do bot.
- O pedido confirmado baixa o estoque em uma transação. Não é possível vender acima do saldo.
- Cancelar um pedido devolve as unidades vendidas uma única vez.
- A edição de nome e preço preserva o saldo atual e os dados dos itens de pedidos anteriores.
- Desmarcar o controle permite vender sem quantidade limitada. Use apenas quando apropriado para seu negócio.

## Pedidos

Em **Atendimento humano**, abra uma solicitação ou informe um telefone e clique em **Assumir e pausar bot**. O cliente também pode digitar **ATENDENTE** ou **10**. Leia as últimas mensagens, escreva sua resposta e confirme o envio. A mensagem entra na fila persistente: falhas e envios incertos precisam ser conferidos em WhatsApp e IA antes de tentar novamente. O modo de teste não envia. Use **Retomar bot** ao terminar; envios manuais pendentes bloqueiam a retomada. Mensagens recebidas durante a pausa ficam no histórico e não recebem resposta automática retroativa.

O painel oferece **Recebido → Em separação → Pronto → Entregue/Retirado**. É possível cancelar pedidos em andamento. Pedidos concluídos não podem ser cancelados nesse fluxo.

O teste de compra usa o mesmo banco de verdade: também baixa estoque. Cancele o pedido de teste para devolver as unidades.

## Conectar WhatsApp

O aplicativo começa em **modo de teste** e não envia mensagens reais. Para receber clientes:

- **Conexão integrada (recomendada):** na primeira vez, abra **WhatsApp e IA → Conectar WhatsApp**. No celular, abra **WhatsApp → Aparelhos conectados → Conectar um aparelho** e escaneie o QR Code exibido no aplicativo. Ele é atualizado automaticamente enquanto aguarda o celular. O componente inicia em segundo plano e não abre outro programa. Depois dessa escolha, ao abrir o DeliveryBot, ele prepara automaticamente o túnel HTTPS, o serviço integrado e a sessão, e abre a tela do WhatsApp; quando o WhatsApp pedir autenticação, basta escanear o QR Code. Ao atualizar de uma versão com Docker local, o aplicativo seleciona a conexão integrada e será necessário escanear um novo QR Code uma vez. Os demais dados são preservados.
- **Servidor WAHA externo (opcional):** para quem já utiliza um servidor próprio, selecione WAHA em Configurações e salve endereço, sessão e chave. Em um servidor remoto, preencha o endereço público da loja ou **Endereço visto pelo WAHA externo**. Depois clique em **Conectar WhatsApp**. Para voltar ao modo integrado, use **Usar conexão integrada** no painel.
- **Meta:** preencha as credenciais da WhatsApp Cloud API, incluindo o **App Secret** do aplicativo Meta, e configure a URL pública `/webhook` e o token de verificação no serviço. O App Secret permite verificar a assinatura das mensagens recebidas.
- **Endereço público da loja:** use **Página de pedidos** para iniciar o túnel incluído no aplicativo. O bot usa automaticamente o endereço da conexão atual. Para manter um ngrok ou serviço externo, pare o túnel integrado e mantenha seu `BASE_URL` em Configurações.

Mantenha o computador ligado, conectado e o aplicativo em execução durante o atendimento. Fechar a janela mantém o bot em segundo plano, com um ícone perto do relógio. Clique duas vezes no ícone ou use **Abrir DeliveryBot** para voltar ao painel. Para encerrar o servidor e o WhatsApp, use **Sair do aplicativo** no painel ou **Sair e interromper atendimento** no ícone. Desligar ou suspender o computador interrompe o atendimento. O Ollama pode continuar ativo em segundo plano. Depois de conectar, envie uma mensagem de outro número para confirmar o recebimento.

A sessão WhatsApp fica salva em **%LOCALAPPDATA%\DeliveryBot\whatsapp**. A conexão ativa é retomada ao reabrir o aplicativo; não é necessário escanear novamente enquanto a sessão continuar válida. **Pausar conexão** mantém a autenticação, preserva a pausa na próxima abertura e deixa as mensagens da fila aguardando a retomada.

As mensagens recebidas são preservadas localmente e processadas em segundo plano. O componente mantém uma caixa de entrada em disco até o servidor do aplicativo confirmar o recebimento. Repetições do mesmo evento são ignoradas. O atendimento preserva a ordem das mensagens de cada cliente e pode atender dois clientes em paralelo. Falhas aparecem em **Recebimento de mensagens**: confira no celular se a resposta chegou antes de clicar em **Tentar novamente**. A resposta já preparada é reutilizada. **Marcar como resolvida** libera a conversa quando a resposta já foi recebida ou a falha foi resolvida manualmente.

A conexão por QR Code usa Baileys, uma biblioteca comunitária de WhatsApp Web, e pode precisar de atualizações quando o WhatsApp mudar. A API oficial da Meta continua disponível como alternativa nas configurações.

## Página de pedidos pela internet

Em **Página de pedidos**, clique em **Iniciar página de pedidos** para testar ou manter o túnel ligado mesmo antes de conectar o WhatsApp. O conector Cloudflare incluído no executável trabalha em segundo plano, sem instalação separada ou janela de terminal. Ao preparar uma conexão integrada já escolhida, o aplicativo inicia o túnel e aguarda o HTTPS ficar pronto antes de preparar o QR Code; nas próximas aberturas, isso ocorre automaticamente. Se a conexão falhar, o painel informa o motivo; corrija a internet, o firewall ou as configurações e tente novamente. Marque **Iniciar a página junto com o aplicativo** para retomar automaticamente nas próximas aberturas, mesmo antes da preparação do WhatsApp. Salvar ou iniciar grava essa preferência; a inicialização automática pelo WhatsApp não altera essa configuração. O túnel não substitui o domínio manual existente.

**Temporário:** cria um endereço HTTPS sem conta. Serve para começar e testar; o domínio muda a cada novo túnel. Links já enviados deixam de abrir após essa mudança: o cliente deve digitar `2` novamente. Uma resposta automática ainda na fila passa a usar o domínio atual quando enviada; respostas manuais não são alteradas. [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) não oferecem garantia de disponibilidade e têm limite de 200 requisições simultâneas, sem suporte a SSE.

**Domínio fixo:** recomendado para a rotina da loja. Exige uma conta Cloudflare e um domínio sob seu controle. [Crie um túnel remoto](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/) no painel Cloudflare One, adicione o hostname de pedidos como aplicação publicada e use serviço **HTTP** com destino **http://127.0.0.1:5051** (ou a porta indicada no aplicativo). Salve o domínio HTTPS e **somente o token** do conector no app, selecione domínio fixo e inicie. O app substitui a execução manual do conector; não cria sua conta, domínio ou configuração DNS. A confirmação de conector ligado indica conexão com a Cloudflare; valide também a rota do domínio pelo teste no celular. Não aponte o túnel para a porta administrativa 5000. Se a porta pública estiver ocupada, o modo temporário escolhe outra automaticamente; no modo fixo, altere a porta no app e o destino na Cloudflare.

O servidor público separado libera apenas compra, privacidade, diagnóstico, imagens de produtos e webhooks autenticados. Gestão, cozinha, testes internos, exportações e arquivos do painel ficam bloqueados nessa porta, mesmo com cabeçalhos de proxy forjados. O token é protegido pela conta Windows, nunca exibido de volta e excluído do backup portátil. A URL temporária fica em memória, sem sobrescrever `BASE_URL`. O aviso de privacidade informa o uso da Cloudflare quando o túnel integrado está ativo.

Use **Gerar link de teste**, copie o endereço e abra no celular com dados móveis. O endereço principal sozinho não é um link de compra: o bot gera um link individual por pedido. Em **Visão geral**, confirme a preparação. Na desconexão, o bot informa a indisponibilidade em vez de enviar `localhost`; o conector tenta novamente com intervalos crescentes. O túnel continua ativo com o app na bandeja e encerra ao sair completamente. Ele depende do computador ligado e conectado; não mantém a loja online com a máquina desligada. Para disponibilidade contínua, use uma máquina sempre ligada ou o modo servidor em hospedagem própria.

### Compilar com o conector incluído

Na máquina de desenvolvimento, prepare o componente WhatsApp conforme o fluxo existente e execute `.venv/Scripts/python.exe packaging/preparar_tunel.py` antes do PyInstaller. O script baixa o binário Windows oficial da versão fixada em `packaging/cloudflared.json`, valida tamanho e SHA-256 e inclui a licença Apache. Arquivos de runtime ficam ignorados pelo Git. Para atualizar o conector, revise uma nova release oficial e altere a versão, tamanho e hash fixados; não use executáveis locais arbitrários. O usuário final recebe tudo no aplicativo.

## Iniciar Ollama pelo aplicativo

1. Instale o [Ollama para Windows](https://ollama.com/download/windows) uma vez.
2. Em **WhatsApp e IA**, escolha o modelo e clique em **Iniciar Ollama**. O aplicativo inicia o serviço em segundo plano ou reutiliza o serviço já aberto.
3. Se o modelo faltar, clique em **Baixar modelo** e confirme. Acompanhe o progresso mantendo o aplicativo aberto. O download pode ocupar alguns GB; depende da sua internet e do espaço em disco.
4. Ao terminar, o modelo é carregado na memória e a IA Ollama é ativada no bot. Depois que Ollama estiver selecionado, o aplicativo inicia automaticamente o serviço local e carrega o modelo nas próximas aberturas. Endereços remotos continuam dependendo do servidor externo estar ligado.

A IA é opcional. Quando indisponível, o bot continua pelo menu. Anthropic requer uma chave de API e tem custo conforme o uso. Os limites e créditos do Codex são separados do atendimento Ollama local.

## Dados, backups e atualização

Em **Proteção automática**, habilite backups, escolha uma senha, intervalo, número de cópias e uma pasta de destino. A senha do agendamento é guardada com DPAPI; guarde-a também separadamente para recuperar em outro computador. Cada cópia é decifrada em memória e verificada antes da rotação. Só arquivos `automatico-DeliveryBot-*.dbot` nessa pasta são removidos pela retenção. Não escolha uma pasta usada por outra loja. Trocar a senha não altera backups antigos. A cópia portável desativa o agendamento ao restaurar e não leva sua senha nem o destino.

**Limpar diariamente** é opcional e aplica a retenção das conversas definida em Privacidade e LGPD, preservando pendências. As rotinas funcionam enquanto o app estiver em execução; horários perdidos são recuperados na próxima abertura. Confira o status e mantenha uma cópia fora do computador.

Os dados ficam em **%LOCALAPPDATA%\DeliveryBot**, fora da pasta do programa. A instalação de uma nova versão e a desinstalação preservam essa pasta.

Use **Criar backup** na Visão geral e escolha uma senha com pelo menos 12 caracteres. O arquivo `.dbot` contém produtos, estoque, clientes, pedidos e configurações, protegido com criptografia autenticada. Credenciais dos serviços são excluídas dessa cópia. Copie-o para um local seguro fora desse computador e guarde a senha separadamente: ela não fica salva no aplicativo. **Abrir pasta de dados** ajuda a localizar o arquivo.

O backup `.dbot` não inclui a autenticação nem a caixa de entrada do componente WhatsApp. Em outro computador, reconecte pelo QR Code e informe novamente as credenciais necessárias. A pasta `whatsapp` contém dados privados da sessão e mensagens ainda não entregues ao servidor; não envie essa pasta a outras pessoas. Planeje a migração com o atendimento pausado e a fila concluída.

Para recuperar, use **Restaurar backup**, informe a senha, selecione um `.dbot` e confirme. O aplicativo cria uma cópia protegida dos dados atuais, fecha e aplica o backup na próxima abertura. Senha incorreta ou arquivo alterado não substituem o banco atual. A função também importa um `.db` de versões anteriores; nesse caso, a senha escolhida protege a cópia de segurança dos dados atuais. Cópias automáticas `.dbot-local` só podem ser abertas pela conta Windows que as criou. Os produtos antigos entram sem controle de estoque; habilite-o e informe o saldo inicial.

## Privacidade e LGPD

Antes de atender clientes, abra **Privacidade e LGPD**, informe a empresa responsável e o contato para solicitações e revise a descrição da retenção dos pedidos. O formulário de compra e o primeiro atendimento incluem o aviso; o cliente pode digitar **PRIVACIDADE** no WhatsApp.

Após verificar a identidade e a solicitação do cliente, use **Exportar dados**, **Corrigir cadastro** ou **Remover identificação**. A remoção bloqueia pedidos e envios em andamento; preserva os itens e totais das vendas. A exportação contém dados pessoais e deve ser entregue apenas ao titular. Essas operações abrangem o banco atual; revise também backups, exportações, sessões e provedores externos.

O prazo operacional das conversas começa em 30 dias e pode ser ajustado. **Limpar histórico fora do prazo** remove mensagens antigas de conversas concluídas e links expirados, preservando atendimentos pendentes. Execute ou agende a limpeza conforme sua política; não existe remoção automática dos pedidos ou das cópias de backup.

O envio a IA externa fica desligado por padrão. Ollama neste computador funciona normalmente. Para usar Anthropic ou Ollama em outro servidor, revise o compartilhamento e habilite essa opção na área de privacidade. A redução de dados no texto não garante anonimização de tudo que um cliente escrever.

No Windows, a pasta de dados fica restrita à conta atual e SYSTEM; segredos das configurações usam a proteção da conta Windows. O banco em uso continua SQLite e não é criptografado integralmente. Proteja a conta, bloqueie a tela e use criptografia de disco para proteção contra acesso físico. Veja [PRIVACIDADE E SEGURANÇA.md](PRIVACIDADE%20E%20SEGURAN%C3%87A.md) para procedimentos e limites das medidas.

Fotos antigas armazenadas em `web/static/produtos` não fazem parte do backup do banco. Preserve esses arquivos separadamente ao transferir um projeto antigo. O novo cadastro usa nome, descrição e categoria sem exigir fotos.

Para desinstalar, use **Configurações do Windows → Aplicativos → DeliveryBot → Desinstalar**.

Se aparecer erro de porta ocupada, feche o servidor antigo iniciado pelos scripts `.bat`. Logs ficam em `%LOCALAPPDATA%\DeliveryBot\deliverybot.log`. Não abra simultaneamente a versão antiga e a nova usando o mesmo banco.

## Para desenvolver e compilar novamente

O código continua compatível com `python -m src.app` e com as integrações anteriores. Esse comando e o executável iniciam a fila automaticamente e retomam o componente integrado quando o provedor LOCAL estiver selecionado; ao usar outro servidor WSGI, inicialize os componentes explicitamente uma vez no processo do servidor, sem iniciar múltiplos processos concorrentes. O painel administrativo fica em `/gestao`, usando a autenticação administrativa já configurada no `.env`. O aplicativo Desktop autentica a própria janela com uma sessão local; o painel não fica aberto para a rede.

Execute **Compilar aplicativo.ps1** com Python 3.12 e Node.js 20 ou mais recente instalados na máquina de compilação. O script cria um ambiente virtual, instala as versões verificadas em `requirements-desktop.lock.txt` e `whatsapp-native/package-lock.json`, roda os testes, inclui o runtime Node e suas licenças e gera o executável e o instalador em `dist`. O usuário final recebe todos esses componentes no programa.

Arquivos principais: `desktop.py`, `src/estoque.py`, `src/gestao.py`, `src/preferencias.py`, `web/templates/gestao.html`, `web/static/gestao.js`, `DeliveryBot.spec` e `packaging/`.


## Funcionários e permissões

Em **Funcionários e auditoria**, crie primeiro sua conta administradora com senha de pelo menos 12 caracteres. Crie contas individuais para os atendentes. Eles podem consultar produtos, avançar pedidos e responder no atendimento humano. Preços, custos, relatórios, conexões, exportações, backups e configurações ficam restritos ao administrador, inclusive pelas APIs. Use **Trocar funcionário** ao encerrar seu turno.

Ao desativar uma conta, trocar sua senha ou mudar seu perfil, todas as suas sessões são revogadas. O último administrador ativo não pode ser desativado ou rebaixado. Outro administrador pode redefinir senhas; mantenha acesso seguro a pelo menos uma conta administradora. A auditoria registra até 100 ações na tela, com conta, ação, identificador e horário, sem copiar mensagens ou senhas. Os registros anteriores permanecem no banco.

As senhas são guardadas como hashes scrypt e acompanham os backups criptografados. As permissões do aplicativo dependem também da proteção do computador: quem controla a conta Windows ou altera diretamente o banco pode contornar controles locais. Proteja o acesso ao Windows e aos backups. As contas do aplicativo não substituem essa proteção.


## Distribuições e atualizações

Baixe o instalador em [Releases do DeliveryBot](https://github.com/cleryton/deliverybot-desktop/releases). O instalador por usuário mantém o banco existente; encerre o aplicativo pela bandeja antes de instalar. Não exige Docker, Python ou Node.js no computador do usuário.

Em **Atualizações**, consulte a última versão publicada. A consulta automática é opcional, ocorre uma vez por dia enquanto o app está aberto e usa a API pública do GitHub. Nenhum dado dos clientes é enviado; o GitHub recebe os dados normais de uma conexão de internet, como endereço IP. O download confere tamanho, origem e SHA-256 conforme o manifesto da release, e cria um backup portátil criptografado e verificado com sua senha. Isso verifica a integridade conforme a publicação; não substitui a confiança na conta do editor no GitHub.

A instalação automática exige uma assinatura Authenticode válida e o certificado do editor fixado na distribuição. A distribuição atual ainda não possui certificado comercial; o botão de instalar automaticamente permanece bloqueado. O instalador manual e o manifesto continuam disponíveis no GitHub. Para voltar aos dados anteriores, encerre o app, abra uma versão compatível e use **Restaurar backup** com a senha guardada. A restauração substitui alterações posteriores à cópia. Não há reversão automática do executável.

### Preparação de uma distribuição assinada

O mantenedor deve obter um certificado confiável de assinatura de código, manter a chave privada no repositório de certificados Windows e configurar apenas seu thumbprint público em `packaging/assinatura.json` **antes** de reconstruir o aplicativo. Não inclua certificados com chave privada no Git. Use `packaging/assinar.ps1 -Arquivo caminho -SignTool caminho-do-signtool.exe` para assinar o aplicativo, compile o instalador para incorporar o aplicativo assinado e assine também o instalador. Execute `packaging/gerar_hashes.py` por último. Publique o instalador e `SHA256SUMS.txt` na mesma release, sem substituir assets de uma versão já publicada. Consulte a [documentação de assinatura da Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/get-authenticodesignature) e a [API de releases do GitHub](https://docs.github.com/en/rest/releases/releases).
