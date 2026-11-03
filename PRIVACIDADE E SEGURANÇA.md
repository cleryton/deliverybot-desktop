# Privacidade e segurança — DeliveryBot

Este documento descreve as medidas implementadas e as decisões que a loja precisa manter. Não representa certificação de conformidade: a aplicação da LGPD depende das finalidades, bases legais, pessoas com acesso, fornecedores e práticas da empresa.

## Preparação da loja

Em **Privacidade e LGPD**, informe a razão social ou nome do responsável e um contato acessível para os titulares. Revise o aviso público em `/privacidade`. O pedido informa o uso dos dados antes da confirmação, e o primeiro atendimento contém um link para o aviso. O comando PRIVACIDADE funciona sem IA.

O cadastro usa nome, telefone e, quando necessária a entrega, CEP e endereço. Não é necessário coletar CPF, documento, data de nascimento ou dados de cartão. A política explica o atendimento e a compra; não usa uma caixa obrigatória de consentimento genérico para autorizar marketing. Qualquer nova finalidade, incluindo campanhas, requer avaliação própria da base legal e transparência.

## Acesso e proteção local

O executável escuta apenas em `127.0.0.1`; a janela administrativa usa uma sessão exclusiva do processo. O painel e a cozinha ficam restritos ao computador por padrão. No modo servidor, a opção de ambiente `ADMIN_PERMITIR_REMOTO=true` exige uma conexão reconhecida como HTTPS pelo servidor WSGI e autenticação administrativa. Não confie em cabeçalhos enviados diretamente por clientes: configure eventual proxy reverso para aceitar cabeçalhos apenas de proxies conhecidos e impeça acesso direto ao servidor de origem. O código não habilita confiança automática em `X-Forwarded-*`.

Há proteção CSRF nas alterações administrativas, cozinha e formulário de compra, limitação das tentativas de senha e cabeçalhos que evitam cache, exposição do link por referência, enquadramento e scripts não autorizados. O ambiente de desenvolvimento não deve ser publicado com debugger. Serviços externos que recebem dados ou credenciais precisam usar HTTPS; HTTP fica permitido apenas no loopback.

A pasta Desktop em `%LOCALAPPDATA%\DeliveryBot` tem permissões restritas à conta Windows atual e SYSTEM, incluindo dados antigos. Atalhos e junções não são percorridos. Não coloque a pasta em localização compartilhada nem abra o app por uma conta coletiva. Administradores do Windows, programas na mesma conta e pessoas com acesso a uma sessão desbloqueada podem acessar os dados. Bloqueio de tela, proteção da conta, atualização do Windows e criptografia de disco são medidas complementares.

Segredos guardados nas configurações são protegidos por DPAPI no Windows, com migração dos valores antigos sem mudança das credenciais. Em outra conta, informe novamente a credencial. O `.env` de um servidor e os dados internos da sessão WhatsApp exigem controle de acesso próprio. O banco SQLite em uso não tem criptografia integral; o objetivo das permissões é restringir acesso por outras contas, não proteger um disco removido ou um computador comprometido.

## Pedidos públicos e autenticações

No aplicativo real, o formulário assina uma prova vinculada à sessão e ao link específico do pedido. Uma prova de outro pedido ou de um formulário administrativo não confirma a compra. O primeiro acesso pelo WhatsApp e pedidos em abas diferentes continuam funcionando. A assinatura usa a chave privada do servidor, sem acrescentar telefones ou links ao cookie. As verificações de origem e de campos repetidos continuam obrigatórias.

O link de compra continua sendo uma credencial de posse, temporária e de uso único: quem recebe um link válido pode abrir seu formulário. A assinatura do formulário não comprova a identidade de quem abriu esse link. Não compartilhe o endereço individual; o formulário não preenche dados pessoais de compras anteriores, e o comprovante exige a sessão que confirmou a compra, seu identificador e a correspondência entre cliente e link.

A confirmação admite até oito tentativas por link e sessenta por banco a cada minuto, com duas operações simultâneas por processo. Os limites são aplicados antes da consulta de entrega, gravação e notificações. Uma recusa responde com 429 e prazo para tentar novamente, preservando o link e o estoque. As vagas são liberadas inclusive em falhas. O controle guarda somente resumos de identificadores e não substitui os limites de rede da hospedagem.

As tentativas de autenticação da cozinha, do operador e do terminal são independentes. Um acesso válido a uma dessas barreiras não reinicia erros da outra. O bloqueio por origem continua durando cinco minutos após dez falhas; pessoas no mesmo endereço de rede podem compartilhar esse bloqueio no mesmo tipo de acesso.

A criação e a alteração de contas conferem novamente o administrador ativo e a versão de sua sessão dentro da transação que grava a mudança. Uma conta revogada durante a preparação da requisição não pode recriar privilégios administrativos. O primeiro cadastro mantém seu fluxo próprio, com conferência do estado inicial na transação. As respostas de listagem e de avanço de pedidos ocultam o custo interno dos itens para atendentes; a consulta administrativa mantém esse dado.

Eventos WAHA só iniciam atendimento quando LOCAL ou WAHA é o provedor ativo. O recebimento captura a conexão de origem e a fila a confere dentro da transação de gravação. Uma troca concorrente não pode atribuir o evento à conta substituta. Eventos ignorados ou recusados não atualizam os contatos. Ao mudar de conexão, as rotas técnicas aprendidas para contatos são descartadas; nomes, telefones, pedidos e histórico comercial são preservados. A nova conexão aprende seus próprios identificadores nas próximas mensagens. Credenciais comprometidas precisam ser revogadas ou substituídas pelo responsável.

O webhook Meta rejeita assinaturas ausentes ou com formato inválido antes de ler o corpo. A comparação continua usando a credencial capturada com a conexão. A verificação inicial exige um desafio preenchido de até 1.024 caracteres e o devolve como texto simples. O filtro dos logs oculta também `hub.verify_token`, incluindo o nome codificado no endereço.

## Backups e restauração

Backups novos `.dbot` usam AES-256-GCM e scrypt com salt aleatório e senha de 12 a 256 caracteres. A autenticação detecta senha incorreta e alteração do arquivo. A cópia é feita em memória e não gera um intermediário de exportação sem criptografia. Chaves e tokens de provedores são excluídos da cópia portável; as credenciais precisam ser reconfiguradas após restaurar.

A senha não é armazenada pelo app. Guarde-a separadamente, restrinja o acesso ao arquivo e mantenha uma cópia em outro equipamento. Teste a recuperação com dados fictícios. Cópias automáticas anteriores à restauração usam DPAPI e extensão `.dbot-local`; só podem ser abertas pela conta Windows de origem. Backups antigos `.db` continuam legíveis por quem tiver acesso: planeje sua conversão e descarte conforme a política da loja. A atualização não remove cópias antigas automaticamente.

Antes de aceitar a restauração, o aplicativo abre o banco de origem somente para leitura e testa o esquema e as migrações distribuídos com o aplicativo em uma cópia isolada em memória. Confere colunas, chaves primárias, unicidade, referências e integridade, recusando estruturas incompatíveis e SQL de vistas, gatilhos ou tabelas virtuais. A validação não troca a configuração do banco em uso nem modifica o arquivo original. Backups antigos compatíveis continuam migrando; uma recusa preserva o banco atual e o arquivo pendente. Há limite de 256 MB e prazo de validação de 30 segundos.

## Direitos dos titulares

O administrador deve verificar a identidade e registrar a solicitação antes de usar as ferramentas. O aplicativo exige essa confirmação e registra exportação, correção, remoção de identificação e limpeza em uma auditoria sem telefone, endereço ou conteúdo de conversa. A confirmação na interface é uma declaração do operador; o aplicativo não verifica documentos nem comprova identidade sozinho.

**Exportar dados** inclui cadastro, pedidos, mensagens e atendimentos do banco atual. Links de compra e segredos não são exportados. O relatório JSON não é criptografado: escolha um destino protegido, entregue por um canal adequado ao titular e elimine a cópia de trabalho conforme sua política. Dados mantidos pelo WhatsApp, arquivos internos de autenticação, caixa de entrada ainda não entregue, backups e outros fornecedores precisam de tratamento separado.

**Corrigir cadastro** permite atualizar nome, CEP e endereço sem modificar os valores de venda. **Remover identificação** elimina as conversas e links do banco atual e substitui nome, telefone e endereço do cadastro, preservando itens e totais dos pedidos. Pedidos abertos e envios em processamento bloqueiam a operação para evitar perda operacional. Os dados remanescentes de compra podem permitir reidentificação em combinação com informações externas; avalie a solicitação e as obrigações de conservação antes de concluir que um registro está anonimizado.

Não restaure um backup antigo sem reavaliar solicitações de remoção atendidas depois da data da cópia. Mantenha um registro administrativo separado das solicitações necessário para esse controle, com acesso restrito e retenção definida.

## Retenção e IA

O prazo operacional das conversas começa em 30 dias, configurável de 1 a 365. A limpeza pode ser manual ou diária quando habilitada em Proteção automática: apaga mensagens antigas concluídas, limpa o conteúdo dos atendimentos concluídos e elimina links expirados. Atendimentos pendentes ou incertos são preservados. Identificadores de eventos são guardados como hashes para manter a deduplicação. Pedidos, perfis sem solicitação de remoção, auditoria, backups, logs anteriores e exportações não são eliminados por esse botão. Defina responsáveis e periodicidade para cada conjunto; o prazo fiscal/legal dos pedidos deve ser avaliado para a atividade da empresa, não escolhido genericamente pelo software.

Por padrão, o bot não envia mensagens à Anthropic nem a um Ollama externo. Ollama em loopback permanece disponível. A habilitação de IA externa depende da avaliação da loja sobre base legal, contratos, transparência e transferências internacionais. Antes de enviar, o app reduz telefones, e-mails, documentos numéricos, nomes e endereços conhecidos e links privados do histórico. Isso é minimização, não garantia de anonimização de texto livre. Links gerados pelas ferramentas Anthropic são substituídos por marcadores durante a interação com o provedor e recolocados no resultado localmente.

O WhatsApp, ViaCEP, a equipe de entrega e o serviço que disponibiliza o link também precisam ser incluídos no inventário de tratamento e na análise dos fornecedores. Logs novos omitem corpos de mensagens e informações de provedores, reduzem identificadores e têm rotação no Desktop; logs e cópias de versões anteriores exigem revisão separada.

## Incidentes e manutenção

Em caso de suspeita de acesso indevido, pause o atendimento e a exposição pública, preserve evidências com acesso restrito, identifique dados e titulares afetados, revogue sessões e credenciais comprometidas e restaure o serviço somente após correção. Avalie as comunicações aos titulares e à ANPD conforme a regulamentação vigente. Não envie bancos, sessões WhatsApp ou backups sem proteção para suporte técnico.

Mantenha o inventário de dados, responsáveis por acesso, rotina de backups e registro de solicitações. Revise dependências, distribuição e fornecedores em cada atualização. As verificações automatizadas desta versão cobrem controles e regressões; não substituem análise contínua de segurança ou governança da loja.

Para verificar avisos das versões Python fixadas, execute `python packaging/auditar_dependencias.py` em um ambiente com acesso ao PyPI. O relatório fica em `artifacts/auditoria-python.json`; consultas indisponíveis não são tratadas como resultado seguro. Para o componente WhatsApp, use `npm audit --omit=dev` na pasta `whatsapp-native`. Esses serviços cobrem vulnerabilidades conhecidas por suas bases na data da consulta.

Referências: [LGPD, texto compilado](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm), [ANPD — direitos dos titulares](https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados/direito-dos-titulares), [ANPD — materiais educativos e publicações](https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes), [PyCA — criptografia autenticada](https://cryptography.io/en/stable/hazmat/primitives/aead/).
