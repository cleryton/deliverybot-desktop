# DeliveryBot Desktop 2.6.0

Aplicativo para Windows 10/11 de 64 bits, com uma janela própria, catálogo de produtos, controle de estoque e pedidos pelo WhatsApp.

## Instalar e abrir

1. Abra **dist/Instalar DeliveryBot.exe** e clique em **Instalar**.
2. Use o atalho **DeliveryBot** na área de trabalho ou no menu Iniciar.
3. Em **Configurações**, informe o nome da loja, contato, horário, formas de pagamento, taxa de entrega e tempo estimado.
4. Em **Produtos e estoque**, clique em **Cadastrar produto**. Cadastre nome, código opcional, categoria, descrição, preço, unidade, saldo inicial e alerta de estoque mínimo.
5. Experimente **Testar atendimento**. Envie `4` para ver o catálogo ou `2` para abrir uma compra de teste.

Também pode abrir **dist/DeliveryBot.exe** diretamente, sem instalar. O usuário final não precisa instalar Python, Node.js ou Docker nem abrir um terminal. O componente de conexão do WhatsApp já está incluído no executável.

A janela usa o Microsoft Edge WebView2 Runtime, normalmente presente no Windows. Se faltar, instale pelo [site da Microsoft](https://developer.microsoft.com/microsoft-edge/webview2/). Os arquivos gerados ainda não possuem assinatura digital de um editor comercial.

## Produtos de qualquer categoria

Na Visão geral, **Prepare sua loja, passo a passo** reúne os atalhos das configurações essenciais. Para validar o endereço público, configure um domínio ou túnel HTTPS, gere o teste e abra o endereço no celular pelos dados móveis. Volte ao app e clique em **Verificar preparação**. O teste expira em 30 minutos; uma abertura recebida só é evidência do aparelho que o abriu, não uma garantia de disponibilidade permanente. Não envia mensagens pelo WhatsApp nem cria hospedagem.

Cadastre roupas, acessórios, alimentos, eletrônicos, materiais, cosméticos ou outros produtos. Cada tamanho, cor ou embalagem pode ter seu próprio código e saldo. As categorias são livres.

As quantidades são **inteiras**. Para vendas fracionadas, cadastre embalagens (por exemplo, pacote de 500 g) como unidades. O campo de unidade descreve a medida; não faz conversão de peso, volume ou embalagem.

- **Movimentar** registra reposições e perdas com motivo, sem sobrescrever compras simultâneas.
- Produtos inativos ou com saldo zero ficam fora do catálogo público e das ofertas do bot.
- O pedido confirmado baixa o estoque em uma transação. Não é possível vender acima do saldo.
- Cancelar um pedido devolve as unidades vendidas uma única vez.
- A edição de nome e preço preserva o saldo atual e os dados dos itens de pedidos anteriores.
- Desmarcar o controle permite vender sem quantidade limitada. Use apenas quando apropriado para seu negócio.

## Pedidos

O painel oferece **Recebido → Em separação → Pronto → Entregue/Retirado**. É possível cancelar pedidos em andamento. Pedidos concluídos não podem ser cancelados nesse fluxo.

O teste de compra usa o mesmo banco de verdade: também baixa estoque. Cancele o pedido de teste para devolver as unidades.

## Conectar WhatsApp

O aplicativo começa em **modo de teste** e não envia mensagens reais. Para receber clientes:

- **Conexão integrada (recomendada):** abra **WhatsApp e IA → Conectar WhatsApp**. No celular, abra **WhatsApp → Aparelhos conectados → Conectar um aparelho** e escaneie o QR Code exibido no aplicativo. Ele é atualizado automaticamente enquanto aguarda o celular. O componente inicia em segundo plano e não abre outro programa. Ao atualizar de uma versão com Docker local, o aplicativo seleciona a conexão integrada e será necessário escanear um novo QR Code uma vez. Os demais dados são preservados.
- **Servidor WAHA externo (opcional):** para quem já utiliza um servidor próprio, selecione WAHA em Configurações e salve endereço, sessão e chave. Em um servidor remoto, preencha o endereço público da loja ou **Endereço visto pelo WAHA externo**. Depois clique em **Conectar WhatsApp**. Para voltar ao modo integrado, use **Usar conexão integrada** no painel.
- **Meta:** preencha as credenciais da WhatsApp Cloud API, incluindo o **App Secret** do aplicativo Meta, e configure a URL pública `/webhook` e o token de verificação no serviço. O App Secret permite verificar a assinatura das mensagens recebidas.
- **Endereço público da loja:** precisa apontar para o servidor deste computador, na porta 5000, por um domínio/túnel configurado à parte. `localhost` não abre no celular de outro usuário. O aplicativo não cria hospedagem nem túnel automaticamente.

Mantenha o computador ligado, conectado e o aplicativo em execução durante o atendimento. Fechar a janela mantém o bot em segundo plano, com um ícone perto do relógio. Clique duas vezes no ícone ou use **Abrir DeliveryBot** para voltar ao painel. Para encerrar o servidor e o WhatsApp, use **Sair do aplicativo** no painel ou **Sair e interromper atendimento** no ícone. Desligar ou suspender o computador interrompe o atendimento. O Ollama pode continuar ativo em segundo plano. Depois de conectar, envie uma mensagem de outro número para confirmar o recebimento.

A sessão WhatsApp fica salva em **%LOCALAPPDATA%\DeliveryBot\whatsapp**. A conexão ativa é retomada ao reabrir o aplicativo; não é necessário escanear novamente enquanto a sessão continuar válida. **Pausar conexão** mantém a autenticação, preserva a pausa na próxima abertura e deixa as mensagens da fila aguardando a retomada.

As mensagens recebidas são preservadas localmente e processadas em segundo plano. O componente mantém uma caixa de entrada em disco até o servidor do aplicativo confirmar o recebimento. Repetições do mesmo evento são ignoradas. O atendimento preserva a ordem das mensagens de cada cliente e pode atender dois clientes em paralelo. Falhas aparecem em **Recebimento de mensagens**: confira no celular se a resposta chegou antes de clicar em **Tentar novamente**. A resposta já preparada é reutilizada. **Marcar como resolvida** libera a conversa quando a resposta já foi recebida ou a falha foi resolvida manualmente.

A conexão por QR Code usa Baileys, uma biblioteca comunitária de WhatsApp Web, e pode precisar de atualizações quando o WhatsApp mudar. A API oficial da Meta continua disponível como alternativa nas configurações.

## Iniciar Ollama pelo aplicativo

1. Instale o [Ollama para Windows](https://ollama.com/download/windows) uma vez.
2. Em **WhatsApp e IA**, escolha o modelo e clique em **Iniciar Ollama**. O aplicativo inicia o serviço em segundo plano ou reutiliza o serviço já aberto.
3. Se o modelo faltar, clique em **Baixar modelo** e confirme. Acompanhe o progresso mantendo o aplicativo aberto. O download pode ocupar alguns GB; depende da sua internet e do espaço em disco.
4. Ao terminar, o modelo é carregado na memória e a IA Ollama é ativada no bot. Se já estiver instalado, basta **Iniciar Ollama**.

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

O prazo operacional das conversas começa em 30 dias e pode ser ajustado. **Limpar histórico fora do prazo** remove mensagens antigas de conversas concluídas e links expirados, preservando atendimentos pendentes. Execute a limpeza conforme sua política; não existe remoção automática dos pedidos ou das cópias de backup.

O envio a IA externa fica desligado por padrão. Ollama neste computador funciona normalmente. Para usar Anthropic ou Ollama em outro servidor, revise o compartilhamento e habilite essa opção na área de privacidade. A redução de dados no texto não garante anonimização de tudo que um cliente escrever.

No Windows, a pasta de dados fica restrita à conta atual e SYSTEM; segredos das configurações usam a proteção da conta Windows. O banco em uso continua SQLite e não é criptografado integralmente. Proteja a conta, bloqueie a tela e use criptografia de disco para proteção contra acesso físico. Veja [PRIVACIDADE E SEGURANÇA.md](PRIVACIDADE%20E%20SEGURAN%C3%87A.md) para procedimentos e limites das medidas.

Fotos antigas armazenadas em `web/static/produtos` não fazem parte do backup do banco. Preserve esses arquivos separadamente ao transferir um projeto antigo. O novo cadastro usa nome, descrição e categoria sem exigir fotos.

Para desinstalar, use **Configurações do Windows → Aplicativos → DeliveryBot → Desinstalar**.

Se aparecer erro de porta ocupada, feche o servidor antigo iniciado pelos scripts `.bat`. Logs ficam em `%LOCALAPPDATA%\DeliveryBot\deliverybot.log`. Não abra simultaneamente a versão antiga e a nova usando o mesmo banco.

## Para desenvolver e compilar novamente

O código continua compatível com `python -m src.app` e com as integrações anteriores. Esse comando e o executável iniciam a fila automaticamente e retomam o componente integrado quando o provedor LOCAL estiver selecionado; ao usar outro servidor WSGI, inicialize os componentes explicitamente uma vez no processo do servidor, sem iniciar múltiplos processos concorrentes. O painel administrativo fica em `/gestao`, usando a autenticação administrativa já configurada no `.env`. O aplicativo Desktop autentica a própria janela com uma sessão local; o painel não fica aberto para a rede.

Execute **Compilar aplicativo.ps1** com Python 3.12 e Node.js 20 ou mais recente instalados na máquina de compilação. O script cria um ambiente virtual, instala as versões verificadas em `requirements-desktop.lock.txt` e `whatsapp-native/package-lock.json`, roda os testes, inclui o runtime Node e suas licenças e gera o executável e o instalador em `dist`. O usuário final recebe todos esses componentes no programa.

Arquivos principais: `desktop.py`, `src/estoque.py`, `src/gestao.py`, `src/preferencias.py`, `web/templates/gestao.html`, `web/static/gestao.js`, `DeliveryBot.spec` e `packaging/`.
