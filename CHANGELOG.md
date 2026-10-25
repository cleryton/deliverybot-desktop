# Histórico de versões

## 2.44.6 — 2026-10-25

Amplia as regressões de recuperação do link para WhatsApp por QR Code e Meta e atualiza setuptools para 84.1.0, corrigindo o alerta GHSA-xmj3-9gf7-h52w sem desativar a auditoria de segurança.

## 2.44.5 — 2026-10-24

Corrige o envio do link de pedidos após reconexão do HTTPS: a fila aguarda o endereço seguro e substitui avisos preparados anteriormente, inclusive na opção 2. Reconhece solicitações diretas de link sem depender da IA; inclui regressões simuladas da Meta.

## 2.44.4 — 2026-10-23

Protege a publicação dos backups com validação da cópia de destino antes da retenção; corrige o diagnóstico da Meta para não confundir credenciais salvas com conexão comprovada. Inclui seis regressões e roteiro de operação comercial.

## 2.44.3 — 2026-10-22

Diferencia comprovante indisponível de link para nova compra: orienta conferir o pedido existente e não refazê-lo para recuperar o recibo. Mantém a recusa de acesso e adapta a orientação ao laboratório fictício. Amplia testes de recuperação e não exposição de dados.

## 2.44.2 — 2026-10-22

Preserva a regra exata ativo=1 na leitura de produtos em lote, recusando marcadores inválidos de bancos antigos ou alterados. Adiciona regressão e valida as suítes de carrinho, comprovante, CEP e pedidos.

## 2.44.1 — 2026-10-22

Atualiza duas regressões legadas para conferir o redirecionamento da confirmação e a leitura do comprovante, preservando validação de estoque e recusa de segunda compra. Testes direcionados aprovados.

## 2.44.0 — 2026-10-22

Após confirmar, redireciona com HTTP 303 para um comprovante recarregável somente no navegador que confirmou o pedido, sem repetir gravação, baixa de estoque ou mensagens. Acesso limitado a oito horas e cinco autorizações por sessão, sem dados pessoais no cookie. Mantém link original de uso único e inclui testes de isolamento, expiração e repetição; documenta as melhorias de desempenho e CEP.

## 2.43.2 — 2026-10-22

Valida o formato e os campos das respostas ViaCEP, impedindo falhas internas com JSON inesperado ou endereço incompleto. Reutiliza somente CEPs válidos por cinco minutos em cache limitado a 256 entradas, sem armazenar nome, número ou complemento. Falhas não ficam em cache, redirecionamentos externos são recusados e a área de entrega é conferida em cada uso.

## 2.43.1 — 2026-10-22

Valida produtos do carrinho em lotes de até 400 parâmetros, preservando ordem, itens repetidos, precisão, estoque e custos internos. A cotação usa uma transação de leitura para não misturar preços durante edições concorrentes. Inclui regressões de desempenho por quantidade de consultas e de consistência concorrente.

## 2.43.0 — 2026-10-21

Melhora a recuperação de falhas no laboratório QA, preservando códigos HTTP, CSRF, limites e ocultação de detalhes internos. Adiciona impressão ou salvamento local do comprovante pelo navegador, com identificação da loja, aviso sem valor fiscal e sem comprovante de pagamento; não reenvia a compra nem utiliza serviços externos. Inclui testes de recuperação, isolamento e impressão.

## 2.42.2 — 2026-10-21

Corrige as opções de pagamento no formulário hospedado para QA, reutilizando o contexto público da loja. Acrescenta regressão para impedir que o seletor seja publicado vazio.

## 2.42.1 — 2026-10-21

Atualiza Pillow para 13.0.0 e certifi para 2026.10.19, corrigindo os alertas encontrados pelo Actions antes da hospedagem QA. Valida catálogo, fotos, controles OWASP e distribuição com as dependências corrigidas.

## 2.42.0 — 2026-10-21

Adiciona publicação web isolada para QA no Render Free, com HTTPS, catálogo fictício com fotos e fluxo de pedido sem WhatsApp real. Restringe a hospedagem às páginas do cliente, usa banco descartável separado e inclui testes de isolamento e instruções de publicação.

## 2.41.0 — 2026-10-17

Atualização automática do webhook da Meta após validar o HTTPS do túnel integrado, com tarefa em segundo plano, novas tentativas com espera crescente e proteção contra resultados de conexões antigas. Preserva o ajuste manual e a conexão WAHA. Inclui testes de regressão simulados; o catálogo fictício solicitado foi cadastrado somente na instalação local, sem versionar dados de uso.

## 2.40.3 — 2026-10-16

Reduz consultas e conexões da listagem de pedidos com leitura em lote e snapshot consistente. Calcula o resumo no banco sem carregar catálogo ou itens; cria índices para itens, posição da fila e ordem das mensagens por contato. Separa a atualização do Obsidian Graph da preparação de cada resposta, mantendo a releitura e a validação das notas. Carrega o SDK Anthropic somente quando utilizado. Acrescenta testes de regressão e benchmark isolado com dados fictícios e medições reproduzíveis.

## 2.40.2 — 2026-10-15

Profissionaliza o relatório acadêmico com síntese, rastreabilidade dos commits, justificativas das implementações, resultados técnicos identificados por versão, limitações e roteiro de demonstração. Acrescenta a evidência preservada da validação da v2.40.1, sem atribuir resultados de testes à qualidade da IA.

## 2.40.1 — 2026-10-15

Esclarece a unidade de uma tentativa no protocolo DB-TCC-1, a preparação dos casos C08/C12 e o registro de snapshots por caso. Delimita oficina como extensão dos cenários principais e atualiza os links da entrega acadêmica.

## 2.40.0 — 2026-10-15

Fortalece a base acadêmica com plano de pesquisa, trabalhos relacionados, fronteiras de segurança, requisitos atualizados e roteiro de entrega. Adiciona laboratório DB-TCC-1 para preparar 72 tentativas A/B e analisar medidas declaradas, preservando falhas, bloqueios, denominadores e limites da comparação. Inclui testes do instrumento sem produzir resultados empíricos.

## 2.39.0 — 2026-10-15

Adiciona gestão remota isolada com convites de uso único, conta vinculada, permissões de consulta ou avanço de pedidos, prazo e revogação local. Inclui proteção de sessão, CSRF, limites de tentativas e revalidação transacional, interface responsiva e testes com dados fictícios.

## 2.38.0 — 2026-10-15

Assistente individual da Meta com credenciais próprias por instalação, consulta dos números, validação de aplicativo e validade do token, chave de webhook automática e configuração do HTTPS/webhook com confirmação. Interface em etapas, campos protegidos durante a gravação, tratamento de respostas atrasadas e recuperação de configuração parcial. Oculta tokens de diagnóstico nos logs e impede escritas simultâneas e troca de conta com fila pendente. Nenhuma credencial do autor é incluída na distribuição. Testes de isolamento, autenticação, CSRF, concorrência e formulários.

## 2.37.0 — 2026-10-13

Prepara a migração local para um número próprio da Meta com validação de acesso e vínculo à conta, confirmação e bloqueio de troca com fila pendente. Adiciona acompanhamento idempotente por mensagem, tarifas com histórico, custos pendentes explícitos e orçamento mensal separado entre teste e produção, restrito ao administrador e sem conteúdo ou telefones de clientes. Mantém a proteção de credenciais e inclui roteiro, interface e testes simulados.

## 2.36.3 — 2026-10-13

Aplica a marca escolhida de caixa e balão de conversa no painel, login e terminal do funcionário; mantém contraste nos temas claro e escuro e gera o ícone Windows em sete resoluções a partir da mesma fonte vetorial. Inclui a proposta aprovada, guia da identidade e regressões de transparência, recursos e sincronização do ícone.

## 2.36.2 — 2026-10-13

Atualiza o envio Meta para Graph API v25.0, conforme o exemplo do painel de testes, e centraliza a versão para manter a inicialização e as preferências consistentes. Documenta credenciais, número de teste e webhook HTTPS; adiciona regressões de inicialização, troca de ID e transporte com autenticação, prazo e redirecionamentos controlados.

## 2.36.1 — 2026-10-12

Corrige a continuidade do atendimento humano: mensagens durante a pausa ficam imediatamente no histórico privado fora do contexto da IA, entradas automáticas pendentes são transferidas sem repetição na retomada e respostas manuais não ficam bloqueadas por falhas automáticas anteriores. Preserva envios incertos e a ordem dos envios manuais, exige conferência antes de retomar o bot, atualiza a conversa aberta e adiciona guia ao visual e Graph Obsidian. Inclui regressões de fila, privacidade, transferência transacional e interface.

## 2.36.0 — 2026-10-12

Adiciona proteção por conversa antes da IA e do envio, com detecção de sinais conhecidos de manipulação e extração de dados, limites de mensagens e repetição, verificação de credenciais e estrutura interna na saída e invalidação de respostas em andamento após pausa ou liberação. Mantém mensagens pausadas no histórico privado fora do contexto da IA, exige revisão administrativa com retomada separada, preserva aviso local de privacidade e integra os dados de proteção às operações do titular. Inclui guia no visual e Graph Obsidian e testes de abuso, falsos positivos, fila, concorrência, permissões e interface.

## 2.35.0 — 2026-10-12

Restringe o terminal por vínculo individual de conta Caixa e computador, impede login administrativo e exige autorização explícita para sangria e suprimento. Revalida acesso dentro da transação, limita requisições e pareamento, expira sessões no servidor sem renovação por consultas automáticas e preserva pendências incertas. Inclui auditoria de recusas, revisão segura de acessos anteriores, recuperação restrita de conta bloqueada, guia no visual e Graph Obsidian sem poder de autorização e testes de abuso e da interface.

## 2.34.1 — 2026-10-12

Corrige o encerramento TLS do gateway de funcionários para concluir respostas curtas antes de fechar o socket e limita a espera pelo cliente. O terminal lê respostas por iter_content, traduz falhas de protocolo para orientação de reconexão e preserva operações pendentes sem repetir gravações; acrescenta regressões de resposta truncada, saída local e conexões HTTPS repetidas no Windows.

## 2.34.0 — 2026-10-12

Adiciona aplicativo Windows separado para funcionários da rede da loja, com pedidos manuais no banco central, perfil Caixa, pareamento de dispositivo e HTTPS com certificado específico. Implementa caixa individual em centavos com abertura, recebimentos separados, troco, sangria, suprimento, conferência, fechamento e estorno administrativo; preserva operações pendentes e retentativas idempotentes. Inclui gestão pelo responsável, guias operacionais no Obsidian, segundo instalador, testes financeiros e de acesso e validação dos dois executáveis no Actions.

## 2.33.1 — 2026-10-12

Organiza o DeliveryBot como artefato de TCC com base de monografia, arquitetura, requisitos rastreáveis, protocolo de avaliação, referências verificadas e roteiro de banca. Adiciona consolidação de evidências JUnit com hashes, contagens e metadados do checkout, sem copiar dados dos casos e distinguindo resultados existentes de avaliações ainda pendentes; inclui testes de segurança e integridade dos relatórios.

## 2.33.0 — 2026-10-11

Adiciona validadores HTTP e testes adversariais orientados pelo OWASP: JSON UTF-8 com limites, campos duplicados e números não finitos recusados, parâmetros de formulário inequívocos, URLs de serviços validadas e cabeçalhos defensivos inclusive nas respostas do gateway público. Inclui política documentada, auditorias de dependências e ZAP Baseline passivo em dados fictícios como parte da validação obrigatória do Actions.

## 2.32.0 — 2026-10-11

Melhora a orientação da configuração com próximo passo baseado nas verificações atuais, catálogo com produtos em primeiro plano e ferramentas expansíveis, busca de pedidos e catálogo sem exigir acentos, filtros vazios com recuperação e atualização dos pedidos que preserva o foco. Adiciona retorno de operações em andamento, proteção de rascunhos de produtos, mensagens de sessão e falha de conexão sem repetição automática de gravações e menu acessível em telas menores. Inclui testes JavaScript e verificação da interface e dos recursos na distribuição.

## 2.31.0 — 2026-10-11

Adiciona diagnóstico do Ollama e do cofre, recuperação automática opcional e verificação manual pelo administrador. Detecta serviço desligado, modelo ausente, falhas consecutivas de inferência e notas indisponíveis; prepara o Ollama local instalado com tentativas limitadas e preserva o provedor e as edições. O Obsidian recebe um estado operacional derivado e um guia, enquanto a IA recebe somente um sinal técnico confiável. Inclui testes de intervalos, cancelamento, permissões, privacidade, inferência e empacotamento.

## 2.30.0 — 2026-10-11

Adiciona pingue-pongue opcional à confirmação do pedido, com acesso independente em /jogar, controles por toque, mouse e teclado, duas dificuldades, placar até cinco pontos, pausa e reinício. A partida pausa ao trocar de aba ou fechar o jogo e funciona sem dados do pedido, persistência ou serviços externos. Amplia testes de física, fluxo público e empacotamento e inclui os testes JavaScript no Actions.

## 2.29.0 — 2026-10-11

Cria padrões Obsidian individuais por segmento de comércio e etapa de atendimento. O Ollama consulta somente o perfil ativo e a etapa relacionada à mensagem, preservando personalizações e isolando categorias anteriores. O painel exibe o perfil e as notas, o Graph liga os padrões ativos e os backups preservam a estrutura. Inclui testes de seleção, revogação, validade, privacidade, preservação e integração no executável.

## 2.28.0 — 2026-10-11

Inicia a preparação de HTTPS e WhatsApp ao salvar uma nova conexão no desktop, valida a página antes do serviço e do QR Code, regenera túneis temporários com falha DNS dentro do prazo de login e organiza automaticamente o mapa do Obsidian Graph sem alterar as notas da equipe. Inclui testes de ordem, configuração, acesso ao QR, recuperação DNS e sincronização do mapa.

## 2.27.0 — 2026-10-11

Permite montar e confirmar pedidos diretamente pelo WhatsApp, com resumo oficial, validação transacional de preços e estoque, confirmação idempotente e integração com o painel e a fila. Inclui guia no cofre Obsidian, leitor protegido de notas no aplicativo e privacidade dos rascunhos; amplia testes de conversa, concorrência e retentativas.

## 2.26.1 — 2026-10-11

Corrige links de pedidos inventados pela IA e respostas antigas da fila, rejeita domínios WhatsApp como hospedagem, melhora o diagnóstico DNS e organiza distribuições com guias, metadados, integridade e limpeza conservadora; amplia os testes.

## 2.26.0 — 2026-10-11

Adiciona guias locais de configuração com tutorial por etapas, exemplos por tipo de comércio, atalhos para as telas e verificações atuais sem iniciar serviços; inclui testes unitários de orientação, disponibilidade e acesso.

## 2.25.0 — 2026-10-11

Personaliza o comércio na instalação e no painel com descrição, segmento e operação de revenda, produção, serviços ou mista; estoque opcional por item, preservação de dados existentes e novos testes unitários e do instalador.

## 2.24.3 — 2026-10-11

Adiciona GitHub Actions com testes Python e WhatsApp, conferência de versões, compilação Windows e teste do executável; documenta a validação obrigatória da main e atualizações dos componentes do Actions.

## 2.24.2 — 2026-10-11

Melhora o guia do Obsidian com exemplos de tom de atendimento, aprovação de conhecimento e fluxo de importação de estoque e catálogo PDF.

## 2.24.1 — 2026-10-11

Evita tratar a coluna genérica de preço em notas de compra como preço de venda; mantém a revisão obrigatória do valor de venda antes de cadastrar produtos.

## 2.24.0 — 2026-10-11

Leitura local de PDF, XLSX, CSV e notas Obsidian com Ollama, revisão editável, entrada e contagem transacionais; registro no cofre e catálogo PDF com fotos para clientes pelo HTTPS.

## 2.23.0 — 2026-10-11

Fotos opcionais no cadastro de produtos, com prévia, substituição e remoção; catálogo visual pelo HTTPS, imagens otimizadas sem metadados e preservadas nos backups e atualizações.

## 2.22.0 — 2026-10-11

Consulta do cérebro Obsidian por assunto, tags compatíveis com as propriedades e prioridade; validade opcional de conhecimento aprovado, leitura limitada e protegida, preservação das notas existentes e orçamento de contexto incluindo títulos.

## 2.21.0 — 2026-10-10

Atendimento mais natural com respostas locais rápidas e contexto recente; validação de todos os links antes do envio, verificação HTTPS da origem, espera automática na reconexão e renovação do callback WAHA remoto; catálogo público redesenhado com busca, carrinho acessível e recibo com valores precisos.

## 2.20.0 — 2026-10-10

Cofre Obsidian estruturado com notas aprovadas de estilo e conhecimento, contexto local protegido contra instruções e dados operacionais inconsistentes, além de inclusão cifrada do vault nos novos backups e restauração com preservação de notas adicionais.

## 2.19.1 — 2026-10-10

Personalidade do atendimento mais calorosa e reconhecível, com respostas variadas e adaptação ao contexto, sem perder clareza, precisão e respeito.

## 2.19.0 — 2026-10-10

Cofre Markdown compatível com Obsidian para personalizar o estilo de atendimento; Ollama consulta a nota atual sem aprender automaticamente com conversas de clientes.

## 2.18.2 — 2026-10-10

Ignora ruído sem conteúdo útil e mensagens comuns que envelhecem na fila; reduz o limite de geração do Ollama para agilizar respostas.

## 2.18.1 — 2026-10-10

Respostas do Ollama com tom mais natural, melhor aproveitamento do contexto da conversa e menos frases repetidas, preservando as regras da loja.

## 2.18.0 — 2026-10-10

Modelo de importação de produtos em CSV, atalho para filtrar itens com estoque baixo e relatório com ticket médio, margem parcial e destaque dos mais vendidos.

## 2.17.0 — 2026-10-10

Diagnóstico operacional exportável com campos reduzidos para suporte e alerta de backups automáticos desativados, atrasados ou com falha.

## 2.16.0 — 2026-10-10

Assistente de domínio fixo com passos, validação visual do domínio/token/túnel e cópia rápida do destino HTTP exigido pela Cloudflare.

## 2.15.0 — 2026-10-10

Checklist inicial com estado real do WhatsApp, HTTPS e fila de atendimento, com atalhos para corrigir componentes indisponíveis.

## 2.14.0 — 2026-10-10

Inicialização automática da conexão WhatsApp integrada e da página HTTPS quando o provedor já foi escolhido, abertura direta da tela de conexão para facilitar a leitura do QR Code e inicialização do Ollama local quando selecionado.

## 2.13.0 — 2026-10-10

Início automático do túnel HTTPS antes de preparar o login do WhatsApp, aguardando a disponibilidade do endereço público e exibindo falhas com orientação para nova tentativa.

## 2.12.0 — 2026-10-10

Modo claro, escuro e automático conforme o Windows, com preferência persistida na instalação, tela de login e contraste adaptado no painel. Verificações de acesso, CSRF e funcionamento na janela nativa.

## 2.11.1 — 2026-10-10

- Remoção dos iniciadores, configurações e manual do fluxo antigo com Docker/n8n/ngrok.
- Limpeza de artefatos temporários, instalações de teste, caches e distribuições antigas, preservando dados e dependências de manutenção.
- Documentação das pastas necessárias e compilação limpa com preparação do túnel, licenças e hashes da distribuição.

## 2.11.0 — 2026-10-10

- Página de pedidos com túnel Cloudflare integrado, início pelo painel, opção de início automático e reconexão em segundo plano.
- Endereço temporário sem conta e opção de domínio fixo com token protegido pela conta Windows.
- Servidor público separado, com rotas permitidas, bloqueio do painel e preservação de CSRF em compras HTTPS.
- Bot usa o endereço da sessão, informa indisponibilidade e atualiza links automáticos ainda na fila.
- Conector oficial incluído na distribuição com versão e SHA-256 fixados; testes com dados fictícios e aviso de privacidade atualizado.

## 2.10.1 — 2026-10-10

Padronização do instalador como Instalar-DeliveryBot.exe e compatibilidade com nomes normalizados pelo GitHub nas versões anteriores, mantendo validação de origem, tamanho, hash e backup.

## 2.10.0 — 2026-10-10

Consulta opcional de releases, download com origem e SHA-256 verificados, backup antes de atualizar e instalação condicionada à assinatura confiável. Preparação de distribuição e assinatura digital, com correções da integração do atendimento humano.

## 2.9.0 — 2026-10-10

Contas individuais de administradores e atendentes, permissões verificadas no servidor e na ponte nativa, senhas scrypt, revogação de sessões e auditoria sem conteúdo de mensagens.

## 2.8.0 — 2026-10-10

Estoque fracionado com precisão de três casas, famílias e variações, importação CSV com prévia e transação integral, custos históricos e relatórios por período. Validados 33 testes de catálogo, pedidos e aprimoramentos, incluindo cancelamento e ausência de importação parcial.

## 2.7.0 — 2026-10-10

Atendimento humano por conversa: comando ATENDENTE, leitura do histórico, pausa e retomada do bot, respostas manuais confirmadas pela fila persistente e proteção contra retomada com envios pendentes. Validado com serviços simulados.

## 2.6.0 — 2026-10-10

Backups automáticos portáteis criptografados, senha protegida no Windows, verificação de recuperação, destino e rotação configuráveis. Limpeza diária opcional da retenção, alertas de atraso e recuperação de horários perdidos. Testes de rotação e ausência da senha na cópia aprovados.

## 2.5.0 — 2026-10-10

Atendimento em segundo plano com ícone na área do relógio, opções de reabrir e encerrar, preservando os serviços ao fechar a janela. Validado o ciclo real da bandeja Windows, sem contas ou dados reais.

## 2.4.0 — 2026-10-10

Configuração inicial guiada com checklist da loja, privacidade, catálogo, WhatsApp, IA e confirmação de abertura do endereço público no celular. Teste temporário vinculado ao endereço configurado, sem expor dados ou segredos.

## 2.3.0 — 2026-10-10

- Área Privacidade e LGPD com identificação do responsável, canal de contato, aviso público, exportação, correção e remoção da identificação do cadastro.
- Retenção configurável das conversas, limpeza manual do histórico concluído e auditoria sem conteúdo pessoal.
- Backups portáveis com AES-256-GCM, senha derivada por scrypt e detecção de alteração; credenciais dos serviços excluídas da cópia portável. Cópias de recuperação automáticas protegidas pela conta Windows.
- Segredos das configurações protegidos com DPAPI no Windows; permissões da pasta de dados restritas à conta atual e SYSTEM.
- Servidor Desktop restrito ao computador; acesso administrativo remoto desligado por padrão; limitação de tentativas de senha e proteção CSRF também na cozinha e no pedido.
- Cabeçalhos contra exposição em cache, referências externas e execução de scripts não autorizados. Fontes externas removidas da cozinha.
- Dados pessoais reduzidos em logs e no histórico enviado à IA; envio a IA externa desligado por padrão e HTTPS exigido para serviços externos com dados ou credenciais.
- Aviso de privacidade no formulário de compra e no primeiro atendimento; comando PRIVACIDADE disponível sem depender de IA.
- Atualização das versões de Flask, Requests, python-dotenv, pytest, setuptools e wheel para corrigir avisos públicos de vulnerabilidades; utilitário de consulta ao PyPI disponível em `packaging/auditar_dependencias.py`.

Validação: 67 testes Python e 10 testes Node aprovados; janela, cadastro de privacidade, backup criptografado e API nativa verificados no executável. Consultas ao PyPI (49 pacotes fixados) e npm audit sem avisos conhecidos. Conexões simuladas, sem contas ou mensagens reais.

As medidas técnicas apoiam a proteção de dados. A loja continua responsável pela política de retenção, bases legais, identidade dos solicitantes, provedores e tratamento de incidentes; veja `PRIVACIDADE E SEGURANÇA.md`.

## 2.2.0 — 2026-10-10

Primeira versão registrada neste repositório, reunindo o aplicativo Windows já desenvolvido.

- Aplicativo e instalador Windows com painel de produtos, estoque, pedidos e configurações.
- Cadastro de produtos de qualquer categoria e controle de movimentações de estoque.
- WhatsApp integrado com QR Code e sessão persistente, sem instalação de Docker ou Node.js.
- Fila persistente de mensagens, proteção contra eventos duplicados e revisão de envios incertos.
- Botões para iniciar o Ollama, baixar modelos e ativar a IA local.
- Backup e restauração do banco, preservação dos dados nas atualizações e serviços em segundo plano.
- Política de commits e versões por pedido registrada em `AGENTS.md`.

Validação do aplicativo antes deste registro: 46 testes Python e 10 testes Node aprovados; abertura do executável e formulários verificados; QR Code real gerado sem parear uma conta nem enviar mensagens.
