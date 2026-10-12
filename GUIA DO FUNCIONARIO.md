# DeliveryBot Funcionário

Aplicativo Windows separado para registrar pedidos de balcão e conferir o caixa individual. Usa o catálogo e o banco do aplicativo do responsável pela rede privada da loja. Não exige Docker, Python, Node.js, Obsidian ou Ollama no computador do funcionário. O Microsoft Edge WebView2 precisa estar disponível, assim como no aplicativo principal.

## Preparar no computador do responsável

1. Instale ou atualize o aplicativo principal e deixe-o aberto; a bandeja mantém o atendimento e a conexão dos funcionários funcionando.
2. Em **Funcionários e auditoria**, mantenha a conta administradora e crie uma conta individual com perfil **Caixa** para cada funcionário. Atendente e Caixa são perfis diferentes. Não compartilhe a senha administradora.
3. Em **Caixas dos funcionários**, habilite a conexão, confira o IPv4 privado deste computador e salve. O painel sugere endereços disponíveis. A porta padrão é **5443**.
4. Autorize somente a rede privada caso o Firewall do Windows solicite acesso. Não publique essa porta na internet nem no túnel de pedidos. Os computadores precisam alcançar o endereço pela mesma rede da loja. Reserve o IP no roteador para reduzir mudanças de endereço.
5. Clique em **Salvar acesso para outro computador** e entregue o arquivo `.dbterminal` ao funcionário por um meio controlado. O arquivo contém certificado público e convite de uso único que expira em **dez minutos**. Gere um arquivo por computador; o certificado é confiado somente pelo segundo aplicativo, sem instalar uma autoridade global no Windows.

O gateway dos funcionários aceita somente suas próprias rotas e verifica dispositivo e conta. O painel administrativo permanece separado. A conexão começa desativada e pode ser desligada pelo responsável. Para revogar um computador, use **Revogar acesso**; senhas alteradas, contas desativadas e permissões alteradas também invalidam o acesso na próxima requisição.

## Instalar no computador do funcionário

Execute **Instalar-DeliveryBot-Funcionario.exe**. Abra **DeliveryBot Funcionário**, importe o arquivo de acesso e entre com a conta individual de Caixa. A versão portátil é **DeliveryBot-Funcionario.exe**. O aplicativo principal não precisa ser instalado nesse computador.

A credencial de dispositivo e as operações pendentes ficam protegidas pela conta Windows em `%LOCALAPPDATA%\DeliveryBotFuncionario`. A senha de login não é salva. Não apague essa pasta se existir uma operação aguardando conferência. A sessão exige novo login ao reabrir; o pareamento continua válido enquanto o dispositivo estiver autorizado e o certificado não mudar.

## Registrar pedidos e receber

Abra seu caixa informando o dinheiro inicial para troco. Selecione produtos e variações, ajuste a quantidade, informe uma identificação opcional e revise os valores na loja. Confirme somente depois de conferir o resumo. O preço e o saldo são verificados no servidor; o funcionário não altera cadastro, custos ou preços.

Escolha retirada na loja ou entrega, com endereço obrigatório e taxa calculada pela configuração da loja. Esses pedidos aparecem na mesma fila e no painel do responsável. Não exige telefone e não envia notificações WhatsApp. Pagamento marcado como recebido representa a declaração do operador; o aplicativo não cobra cartão, verifica extrato nem efetua transferência Pix.

- **Dinheiro:** informe o valor recebido. O aplicativo calcula troco e registra somente o valor líquido da venda como entrada. A abertura deve ter saldo suficiente para o troco declarado.
- **Pix e cartão:** ficam separados do dinheiro esperado na gaveta.
- **Pagamento pendente:** registre sem marcar recebimento; a venda não aumenta o saldo de dinheiro. Use **Registrar recebimento** no pedido depois que o pagamento ocorrer. Apenas seus próprios pedidos de balcão podem ser recebidos pelo terminal nesta versão.

Pedido, estoque, fila e recebimento são gravados em uma transação. Uma operação repetida com o mesmo identificador retorna o resultado anterior. Itens de produção sem controle de unidades continuam sem baixa de saldo; itens controlados respeitam a disponibilidade.

## Conferir dinheiro

**Dinheiro esperado = abertura + vendas recebidas em dinheiro + suprimentos − sangrias − devoluções registradas em dinheiro.**

Exemplo: abertura de R$ 100, venda de R$ 30 paga com R$ 50 e troco de R$ 20, Pix de R$ 40 e sangria de R$ 25 resultam em **R$ 105 de dinheiro esperado**. Pix não entra na gaveta e o troco não aumenta o valor da venda.

Registre suprimento ao adicionar dinheiro para troco e sangria ao retirar, sempre com motivo. Cada funcionário tem um caixa individual aberto por vez; não atribua o mesmo fundo físico simultaneamente a dois caixas. Este modo não consolida automaticamente uma única gaveta compartilhada por vários funcionários.

Ao fechar, conte o dinheiro físico e informe o total. O aplicativo grava valor esperado, valor contado e diferença; os fechamentos são preservados. O responsável consulta os caixas e pode conferir e fechar um caixa, inclusive de conta desativada. Valores previstos e declarados não substituem a contagem física.

## Cancelamento e devolução

Pedidos de balcão já recebidos exigem estorno pelo responsável em **Caixas dos funcionários**. Confirme que o dinheiro ou pagamento foi realmente devolvido; só então o aplicativo registra o estorno e cancela o pedido, devolvendo estoque controlado. Não existe transferência automática.

O estorno está disponível no caixa original ainda aberto e em pedidos ainda canceláveis pelo fluxo da loja. Caixas fechados são imutáveis: correções posteriores precisam de conferência financeira do responsável fora desse fluxo, sem reescrever o fechamento. Não há emissão fiscal, conciliação bancária automática, pagamento dividido ou controle de denominações de cédulas nesta versão.

## Queda de conexão

Uma falha pode ocorrer depois de a loja gravar a operação. Use **Conferir na loja** antes de registrar outro pedido. Se o resultado ainda não existir, **Repetir a mesma operação** reaproveita o identificador, evitando duplicação. Não repete gravações automaticamente. A pendência permanece cifrada mesmo se fechar o aplicativo; entre com a mesma conta para conferi-la.

Se a conta original foi desativada, o responsável pode entrar no terminal com sua conta administradora para conferir a pendência. Um resultado já registrado é recuperado; se a conta estiver bloqueada e a operação não tiver sido gravada, a pendência local pode ser encerrada com segurança. O responsável não repete vendas em nome de outra conta.

Se IP, porta ou certificado da loja mudarem, peça um novo arquivo ao responsável. Certificado incorreto ou conexão insegura são recusados. Não existe modo de venda offline com banco independente: sem a loja disponível, aguarde a reconexão para confirmar novos registros.

Backups portáteis preservam pedidos e livros de caixa, mas desativam a conexão remota e removem pareamentos e convites. Depois de restaurar, o responsável configura a rede e autoriza novamente os computadores.
