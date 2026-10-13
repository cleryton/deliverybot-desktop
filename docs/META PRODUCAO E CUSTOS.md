# Número próprio e custos da Meta

Em **Meta oficial e custos**, o responsável pode preparar a futura troca do número de teste para um número próprio definitivo. A conexão por QR Code continua sendo outra modalidade; a Cloud API usa os identificadores e credenciais emitidos pela Meta.

## Preparação e troca

1. Adicione e verifique seu número no painel da Meta. Se ele já é usado no WhatsApp Business, confira o fluxo de coexistência ou migração disponibilizado para a conta antes de alterar o cadastro. O DeliveryBot não exclui sua conta móvel nem registra números automaticamente.
2. Conclua as etapas de produção exigidas pela Meta, incluindo as autorizações, verificação, publicação e pagamento quando aplicáveis. Use um token de usuário do sistema apropriado à conta; sua duração e revogação são controladas pela Meta. O aplicativo não transforma um token temporário em permanente.
3. Prepare um domínio e túnel HTTPS fixos. Configure o callback `/webhook`, o token de verificação e a assinatura `messages`. A consulta do número não comprova que o webhook funciona. O túnel rápido muda de endereço ao reiniciar; ter um número definitivo não torna o endereço do servidor permanente. O computador precisa continuar ligado para o atendimento local.
4. Informe o ID do novo número e o ID da conta WhatsApp Business. Valide o acesso. A consulta faz apenas GET na Graph API com o token em cabeçalho, prazo de dez segundos e sem redirecionamentos; confere também que o número pertence à conta indicada.
5. Revise e conclua ou ignore as pendências do atendimento, inclusive envios incertos. Confirme a troca local. Uma alteração simultânea do número invalida a confirmação; a transação revalida o número e a fila antes de salvar. Renovar somente o token continua permitido para recuperar uma fila parada.
6. Faça um teste autorizado de recebimento e resposta pelo novo número. A aplicação preserva produtos, clientes, pedidos e o acompanhamento financeiro anterior. As credenciais seguem a proteção local existente do Windows e não aparecem no retorno da API. Nunca guarde tokens no Obsidian ou Git.

A troca é local e não publica o app Meta, muda pagamentos ou envia mensagens de teste sozinha. O histórico por número permite registrar eventos de entrega antigos quando eles continuam chegando com a assinatura do aplicativo configurado. Mensagens recebidas por um número anterior não iniciam atendimento pela conexão nova. Mantenha o webhook e a conta anteriores disponíveis quando precisar concluir a conciliação de entregas pendentes.

## Como a estimativa funciona

A Meta informa a cobrança por categoria e mercado, e os preços podem mudar. Referências primárias consultadas em 13/10/2026: [preços da plataforma](https://whatsappbusiness.com/products/platform-pricing/), [webhooks](https://developers.facebook.com/documentation/business-messaging/whatsapp/webhooks/overview/) e [API oficial de registro](https://www.postman.com/meta/whatsapp-business-platform/request/13382743-c953a6a4-3457-4845-91c6-e13e1db9f5ba).

O aplicativo registra o identificador de envio como hash e consolida os eventos assinados `sent`, `delivered`, `read` e `failed`. Cada mensagem e número têm um único registro. A estimativa só é somada depois de um evento que confirme entrega ou leitura; o aceite da API, sozinho, não comprova entrega. O instante de entrega mais antigo recebido define o período do acompanhamento, em America/Sao_Paulo (UTC−3). Uma confirmação atrasada pode corrigir o mês e a tarifa aplicável; se eventos anteriores não chegaram, os valores podem divergir da fatura e exigem conciliação. Eventos antigos não revertem uma classificação de cobrança mais recente.

- `pricing.billable=false` confirma gratuidade. Ausência desse campo não significa custo zero. O aplicativo não pressupõe que toda mensagem de serviço seja gratuita.
- `pricing.billable=true` e modelo `PMP` permitem uma estimativa por mensagem usando a tarifa cadastrada para a categoria e destinatários no Brasil. O evento de status informa a classificação, não necessariamente o valor exato em reais.
- Sem tarifa vigente na data da entrega, sem classificação, com outro modelo de cobrança ou com destinatários de outro mercado, o custo fica **pendente**. Categorias e formatos novos também precisam de revisão, sem assumir gratuidade.
- Tarifas são informadas pelo responsável em reais, com até seis casas decimais. Não existem preços presumidos ou tabela fixa embutida. Mudanças têm vigência a partir do cadastro e não reescrevem estimativas já conhecidas; eventos atrasados usam a tarifa disponível para a data da entrega.
- O orçamento mensal considera somente registros classificados como **produção**, avisa no painel ao atingir o percentual configurado e ao exceder o valor. Não bloqueia o bot nem limita a cobrança efetiva. Estimativas incompletas continuam sinalizadas mesmo que o valor conhecido esteja abaixo do orçamento.
- Impostos, câmbio, descontos por volume, taxas de intermediários e itens fora dos eventos recebidos não são calculados automaticamente. Confira os valores efetivos no faturamento da Meta. O sistema não importa retroativamente o gasto de versões anteriores.

Este acompanhamento não grava conteúdo, nomes ou telefones de clientes; guarda apenas o número comercial por ID, o hash da mensagem, ambiente, datas, categoria, mercado e classificação de cobrança. Os dados locais acompanham os backups. Contas Caixa e Atendente não têm acesso aos endpoints de custos, tarifas ou migração. O controle pertence ao administrador e não é delegado a notas do Obsidian ou ao modelo de IA.
