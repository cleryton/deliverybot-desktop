# Relatório técnico do DeliveryBot

Este relatório explica o que foi desenvolvido no DeliveryBot, como suas partes trabalham juntas e quais cuidados sustentam sua utilização. O projeto reúne atendimento pelo WhatsApp, catálogo de produtos e serviços, pedidos, estoque, caixa e gestão em um aplicativo Windows. A proposta é reduzir tarefas repetitivas da loja sem entregar à inteligência artificial o controle dos preços, das permissões ou das operações financeiras.

A versão de referência deste documento é a 2.48.0. A evolução mais recente fecha a saída do atendimento Ollama em uma proposta de ação, referências e tom, validada e renderizada pelo aplicativo. As melhorias anteriores de navegação, concorrência de pedidos, publicação HTTPS e proteção de recursos também compõem a solução. Os resultados precisam ser lidos conforme seu contexto: testes automatizados usam dados fictícios; o laboratório público demonstra a página de pedidos; uma operação real depende da configuração da loja e dos serviços envolvidos.

## 1 Objetivo e organização do projeto

O problema tratado é a fragmentação do atendimento e do registro de vendas. Quando catálogo, conversa, pedidos e caixa ficam separados, a equipe pode informar um preço desatualizado, perder a confirmação de uma compra ou confundir uma intenção de pagamento com dinheiro efetivamente recebido. O DeliveryBot aproxima esses processos e mantém os registros comerciais no mesmo sistema.

O aplicativo principal pertence ao responsável pelo comércio. Nele são configurados o negócio, os produtos, os canais de atendimento, as permissões e as rotinas de proteção. Um segundo aplicativo atende funcionários em outros computadores da loja. O cliente interage pelo WhatsApp ou por uma página de pedidos adaptada ao celular. As funções não exigem o mesmo nível de acesso: escolher produtos não deve liberar a administração, e registrar uma venda não deve permitir trocar credenciais.

A distribuição inclui os componentes necessários para abrir o sistema no Windows, sem exigir Docker, Node.js ou Python do usuário final. Ferramentas de desenvolvimento continuam necessárias para quem modifica e compila o código. O Ollama é um componente opcional para inferência local e precisa estar configurado quando essa modalidade de IA for utilizada.

O código está no repositório público `https://github.com/cleryton/deliverybot-desktop`. Os arquivos `README.md`, `CHANGELOG.md` e `VERSION` apresentam, respectivamente, a orientação inicial, o histórico das alterações e a versão do projeto. Dados de uso e credenciais ficam separados da distribuição e não pertencem ao repositório.

## 2 Arquitetura e responsabilidade das partes

O DeliveryBot combina uma janela desktop com uma aplicação web local. `desktop.py` organiza a abertura do aplicativo, a janela WebView e os componentes auxiliares. O backend usa Flask para receber requisições, Python para as regras comerciais e SQLite para persistência. HTML, CSS e JavaScript apresentam o painel e a página do cliente. Essa organização permite compartilhar regras entre os diferentes canais de entrada.

| Parte | Responsabilidade principal |
| --- | --- |
| Aplicativo principal | Administrar a loja e coordenar serviços locais |
| Backend e banco | Validar e registrar operações comerciais |
| Página do cliente | Apresentar catálogo, seleção e confirmação |
| Conector WhatsApp | Receber eventos e transportar mensagens |
| IA e cofre editorial | Interpretar e redigir dentro do atendimento permitido |
| Aplicativo do funcionário | Registrar pedidos e operar o caixa autorizado |

`src/app.py` concentra rotas públicas, webhooks e recursos da compra. `src/gestao.py` fornece as operações do painel. Essas rotas encaminham a execução para módulos como `pedidos.py`, `estoque.py`, `fila.py` e `caixa.py`. Separar responsabilidades facilita testar uma regra sem iniciar uma conta real de WhatsApp ou uma janela desktop.

O banco é a referência para produtos, preços, saldos, pedidos e caixa. As notas do Obsidian podem explicar como atender, mas não substituem esses registros. Da mesma forma, uma resposta do modelo não é prova de que uma compra foi gravada. O aplicativo deve apresentar confirmação somente depois que o fluxo oficial concluir a operação.

O projeto possui diferentes limites de confiança. Formulários, mensagens de clientes, documentos importados e textos de modelos são entradas a validar. A página pública tem menos acesso que a gestão. O terminal do funcionário tem sua própria autenticação. Serviços externos recebem somente os dados necessários ao fluxo configurado, sujeitos às proteções e limitações de cada integração.

## 3 Perfil do comércio e catálogo individual

O cadastro inicial deixou de representar somente uma lanchonete. Em `src/perfil_comercio.py`, `obter()` apresenta o perfil atual e `salvar()` valida nome, segmento, descrição e modelo de operação. A loja pode selecionar revenda, produção sob pedido, serviços ou operação mista. Esse perfil orienta os títulos da interface, o padrão de controle de estoque e o contexto do atendimento.

Na revenda, é comum limitar a quantidade disponível. Na produção sob pedido, um lanche pode ser preparado depois da confirmação, sem representar uma unidade pronta em estoque. Em serviços, o item pode identificar uma atividade contratável. A operação mista combina essas possibilidades. O controle permanece individual por item: uma lanchonete pode produzir sanduíches sob encomenda e contar bebidas industrializadas.

O catálogo permite nome, categoria, preço, descrição, unidade, código, família e variação. Tamanho ou cor podem ser registrados como itens próprios, preservando preço e saldo específicos. Quantidades fracionadas atendem venda por peso, volume ou comprimento, conforme a unidade definida. O sistema não converte automaticamente quilogramas em gramas nem interpreta equivalências comerciais entre embalagens.

As fotos são normalizadas antes de integrar o catálogo. O cliente visualiza imagens, categorias, preços e disponibilidade. A importação por CSV, planilha, PDF ou nota de estoque inclui uma etapa de revisão antes do lançamento. A leitura assistida por IA pode interpretar o documento, mas não deve registrar silenciosamente valores que a equipe ainda não conferiu.

Alterar o perfil não autoriza apagar produtos ou pedidos anteriores. Migrações e atualizações preservam os dados existentes. Produtos inativos ou indisponíveis ficam fora das ofertas públicas conforme suas regras. `estoque.salvar_produto()` cuida do cadastro; `ajustar_estoque()` registra movimentações com motivo, em vez de substituir o saldo sem histórico.

## 4 Percurso de uma mensagem e de uma compra

O fluxo começa no transporte. A integração Meta valida a assinatura do webhook; o conector local entrega eventos com a autenticação prevista para essa modalidade. O módulo `whatsapp.py` normaliza o evento recebido. `processamento.enfileirar()` registra a tarefa e a identificação de duplicidade, evitando tratar a repetição do mesmo evento como uma nova mensagem comercial.

Antes da resposta, o processamento considera idade, ruído, pausa humana e proteção da conversa. Mensagens antigas ou sem utilidade podem ser descartadas conforme a política operacional. Saudações e dúvidas conhecidas usam respostas locais quando existe informação suficiente. Isso reduz dependência de inferência para perguntas como horário, endereço e formas de pagamento.

Para comprar pelo navegador, o aplicativo gera um link pessoal. O cliente escolhe itens, informa os dados necessários e revisa os valores. A seleção exibida no navegador não é aceita como preço definitivo: o servidor confere produtos e quantidades ao confirmar. O pedido, seus itens, a movimentação de estoque controlado e a entrada na fila são registrados de forma transacional.

Uma transação reúne alterações que precisam acontecer juntas. Se ocorrer uma falha antes da conclusão, não deve existir uma venda parcialmente registrada com saldo incoerente. Em `pedidos.criar_pedido()`, a resolução dos itens e as verificações comerciais precedem a gravação. O link de compra é de uso único, e a confirmação conduz ao comprovante para que atualizar a página não repita a compra.

O cliente também pode optar por `PEDIDO PELO WHATSAPP`. `conversa_pedido.responder()` mantém um rascunho, solicita produtos e quantidades, dados de recebimento e pagamento e apresenta um resumo. A confirmação explícita usa as mesmas regras comerciais do aplicativo. Assim, a conversa não depende de o cliente abrir a página, e o modelo não precisa inventar uma confirmação.

Depois da gravação, a fila acompanha recebido, separação, pronto e conclusão. Avanço e cancelamento no painel enviam o estado que estava na tela. O servidor confere esse estado dentro da transação. Se outra pessoa já mudou o pedido, a ação é recusada antes de pular etapas, devolver estoque ou enviar uma notificação indevida.

## 5 Inteligência artificial limitada ao negócio

O papel da IA é auxiliar o atendimento, interpretar linguagem natural e redigir respostas com o tom da loja. O projeto admite Ollama local e um provedor externo configurável. Nenhum deles recebe autorização para alterar permissões ou decidir sozinho os valores de uma venda. Perguntar pelo catálogo e confirmar uma compra são intenções distintas.

A triagem em `ia.assunto_negocio()` antecede o uso do modelo. A evolução da versão 2.47.2 torna essa decisão mais específica ao perfil e ao catálogo. Uma lanchonete pode responder sobre lanches, ingredientes cadastrados, retirada, entrega e pedidos. Uma oficina pode orientar o atendimento sobre os serviços oferecidos. Mencionar “produto”, “serviço” ou “preço” não deve transformar qualquer assunto em uma pergunta permitida.

O cadastro oficial pode ampliar o vocabulário necessário ao comércio. Isso permite que uma loja mista atenda categorias diferentes que realmente oferece. As notas editoriais e o texto do cliente não podem ampliar a autorização. Um pedido para mudar as regras, responder sobre outro negócio ou ignorar o perfil precisa continuar sendo tratado como entrada não confiável.

O módulo `escopo_loja.py` reconhece referências ao segmento e ao catálogo ativo. Um perfil específico prevalece sobre itens antigos de outro ramo; a operação mista combina as atividades cadastradas. Itens incompatíveis ficam fora da referência enviada ao modelo, sem serem apagados do banco. Expressões operacionais fechadas, como perguntar o horário ou se a loja aceita Pix, dispensam percorrer o catálogo inteiro. Perguntas que misturam um tema comercial com outro assunto não recebem essa liberação rápida.

Assuntos universais da operação permanecem possíveis: horário, contato, pagamento, entrega, andamento do pedido, privacidade e solicitação de atendente. Quando faltar relação clara com o negócio, o bot deve pedir esclarecimento ou orientar o cliente sobre o que pode atender. Essa recusa operacional não deve humilhar a pessoa nem afirmar que ela está atacando o sistema.

Continuações curtas, como “pode explicar” ou “esse tamanho”, dependem do contexto recente. O histórico precisa ser considerado com cuidado para que uma conversa anterior não autorize assuntos que deixaram de pertencer ao perfil atual. O prompt também deve refletir mudanças do comércio, sem conservar indefinidamente dados de uma configuração anterior.

A revisão também ocorre depois da geração. No Ollama, `circuito_comercial.preparar()` cria um registro limitado de fontes públicas e o modelo devolve somente JSON com `acao`, `fontes` e `tom`. O aplicativo valida campos, tipos e referências, recusa texto livre e monta a resposta usando as fontes registradas. O campo `format` da API solicita o esquema, mas a validação local permanece obrigatória. Nenhum texto factual novo do modelo é publicado nesse caminho. Estilo e padrões editoriais ajudam a escolher entre tons previamente definidos; não permitem inserir fatos ou novas ações.

As ações possíveis são responder, esclarecer, orientar atendimento humano ou propor um link de pedido. Propor não executa: a intenção de compra, a proteção da conversa e a atualidade das fontes precisam ser conferidas antes da criação do acesso. O token pessoal nunca volta ao modelo. Não há segunda inferência para esse resultado. O provedor Anthropic mantém o caminho próprio de geração, com as verificações de assunto, privacidade e ferramentas existentes; o contrato de seleção de fontes descrito aqui pertence ao Ollama.

Se o perfil, catálogo ou uma nota selecionada mudar durante a inferência, a resposta preparada com a referência anterior não é publicada. O aplicativo não inicia uma segunda geração para essas recusas. Os testes utilizam modelos simulados para verificar esses caminhos; não equivalem a uma avaliação de qualidade de todas as respostas de um modelo real.

Essas camadas reduzem a abertura do atendimento geral, mas não constituem uma garantia de compreensão semântica perfeita. Palavras ambíguas, erros de escrita e mensagens com mais de um assunto exigem testes contínuos. A prioridade é conservar as validações determinísticas e oferecer uma saída para atendimento humano quando a relação com a atividade não estiver clara.

## 6 Obsidian como conhecimento editorial

O chamado cérebro do projeto é um cofre de arquivos Markdown compatível com Obsidian. Ele organiza estilo de atendimento, orientações aprovadas, exemplos e padrões por segmento e etapa da conversa. `src/cerebro.py` prepara a estrutura, oferece visualização das notas e seleciona contexto relacionado à pergunta. O Graph apresenta ligações entre essas notas.

Esse mecanismo não treina automaticamente a rede neural. O texto aprovado é consultado durante a preparação da resposta, de forma semelhante a uma base de referência. Alterar uma nota pode mudar o contexto enviado ao modelo, mas não atualiza os pesos internos do Ollama. Um futuro treinamento supervisionado exigiria outro processo de seleção, preparação e avaliação de dados.

A leitura segura das notas passa por `_ler()`, que verifica o caminho, recusa vínculos indevidos e limita conteúdo. `contexto_revisado()` produz um retrato imutável dos trechos selecionados e das assinaturas de conteúdo e metadados. `contexto_valido()` relê essas fontes antes da publicação, sem depender de uma atualização do Graph ou de uma varredura integral do cofre. A consulta não persiste a pergunta. `instrucoes_contexto()` preserva a interface de leitura editorial anterior, enquanto a inferência usa o retrato estrito. Preço, estoque e disponibilidade continuam vindo do cadastro oficial.

Notas de Conhecimento precisam declarar `categoria_atendimento`, como `ALIMENTACAO` ou `OFICINA`, para se tornarem fontes factuais do circuito. O campo deve corresponder ao perfil ativo; ausência, valor vazio, repetido ou desconhecido impede esse uso. Referências legadas continuam no cofre para revisão, sem migração destrutiva. Cada sentença passa por triagem de vínculo com o comércio; conteúdo ambíguo ou misturado com outro assunto fica fora da inferência. Notas com valores operacionais conflitantes, comandos ou URLs não viram fontes de resposta. Mudar o perfil altera a seleção sem apagar arquivos.

As notas podem definir, por exemplo, uma recepção cordial ou uma forma de encaminhar uma reclamação. Não podem conceder acesso administrativo, autorizar sangria, trocar um token Meta ou oferecer um produto inexistente. Conteúdo desatualizado ou contraditório precisa de revisão da equipe. O Graph facilita navegar na base; a existência de uma ligação visual não prova que uma resposta está correta.

O aplicativo também registra orientações sobre funcionamento e recuperação dos componentes. O responsável pode verificar Ollama e cofre e habilitar a recuperação automática permitida. Esse estado técnico informa disponibilidade, não qualidade semântica. O fato de o modelo estar iniciado não demonstra, por si só, que ele atende bem ao segmento.

## 7 WhatsApp e publicação HTTPS

Existem modalidades diferentes de conexão. O modo local integrado utiliza um componente de WhatsApp Web e autenticação por QR Code. A Meta utiliza a Cloud API oficial, com identificadores, token e segredo do aplicativo. WAHA permanece como integração externa opcional. Essas modalidades não devem ser apresentadas como se tivessem as mesmas condições operacionais ou o mesmo processo de autenticação.

O túnel Cloudflare publica a parte necessária ao cliente. `publicacao.PaginaPublica` permite apenas rotas e recursos conhecidos. A gestão, exportações internas e outros recursos administrativos não são liberados simplesmente porque o túnel foi iniciado. O servidor público também trata cabeçalhos encaminhados para não interpretar um acesso externo como acesso local confiável.

Antes de fornecer o link, o aplicativo precisa reconhecer um endereço HTTPS público válido. `links.gerar_link_pedido()` cria o acesso pessoal e `atualizar_resposta()` ajusta links às condições da publicação. Endereços locais, tokens inventados e domínios construídos pelo modelo não substituem o endereço real. Se o HTTPS permanecer indisponível no fluxo de recuperação, o catálogo em PDF oferece uma alternativa para continuar a escolha pela conversa.

O túnel temporário pode mudar de endereço. Para links mais estáveis no uso diário, a configuração admite domínio fixo. A operação instalada continua dependendo do computador ligado, do aplicativo disponível e da conexão com a internet. O túnel não transforma o notebook em hospedagem independente que funciona depois de desligá-lo.

Na Meta, `meta_configuracao.conectar()` verifica a conta informada e o número selecionado. Cada instalação deve usar suas próprias credenciais. A sincronização de webhook acompanha o HTTPS integrado quando as condições estão completas; não cria nem transforma tokens temporários em permanentes. `meta_custos.registrar_status()` e `relatorio()` acompanham eventos e estimativas configuradas, sem substituir a fatura do provedor ou presumir custo zero quando faltam dados.

## 8 Funcionários caixa e gestão remota

O DeliveryBot Funcionário foi separado para que a equipe registre vendas sem receber o acesso completo do responsável. O computador é pareado, vinculado a uma conta Caixa e autorizado pelo servidor da loja. O terminal utiliza HTTPS na rede privada e não deve ser publicado no túnel destinado aos clientes.

As permissões são conferidas no servidor, inclusive dentro das transações financeiras. Alterar a interface, editar uma nota do Obsidian ou instruir a IA não deve liberar uma ação bloqueada. Sangria e suprimento exigem autorização adicional. Revogação do computador, mudança de conta e expiração da sessão afetam o acesso conforme as regras do terminal.

O caixa distingue dinheiro físico de Pix e cartão. O valor esperado resulta da abertura, das vendas recebidas em dinheiro, dos suprimentos, das sangrias e das devoluções registradas em dinheiro. Selecionar uma forma de pagamento representa uma informação do atendimento; registrar recebimento representa uma declaração do operador. O aplicativo não confirma automaticamente uma transferência bancária ou uma cobrança de cartão.

Pedidos de balcão, estoque, fila e recebimento passam por uma operação transacional. Um identificador permite conferir uma operação após queda da conexão sem criar outra venda. O terminal preserva pendências protegidas e orienta verificar o resultado na loja. Ele não mantém uma segunda base independente para continuar confirmando vendas offline.

A gestão remota pela internet possui autorização própria em `src/acesso_remoto.py`. Ela oferece as operações previstas pelo aplicativo e permite revogação, sem equivaler a controlar a tela inteira do computador. Consultar ou avançar um pedido não implica acesso irrestrito ao Windows, ao banco ou às credenciais dos provedores.

## 9 Segurança e proteção dos dados

As proteções foram distribuídas por diferentes camadas. Autenticação identifica a sessão e a conta; autorização verifica o perfil e a operação; CSRF dificulta gravações originadas por páginas externas; validação de entrada recusa formatos ambíguos. O backend utiliza consultas parametrizadas e a interface escapa dados ao apresentá-los, reduzindo riscos de interpretar texto como SQL ou HTML executável.

O parsing JSON recusa campos duplicados, números não finitos e estruturas excessivas. Uploads têm limites e validações próprias. Cabeçalhos HTTP restringem enquadramento e interpretação de conteúdo e reduzem exposição de informações. Logs novos reduzem identificadores e detalhes sensíveis; isso não remove automaticamente cópias antigas ou registros mantidos por terceiros.

Os segredos das configurações usam proteção da conta Windows por DPAPI. Essa proteção é diferente de criptografar integralmente o banco SQLite em uso. Uma conta comprometida ou uma sessão desbloqueada exige medidas complementares no equipamento. Tokens, sessões WhatsApp, bancos reais, logs e executáveis gerados ficam fora do versionamento.

Backups portáteis utilizam criptografia autenticada e derivação de chave com senha. `backups.criar()` prepara a cópia protegida; `decifrar()` recusa senha incorreta ou arquivo alterado. Credenciais de provedores são excluídas da cópia portátil. A recuperação precisa ser testada, e a senha deve ser guardada separadamente. Permissões e criptografia não dispensam a definição de quem pode acessar ou reter os arquivos.

As ferramentas de privacidade permitem exportar, corrigir e remover identificação após confirmação operacional do responsável. A confirmação não verifica documentos automaticamente. Prazos de retenção, atendimento dos direitos dos titulares, tratamento de backups e relação com fornecedores exigem decisões da loja. O projeto oferece controles de apoio; não declara conformidade integral com a LGPD nem eliminação de todos os riscos.

A proteção da IA identifica sinais explícitos de alteração de regras e exposição de informações internas e pode pausar a conversa para revisão. Também existem limites de frequência e repetição. No PDF público, `ProtecaoCatalogo.reservar()` limita tentativas por link, frequência global e gerações simultâneas por processo, liberando a vaga após erro. Esses mecanismos complementam a segurança; não equivalem a uma defesa distribuída contra qualquer ataque.

## 10 Experiência de uso e desempenho

A interface passou a agrupar tarefas do dia a dia, preparação do atendimento e administração. A busca do menu aceita termos relacionados às telas, e a página inicial destaca o próximo passo. Configurações e perfil do comércio avisam sobre alterações não salvas. Uma resposta atrasada não deve apagar o que a pessoa acabou de digitar durante uma consulta ou salvamento.

No pedido do cliente, as quantidades podem ser ajustadas diretamente no resumo. A interface preserva foco após a atualização, apresenta o campo obrigatório que precisa de correção e adapta os controles ao celular. O tema permite escolher claro, escuro ou acompanhar o Windows. O recibo oferece impressão e um minijogo opcional, sem transformar o jogo em indicador do preparo.

No painel, `DeliveryUX.consultaAtual()` compartilha somente a leitura em andamento e invalida resultados anteriores a uma alteração. Não mantém um cache permanente de preferências ou dados do cliente. Consultas periódicas aguardam durante certas interações e ficam restritas à tela e à visibilidade aplicáveis. Gravações não são repetidas automaticamente quando o resultado é incerto.

Na fila de mensagens, consumidores reservados ajudam a impedir que uma inferência demorada bloqueie todas as respostas locais. Perguntas operacionais conhecidas dispensam o modelo. Outras otimizações reduziram consultas repetidas ao banco, separaram a sincronização do Graph da leitura de contexto e adiaram a importação do SDK remoto até sua necessidade.

As medições em `docs/DESEMPENHO.md` descrevem bases fictícias, comandos e limites. Elas demonstram ganhos locais de consultas e preparação, mas não medem toda a viagem entre WhatsApp, modelo e celular do cliente. Velocidade final depende de hardware, modelo, rede, disco, provedores e carga. Não se deve apresentar o projeto como resposta instantânea garantida em qualquer instalação.

## 11 Qualidade testes e controle de versões

A suíte Python cobre regras comerciais, privacidade, documentos, fila, concorrência e componentes do backend. Os testes JavaScript cobrem comportamento da interface e o conector WhatsApp simulado. Casos adversariais exercitam entradas inválidas, duplicações, permissões e falhas de comunicação. Dados fictícios e serviços simulados permitem repetir esses testes sem enviar mensagens reais.

Na versão 2.48.0, as regressões incluem propostas JSON inválidas ou duplicadas, referências inexistentes, saída livre misturada ao contrato, divergência de valores oficiais, notas sem categoria e edição ou revogação durante a inferência. Também preservam consultas locais compostas com saudações e a criação de link somente após intenção e proteção conferidas. Os relatórios JUnit e o check do commit atual registram o resultado integral; um resultado de versão anterior não substitui essa execução. Os testes usam modelos e transportes simulados, sem medir a qualidade de um Ollama real nem enviar mensagens a clientes. Há também 135 casos JavaScript para interface e conector; no Windows, um teste de vínculo simbólico pode ser pulado quando a conta não possui a permissão necessária.

O workflow `.github/workflows/validar.yml` confere versões e sintaxe, executa testes, audita dependências, realiza a análise passiva ZAP em ambiente isolado e compila os instaladores Windows. O check `DeliveryBot / validacao obrigatoria` exige sucesso das etapas necessárias. Relatórios ficam disponíveis temporariamente nos artifacts do GitHub Actions.

O trabalho usa branches `codex/` e pull requests antes da integração na `main`. Cada pedido concluído que altera arquivos versionados recebe versão em `VERSION`, registro em `CHANGELOG.md`, commit e tag. Painel e instaladores acompanham a versão. A aprovação do CI reduz o risco de regressões, mas não representa certificação de segurança ou prova de usabilidade com todos os clientes.

O laboratório público no Render usa uma lanchonete fictícia e permite conferir catálogo, fotos, formulário, PDF, comprovante e minijogo. A gestão, a IA, o WhatsApp real e o terminal dos funcionários não estão publicados nesse ambiente. A hospedagem de QA é descartável e pode demorar para abrir após ociosidade; não substitui a instalação e validação da operação real.

## 12 Como apresentar e demonstrar o código

Uma apresentação pode começar pelo percurso visível do cliente e depois mostrar as decisões do código. Abra o aplicativo, informe o perfil da loja e cadastre um produto sob pedido e outro com estoque. Explique por que a venda de um lanche produzido na hora não precisa usar a mesma contagem de uma bebida pronta. Mostre que o perfil organiza o atendimento sem apagar registros anteriores.

Em seguida, use o modo de teste ou o laboratório fictício. Selecione produtos, ajuste a quantidade pelo resumo e provoque uma validação simples, como tentar confirmar sem nome. Depois preencha um nome inventado e conclua. O comprovante deve refletir o total calculado pelo sistema. Uma demonstração acadêmica não precisa usar telefone, endereço ou credencial de uma pessoa real.

Para explicar a IA, compare perguntas relacionadas ao negócio com uma solicitação de outro segmento. Mostre a triagem antes do modelo e uma nota editorial aprovada. Esclareça que a nota orienta o texto, enquanto uma compra real passa por funções determinísticas. O objetivo da demonstração é evidenciar as fronteiras de responsabilidade, não sugerir que o modelo ficou incapaz de qualquer erro.

### Trechos principais para leitura

`perfil_comercio.salvar()` mostra a configuração individual. Ela valida dados e escolhe um modelo entre as operações aceitas. É um bom trecho para explicar a passagem de um aplicativo focado em lanches para uma base comercial genérica, sem remover o comportamento especializado da loja configurada.

`processamento.enfileirar()` e `processar_proxima()` explicam confiabilidade. A mensagem torna-se uma tarefa persistente, que pode ser retomada conforme seu estado. Preparação interrompida é diferente de envio incerto: a equipe precisa conferir se o cliente recebeu antes de provocar uma duplicação.

`ia.assunto_negocio()` representa a fronteira do assunto permitido. `_system_prompt_ollama()` reúne as instruções de atendimento e referências locais; `_mensagens_atualizadas()` prepara histórico reduzido. A apresentação deve distinguir uma autorização feita por código de uma orientação textual enviada ao modelo.

`cerebro.instrucoes_contexto()` mostra a seleção editorial, e `_ler()` concentra verificações de leitura. Explique aprovação, pertinência e segurança do caminho antes de destacar o Graph. A organização visual ajuda o responsável a manter conhecimento, mas não participa da autorização de caixa ou administração.

`pedidos.criar_pedido()` é o ponto central da confirmação. O trecho da transação evidencia que quantidade, preço, pedido e estoque precisam ser coerentes. `fila.avancar_status()` recebe o estado esperado; `pedidos.cancelar_pedido()` pode conferir o estado antes do estorno. A aplicação não confia apenas no que estava desenhado no botão.

`publicacao.PaginaPublica` demonstra isolamento de rotas. `links.gerar_link_pedido()` e `atualizar_resposta()` demonstram por que o endereço precisa vir do aplicativo e corresponder ao HTTPS atual. A alternativa PDF mantém o catálogo acessível quando o fluxo não consegue apresentar um link seguro.

`politica_terminal.exigir_gravacao()` e os endpoints do terminal exemplificam autorização junto da operação financeira. Essa verificação impede que uma permissão revogada seja substituída por uma decisão anterior da interface. O registro do caixa deve ser explicado como controle operacional, sem atribuir ao sistema uma conciliação bancária que ele não executa.

`DeliveryUX.consultaAtual()` e o contexto de edição em `navegacao.js` ajudam a explicar fluidez com segurança. O primeiro evita concorrência desnecessária de leitura; o segundo identifica alterações locais não salvas. O ganho vem de reduzir trabalho repetido e preservar a intenção do usuário, mantendo verificações de negócio no servidor.

### Preparação para uso e continuidade

Antes de entregar uma instalação, confira o perfil do comércio, os itens e preços, as contas individuais, a conexão escolhida e a abertura do HTTPS em outro aparelho. Faça um pedido fictício completo, uma conferência de caixa e uma restauração de backup de teste. Distribua somente os arquivos preparados, sem a pasta de dados da loja ou tokens do desenvolvedor.

Para evolução comercial, as prioridades incluem avaliação com usuários de segmentos diferentes, revisão dos falsos bloqueios da IA, medições de resposta de ponta a ponta e testes de recuperação em equipamentos representativos. Também cabem revisão de assinatura dos instaladores, governança de credenciais e fornecedores e proteção compartilhada se a aplicação passar a usar vários processos ou servidores.

O resultado é uma base funcional que aproxima atendimento, pedidos e gestão, com separação entre linguagem natural e operações comerciais. Sua manutenção depende de testes, revisão de cadastros e limites explícitos. A qualidade deve ser demonstrada por comportamentos reproduzíveis e resultados observados, sem prometer ausência absoluta de falhas.

## Apêndice de módulos e pontos de leitura

O inventário identifica os arquivos Python da aplicação e uma responsabilidade concreta de cada parte. As funções indicadas servem como pontos iniciais de leitura; regras complementares, métodos internos e testes completam os fluxos descritos.

**desktop.py** coordena a janela do responsável, a preparação dos dados e os serviços auxiliares; `preparar_dados()` preserva a instalação e `smoke_test()` verifica recursos do executável com cenário fictício.

**funcionario.py** inicia o aplicativo separado do caixa, conecta a janela ao cliente autorizado e oferece verificação do pacote; `main()` organiza a abertura sem disponibilizar a administração completa da loja.

**src/__init__.py** identifica o diretório como pacote Python, permitindo importações entre os módulos; o arquivo não contém regras comerciais, funções de atendimento ou um serviço executado independentemente.

**src/acesso_remoto.py** mantém convites, sessões e revogação da gestão pela internet; `criar()` prepara o acesso permitido e `_validar()` confere conta, prazo e autorização antes das operações previstas.

**src/aparencia.py** lê e salva a escolha de tema compartilhada pela instalação; `tema()` recupera a preferência e `salvar()` altera a apresentação sem modificar credenciais, permissões ou dados comerciais.

**src/app.py** define webhooks, compra, comprovante e demais rotas principais; `enviar_pedido()` recebe a confirmação do cliente e `catalogo_cliente_pdf()` aplica a proteção antes de disponibilizar o documento público.

**src/atualizacoes.py** consulta versões e prepara downloads verificados, considerando origem, integridade e assinatura; `atual()` identifica a versão instalada e as demais operações coordenam o backup anterior à instalação.

**src/auth_windows.py** disponibiliza autenticação pela conta Windows na modalidade de cozinha configurada; `disponivel()` verifica suporte e `validar_credenciais_windows()` trata a entrada sem substituir as permissões próprias dos operadores.

**src/backups.py** prepara cópias protegidas do banco e das notas necessárias à recuperação; `cifrar()` e `decifrar()` aplicam criptografia autenticada, enquanto a restauração conserva verificações de conteúdo e portabilidade.

**src/bandeja.py** mantém o ícone próximo ao relógio e as ações de mostrar ou encerrar; a classe `Bandeja` ajuda a distinguir fechar a janela de interromper os serviços locais.

**src/bot.py** encaminha intenções para respostas locais, catálogo, compra e IA; `_resposta_rapida()` evita inferência desnecessária e `processar_mensagem()` coordena os caminhos conforme as regras e o contexto da conversa.

**src/caixa.py** registra abertura, vendas, recebimento, movimentos e fechamento por operador; `vender()` integra venda e estoque, e `fechar()` conserva o valor esperado, a contagem declarada e a diferença.

**src/cardapio.py** consulta os produtos ativos e organiza sua apresentação por categoria; `listar_produtos_ativos()` e `agrupar_por_categoria()` atendem o cadastro genérico, apesar do nome histórico relacionado à alimentação.

**src/catalogo_avancado.py** reúne importação de catálogo e relatórios comerciais; `importar()` encaminha linhas às validações do cadastro, enquanto `relatorio()` apresenta vendas e custos registrados sem substituir uma apuração contábil.

**src/catalogo_pdf.py** gera o documento de produtos com imagens, preços e disponibilidade; `gerar()` utiliza dados públicos do cadastro, com opção de quantidades e sem incluir custos internos ou cadastros de clientes.

**src/catalogo_publico.py** restringe o trabalho de geração do PDF exposto ao cliente; `ProtecaoCatalogo.reservar()` aplica frequência e concorrência limitadas por processo, devolvendo a vaga mesmo após erro da geração.

**src/cerebro.py** prepara, visualiza e consulta o cofre editorial; `_ler()` concentra verificações de caminho e conteúdo, e `instrucoes_contexto()` seleciona referências aprovadas sem transformar Markdown em comando privilegiado do sistema.

**src/circuito_comercial.py** define o contrato de seleção de ação, fontes e tom do Ollama; `preparar()` limita as referências públicas e `renderizar()` rejeita propostas inválidas e monta a mensagem a partir dos dados autorizados, sem publicar texto factual livre do modelo.

**src/cliente_terminal.py** implementa a comunicação HTTPS do aplicativo do funcionário; `validar_conexao()` confere o arquivo recebido e a classe `Cliente` trata sessão e pendências sem abrir diretamente o banco central.

**src/comprovantes.py** mantém autorizações temporárias de consulta ao recibo na sessão assinada; `registrar()` associa compra e prazo, e `consultar()` exige o vínculo adequado sem publicar uma lista de pedidos.

**src/conexoes.py** coordena consultas ao WhatsApp e ao Ollama e tarefas auxiliares de preparação; `url_local()` distingue destinos locais, e `url_webhook()` auxilia a composição da integração conforme a publicação configurada.

**src/config.py** reúne valores iniciais e opções do ambiente; `_env_bool()` interpreta escolhas booleanas e as constantes orientam serviços e operação, sem substituir os controles aplicados nas requisições do aplicativo.

**src/conversa_pedido.py** mantém o rascunho de compra pelo WhatsApp; `responder()` solicita e interpreta os campos necessários, apresenta o resumo e delega a confirmação às regras transacionais de pedidos.

**src/db.py** controla conexões, pragmas e evolução da estrutura SQLite; `get_conn()` organiza conclusão, reversão e fechamento, enquanto `init_db()` inicializa ou migra o banco no caminho definido para a instalação.

**src/diagnosticos.py** consolida informações técnicas úteis ao suporte; `coletar()` prepara o estado operacional com redução de dados sensíveis, evitando usar uma exportação irrestrita de conversas como diagnóstico padrão.

**src/documentos_estoque.py** interpreta documentos e prepara itens para revisão, admitindo extração assistida pelo Ollama; suas funções de leitura e lançamento separam reconhecer uma tabela de aprovar alterações comerciais no cadastro.

**src/escopo_loja.py** reúne a política de assunto conforme perfil e catálogo; `politica()` descreve a atividade reconhecida e `fora_do_segmento()` ajuda a recusar referências incompatíveis antes da utilização do modelo.

**src/estoque.py** valida produtos, preços, medidas e movimentos de saldo; `salvar_produto()` mantém o cadastro e `ajustar_estoque()` registra alterações justificadas, preservando as diferenças entre itens controlados, fracionados e sob pedido.

**src/fila.py** representa a fila operacional de preparo, separada da fila técnica de mensagens; `listar_fila()` apresenta pedidos e `avancar_status()` verifica a transição esperada antes de atualizar e notificar o cliente.

**src/fotos.py** normaliza imagens recebidas e vincula a versão aceita ao produto; `normalizar()` trata o conteúdo e `salvar()` mantém a foto, sem autorizar a leitura de caminhos arbitrários do equipamento.

**src/gestao.py** agrupa os contratos HTTP do painel e suas verificações de acesso; `autorizado()` identifica a sessão permitida e o decorador `protegido()` antecede a execução das operações comerciais expostas.

**src/humano.py** registra pedidos de atendimento e pausas do bot para atuação da equipe; `solicitar()` mantém o encaminhamento e `pausado()` informa quando a automação precisa respeitar o atendimento humano.

**src/ia.py** prepara instruções, histórico reduzido e interação com o provedor escolhido; `assunto_negocio()` aplica a triagem e `responder()` coordena a geração, mantendo ferramentas e respostas submetidas às proteções locais.

**src/links.py** controla o endereço público e o acesso pessoal de compra; `gerar_link_pedido()` cria o token e `atualizar_resposta()` ajusta referências permitidas ao HTTPS atual, sem aceitar endereços inventados pelo modelo.

**src/meta_configuracao.py** conecta as credenciais da própria conta e configura seu webhook; `conectar()` revalida os dados selecionados e `renovar_webhook_automatico()` acompanha mudanças de endereço sob as condições de sincronização.

**src/meta_custos.py** registra envios, eventos de entrega e informações de cobrança; `registrar_status()` consolida os eventos disponíveis e `relatorio()` apresenta estimativas conforme tarifas e dados conhecidos, sem substituir a fatura.

**src/meta_oficial.py** consulta e verifica a identificação da conta e do número da Cloud API; `verificar()` trata o diagnóstico e as operações de migração preservam a distinção entre configuração local e aprovação da Meta.

**src/operadores.py** administra contas, credenciais, perfis e auditoria de ações; `usuario()` identifica a sessão e `admin()` auxilia a autorização, aplicada também às operações privilegiadas que passam pela ponte nativa.

**src/padroes_atendimento.py** relaciona perfil comercial e etapa editorial com notas de referência; `categoria()` escolhe o grupo do comércio e `etapa()` interpreta o momento da conversa sem redefinir o segmento cadastrado.

**src/pedidos.py** calcula cotação e confirma compras de forma consistente; `criar_pedido()` grava os registros relacionados e `cancelar_pedido()` verifica condições antes do estorno, preservando valores e custos históricos dos itens.

**src/perfil_comercio.py** representa identidade, segmento e modelo operacional da loja; `obter()` fornece o perfil e `salvar()` valida as escolhas sem usar a mudança de padrão para apagar produtos ou registros anteriores.

**src/politica_terminal.py** reúne as permissões de dispositivo e conta Caixa; `exigir_gravacao()` reconfere a autorização dentro da transação financeira, enquanto sessões e contadores limitam a duração e a frequência dos acessos.

**src/preferencias.py** carrega, aplica e persiste configurações do aplicativo, incluindo proteção dos campos sensíveis; `carregar()` recupera opções salvas e `aplicar()` atualiza o estado utilizado pelos módulos da instalação.

**src/primeiros_passos.py** organiza o estado inicial de preparação e o teste do endereço público; `situacao()` mostra pendências e `testar()` produz a verificação, sem transformar a conclusão do tutorial em garantia de disponibilidade.

**src/privacidade.py** implementa operações de exportação, correção, remoção e retenção; `auditar()` registra ações e a redução de contexto enviado à IA minimiza dados conhecidos, sem garantir anonimização de qualquer texto livre.

**src/processamento.py** mantém tarefas persistentes, duplicidade, ordem e recuperação das mensagens; `enfileirar()` registra a entrada e `processar_proxima()` diferencia preparação, envio, conclusão e resultados que exigem conferência pela equipe.

**src/protecao_ia.py** identifica padrões suspeitos e controla pausa e revisão da conversa; `classificar()` reconhece sinais previstos e `validar_saida()` recusa conteúdos protegidos ou resultados invalidados durante o processamento em andamento.

**src/protecao_terminal.py** encapsula a proteção local do aplicativo do funcionário; `dpapi()` utiliza o contexto Windows apropriado para resguardar credenciais e pendências, sem tornar essas informações livremente portáteis entre contas.

**src/publicacao.py** inicia e supervisiona o túnel e a superfície exposta ao cliente; a classe `PaginaPublica` filtra rotas, enquanto `validar_dominio()` ajuda a exigir um destino adequado para a publicação configurada.

**src/recibo.py** formata confirmação e atualização com o pedido já registrado; `montar_recibo()` apresenta itens e valores, sem assumir o papel de calcular a venda, conferir estoque ou comprovar pagamento recebido.

**src/recuperacao.py** acompanha a saúde do atendimento e as tentativas permitidas de recuperação local; `verificar_recuperar()` coordena o procedimento e `resultado_inferencia()` atualiza o diagnóstico técnico sem avaliar sozinho a qualidade semântica.

**src/rotinas.py** agenda backup, retenção e consulta de atualizações enquanto o Desktop funciona; `situacao()` apresenta o estado e o agendamento trata falhas independentes para preservar as demais tarefas de proteção.

**src/seguranca.py** centraliza CSRF, identificação local, proteção de segredos e cabeçalhos HTTP; `csrf_valido()` verifica a origem da operação e `reduzir_dados()` limita informações sensíveis nos registros destinados ao suporte.

**src/terminal.py** serve a API HTTPS dos funcionários na rede privada; `parear()` vincula o computador e `revogar()` encerra sua autorização, mantendo o painel administrativo fora das rotas previstas para o terminal.

**src/tutorial.py** descreve etapas e orientações contextuais de configuração; `etapas()` apresenta o percurso básico, ajudando a localizar tarefas sem executar automaticamente as decisões administrativas ou substituir a validação de serviços.

**src/validacao_http.py** controla a interpretação inequívoca de JSON e parâmetros; `ler_json()` limita estrutura e números e `parametros_unicos()` recusa repetições, antes de as rotas utilizarem esses valores em operações posteriores.

**src/viacep.py** trata CEP e consulta de endereço com validação de retorno; `consultar_cep()` busca a referência e `validar_area_entrega()` confere a área, sem converter uma falha de comunicação em endereço confirmado.

**src/web_qa.py** monta o laboratório público com base e catálogo fictícios; `criar_app()` aplica o isolamento e os limites próprios desse cenário, separado da gestão e das contas reais de WhatsApp.

**src/whatsapp.py** normaliza eventos e oferece transporte entre as modalidades configuradas; `enviar_mensagem()` executa o envio de texto e as verificações preservam o vínculo entre telefone, identificador privado e conexão selecionada.

**src/whatsapp_documentos.py** valida e transporta PDFs em memória para os provedores suportados; `enviar()` confere conteúdo e destino, utilizando o caminho apropriado da Meta, do componente local ou do servidor WAHA configurado.

**src/whatsapp_local.py** localiza e inicia o componente de conexão incluído no pacote; `iniciar()` coordena o processo em segundo plano e `credenciais()` fornece a autenticação própria da comunicação local entre os componentes.

As interfaces ficam em `web/templates` e `web/static`, incluindo gestão, compra, recibo, terminal e jogo. A conexão integrada possui código em `whatsapp-native`, e os componentes de runtime são preparados para acompanhar a distribuição. `packaging` concentra compilação, instaladores, versões, integridade e verificações; `sql/schema.sql` descreve a persistência, e `tests` reúne regressões. Esses grupos complementam os módulos Python sem representar novas permissões de acesso.

## Referências do próprio projeto

- `README.md` e `CHANGELOG.md` para orientação e histórico.
- `GUIA DO APLICATIVO.md` e `GUIA DO FUNCIONARIO.md` para operação.
- `docs/tcc/GUIA_DO_CODIGO.md` para inventário detalhado dos módulos.
- `docs/DESEMPENHO.md` para cenários e limites das medições.
- `SEGURANCA OWASP.md` e `PRIVACIDADE E SEGURANÇA.md` para controles e responsabilidades.
- `docs/META PRODUCAO E CUSTOS.md`, `docs/ACESSO REMOTO.md` e `docs/HOSPEDAGEM QA.md` para integrações e ambientes.
- `tests/` e `.github/workflows/validar.yml` para evidências automatizadas.
