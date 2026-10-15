# Acesso remoto à gestão

O responsável pode autorizar a consulta de produtos ativos e pedidos em andamento pela internet. A permissão **Consultar e avançar pedidos** também permite iniciar o preparo, marcar como pronto e concluir entrega ou retirada. Essas mudanças podem notificar o cliente pelo WhatsApp, como no aplicativo local.

## Preparar e acessar

1. No aplicativo Windows do responsável, crie sua conta administradora em **Funcionários e permissões**. Cadastre uma conta individual de administrador ou atendente para a pessoa que acessará remotamente. Caixas continuam usando o aplicativo próprio na rede da loja.
2. Inicie a **Página de pedidos** e aguarde o HTTPS ficar disponível. O acesso usa o conector já incluído, sem instalar serviços adicionais no computador remoto.
3. Abra **Acesso remoto**, escolha a conta, a permissão e o prazo (15 minutos, uma hora, quatro horas ou 24 horas). O padrão é somente consulta.
4. Gere e copie o convite. Ele é mostrado somente nessa ocasião. Compartilhe com a pessoa autorizada por um canal de confiança; entregue a senha separadamente. Não publique o link nem use contas compartilhadas.
5. No navegador do dispositivo remoto, abra o convite e informe o login e a senha da conta vinculada. O código é preenchido a partir do fragmento do link e retirado da barra do navegador. Sem o fragmento, cole o código do convite no campo indicado.
6. Use **Atualizar agora** para consultar os dados mais recentes. O painel não fica atualizando sozinho. Antes de avançar um pedido, confirme a operação.

O computador da loja precisa permanecer ligado, conectado e com o aplicativo aberto. Um domínio temporário pode mudar quando o túnel reiniciar: nesse caso, revogue o convite antigo e gere outro com o endereço atual. Para um endereço estável, configure um domínio próprio na publicação existente.

## Encerrar e revisar

Cada convite permite **uma única entrada**, de uma conta específica. A sessão expira após 15 minutos sem atividade ou quando atingir o prazo máximo do convite. Encerrar o acesso no navegador invalida a sessão no servidor, inclusive cópias anteriores do cookie.

No aplicativo local, use **Revogar acesso** ou **Encerrar todos os acessos**. Alterar senha, desativar a conta ou mudar seu perfil invalida o acesso. Reiniciar/atualizar o aplicativo encerra convites e sessões, inclusive convites antigos recuperados de um backup. Para entrar novamente, solicite outro convite.

A revogação impede novas consultas e operações. Uma operação já confirmada não é desfeita; uma resposta ou notificação já em trânsito pode chegar depois da revogação. A criação, entrada, avanço, saída e revogação ficam na auditoria local, com conta, ação e identificador, sem senha ou código do convite.

## Limites e proteção

- A área remota é separada do painel interno. Mesmo uma conta administradora recebe somente a capacidade selecionada no convite.
- Não permite configurações da Meta/IA/Obsidian, gerenciamento de contas, backups, caixa, cancelamentos, exclusão de produtos ou comandos no computador.
- Retorna apenas produtos ativos e pedidos abertos, sem telefone/endereço do cliente, custos internos ou credenciais. Os nomes e observações dos pedidos necessários ao atendimento continuam visíveis; oriente os funcionários a não inserir dados sensíveis nessas observações.
- Requer HTTPS, convite aleatório de 256 bits, senha da conta e cookie HttpOnly/Secure/SameSite=Strict. O banco guarda hashes dos convites e sessões. O convite não vai em parâmetros de consulta enviados ao servidor, nem é salvo no Obsidian ou armazenamento do navegador pelo aplicativo.
- As rotas públicas aceitam somente as operações remotas explicitamente listadas. Cabeçalhos de proxy não concedem identidade local. A autorização para avançar é novamente conferida dentro da transação do pedido; um estado desatualizado é recusado em vez de avançar duas etapas.
- Há limites de requisições, tentativas de entrada e tamanho dos formulários. Os bloqueios de tentativas não dependem de IP informado pelo visitante. No máximo 20 convites não expirados podem ficar ativos; revogue os antigos quando não precisar deles.
- Não há integração com controle da tela do Windows. O acesso não oferece shell, arquivos do sistema ou comandos arbitrários.

As decisões de expiração, revogação e negação por padrão seguem as orientações de [gerenciamento de sessões](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) e [autorização da OWASP](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html). Os controles reduzem riscos; não equivalem a uma certificação ou auditoria externa.

## Validação

Testes automatizados usam bancos temporários, contas fictícias e notificações simuladas. Cobrem convite de uso único, conta vinculada, permissões, HTTPS, CSRF, revogação, prazos, troca de senha durante login, revogação antes da transação, cliques repetidos e bloqueio de rotas internas. Não conectam contas reais nem iniciam túneis.
