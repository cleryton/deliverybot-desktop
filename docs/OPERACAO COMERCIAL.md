# Operação comercial do DeliveryBot

## Proteção dos dados e continuidade

Configure as cópias automáticas na gestão e escolha uma pasta protegida, de preferência em outro dispositivo. Guarde a senha de recuperação separadamente. Um backup no mesmo disco não protege contra perda desse disco.

Nas transferências para outra pasta, a rotina verifica a integridade e a senha do arquivo de destino antes de publicá-lo, remover a origem e aplicar a retenção. Se a cópia estiver incompleta, faltar espaço ou a sincronização com o disco falhar, a rotina mantém a origem e as cópias anteriores e informa falha. O horário da última cópia bem-sucedida não avança nesse caso.

Faça uma restauração de teste em instalação separada, com dados fictícios, antes de depender da recuperação em produção. Cópias portáteis exigem reconfiguração das credenciais e novo pareamento de dispositivos após restaurar.

## Conferência da comunicação

O relatório de diagnóstico distingue credenciais Meta configuradas de conexão comprovada. O estado `META_CONFIGURADA` informa apenas que os campos necessários estão presentes; não confirma validade do token, webhook ou entrega. A coleta não chama a conta Meta nem inclui seus segredos.

Antes de disponibilizar uma loja, valide o fluxo completo com um destinatário autorizado: mensagem recebida, resposta, pedido registrado com preço correto e atualização de andamento. Use os indicadores de entrega para investigar falhas. Autorize explicitamente qualquer teste que envie mensagens reais.

O webhook recebe mensagens; o link de compra é pessoal e só é criado quando o cliente pede para comprar, solicita o link ou escolhe a opção 2. A criação desse link não confirma a compra. Durante a reconexão do HTTPS, uma solicitação de link permanece na fila e é retomada quando houver endereço válido, respeitando a expiração da fila e as pausas de atendimento humano. Avisos de indisponibilidade preparados antes da reconexão são substituídos pelo link real antes do envio; endereços locais continuam bloqueados. Se a fila expirar, o cliente precisará solicitar novamente.

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
