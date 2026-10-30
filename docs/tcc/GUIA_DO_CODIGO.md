# DeliveryBot — guia de leitura e explicação do código

Versão de referência: 2.45.3. Preparado em 26/10/2026 para estudo, manutenção e apresentação do projeto. O relatório explica responsabilidades e fluxos; os links apontam para o código que implementa cada parte. Não substitui a leitura das funções quando uma regra for alterada.

## 1. Como apresentar o projeto

O DeliveryBot é um aplicativo Windows para organizar catálogo, pedidos e atendimento de um comércio. O responsável administra a operação no computador principal; funcionários podem registrar vendas e controlar seu próprio caixa em terminais autorizados da rede. Clientes usam o WhatsApp e uma página de pedidos. O atendimento pode consultar um modelo de linguagem, mas preços, estoque, permissões e confirmação de compra pertencem às regras do aplicativo.

Uma explicação inicial possível: “O projeto reúne atendimento e gestão comercial. A IA ajuda a interpretar e redigir a conversa; as operações financeiras passam por validações e transações no banco. Essa separação permite adaptar o atendimento sem entregar à IA o controle dos dados e das permissões.”

## 2. Arquitetura e limites de confiança

O aplicativo é organizado por módulos de responsabilidade, com rotas Flask, regras comerciais em Python, persistência SQLite e interfaces HTML/CSS/JavaScript. Existem processos auxiliares para WhatsApp local, túnel HTTPS e, opcionalmente, Ollama. Isso não significa que cada arquivo seja um serviço independente.

| Parte | Responsabilidade | Limite importante |
| --- | --- | --- |
| `desktop.py` e WebView | Iniciar e apresentar o painel do responsável; coordenar serviços e encerramento | A ponte nativa confere sessão e perfil antes de operações privilegiadas |
| `src/app.py` e `src/gestao.py` | Receber requisições e encaminhá-las às regras do domínio | Dados vindos de formulários, webhooks e navegadores são entradas não confiáveis |
| Regras comerciais | Cotar, confirmar, registrar estoque, fila e caixa | A conversa da IA não substitui os cálculos e verificações do sistema |
| SQLite e `sql/schema.sql` | Armazenar registros, relacionamentos e estados de recuperação | Migrações preservam bancos existentes; escrita precisa de transação |
| `src/publicacao.py` | Expor a página e somente rotas públicas permitidas pelo gateway | Abrir o túnel não deve publicar todo o painel administrativo |
| `funcionario.py` e terminal HTTPS | Operar pedidos manuais e caixa pela rede privada | Conta, dispositivo e autorização são verificados separadamente |
| Ollama/Anthropic e Obsidian | Produzir texto com regras e conhecimento editorial aprovado | Notas e respostas não podem conceder permissões nem alterar valores comerciais |

O código principal do responsável fica no computador da loja. A página pública depende desse computador, da internet e do túnel disponíveis. O ambiente de QA no Render é separado e usa dados fictícios; não deve ser apresentado como hospedagem automática da operação real completa.

## 3. Percurso de uma mensagem e de um pedido

1. O transporte identifica uma mensagem nova. Na Meta, o webhook valida a assinatura do corpo; no modo local, o componente integrado entrega eventos ao backend com autenticação própria.
2. `whatsapp.py` normaliza o evento. `processamento.enfileirar` registra uma tarefa e uma chave de deduplicação; repetições do mesmo evento não devem criar outro atendimento.
3. O processamento confere validade, pausa humana e proteção da conversa. Mensagens antigas, ruído ou bloqueadas seguem as regras correspondentes, sem iniciar uma inferência desnecessária.
4. `bot.py` encaminha a intenção. Respostas determinísticas, catálogo e fluxo de compra são preferidos quando já existe uma regra adequada. `ia.py` é consultado nos casos que usam linguagem natural.
5. Para comprar pelo site, `links.py` exige um endereço público válido. `publicacao.py` verifica o destino HTTPS. Se a página continuar indisponível no fluxo de recuperação, a fila pode enviar o catálogo em PDF e orientar a compra pela conversa.
6. Pelo WhatsApp, `conversa_pedido.py` mantém um rascunho. Pelo navegador, o formulário contém a seleção do cliente. Em ambos os caminhos, a confirmação passa por `pedidos.py`.
7. `pedidos.criar_pedido` resolve itens, verifica valores e disponibilidade e grava pedido, itens, movimentos de estoque e fila dentro da operação transacional. A contagem de estoque depende do cadastro do produto; itens sob encomenda podem não ter saldo obrigatório.
8. `fila.py` acompanha o preparo. `recibo.py`, comprovantes e notificações apresentam o resultado registrado. Uma forma de pagamento escolhida não comprova que o dinheiro foi recebido; o caixa possui suas próprias operações.

### Estados da fila de mensagens

| Estado | Significado operacional |
| --- | --- |
| `PENDENTE` | Aguarda processamento; pode estar esperando reconexão do HTTPS |
| `PROCESSANDO` | Uma tarefa foi reservada para preparar a resposta |
| `ENVIANDO` | O envio foi iniciado; uma interrupção pode tornar o resultado incerto |
| `CONCLUIDA` | A tarefa terminou ou foi descartada conforme a regra aplicada |
| `FALHOU` | A operação precisa de revisão antes de nova tentativa |
| `VERIFICAR` | Após interrupção durante envio, a equipe deve conferir se o cliente recebeu |

Ao explicar esse trecho, destaque que sistemas externos podem aceitar uma mensagem antes de a conexão cair. Reenviar automaticamente nesse caso pode duplicá-la. A recuperação diferencia preparação interrompida de envio com resultado incerto.

## 4. O que foi otimizado nesta revisão

Foram examinadas duas hipóteses locais: retirar resolução de caminho duplicada na descoberta das notas e normalizar cada campo do perfil comercial uma única vez por classificação. Não foram eliminadas a releitura de notas, a checagem de aprovação e validade, as permissões ou as transações financeiras.

A descoberta de notas continua usando `_ler` como fronteira de leitura segura: valida raiz e componentes do caminho, recusa vínculos, limita tamanho e trata texto inválido. A remoção ocorre antes dessa fronteira, em uma checagem repetida. A classificação continua respeitando segmento, descrição e identificação de perfil misto; o texto normalizado é apenas uma variável local da chamada, sem cache de autorização ou de conteúdo.

| Recorte medido | Mediana antes | Mediana depois | Leitura do resultado |
| --- | ---: | ---: | --- |
| Contexto com 80 notas, rodada C | 943,861 ms | 869,701 ms | Cerca de 7,9% menos tempo; outra rodada encontrou redução de 8,0% |
| Lote de 200 classificações, rodada B | 386,416 ms | 157,258 ms | Cerca de 2,5 vezes mais rápido nesse cenário de descrição longa; outra rodada encontrou 2,3 vezes |

As comparações alternam referência e variante no mesmo processo e exigem saída idêntica, com 16 amostras por condição para contexto e 20 para classificação. Foram feitas em Windows/Python 3.12, com material fictício e duas rodadas de aquecimento. A referência da função é a árvore v2.45.2; os demais helpers permanecem os da variante. Tempos absolutos variaram entre sessões do equipamento.

As medidas, comandos, condições e limites estão em [Desempenho](../DESEMPENHO.md). Os tempos do laboratório não representam o tempo de geração do Ollama, a rede da Meta, a renderização ou a abertura completa do instalador. Não há afirmação de “máximo global”: são melhorias locais verificadas no recorte medido.

## 5. Como ler o inventário de módulos

Os módulos a seguir são agrupados pela sua responsabilidade principal. Alguns colaboram com vários fluxos; por exemplo, o processamento usa simultaneamente transporte, privacidade, atendimento humano e compra. As funções indicadas são pontos de leitura, não uma lista de todas as chamadas de cada arquivo. Métodos internos, validadores e testes complementam a explicação.

### src/acesso_remoto.py

Cria convites temporários, valida a conta responsável e controla sessões da gestão pela internet. Permissão de consulta e avanço de pedidos são verificadas no servidor; revogar acesso encerra a autorização correspondente.

Pontos de leitura: [encerrar_ao_iniciar](../../src/acesso_remoto.py#L18), [_hash](../../src/acesso_remoto.py#L24), [_responsavel](../../src/acesso_remoto.py#L28).

### src/aparencia.py

Lê e salva a preferência de tema. A mudança é cosmética e não concede acesso a operações comerciais.

Pontos de leitura: [tema](../../src/aparencia.py#L7), [salvar](../../src/aparencia.py#L14).

### src/app.py

Define as rotas principais do servidor: webhooks, compra, comprovante, cozinha, privacidade e jogo. Recebe a entrada HTTP e encaminha a operação aos módulos responsáveis, com autenticação e validações conforme a rota.

Pontos de leitura: [catalogo_do_comercio](../../src/app.py#L46), [limite_upload_produto](../../src/app.py#L55), [entrada_invalida](../../src/app.py#L64).

### src/atualizacoes.py

Consulta versões, valida a origem de downloads, confere hashes e assinatura e prepara atualização com backup. Consultar uma versão não significa autorizar qualquer executável recebido da internet.

Pontos de leitura: [versao](../../src/atualizacoes.py#L28), [atual](../../src/atualizacoes.py#L34), [_url_arquivo](../../src/atualizacoes.py#L38).

### src/auth_windows.py

Oferece autenticação com a conta Windows no modo de cozinha configurado para isso. Não substitui as contas e permissões específicas dos operadores do aplicativo.

Pontos de leitura: [disponivel](../../src/auth_windows.py#L23), [validar_credenciais_windows](../../src/auth_windows.py#L27).

### src/backups.py

Serializa o banco e inclui notas do cofre em cópias de recuperação ou backups criptografados. Verifica o conteúdo antes da restauração; segredos protegidos pelo Windows possuem limites de portabilidade.

Pontos de leitura: [_chave](../../src/backups.py#L20), [cifrar](../../src/backups.py#L26), [decifrar](../../src/backups.py#L34).

### src/bandeja.py

Mantém o ícone próximo ao relógio e as ações de mostrar ou encerrar o aplicativo. Distingue esconder a janela de interromper os serviços de atendimento.

Pontos de leitura: [Bandeja](../../src/bandeja.py#L7).

### src/bot.py

Orquestra as intenções da conversa e respostas determinísticas, com encaminhamento à compra, ao catálogo ou à IA. Limites e políticas adicionais também são aplicados pela fila e pelos módulos de proteção.

Pontos de leitura: [_dentro_do_rate_limit](../../src/bot.py#L32), [_resposta_opcao](../../src/bot.py#L51), [_resposta_rapida](../../src/bot.py#L82).

### src/caixa.py

Registra abertura, vendas, recebimentos, sangria, suprimento, estorno e fechamento por operador. Usa centavos e chaves de operação para controlar dinheiro esperado e evitar repetição de lançamentos.

Pontos de leitura: [centavos](../../src/caixa.py#L12), [_aberto](../../src/caixa.py#L22), [_saldo](../../src/caixa.py#L29).

### src/cardapio.py

Lista e agrupa os produtos ativos para catálogo e atendimento. O nome histórico não restringe o domínio a lanches: a fonte é o cadastro genérico de produtos.

Pontos de leitura: [listar_produtos_ativos](../../src/cardapio.py#L16), [agrupar_por_categoria](../../src/cardapio.py#L31), [buscar_produto](../../src/cardapio.py#L38).

### src/catalogo_avancado.py

Importa linhas de catálogo e calcula relatórios comerciais. O lançamento deve passar pelas validações do cadastro, preservando a consistência dos produtos.

Pontos de leitura: [importar](../../src/catalogo_avancado.py#L11), [relatorio](../../src/catalogo_avancado.py#L44).

### src/catalogo_pdf.py

Monta o catálogo público em PDF, com dados do cadastro e imagens disponíveis. A geração pode ocultar quantidades; custos internos e dados de clientes não pertencem ao catálogo público.

Pontos de leitura: [_fontes](../../src/catalogo_pdf.py#L25), [_texto](../../src/catalogo_pdf.py#L33), [gerar](../../src/catalogo_pdf.py#L38).

### src/cerebro.py

Prepara o cofre Obsidian, valida leituras e seleciona notas aprovadas. `contexto_revisado()` registra fontes, trechos e assinaturas; `contexto_valido()` confere as referências antes da publicação. Conhecimento factual exige categoria explícita. Também mantém mapa, visualização e snapshots; guias operacionais não executam ações comerciais.

Pontos de leitura: [diretorio](../../src/cerebro.py#L258), [arquivo_inicio](../../src/cerebro.py#L296), [_criar_se_ausente](../../src/cerebro.py#L300).

### src/circuito_comercial.py

Limita o atendimento Ollama a uma proposta com ação, referências e tom. `preparar()` congela fontes públicas do cadastro e conhecimento revisado, com limite de contexto. Quando recebe o foco da consulta, seleciona apenas os produtos e aspectos pedidos; preço e descrição não são expostos juntos sem necessidade. Notas pertinentes são mantidas inteiras, sem cortar condições. `CircuitoPreparado.renderizar()` valida JSON, campos, tipos e IDs, e monta a mensagem usando somente as fontes disponíveis. Texto livre, referências desconhecidas, valores de notas que substituam o cadastro e respostas acima do limite são recusados. O módulo não acessa banco, arquivos, rede ou pedidos; a execução da ação continua em `ia.py`.

Pontos de leitura: [contrato e renderização](../../src/circuito_comercial.py), [testes do circuito](../../tests/test_circuito_comercial.py) e [integração do Ollama](../../tests/test_ia_circuito.py).

### src/foco_atendimento.py

`resolver()` extrai o assunto atual, os aspectos perguntados e as posições dos produtos no retrato permitido do catálogo. Uma continuação curta só recupera um produto identificado pelo cliente, sem atravessar uma mudança de assunto ou confirmação ambígua. `Foco.historico()` limita os antecedentes necessários; a pergunta atual é enviada separadamente. Sem produto inequívoco, retorna uma pergunta dirigida que pode ser respondida sem inferência. Não consulta banco, arquivos ou rede, não autoriza ferramentas e não substitui a triagem de escopo.

Pontos de leitura: [resolução do foco](../../src/foco_atendimento.py), [regressões de continuidade](../../tests/test_foco_atendimento.py) e [integração de fontes e histórico](../../tests/test_ia_circuito.py).

### src/cliente_terminal.py

Cliente HTTPS usado pelo aplicativo do funcionário. Valida o arquivo de conexão, comunica com o serviço autorizado e trata sessão e operações pendentes sem acesso direto ao banco da loja.

Pontos de leitura: [FalhaTerminal](../../src/cliente_terminal.py#L18), [validar_conexao](../../src/cliente_terminal.py#L22), [Cliente](../../src/cliente_terminal.py#L47).

### src/comprovantes.py

Mantém autorizações temporárias de recibos na sessão assinada do navegador. Relaciona hash do token, pedido e prazo, em vez de publicar uma lista de compras.

Pontos de leitura: [_validos](../../src/comprovantes.py#L15), [registrar](../../src/comprovantes.py#L25), [consultar](../../src/comprovantes.py#L34).

### src/conexoes.py

Consulta WhatsApp e Ollama, configura webhooks e coordena tarefas de preparação e download de modelos. A execução de auxiliares usa opções de processo apropriadas ao aplicativo Windows.

Pontos de leitura: [http](../../src/conexoes.py#L22), [url_local](../../src/conexoes.py#L28), [url_webhook](../../src/conexoes.py#L32).

### src/config.py

Carrega os valores de configuração do ambiente e seus padrões. Ao apresentar o arquivo, explique categorias e opções; não mostre valores reais de credenciais.

Pontos de leitura: [_env_bool](../../src/config.py#L8).

### src/conversa_pedido.py

Implementa o rascunho de compra por texto: seleção, variações, nome, entrega, pagamento, resumo e confirmação. A gravação final é delegada à regra de pedidos e não a uma promessa textual do modelo.

Pontos de leitura: [normalizar](../../src/conversa_pedido.py#L16), [dinheiro](../../src/conversa_pedido.py#L21), [_ler](../../src/conversa_pedido.py#L25).

### src/db.py

Abre conexões SQLite, configura pragmas, delimita commit/rollback/fechamento e aplica migrações. Inicializa cada banco conforme o caminho, permitindo testes isolados com bases temporárias.

Pontos de leitura: [_connect](../../src/db.py#L48), [get_conn](../../src/db.py#L64), [_colunas_existentes](../../src/db.py#L76).

### src/diagnosticos.py

Reúne informações operacionais para suporte com redução de dados sensíveis. Um diagnóstico não deve ser apresentado como cópia irrestrita de logs ou conversas.

Pontos de leitura: [coletar](../../src/diagnosticos.py#L11).

### src/documentos_estoque.py

Lê PDF ou planilha, pode usar extração estruturada via Ollama e prepara itens para conferência. Aplicar a revisão e salvar uma nota são operações distintas; a leitura não deve lançar dados comerciais sem a etapa correspondente.

Pontos de leitura: [_normal](../../src/documentos_estoque.py#L39), [_linhas](../../src/documentos_estoque.py#L43), [_texto_curto](../../src/documentos_estoque.py#L63).

### src/estoque.py

Valida produto, preço, quantidade, variação e saldo e registra movimentos. Distingue itens fracionados e estoque opcional, mantendo o catálogo atualizado após mudanças.

Pontos de leitura: [inteiro](../../src/estoque.py#L10), [dinheiro](../../src/estoque.py#L22), [medida](../../src/estoque.py#L34).

### src/fila.py

Lista a fila de preparo e avança o estado do pedido conforme as regras. Representa a operação da loja, não a fila técnica de mensagens do bot.

Pontos de leitura: [listar_fila](../../src/fila.py#L21), [avancar_status](../../src/fila.py#L62).

### src/fotos.py

Normaliza imagens recebidas, armazena a versão aceita e produz endereços de fotos do catálogo. A validação de imagem não autoriza leitura de arquivos arbitrários do computador.

Pontos de leitura: [normalizar](../../src/fotos.py#L13), [url](../../src/fotos.py#L43), [salvar](../../src/fotos.py#L48).

### src/gestao.py

Agrupa as rotas do painel administrativo e aplica os controles de acesso antes de delegar às regras comerciais. Concentra contratos HTTP, enquanto cálculos e transações permanecem nos módulos de domínio.

Pontos de leitura: [_local](../../src/gestao.py#L17), [acesso_base](../../src/gestao.py#L22), [autorizado](../../src/gestao.py#L32).

### src/humano.py

Registra solicitações e pausas para atendimento pela equipe, lista a conversa e prepara respostas humanas. A pausa precisa ser respeitada também por uma resposta de IA que já estava em processamento.

Pontos de leitura: [telefone](../../src/humano.py#L8), [pausado](../../src/humano.py#L15), [solicitar](../../src/humano.py#L20).

### src/ia.py

Monta regras, histórico reduzido e contexto e escolhe o provedor de linguagem. Respostas e links são tratados antes do envio; SDK opcional e serviço local têm falhas controladas, sem garantir a qualidade de toda geração.

Pontos de leitura: [IAIndisponivel](../../src/ia.py#L49), [normalizar_texto](../../src/ia.py#L100), [intencao_pedido](../../src/ia.py#L107).

### src/links.py

Gera e valida tokens de compra, prazo, uso único e endereço público. Atualiza respostas quando o endereço muda e recusa a ausência de uma página pública adequada.

Pontos de leitura: [PaginaIndisponivel](../../src/links.py#L23), [_base_pedido](../../src/links.py#L27), [_endereco_local](../../src/links.py#L38).

### src/meta_configuracao.py

Configura credenciais e webhook da própria conta Meta e coordena renovação do endereço. Usa mecanismos de exclusão e estado para reduzir disputas de configuração entre tarefas.

Pontos de leitura: [_exclusivo](../../src/meta_configuracao.py#L15), [_credenciais](../../src/meta_configuracao.py#L27), [consultar](../../src/meta_configuracao.py#L38).

### src/meta_custos.py

Registra envios, eventos de entrega/cobrança, tarifas e orçamento em unidades monetárias apropriadas ao relatório. As estimativas locais e eventos recebidos precisam ser distinguidos da fatura do provedor.

Pontos de leitura: [agora](../../src/meta_custos.py#L14), [utc](../../src/meta_custos.py#L18), [micros](../../src/meta_custos.py#L22).

### src/meta_oficial.py

Consulta e verifica a identificação da conta e do número oficial e trata migração de configuração. Não cria automaticamente a aprovação comercial de uma conta na Meta.

Pontos de leitura: [_id](../../src/meta_oficial.py#L13), [_consulta](../../src/meta_oficial.py#L19), [verificar](../../src/meta_oficial.py#L38).

### src/operadores.py

Gerencia contas, senhas, sessões, perfis, permissões e auditoria. As verificações ocorrem no backend e também protegem operações privilegiadas da ponte nativa.

Pontos de leitura: [existem](../../src/operadores.py#L12), [usuario](../../src/operadores.py#L17), [admin](../../src/operadores.py#L24).

### src/padroes_atendimento.py

Escolhe o perfil comercial e a etapa editorial da conversa e cria notas padrão. A pergunta do cliente influencia a etapa, mas não redefine o segmento cadastrado da loja.

Pontos de leitura: [normalizar](../../src/padroes_atendimento.py#L38), [categoria](../../src/padroes_atendimento.py#L42), [etapa](../../src/padroes_atendimento.py#L55).

### src/pedidos.py

Resolve os produtos do carrinho, calcula cotação e confirma o pedido em transação. Mantém nomes e custos históricos dos itens e controla cancelamento e reposição de estoque conforme o estado da operação.

Pontos de leitura: [CotacaoAlterada](../../src/pedidos.py#L12), [cotacao](../../src/pedidos.py#L16), [_cotacao](../../src/pedidos.py#L24).

### src/perfil_comercio.py

Lê, valida e salva identidade, segmento, descrição e modelo operacional da loja. A preferência de estoque padrão não deve apagar produtos e registros anteriores.

Pontos de leitura: [obter](../../src/perfil_comercio.py#L17), [salvar](../../src/perfil_comercio.py#L26), [importar_instalacao](../../src/perfil_comercio.py#L45).

### src/politica_terminal.py

Valida conta Caixa, vínculo de dispositivo, permissões de movimento, limites e sessões do terminal. Revalida a autorização dentro da transação financeira para tratar revogação concorrente.

Pontos de leitura: [AcessoNegado](../../src/politica_terminal.py#L15), [conta_caixa](../../src/politica_terminal.py#L19), [dados_autorizacao](../../src/politica_terminal.py#L25).

### src/preferencias.py

Lê e aplica configurações persistentes do aplicativo, com proteção dos campos sensíveis. A configuração é distinta dos dados comerciais e dos arquivos de exemplo versionados.

Pontos de leitura: [aplicar](../../src/preferencias.py#L29), [carregar](../../src/preferencias.py#L43), [obter](../../src/preferencias.py#L59).

### src/primeiros_passos.py

Mantém o estado de preparação e teste dos recursos iniciais do aplicativo. A confirmação do guia orienta o uso, mas não substitui as validações técnicas de cada serviço.

Pontos de leitura: [publico](../../src/primeiros_passos.py#L14), [situacao](../../src/primeiros_passos.py#L21), [testar](../../src/primeiros_passos.py#L56).

### src/privacidade.py

Executa exportação, correção, remoção de identificação, retenção de mensagens e redução do histórico enviado à IA. Registra auditoria e exige procedimentos do responsável para atender a pessoa correta.

Pontos de leitura: [aviso](../../src/privacidade.py#L12), [auditar](../../src/privacidade.py#L25), [_telefone](../../src/privacidade.py#L29).

### src/processamento.py

Mantém a fila persistente, deduplicação, ordem por conversa, prazo, processamento e envio. Distingue falha, envio incerto e conclusão e coordena alternativas de link e PDF sem criar um pedido por conta própria.

Pontos de leitura: [_mensagem_ruido](../../src/processamento.py#L29), [_concluir_sem_resposta](../../src/processamento.py#L38), [ativo](../../src/processamento.py#L48).

### src/protecao_ia.py

Classifica entradas suspeitas, controla bloqueios e versões de proteção e valida a saída da IA. Uma mensagem classificada não concede ao modelo acesso ao sistema operacional ou ao banco.

Pontos de leitura: [ConversaBloqueada](../../src/protecao_ia.py#L27), [trava](../../src/protecao_ia.py#L32), [normalizar](../../src/protecao_ia.py#L42).

### src/protecao_terminal.py

Encapsula proteção DPAPI de dados locais do aplicativo do funcionário. A credencial protegida depende do contexto Windows apropriado e não deve ser copiada em texto para documentação.

Pontos de leitura: [dpapi](../../src/protecao_terminal.py#L7).

### src/publicacao.py

Gerencia o processo do túnel, verifica o destino HTTPS e filtra rotas públicas no gateway. Trata reconexão e sincronização do webhook, preservando a separação entre página pública e administração.

Pontos de leitura: [validar_dominio](../../src/publicacao.py#L25), [endereco](../../src/publicacao.py#L50), [situacao](../../src/publicacao.py#L64).

### src/recibo.py

Formata mensagens de confirmação, recibo e atualização com dados do pedido registrado. É apresentação do resultado, não o local que calcula ou confirma uma venda.

Pontos de leitura: [_linha](../../src/recibo.py#L10), [_centralizar](../../src/recibo.py#L14), [montar_recibo](../../src/recibo.py#L18).

### src/recuperacao.py

Verifica o atendimento e coordena tentativas limitadas de recuperar o Ollama local quando habilitado. Mantém estado técnico e notas operacionais sem executar comandos vindos de notas da IA.

Pontos de leitura: [Recuperacao](../../src/recuperacao.py#L12), [iniciar](../../src/recuperacao.py#L176), [encerrar](../../src/recuperacao.py#L183).

### src/rotinas.py

Agenda backups, retenção e consulta de atualização no Desktop. Trata falhas independentes para preservar a supervisão e não expõe erros com dados privados em mensagens de log.

Pontos de leitura: [_instante_utc](../../src/rotinas.py#L19), [_cfg](../../src/rotinas.py#L32), [situacao](../../src/rotinas.py#L37).

### src/seguranca.py

Centraliza comparação segura, identificação de acesso local, CSRF, limites de login, cabeçalhos, redução de logs e proteção de segredos. Esses controles colaboram com as regras específicas de cada rota e de cada perfil.

Pontos de leitura: [igual](../../src/seguranca.py#L23), [local](../../src/seguranca.py#L27), [acesso_administrativo](../../src/seguranca.py#L31).

### src/terminal.py

Serve a API HTTPS da rede privada, configura certificado, pareamento, dispositivos e revogação. O terminal não deve receber todo o acesso administrativo do responsável.

Pontos de leitura: [ip_rede](../../src/terminal.py#L30), [configuracao](../../src/terminal.py#L41), [_certificado](../../src/terminal.py#L46).

### src/tutorial.py

Descreve os passos de configuração e a ajuda contextual exibida ao usuário. É orientação de interface; não altera permissões da conta por meio de texto.

Pontos de leitura: [etapas](../../src/tutorial.py#L4).

### src/validacao_http.py

Limita profundidade e quantidade de elementos JSON e recusa campos duplicados, números inválidos e textos problemáticos. Fornece o provedor JSON usado pelas rotas para tratar entradas inequívocas.

Pontos de leitura: [_profundidade](../../src/validacao_http.py#L10), [_objeto](../../src/validacao_http.py#L31), [_inteiro](../../src/validacao_http.py#L40).

### src/viacep.py

Normaliza CEP, consulta e valida o retorno do serviço de endereços e confere a área atendida. Reutiliza respostas válidas com limite e prazo, sem transformar erro de rede em endereço confirmado.

Pontos de leitura: [limpar_cep](../../src/viacep.py#L19), [consultar_cep](../../src/viacep.py#L23), [endereco_formatado](../../src/viacep.py#L77).

### src/web_qa.py

Constrói um ambiente web com catálogo e banco fictícios e rotas limitadas para testes. Mantém esse cenário separado da conexão real de WhatsApp e da administração comercial.

Pontos de leitura: [criar_app](../../src/web_qa.py#L29).

### src/whatsapp.py

Normaliza os provedores e seus eventos e encaminha envios de texto ou PDF. Preserva número, identificador privado de conversa e sessão conforme o transporte.

Pontos de leitura: [_numero_limpo](../../src/whatsapp.py#L25), [_lembrar_chat_id](../../src/whatsapp.py#L44), [_chat_id_conhecido](../../src/whatsapp.py#L70).

### src/whatsapp_documentos.py

Valida e envia o PDF em memória: pelo componente local/WAHA ou por upload e identificador na Meta. Limita arquivo e destino e verifica a aceitação sem oferecer um caminho de arquivo privado ao cliente.

Pontos de leitura: [_resposta](../../src/whatsapp_documentos.py#L12), [enviar](../../src/whatsapp_documentos.py#L21).

### src/whatsapp_local.py

Localiza e inicia o componente integrado com credenciais próprias de comunicação local. Controla seu encerramento e evita exigir Node.js instalado separadamente pelo cliente final.

Pontos de leitura: [recursos](../../src/whatsapp_local.py#L24), [credenciais](../../src/whatsapp_local.py#L28), [iniciar](../../src/whatsapp_local.py#L39).

### src/__init__.py

Marca o diretório como pacote Python. Está vazio e não representa um serviço ou fluxo comercial.


## 6. Interface, integração local e armazenamento

| Arquivos ou grupo | Como explicar |
| --- | --- |
| `web/templates/gestao.html`, `web/static/gestao.js` e `gestao.css` | Estrutura, ações e aparência do painel. O navegador envia intenções; o backend decide se são permitidas |
| `administracao.js`, `caixa_admin.js`, `acesso_remoto_admin.js` | Contas/atualizações, acompanhamento dos caixas e concessão/revogação de acessos. Não armazenam a autoridade comercial no JavaScript |
| `pedido.html`, `pedido.js`, `pedido.css` e `pedido_sucesso.html` | Catálogo, busca, carrinho, formulário e comprovante. Preço e saldo são novamente conferidos no servidor |
| `publicacao.js`, `meta_oficial.js`, `documentos_estoque.js` | Assistentes de conexão, API oficial e conferência de importações. Credenciais não devem ser copiadas para o relatório |
| `experiencia.js`, `primeiros_passos.js`, `tutorial.js`, `humano.js`, `catalogo_avancado.js` e `tema.js` | Busca/filtros e orientação de uso, configuração inicial, transição para atendente, catálogo e preferência de tema |
| `remoto.html`, `remoto.js` e `remoto.css` | Gestão remota permitida por convite, sessão e perfil; não é controle da tela inteira do computador |
| `web/funcionario/` | Interface independente de balcão e caixa. Usa a ponte nativa do segundo aplicativo e o serviço HTTPS autorizado |
| `pong-core.js`, `pong.js`, `pong.css`, `jogar.html` e `minijogo.html` | Física e controles do minijogo local. Não consultam o preparo nem registram pagamentos |
| `marca.svg` e `packaging/DeliveryBot.ico` | Recursos da identidade visual, incluindo a cópia necessária ao terminal independente |
| `whatsapp-native/bridge.mjs` | Integração com Baileys: sessão, QR, eventos, destinos privados, envio de texto/PDF e recuperação local |
| `whatsapp-native/server.mjs` | API local autenticada com limites de corpo e de Host; faz a ponte entre Python e o cliente WhatsApp |
| `whatsapp-native/self-test.mjs` e `test/` | Verificações do componente, inclusive simulações sem contas reais |
| `sql/schema.sql` | Estrutura persistente. Clientes/produtos/pedidos/itens representam o domínio; tabelas de filas, autorizações e auditoria representam o controle operacional |
| `data/cardapio.json` | Catálogo de exemplo para cenários de demonstração e testes; não é o banco real de um comércio |

No banco, explique os relacionamentos antes das colunas: um cliente pode ter pedidos; um pedido possui itens e entra na fila; movimentos registram alterações de estoque; um caixa possui operações e recebimentos. Outras tabelas mantêm links, rascunhos, mensagens, pausas humanas, autorizações de dispositivos, custos Meta e auditoria. Não confunda a fila de preparo com a fila técnica de envio de mensagens.

## 7. Trechos para apresentar no código

Os trechos abaixo são extraídos do código desta versão. Use-os para mostrar uma regra completa e depois seguir o link para seu contexto. Eles não são um novo programa separado.

### Transação e ciclo da conexão

Fonte: [src/db.py — get_conn](../../src/db.py#L64).

```python
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

O contexto confirma a operação quando termina sem erro, desfaz em caso de exceção e fecha a conexão em ambos os caminhos. A reserva de escrita e as regras comerciais aparecem no chamador, como criar_pedido.

### Validação de preço

Fonte: [src/estoque.py — dinheiro](../../src/estoque.py#L22).

```python
def dinheiro(valor, campo="Preço"):
    try:
        numero = Decimal(str(valor).replace(",", "."))
        if not numero.is_finite() or not 0 <= numero <= 99999999:
            raise InvalidOperation
        if numero != numero.quantize(Decimal("0.01")):
            raise InvalidOperation
        return float(numero)
    except (InvalidOperation, ValueError):
        raise ValueError(f"{campo}: informe um valor válido com até duas casas decimais.") from None
```

A entrada passa por Decimal e verificação de finitude, intervalo e duas casas decimais antes da conversão final. No caixa, as contas usam centavos; não apresente todos os valores SQLite como números inteiros.

### Aprovação e validade editorial

Fonte: [src/cerebro.py — _aprovada](../../src/cerebro.py#L688).

```python
def _aprovada(metadados: str) -> bool:
    if _metadado(metadados, 'atendimento').casefold() != 'true':
        return False
    if re.search(r'^valido_ate[ \t]*:', metadados, re.M | re.I):
        try:
            validade = _metadado(metadados, 'valido_ate')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', validade) or date.fromisoformat(validade) < date.today():
                return False
        except ValueError:
            return False
    return True
```

A nota precisa ter aprovação inequívoca. Validade malformada, duplicada ou vencida é recusada. O teste de caminhos e tamanho ocorre antes, em _ler; a confirmação comercial ocorre em outros módulos.

### Escolha do segmento

Fonte: [src/padroes_atendimento.py — categoria](../../src/padroes_atendimento.py#L42).

```python
def categoria():
    if config.COMERCIO_CONFIGURADO != 'SIM':
        return 'GERAL'
    for texto in (config.COMERCIO_SEGMENTO, config.COMERCIO_DESCRICAO):
        normalizado = normalizar(texto)
        ativos = [nome for nome, padrao in _PALAVRAS.items() if re.search(padrao, normalizado)]
        if len(ativos) == 1:
            return ativos[0]
        if len(ativos) > 1:
            return 'MISTO'
    return config.COMERCIO_MODELO if config.COMERCIO_MODELO in PERFIS else 'GERAL'
```

O segmento cadastrado tem prioridade sobre a descrição. Uma identificação ambígua produz perfil misto. A otimização reutiliza somente a normalização local de cada campo, sem guardar uma decisão entre chamadas.

### Consulta de comprovante

Fonte: [src/comprovantes.py — consultar](../../src/comprovantes.py#L34).

```python
def consultar(token,pedido_id):
    registro = _validos().get(sha256(token.encode()).hexdigest())
    return registro if registro and registro['id']==pedido_id else None
```

O hash do token procura uma autorização válida na sessão e o pedido precisa coincidir. Conhecer um número de pedido não basta para listar recibos de outras pessoas.

### Proteção de alteração por sessão

Fonte: [src/seguranca.py — csrf_valido](../../src/seguranca.py#L40).

```python
def csrf_valido():
    from .validacao_http import parametros_unicos
    if not parametros_unicos(request.args) or not parametros_unicos(request.form):
        return False
    esperado = session.get("csrf", "")
    recebido = request.headers.get("X-CSRF-Token", "") or request.form.get("csrf_token", "")
    origem = request.headers.get("Origin")
    if origem and origem != request.host_url.rstrip("/"):
        return False
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        return False
    return bool(esperado and igual(recebido, esperado))
```

A função compara o token recebido com o token da sessão. Ela precisa ser aplicada junto à autenticação e às permissões da rota; isoladamente não identifica qual usuário pode executar uma ação.


## 8. Instalação, configuração e validação

| Arquivo ou grupo | Papel na entrega |
| --- | --- |
| `Compilar aplicativo.ps1`, `DeliveryBot.spec`, `Funcionario.spec` | Preparar dependências e empacotar aplicações e recursos. O cliente final recebe executáveis |
| `packaging/Instalador.cs`, `InstaladorFuncionario.cs`, `Desinstalador.cs` e `criar_instalador.py` | Instalar/remover a aplicação e construir os instaladores; atualizações preservam os dados de uso |
| `preparar_whatsapp.py`, `preparar_tunel.py`, `cloudflared.json`, `criar_icone.py` | Preparar componentes integrados, conector verificado e ícones de distribuição |
| `distribuicao.py`, `assinar.ps1`, `verificar_assinatura.ps1`, `assinatura.json` | Guias, metadados, integridade por hash e assinatura. Um hash confere bytes; não comprova sozinho a identidade do editor |
| `versionar.py`, `verificar_projeto.py`, `limpar_pasta.py` | Sincronizar versões, verificar arquivos/configuração e planejar limpeza segura de distribuições e caches |
| `benchmark_desempenho.py` | Medir operações com banco e notas fictícios, incluindo comparação alternada do contexto |
| `evidencias_tcc.py`, `avaliacao_tcc.py` | Consolidar evidências técnicas e analisar registros de pesquisa. Não fabricam avaliações de usuários nem respostas de IA |
| `auditar_dependencias.py`, `servidor_seguranca.py`, `validar_zap.py` | Auditoria e validação do ambiente de teste de segurança |
| `requirements*.txt`, `package.json` e lockfiles | Registrar dependências de execução, compilação e testes. Não devem conter credenciais |
| `.github/workflows/validar.yml` | Verificar versões/sintaxe, testar regras e WhatsApp simulado, auditar segurança, compilar e testar executáveis Windows |
| `tests/` | Casos de domínio, concorrência, privacidade, permissões, conexão, documentos e interface. Testes simulados não equivalem a uma homologação de conta real |
| `.env.example`, `gerar_segredos.py`, `definir_senha_cozinha.py`, `testar_ia.py`, `wsgi_qa.py` e `render.yaml` | Exemplos e manutenção de desenvolvimento/servidor; a configuração real e os segredos ficam fora do Git |

`VERSION` identifica a versão do produto; `CHANGELOG.md` descreve alterações; a tag preserva o commit de versão. O pull request só é integrado depois da validação obrigatória. Executáveis, bancos, sessões, credenciais e logs de uso não são fonte versionada.

## 9. Decisões e limites que precisam ser explicados

- O cofre Obsidian fornece contexto editorial. Editar uma nota não treina nem modifica os pesos de uma rede neural.
- O modelo pode falhar, demorar ou inventar informações. O aplicativo aplica regras e validações e oferece atendimento humano; isso não garante que toda resposta gerada será correta.
- O gateway do túnel usa uma lista de rotas permitidas. A gestão remota possui controle próprio; um domínio HTTPS válido não substitui autenticação e autorização.
- Perfis, sessões e dispositivos têm verificações no backend. O Obsidian explica políticas, mas não é a autoridade que concede permissões.
- SQLite é local ao responsável. Terminais usam uma API autorizada, em vez de abrir diretamente o arquivo do banco pela rede.
- A escolha de Pix/cartão/dinheiro e os registros do caixa não constituem uma integração automática com banco ou adquirente.
- Backups, minimização, auditoria e remoção de identificação são medidas técnicas de privacidade. A operação real continua exigindo decisões e procedimentos do responsável.
- Uma conexão temporária pode mudar de endereço; computadores desligados ou internet indisponível interrompem recursos dependentes deles. Não apresente a solução como serviço com disponibilidade garantida.
- Testes automatizados verificam cenários definidos. Avaliações de qualidade do modelo, experiência de usuários e desempenho de produção exigem coleta separada.

## 10. Roteiro de demonstração e estudo

1. Apresente o problema e os atores: responsável, funcionário e cliente.
2. Mostre `desktop.py` e explique como a interface e o servidor local se encontram.
3. Acompanhe um produto até `pedidos.py` e identifique validação, transação, estoque e fila.
4. Mostre o caminho alternativo de compra pela conversa e a confirmação explícita.
5. Explique `processamento.py` e a diferença entre erro antes de enviar e envio incerto.
6. Abra `cerebro.py` e uma nota fictícia aprovada; diferencie consulta editorial de treinamento.
7. Mostre um acesso de funcionário e a revalidação de autorização dentro da operação financeira.
8. Execute os testes pertinentes e abra o Actions do commit da versão.
9. Apresente a comparação medida, o conteúdo preservado e os limites da medição.

Para estudar uma alteração, siga a ordem: interface ou evento de entrada, rota, validação de acesso, regra comercial, transação, resposta, teste. Não tente decorar todos os arquivos de uma vez; escolha um fluxo e localize suas chamadas.

## 11. Conferência antes de apresentar

Use somente catálogo, clientes e credenciais fictícios na demonstração. Não exiba `.env`, tokens Meta, sessões WhatsApp, caminhos privados ou backups reais. Confira a versão e o commit, rode os testes escolhidos e prepare uma demonstração alternativa se a rede ou o modelo não responderem. Consulte [Arquitetura e requisitos](ARQUITETURA_E_REQUISITOS.md), [Evidências](EVIDENCIAS.md) e [Avaliação](AVALIACAO.md) para relacionar a explicação técnica ao trabalho acadêmico.
