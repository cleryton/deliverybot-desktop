# DeliveryBot Desktop 2.29.0

Aplicativo para Windows 10/11 de 64 bits, com uma janela própria, catálogo de produtos, controle de estoque e pedidos pelo WhatsApp.

## Instalar e abrir

1. Dentro de **dist**, abra a pasta da versão atual (indicada em **VERSION**), execute **Instalar-DeliveryBot.exe** e clique em **Instalar**.
2. Use o atalho **DeliveryBot** na área de trabalho ou no menu Iniciar.
3. Em **Configurações**, informe o nome da loja, contato, horário, formas de pagamento, taxa de entrega e tempo estimado.
4. Em **Produtos e estoque**, clique em **Cadastrar produto**. Cadastre nome, código opcional, categoria, descrição, preço, unidade, saldo inicial e alerta de estoque mínimo.
5. Experimente **Testar atendimento**. Envie `4` para ver o catálogo ou `2` para abrir uma compra de teste.

Também pode abrir **DeliveryBot.exe** nessa pasta diretamente, sem instalar. O usuário final não precisa instalar Python, Node.js ou Docker nem abrir um terminal. O componente de conexão do WhatsApp já está incluído no executável.

A janela usa o Microsoft Edge WebView2 Runtime, normalmente presente no Windows. Se faltar, instale pelo [site da Microsoft](https://developer.microsoft.com/microsoft-edge/webview2/). Os arquivos gerados ainda não possuem assinatura digital de um editor comercial.

## Guias para configurar o aplicativo

Abra **Guia de configuração** no menu ou **Começar tutorial** na Visão geral. Os guias do negócio, catálogo, privacidade, conexão, atendimento e pedidos explicam cada etapa e oferecem o botão **Abrir esta configuração**. Use Anterior e Próxima etapa para navegar, incluindo a preparação opcional do Ollama.

Depois de salvar uma configuração, volte ao guia e clique em **Verificar configuração**. As verificações acompanham os dados atuais: apenas visitar uma etapa não a conclui. O catálogo precisa ter ao menos um item ativo e disponível. O teste de acesso pelo celular não cria pedidos nem envia mensagens; a abertura recebida corresponde ao endereço atual e não garante disponibilidade permanente. Confira os dados móveis e o funcionamento do catálogo separadamente.

As orientações são locais, funcionam sem IA e ficam disponíveis ao administrador. Não iniciam serviços nem alteram configurações por conta própria.

## Seu comércio, do seu jeito

Na primeira instalação, informe o nome, o segmento e uma descrição do que você oferece. Escolha **Revenda**, **Produção sob pedido**, **Serviços** ou **Misto**. O aplicativo usa esse perfil para organizar o catálogo e orientar o atendimento. Instalações anteriores continuam com os cadastros e saldos existentes; atualizações não pedem um perfil novo nem substituem o perfil salvo.

**Produção sob pedido e serviços** começam sem contagem obrigatória nos novos itens: um prato preparado depois do pedido ou um serviço de oficina não precisa de um saldo fictício para aparecer no catálogo. **Revenda e misto** sugerem controle de quantidade. Você pode alterar essa escolha durante a instalação e em **Meu comércio**, e escolher o controle em cada item — por exemplo, pratos sem contagem e bebidas com saldo, ou serviços sem contagem e peças de reposição com estoque.

Em **Meu comércio**, revise o segmento, a descrição e a operação sempre que precisar. Mudar o perfil altera apenas o padrão dos novos cadastros. Produtos, saldos, fotos, pedidos e históricos existentes são preservados. Para um item com quantidade controlada, saldo zero continua bloqueando novas vendas. Para itens sem contagem, use **Ativo** para controlar a disponibilidade no catálogo. O sistema não calcula ingredientes, capacidade de produção ou agenda automaticamente.

O perfil acompanha os backups. O Ollama recebe a descrição como referência da operação; ela não é publicada na página do cliente. Para serviços, você pode usar unidades **Serviço** ou **Hora**. Cadastre preços definidos; orçamentos que exigem avaliação e horários de atendimento devem ser combinados com a equipe pelo atendimento humano.

As importações de catálogo seguem o padrão do comércio. No CSV, a coluna opcional `controlar_estoque` aceita `sim` ou `nao`. Na leitura de PDF ou planilha, confira a opção de controle de cada novo item na revisão; entradas e contagens de produtos existentes continuam exigindo SKU e controle de estoque já cadastrado.

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

**Temporário:** cria um endereço HTTPS sem conta. Serve para começar e testar; o domínio muda a cada novo túnel. Links já enviados deixam de abrir após essa mudança: o cliente deve pedir um novo link pelo WhatsApp. Antes do envio, links de compra e do aviso de privacidade são atualizados para o endereço da sessão, inclusive em respostas da IA e no atendimento humano. Tokens inventados ou de outro cliente e endereços locais são bloqueados. Respostas de compra já preparadas aguardam a reconexão do HTTPS e retomam automaticamente, sem repetir a geração pela IA. [Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) não oferecem garantia de disponibilidade e têm limite de 200 requisições simultâneas, sem suporte a SSE.

**Domínio fixo:** recomendado para a rotina da loja. Exige uma conta Cloudflare e um domínio sob seu controle. [Crie um túnel remoto](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/get-started/create-remote-tunnel/) no painel Cloudflare One, adicione o hostname de pedidos como aplicação publicada e use serviço **HTTP** com destino **http://127.0.0.1:5051** (ou a porta indicada no aplicativo). Salve o domínio HTTPS e **somente o token** do conector no app, selecione domínio fixo e inicie. O app substitui a execução manual do conector; não cria sua conta, domínio ou configuração DNS. A página só aparece como pronta depois de confirmar a conexão do conector e uma resposta HTTPS do próprio aplicativo, sem redirecionamentos. Essa confirmação é repetida durante o atendimento; faça também o teste no celular. Não aponte o túnel para a porta administrativa 5000. Se a porta pública estiver ocupada, o modo temporário escolhe outra automaticamente; no modo fixo, altere a porta no app e o destino na Cloudflare.

O servidor público separado libera apenas compra, privacidade, diagnóstico, imagens de produtos, os estilos e scripts da página do cliente e webhooks autenticados. Gestão, cozinha, testes internos, exportações e arquivos do painel ficam bloqueados nessa porta, mesmo com cabeçalhos de proxy forjados. O token é protegido pela conta Windows, nunca exibido de volta e excluído do backup portátil. A URL temporária fica em memória, sem sobrescrever `BASE_URL`. O aviso de privacidade informa o uso da Cloudflare quando o túnel integrado está ativo. Ao trocar o endereço, o aplicativo atualiza automaticamente o callback de sessões WAHA remotas existentes que usam a página pública, preservando outras integrações; um callback manual permanece sob seu controle.

Use **Gerar link de teste**, copie o endereço e abra no celular com dados móveis. O endereço principal sozinho não é um link de compra: o bot gera um link individual por pedido. Em **Visão geral**, confirme a preparação. Na desconexão, o bot informa a indisponibilidade em vez de enviar `localhost`; o conector tenta novamente com intervalos crescentes. O túnel continua ativo com o app na bandeja e encerra ao sair completamente. Ele depende do computador ligado e conectado; não mantém a loja online com a máquina desligada. Para disponibilidade contínua, use uma máquina sempre ligada ou o modo servidor em hospedagem própria.

### Compilar com o conector incluído

Na máquina de desenvolvimento, prepare o componente WhatsApp conforme o fluxo existente e execute `.venv/Scripts/python.exe packaging/preparar_tunel.py` antes do PyInstaller. O script baixa o binário Windows oficial da versão fixada em `packaging/cloudflared.json`, valida tamanho e SHA-256 e inclui a licença Apache. Arquivos de runtime ficam ignorados pelo Git. Para atualizar o conector, revise uma nova release oficial e altere a versão, tamanho e hash fixados; não use executáveis locais arbitrários. O usuário final recebe tudo no aplicativo.

## Cérebro local com Obsidian

Em **WhatsApp e IA → Conexões**, clique em **Abrir o cofre no Obsidian**. O aplicativo cria a pasta `Cerebro Obsidian` junto aos dados locais, com as notas **Estilo de atendimento**, **Informações da loja**, **Perguntas frequentes** e a página **Início** com links entre elas. O Obsidian é opcional; sem ele, a pasta abre no Explorador e os arquivos podem ser editados em qualquer editor de Markdown.

O Ollama consulta a nota de estilo e as notas de loja aprovadas a cada resposta. Para incluir uma nota própria, crie-a em `Conhecimento` usando `Modelos/Conhecimento aprovado.md`; depois de revisar, altere no início do arquivo `atendimento: false` para `atendimento: true`. Notas não aprovadas ficam fora do contexto. O conteúdo orienta as respostas, mas não treina o modelo. Produtos, preços, estoque e pedidos vêm do cadastro do aplicativo.

A consulta seleciona até seis notas relacionadas ao assunto da pergunta, mantendo a nota de estilo. Use palavras claras no título e acrescente `tags: [troca, garantia]` no frontmatter para facilitar a busca. As listas de tags editadas nas propriedades do Obsidian também são reconhecidas, conforme o [formato de propriedades do Obsidian](https://obsidian.md/help/properties). `prioridade: 1` até `prioridade: 5` desempata notas sobre o mesmo assunto; 5 é a maior prioridade. Essas opções são facultativas, e notas antigas continuam funcionando. As notas de informações gerais e perguntas frequentes também podem fornecer contexto de apoio.

Para regras com prazo, adicione `valido_ate: AAAA-MM-DD` no frontmatter. A nota vale até o fim desse dia no computador da loja; depois deixa de ser usada nas respostas, permanecendo no cofre e no backup. Datas inválidas e campos de aprovação ou validade duplicados impedem o uso da nota. Notas acima de 64 KB, conteúdo inválido ou arquivos que apontem para fora do cofre também são ignorados. O contexto enviado mantém um limite de 14 mil caracteres, incluindo os títulos, para reduzir distrações e custo de processamento. A pergunta é usada somente para selecionar referências e não é salva no cofre.

Não guarde dados de clientes nesse cofre. A IA local recebe o texto das notas que estiverem aprovadas; o aplicativo não grava conversas nelas. Backups criptografados `.dbot` novos incluem as notas Markdown do cofre, inclusive rascunhos, e a restauração as recupera sem apagar notas adicionais que existam no computador. Backups de versões anteriores continuam válidos, mas não contêm notas do Obsidian. Se ativar sincronização do Obsidian, revise as configurações e o serviço escolhido.

### Escrever orientações que ajudem o atendimento

Comece por **Estilo de atendimento.md**. Descreva como sua loja conversa e acrescente exemplos fictícios de respostas que você aprova. Prefira instruções concretas: “responda primeiro à dúvida, use frases curtas e faça uma pergunta por vez” ajuda mais que “seja humanizado”. Não é preciso preencher o cofre inteiro para começar.

Você pode adaptar estas orientações ao jeito da sua loja:

> Fale com simpatia e clareza, em português brasileiro. Use uma ou duas frases quando a pergunta for simples. Varie a abertura e evite repetir a saudação em toda mensagem. Use emojis com moderação. Se faltar uma informação, diga o que precisa confirmar e ofereça ajuda da equipe. Em reclamações, reconheça o problema e mantenha um tom respeitoso, sem brincadeiras.

Acrescente exemplos do tom desejado, sem inventar informações comerciais:

- **Cliente:** “Quero ver os produtos.” **Tom desejado:** “Claro! Vou te mostrar as opções para você escolher com calma.”
- **Cliente:** “Preciso falar com alguém.” **Tom desejado:** “Claro, vou chamar a equipe para continuar com você.”
- **Cliente:** “Meu pedido veio errado.” **Tom desejado:** “Sinto muito pelo problema. Vou chamar a equipe para conferir o que aconteceu.”

Esses exemplos orientam a escrita; o aplicativo é responsável por executar o encaminhamento e gerar links válidos. Mantenha preços, quantidades e informações do pedido no cadastro do aplicativo.

Para ensinar uma política da loja, crie uma nota separada em **Conhecimento**, usando **Modelos/Conhecimento aprovado.md**. Dê um título específico, escreva a regra e suas condições, informe a fonte e a data da revisão. Deixe `atendimento: false` enquanto houver informações a confirmar. Depois da aprovação da equipe, mude para `atendimento: true`. Para uma regra temporária, preencha também `valido_ate`.

Após salvar, use **Testar atendimento** com o Ollama ativo e perguntas fictícias. Confira se a resposta segue o tom escolhido e respeita a regra. Ajuste a nota quando necessário: editar exemplos melhora as referências da próxima resposta, mas não garante que o modelo repetirá exatamente uma frase. Respostas rápidas do próprio aplicativo não dependem do texto do Obsidian.

### Usar o Obsidian com documentos de estoque

Use **Modelos/Lista de estoque.md** para preparar uma tabela, ou selecione diretamente seu PDF, XLSX ou CSV no painel. Confira os itens extraídos, escolha cadastro, entrada ou contagem e confirme o lançamento. Marcar **Registrar no Obsidian** cria um histórico da operação em **Documentos de estoque**; editar esse histórico depois não altera os produtos nem o saldo.

O fluxo para compartilhar com o cliente é: **importar → revisar → lançar → gerar o catálogo PDF**. O PDF é gerado pelo aplicativo com os dados atuais do cadastro e pode ser impresso ou enviado como anexo. O Obsidian guarda orientações e registros; o saldo atualizado continua em **Produtos e estoque**.

## Iniciar Ollama pelo aplicativo

1. Instale o [Ollama para Windows](https://ollama.com/download/windows) uma vez.
2. Em **WhatsApp e IA**, escolha o modelo e clique em **Iniciar Ollama**. O aplicativo inicia o serviço em segundo plano ou reutiliza o serviço já aberto.
3. Se o modelo faltar, clique em **Baixar modelo** e confirme. Acompanhe o progresso mantendo o aplicativo aberto. O download pode ocupar alguns GB; depende da sua internet e do espaço em disco.
4. Ao terminar, o modelo é carregado na memória e a IA Ollama é ativada no bot. Depois que Ollama estiver selecionado, o aplicativo inicia automaticamente o serviço local e carrega o modelo nas próximas aberturas. Endereços remotos continuam dependendo do servidor externo estar ligado.

A IA é opcional. Perguntas simples sobre catálogo, preços identificados, horário, pagamento, taxa e endereço recebem respostas locais rápidas. A conversa usa o histórico recente, entende confirmações de uma oferta de link e encaminha dúvidas sobre pedidos e pagamentos para a equipe. Quando a IA estiver indisponível, o bot continua com respostas naturais; o menu numerado continua acessível digitando **MENU**. O Ollama não precisa de uma segunda geração para apresentar o link e não recebe o token privado da compra. Anthropic requer uma chave de API e tem custo conforme o uso. Os limites e créditos do Codex são separados do atendimento Ollama local.

## Compra pelo celular

A página do cliente oferece busca de produtos, navegação por categorias, quantidades ajustáveis e resumo revisável do carrinho. O total acompanha a escolha de entrega ou retirada; produtos fracionados mantêm sua unidade e precisão. Dados digitados permanecem no formulário quando houver um erro de validação, sem armazenamento local de informações pessoais no navegador. A confirmação apresenta os itens, os totais e o número do pedido, com opção de impressão. Preços, disponibilidade e estoque são conferidos novamente pelo aplicativo na confirmação.

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

### Validação de alterações no GitHub

Cada pull request para `main` e cada envio para `main` ou uma branch `codex/` executa **Validar DeliveryBot** no GitHub Actions. O fluxo confere versões e dependências, valida a sintaxe, testa estoque, pedidos, privacidade, documentos e a conexão WhatsApp simulada. Também compila o aplicativo e o instalador no Windows e verifica o catálogo, as fotos e o PDF dentro do executável.

A branch principal exige o resultado **DeliveryBot / validacao obrigatoria**. Uma falha bloqueia a integração; corrija a alteração e aguarde a nova execução. Use uma branch e um pull request para colaborar. Na aba **Actions**, abra a execução para ver o erro e baixar os relatórios, mantidos por sete dias. Os testes usam dados fictícios e não conectam contas reais, iniciam um túnel público ou enviam mensagens a clientes.

As Actions não publicam uma nova distribuição automaticamente. O instalador só deve ser publicado depois da validação e da revisão da versão. Os testes reduzem o risco de regressões, mas ainda é necessário conferir a experiência real em um computador de teste. O Dependabot propõe semanalmente atualizações dos componentes do próprio Actions; cada proposta passa pelas mesmas verificações.

### Preparação de uma distribuição assinada

A distribuição é organizada em `dist/v<versão>/`; `dist/LEIA-ME.txt` indica a versão finalizada. `packaging/distribuicao.py` copia os guias e licenças, registra a versão e confere hashes do aplicativo, instalador e documentos. O mantenedor pode usar `packaging/limpar_pasta.py` para simular a limpeza e acrescentar `--aplicar` para remover versões antigas e caches reconhecidos. A ferramenta mantém a versão atual e a anterior íntegra, exige integridade da atual e preserva dados e arquivos desconhecidos.

O mantenedor deve obter um certificado confiável de assinatura de código, manter a chave privada no repositório de certificados Windows e configurar apenas seu thumbprint público em `packaging/assinatura.json` **antes** de reconstruir o aplicativo. Não inclua certificados com chave privada no Git. Use `packaging/assinar.ps1 -Arquivo caminho -SignTool caminho-do-signtool.exe` para assinar o aplicativo, compile o instalador para incorporar o aplicativo assinado e assine também o instalador. Execute `packaging/gerar_hashes.py` por último. Publique o instalador e `SHA256SUMS.txt` na mesma release, sem substituir assets de uma versão já publicada. Consulte a [documentação de assinatura da Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/get-authenticodesignature) e a [API de releases do GitHub](https://docs.github.com/en/rest/releases/releases).

### Fotos dos produtos

Em **Produtos e estoque**, cadastre ou edite um produto e escolha sua foto. Aceita JPG, PNG e WebP de até 5 MB (até 20 milhões de pixels, sem animação). Você pode conferir a prévia, substituir a foto ou removê-la antes de salvar.

O cliente vê as fotos no catálogo do link de pedido e pode ampliá-las. As imagens usam o próprio endereço HTTPS da loja, sem hospedar arquivos em outro serviço. Fotos de produtos inativos não ficam disponíveis pelo túnel.

As fotos são otimizadas, têm os metadados da câmera removidos e ficam no banco de dados: acompanham as atualizações e os backups, inclusive a restauração em outro computador. Use fotos dos produtos que você tenha autorização para divulgar; elas ficam acessíveis publicamente enquanto o produto estiver ativo.

### Ler PDF, planilha ou uma nota de estoque

Em **Produtos e estoque → Ler uma nota ou documento de estoque**, escolha um PDF, XLSX, CSV ou Markdown (.md). O limite é 10 MB, 200 produtos e 10 páginas; arquivos XLS antigos devem ser salvos como XLSX e planilhas devem conter uma única aba. Colunas reconhecidas (nome, categoria, preco, custo, sku, unidade, estoque, fracionado) dispensam a IA. Valores calculados na planilha devem estar atualizados e salvos pelo editor antes da importação.

Para PDF ou texto sem colunas reconhecidas, inicie o Ollama e selecione um modelo local já instalado. PDFs digitalizados precisam de um modelo com visão. O arquivo é processado neste computador, sem envio à nuvem. A leitura pode errar ou deixar valores em branco: revise todos os produtos, códigos, unidades, preços e quantidades antes de confirmar. O aplicativo não baixa modelos automaticamente para documentos.

Escolha **Lista ou contagem** para uma contagem física ou **Nota de compra** para entrada de mercadoria. O valor unitário de uma compra é custo, não preço de venda. Para um SKU existente, Entrada soma a quantidade e Contagem define o saldo revisado, mantendo nomes, preços e fotos do cadastro. A contagem é bloqueada se houver mudança no saldo entre a leitura e a confirmação. Para novos produtos, preencha nome, categoria, preço de venda e quantidade. Ignore linhas que não sejam produtos.

A confirmação é transacional: se algum item estiver inválido, nenhum é lançado. Uma mesma leitura ou arquivo já confirmado não é aplicado duas vezes. A revisão expira em duas horas. Os arquivos originais não são guardados: ficam apenas os produtos extraídos e o registro do lançamento.

Você pode marcar **Registrar no Obsidian**. O registro revisado fica em `Documentos de estoque`, acompanha os backups e não entra como conhecimento de atendimento: o catálogo do aplicativo continua sendo a fonte do saldo atual. Se o cofre não puder ser gravado, o estoque permanece salvo e o botão de registro pendente permite tentar novamente sem repetir a entrada. Em `Modelos/Lista de estoque.md` há uma tabela para preencher no Obsidian e importar depois.

### Catálogo em PDF para compartilhar ou imprimir

Em **Produtos e estoque → Catálogo em PDF para o cliente**, baixe o arquivo com fotos, preços e disponibilidade dos produtos ativos com estoque. Você pode incluir as quantidades disponíveis. O PDF não lista custo, fornecedor, clientes ou pedidos. Ele registra a data de emissão: preços e estoque podem mudar depois de gerado.

O cliente também encontra **Baixar catálogo em PDF** no link HTTPS de pedido, sem quantidade exata de estoque. Esse download exige um link de pedido válido. Links vencidos ou já usados não dão acesso ao arquivo. Envie o PDF baixado como anexo pelo canal que você preferir; o aplicativo não dispara anexos reais durante testes.

## Pedidos pelo WhatsApp

O cliente pode dizer **PEDIDO PELO WHATSAPP** ou informar uma seleção concreta, como “quero 2 Calabresa Grande”. O aplicativo pede produtos com quantidade e variação, nome, entrega ou retirada, endereço quando necessário e pagamento. O resumo mostra os valores do cadastro; a compra só entra no painel e na fila após **CONFIRMAR**. O fluxo não depende do túnel ou da IA.

Use **adicionar**, **alterar** ou **remover** seguido de quantidade, nome e variação para ajustar itens. **CANCELAR** descarta o rascunho e **ATENDENTE** pausa o bot. Confirmações repetidas retornam o pedido existente. O resumo expira após 30 minutos; preço e estoque são conferidos novamente na gravação. Pagamento combinado não significa pagamento recebido.

Em **WhatsApp e IA → Cérebro local → Visualizar notas**, escolha uma nota para ler seu conteúdo e verificar se ela orienta o estilo, o contexto aprovado ou apenas o guia. O cofre inclui **Pedidos pelo WhatsApp.md**; as notas não substituem ações, preços ou saldo do aplicativo. Dados de clientes não são copiados para o Obsidian.

## WhatsApp, HTTPS e mapa do atendimento

Ao salvar uma nova conexão LOCAL ou WAHA no aplicativo Windows, a preparação começa automaticamente. O túnel temporário fornece o endereço HTTPS; o aplicativo verifica DNS e destino antes de iniciar a sessão e liberar o QR Code no painel. Conectar WhatsApp repete a preparação em caso de falha. Domínio fixo exige configuração na Cloudflare. Mantenha o aplicativo aberto e a internet disponível para receber pedidos pelo link.

No cofre Obsidian, abra `Mapa do atendimento.md` ou a visualização em gráfico. O mapa liga os guias, o estilo e o conhecimento aprovado, e remove referências a conhecimento revogado ou vencido na próxima consulta do aplicativo. As notas existentes são preservadas. O mapa é gerado automaticamente; para mantê-lo manualmente, remova o comentário `DeliveryBot: mapa automático v1`. Os guias operacionais e o mapa não são enviados ao modelo e não executam pedidos ou conexões.

### Padrões individuais por segmento e atendimento

Configure **Meu comércio** com o segmento, a descrição e o modo de operação. O aplicativo prepara em `Atendimentos` o perfil adequado: restaurantes e alimentos, moda e acessórios, eletrônicos, oficinas e peças, lojas de produtos, produção e encomendas, serviços e agendamentos, produtos e serviços ou atendimento geral. O segmento cadastrado tem preferência; a descrição e o modo de operação servem como apoio. Uma pergunta de cliente não muda o segmento da loja.

Cada pasta contém `Perfil.md` e seis notas: **Recepção**, **Dúvidas**, **Escolha**, **Fechamento**, **Pós-venda** e **Atendimento humano**. Edite cada uma com seu tom, perguntas úteis e exemplos fictícios. O Ollama lê o perfil e a etapa relacionada à mensagem, além do estilo e do conhecimento pertinente; a classificação da etapa é aproximada e orienta somente a escrita. Pedidos e outras operações continuam no fluxo oficial do aplicativo.

Em **WhatsApp e IA**, confira o perfil ativo e clique em **Visualizar notas**. `Atendimentos/Como personalizar.md` explica a organização, e `Mapa do atendimento.md` conecta os padrões ativos no Graph. Para suspender uma nota, use `atendimento: false`; para limitar sua validade, acrescente `valido_ate: AAAA-MM-DD`. Preserve `categoria_atendimento` e `etapa_atendimento`. Identificação incorreta, validade vencida ou aprovação ambígua impedem o uso.

Ao mudar o perfil, as edições antigas ficam preservadas na pasta anterior e saem do contexto da nova categoria. Os backups criptografados incluem essas notas. A próxima resposta lê suas alterações sem treinar a rede neural. Não inclua conversas nem dados de clientes; preços, estoque, reservas e condições comerciais precisam de confirmação no cadastro ou pela equipe.
