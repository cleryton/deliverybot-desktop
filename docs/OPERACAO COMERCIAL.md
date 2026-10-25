# Operação comercial do DeliveryBot

## Proteção dos dados e continuidade

Configure as cópias automáticas na gestão e escolha uma pasta protegida, de preferência em outro dispositivo. Guarde a senha de recuperação separadamente. Um backup no mesmo disco não protege contra perda desse disco.

Nas transferências para outra pasta, a rotina verifica a integridade e a senha do arquivo de destino antes de publicá-lo, remover a origem e aplicar a retenção. Se a cópia estiver incompleta, faltar espaço ou a sincronização com o disco falhar, a rotina mantém a origem e as cópias anteriores e informa falha. O horário da última cópia bem-sucedida não avança nesse caso.

Faça uma restauração de teste em instalação separada, com dados fictícios, antes de depender da recuperação em produção. Cópias portáteis exigem reconfiguração das credenciais e novo pareamento de dispositivos após restaurar.

O agendador trata separadamente falhas inesperadas da rotina de proteção e da consulta de atualizações. Uma falha não encerra o agendador nem impede a outra rotina de ser executada; uma nova tentativa ocorre no ciclo seguinte, com intervalo de um minuto. Isso não garante um backup enquanto o disco ou o banco estiver indisponível. Os avisos registrados evitam incluir o conteúdo bruto das exceções.

Datas de agendamento com fuso são convertidas para UTC. Datas antigas sem fuso mantêm a interpretação UTC usada pelo aplicativo. Uma data inválida é tratada como ausência de confirmação anterior, permitindo nova tentativa da rotina que estiver habilitada. A limpeza continua respeitando as regras de retenção configuradas, e a configuração das rotinas não é alterada por essa recuperação.

## Conferência da comunicação

O relatório de diagnóstico distingue credenciais Meta configuradas de conexão comprovada. O estado `META_CONFIGURADA` informa apenas que os campos necessários estão presentes; não confirma validade do token, webhook ou entrega. A coleta não chama a conta Meta nem inclui seus segredos.

Antes de disponibilizar uma loja, valide o fluxo completo com um destinatário autorizado: mensagem recebida, resposta, pedido registrado com preço correto e atualização de andamento. Use os indicadores de entrega para investigar falhas. Autorize explicitamente qualquer teste que envie mensagens reais.

O webhook recebe mensagens; o link de compra é pessoal e só é criado quando o cliente pede para comprar, solicita o link ou escolhe a opção 2. A criação desse link não confirma a compra. Durante a reconexão do HTTPS, a fila tenta recuperar o link, respeitando sua expiração e as pausas de atendimento humano. Se o endereço voltar antes da próxima tentativa, envia o link real; endereços locais continuam bloqueados. Se a fila expirar, o cliente precisará solicitar novamente.

Se o HTTPS continuar indisponível na tentativa seguinte, a solicitação de compra passa a enviar o catálogo em PDF como anexo, com orientação para digitar PEDIDO PELO WHATSAPP. O PDF inclui produtos disponíveis, preços e fotos cadastradas, sem custos internos, quantidades de estoque, telefones ou histórico de clientes. É um catálogo, não uma confirmação de pedido ou pagamento. Sua geração e seu envio não precisam de um link público.

O documento tem limite de 8 MB e é gerado em memória. A conexão local por QR Code usa anexo inline; a Meta recebe o arquivo pela API de mídia e envia por identificador. WAHA externo precisa oferecer o envio de arquivos na edição instalada. Falhas de geração ou envio ficam para conferência no painel; não há reenvio automático quando o transporte pode ter aceitado o documento. A nova tentativa manual continua sendo de PDF e gera o catálogo atualizado. Após reiniciar, envios que estavam em andamento continuam exigindo conferência.

Referências dos contratos de integração: [envio de documentos na coleção oficial da Meta](https://www.postman.com/meta/whatsapp-business-platform/request/zjtbdpz/send-document-message-by-id), [upload de mídia pela Meta](https://whatsappbusiness.com/blog/media-messages-via-app/) e [arquivos inline no WAHA](https://waha.devlike.pro/docs/how-to/send-messages/).

Enquanto o HTTPS estiver indisponível, mensagens de outras conversas que já podem ser atendidas têm prioridade sobre solicitações que aguardam o link. A ordem dentro de cada conversa é preservada. Assim que o endereço volta, a fila retoma a ordem original. O painel informa a quantidade de mensagens aguardando o HTTPS, sem incluir envios incertos que exigem conferência manual.

## Aprovação por comércio

- Conferir catálogo, preços, disponibilidade e regras de entrega ou retirada.
- Testar pedidos pelo navegador e pelo atendimento, incluindo repetição de confirmação e indisponibilidade de produtos.
- Conferir permissões de cada funcionário e conciliação do caixa com dados de teste.
- Verificar endereço HTTPS público, recuperação de falhas e acesso após reiniciar o computador.
- Confirmar backup, recuperação, contato de suporte e política de atualização.
- Definir com o responsável pela loja retenção, atendimento aos titulares e aviso de privacidade aplicável à operação.

## Limites do ambiente de demonstração

O endereço de QA usa catálogo fictício, comunicação simulada e armazenamento temporário. Não deve receber dados reais de clientes nem servir como ambiente comercial. A hospedagem gratuita pode suspender o serviço e perder os dados temporários em reinicializações.

Os testes automatizados e a compilação reduzem regressões; não substituem a validação de cada instalação, o teste de recuperação e a homologação do comércio. Esta documentação não representa certificação de segurança ou conformidade legal.
