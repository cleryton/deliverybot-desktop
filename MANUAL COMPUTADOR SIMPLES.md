# DeliveryBot - instalação e operação em computador simples

Edição 2.51.0. Manual do responsável pela loja e dos funcionários.

## 1. Escolher uma instalação leve

Este roteiro considera um computador Windows de 64 bits com cerca de 4 GB de memória e sem placa de vídeo dedicada. É um cenário de planejamento, não um requisito mínimo comprovado em todas as máquinas. O desempenho depende do processador, disco, internet e volume de atendimento. O aplicativo é destinado a Windows 10/11 de 64 bits; confira também o suporte e as atualizações de segurança do seu Windows.

Para começar com menos consumo, use o atendimento local do DeliveryBot. Menu, catálogo, preços, pedidos, pagamento informado e diversas orientações funcionam sem gerar respostas no Ollama. Instalar Obsidian e carregar um modelo de IA não é obrigatório para operar esses fluxos. Uma pergunta recusada não precisa abrir o modelo. O computador principal deve permanecer ligado, com o aplicativo aberto e conectado à internet durante o atendimento.

Use apenas um computador principal para o banco da loja. Os outros computadores usam o aplicativo do funcionário. Não coloque o banco em uma pasta sincronizada nem abra cópias diferentes como se fossem a mesma loja. Reserve espaço para o instalador, aplicação, fotos e backups. O tamanho do instalador não representa todo o espaço usado durante a instalação; interrompa a instalação se o disco estiver cheio e libere espaço antes de tentar novamente.

## 2. Preparar o computador

1. Salve seus trabalhos e encerre aplicações pesadas que não estiver usando. Reinicie se houver uma atualização pendente.
2. Confira a arquitetura em Configurações do Windows > Sistema > Sobre. Use o pacote de 64 bits.
3. Confira o espaço livre no Explorador de Arquivos. Preserve documentos pessoais, fotos e backups ao fazer a limpeza.
4. Obtenha o instalador de uma distribuição fornecida pelo responsável pelo projeto. O endereço do repositório é https://github.com/cleryton/deliverybot-desktop. Um commit no GitHub não significa que existe um instalador publicado em Releases.
5. Não baixe executáveis enviados por desconhecidos. Se a distribuição tiver SHA256SUMS.txt, peça ao responsável técnico a conferência de integridade. Um hash não substitui a verificação de origem do arquivo.

O usuário final não precisa instalar Docker, Python ou Node.js. Não desative o antivírus para instalar. Se o Windows impedir a execução, confira a origem e peça orientação ao responsável técnico; não aceite exceções automaticamente.

## 3. Instalar ou atualizar o aplicativo principal

1. Em uma atualização, crie antes um backup protegido no DeliveryBot e guarde sua senha separadamente. Não mantenha a única cópia no mesmo disco do computador.
2. Feche o DeliveryBot. Aguarde o encerramento antes de executar outra cópia.
3. Abra Instalar-DeliveryBot.exe. Siga as instruções do instalador e mantenha a pasta sugerida, salvo orientação técnica.
4. Na primeira configuração, informe nome, segmento e descrição do comércio. Escolha Revenda, Produção sob pedido, Serviços ou Misto.
5. Para uma lanchonete, itens preparados após a compra podem ficar sem contagem de estoque. Bebidas ou produtos prontos podem controlar quantidade. Ajuste cada cadastro conforme a operação real.
6. Abra o aplicativo pelo atalho. Uma atualização deve preservar os cadastros existentes; não use importação fictícia para substituir seu banco real.

Os dados de uso do aplicativo instalado ficam na pasta de dados do DeliveryBot da conta Windows, normalmente em %LOCALAPPDATA%\DeliveryBot. Use a ação Abrir pasta de dados no próprio painel quando disponível. Não apague essa pasta como se fosse temporária. O banco real, as credenciais e as sessões não devem ir para o GitHub.

## 4. Configurar a loja com menos consumo

Abra Guia de configuração e siga as etapas. Em Meu comércio, confira o segmento e o que a loja realmente oferece. Em Configurações, revise horário, endereço, contato, formas de pagamento, taxa e tempo estimado. Em Privacidade e LGPD, preencha o responsável e o canal de contato. Cadastre uma conta administradora com senha exclusiva e crie contas individuais para a equipe.

Cadastre poucos produtos de teste antes de importar todo o catálogo. Informe nome, categoria, preço e disponibilidade. Use um produto por variação quando precisar de preços ou saldos diferentes. Cadastre fotos somente quando forem úteis; imagens grandes aumentam armazenamento e tempo de envio. O formulário informa formatos e limites permitidos. Confira o catálogo em PDF e a página no celular.

Para a operação leve, deixe o provedor de IA desativado nas opções do aplicativo. Não clique em iniciar o Ollama se não for usá-lo. Se ele já estiver rodando em segundo plano, encerre-o pela opção própria do Ollama após confirmar que nenhum outro programa precisa dele. Não encerre processos desconhecidos. O atendimento determinístico continua disponível, mas respostas livres e certas consultas complexas podem pedir esclarecimento ou atendimento humano.

O Obsidian organiza notas aprovadas; ele não treina automaticamente a rede neural. Edite apenas informações comerciais, sem senhas ou dados de clientes. No uso cotidiano, não é necessário manter a janela do Obsidian aberta. Se optar por IA local depois, teste separadamente consumo e resposta na máquina antes de usar com clientes. Não existe garantia de resposta quase instantânea em qualquer hardware.

## 5. Conectar WhatsApp e a página HTTPS

Escolha a conexão apresentada pelo aplicativo: a modalidade integrada usa leitura de QR Code; a Meta oficial utiliza a conta e as permissões do próprio comércio. Cada loja deve usar suas credenciais. Não compartilhe o token de outra pessoa, nem envie tokens, senhas ou códigos de verificação pelo chat.

Na conexão integrada, abra WhatsApp e IA, inicie a conexão e leia o QR Code em Aparelhos conectados no celular. Na Meta, siga o assistente de conta, número e webhook. O número de teste da Meta só atende destinatários autorizados por ela. Credenciais temporárias podem expirar; a conexão oficial depende da configuração válida da conta Meta e das regras do provedor.

Em Página de pedidos, confira o estado do endereço público HTTPS. A inicialização automática não dispensa verificar se o endereço realmente abriu no celular. Teste usando dados móveis, não apenas o Wi-Fi da loja. Nunca envie localhost ou 127.0.0.1 ao cliente. Um endereço temporário de túnel pode mudar após reiniciar; atualize e confira o webhook da Meta quando necessário. Sem endereço público válido, o atendimento pode orientar a retentativa, o pedido pela conversa ou o catálogo em PDF, conforme o fluxo disponível.

Não prometa que um túnel gratuito ficará sempre acessível. Não abra o painel administrativo ao público para resolver falha de um link. Se o computador dormir, desligar ou perder internet, o atendimento e a página local ficam indisponíveis. Configure a suspensão durante o expediente de acordo com as regras da loja e a segurança do equipamento.

## 6. Fazer um teste completo antes de atender

Use Testar atendimento e dados fictícios. Confira a privacidade antes de conectar uma conta real. Enviar uma mensagem real exige usar uma conversa de teste autorizada pelo responsável. Um pedido de teste feito no banco de produção afeta seus saldos e relatórios; cancele-o depois para devolver o estoque quando aplicável.

1. Pergunte horário e preço de um produto. A resposta deve corresponder ao cadastro.
2. Solicite um pedido, abra o endereço HTTPS no celular e confira catálogo, fotos, quantidades, retirada ou entrega e pagamento.
3. Confirme uma única compra. Veja se ela apareceu no painel e confira o total calculado pelo sistema.
4. Avance o estado no painel e confira o acompanhamento. Não use uma mensagem da IA como prova de que um pedido foi gravado.
5. Teste o pedido pela conversa, caso o cliente prefira não abrir o link. Revise o resumo antes de confirmar.
6. Pergunte sobre entrega na Lua ou no espaço. O bot deve orientar a conferência da área por CEP/equipe, sem prometer a entrega.
7. Pergunte a raiz quadrada de 144. A resposta local prevista é: não foi dessa vez seu marcos. Essa frase é uma regra da pergunta; o sistema não identifica quem é o professor. O primeiro contato pode incluir também o aviso de privacidade.
8. Volte a pedir um produto. A recusa anterior não deve impedir a compra. Confira também um endereço válido como Rua Marte: ele não deve ser confundido com o planeta.

## 7. Funcionários e caixa em outros computadores

No computador principal, crie as contas e permissões adequadas. No outro computador, use Instalar-DeliveryBot-Funcionario.exe e siga a conexão ao servidor da loja. Utilize o endereço e a credencial fornecidos pelo administrador. O aplicativo do funcionário não deve receber uma cópia do banco principal nem as credenciais da Meta.

Cada funcionário deve registrar suas próprias vendas e movimentações permitidas. Confira abertura, vendas, formas de pagamento e fechamento do caixa. O valor esperado em dinheiro depende do saldo inicial, recebimentos em dinheiro e movimentações registradas; vendas por Pix ou cartão não devem ser tratadas como dinheiro físico na gaveta. Faça uma conferência real no fechamento. O administrador mantém as funções de configuração e revisão.

Para gestão pela internet, utilize apenas o fluxo específico de acesso remoto do DeliveryBot, com autenticação e permissões. Não encaminhe a porta do banco, não compartilhe a senha do administrador e não exponha um endereço local como solução de acesso externo.

## 8. Rotina diária e manutenção

Ao abrir: confira conta de acesso, conexão WhatsApp, HTTPS, fila, disponibilidade de produtos e situação do backup. Ao longo do dia, acompanhe Pedidos e Atendimento humano. Evite várias cópias do aplicativo principal. Use as buscas e filtros para encontrar o que precisa. Na edição, aguarde a confirmação de salvamento e revise avisos de alterações pendentes.

Se o estoque mudar enquanto o cliente preenche o pedido, a página deve apresentar o erro e manter a seleção para revisão. Um produto indisponível pode sair do catálogo com aviso. O aplicativo confere preço e saldo novamente antes de registrar. O carrinho do cliente não é garantia de reserva.

Ao encerrar: confira pedidos, caixa e mensagens pendentes. Faça ou verifique o backup criptografado. Guarde a senha em local separado e protegido; perdê-la pode impedir a recuperação. Em outro computador ou após restauração, as conexões podem precisar ser configuradas novamente. Faça restaurações com orientação técnica e um backup atual preservado; não substitua o banco manualmente com o aplicativo aberto.

## 9. Resolver problemas comuns

Aplicativo lento: confira espaço livre e memória no Gerenciador de Tarefas; feche aplicações que reconhece e não precisa. Teste o atendimento sem Ollama e sem programas pesados simultâneos. Reinicie o aplicativo após concluir operações pendentes. Não limpe o banco ou as sessões para tentar ganhar velocidade.

Mensagem sem resposta: veja se a conversa foi assumida pela equipe, se houve bloqueio por segurança, se a conexão está ativa e se a fila pede intervenção. Assuntos fora da loja podem receber uma recusa local. Não repita várias vezes uma mensagem para forçar o envio; verifique antes o estado e a conversa para evitar duplicações.

Link não abre: teste a internet, o HTTPS atual e a conexão em dados móveis. Links usados ou expirados precisam ser substituídos pelo fluxo do bot. Não reutilize o link de outro cliente. Para falhas persistentes, use atendimento humano e registre somente informações sem dados pessoais para o suporte.

Meta desconectada: confira expiração/revogação de credenciais, número, permissões e webhook na própria conta. Não copie um token de terceiros. Falha de autenticação não se resolve retirando a verificação de segurança do sistema.

Instalação falha ou disco cheio: pare e libere espaço removendo somente arquivos que reconhece. Preserve a distribuição em uso e seus backups. Solicite ao responsável técnico uma nova cópia verificada se o download estiver incompleto. Não apague a pasta de dados e não instale por cima de um processo em execução.

## 10. Checklist de entrega e suporte

Antes de liberar para a equipe, confira: instalação abre sem terminal; conta administradora e contas individuais funcionam; catálogo e preços estão corretos; pedido chega uma única vez; caixa separa as formas de pagamento; HTTPS abre fora do Wi-Fi; WhatsApp está conectado; backup foi verificado; conversas estranhas não alteram pedidos; atendimento humano pode assumir a conversa.

Ao pedir suporte, informe a versão exibida no painel, o horário aproximado, a tela usada, a ação e o texto do erro sem dados pessoais. Não envie banco real, lista de clientes, senha de backup, token, QR Code ou código de autenticação. Novos casos inesperados devem virar testes de regressão. Testes reduzem riscos, mas não garantem ausência de todas as falhas possíveis.

Este manual descreve o pacote 2.51.0. Atualizar o código no GitHub não atualiza automaticamente o aplicativo instalado nem o ambiente web hospedado. Execute o instalador correspondente para aplicar a nova distribuição e faça novamente o checklist.
