# Qualidade e confiabilidade dos pedidos

## Preservação da operação — 2.49.1

Cada pedido guarda nome, telefone, CEP e endereço informados naquela compra. Uma nova compra ou a atualização automática do cadastro do mesmo telefone não reescreve o pedido anterior, a fila, a lista do caixa ou o recibo. Os campos públicos da API continuam os mesmos. Na atualização de um banco antigo, a migração conserva os dados ainda disponíveis; ela não recupera endereços históricos que já tenham sido sobrescritos antes desta versão. Dados desconhecidos permanecem vazios. Confira entregas antigas em andamento após atualizar.

A correção explícita de cadastro, com identidade confirmada pelo responsável, continua abrangendo os registros do titular. A remoção de identificação também apaga os novos campos dos pedidos, preservando os itens e totais e impedindo a remoção enquanto houver pedidos em andamento. Backups antigos exigem a mesma revisão de privacidade já descrita no guia.

A conexão do WhatsApp não pode ser trocada enquanto houver tarefas pendentes ou resultados incertos. A fila confere o transporte antes de reservar e enviar respostas. Trocar tokens da mesma conta continua permitido; trocar provedor, endpoint, sessão ou número exige concluir ou revisar as tarefas. Uma inconsistência interrompe o envio para conferência, sem encaminhar a mensagem por outra conta. Notificações diretas e PDFs usam a sessão ativa configurada, em vez de uma sessão antiga lembrada no cadastro do contato; eventos de outra sessão não atualizam esse cadastro.

Tarefas anteriores à atualização podem não conter o vínculo com a conexão de origem. Elas ficam preservadas para conferência, sem envio automático. Quando a origem não puder ser confirmada, descarte a tarefa pelo painel e solicite uma nova mensagem do cliente na conexão atual. A retomada normal continua disponível para tarefas cujo vínculo permanece válido.

O cadastro de produto e o simulador preservam texto, foto e alterações feitas durante uma requisição. Uma criação confirmada recebe seu ID antes do próximo salvamento, evitando repetir o cadastro. A limpeza agendada do histórico continua sendo tentada mesmo quando o backup falha; os marcadores de sucesso são independentes, e o painel mantém o aviso de falha.

## Foco do atendimento

A versão 2.49.0 resolve o assunto atual antes da inferência. O foco é temporário: identifica os produtos pelo catálogo permitido e os aspectos pedidos, sem criar memória permanente nem ampliar permissões. O histórico enviado ao modelo contém somente antecedentes necessários à continuação; uma pergunta nova independente recebe apenas a entrada atual. Respostas anteriores do assistente não escolhem produtos pelo cliente.

O circuito Ollama oferece somente fontes compatíveis com esse foco e continua montando a resposta no aplicativo. Preço, descrição e dados operacionais são selecionados separadamente. Notas de conhecimento com assunto ou produto extra são excluídas inteiras, preservando condições e ressalvas. Uma pergunta ambígua sobre produto é esclarecida localmente; perguntas sobre prazo encaminham à equipe e não usam o horário de funcionamento ou o tempo de preparo como promessa.

Perguntas compostas associam os aspectos a cada produto: “preço de X e ingredientes de Y” não libera ingredientes de X nem preço de Y. Uma associação ambígua pede esclarecimento. Perguntar se um produto contém lactose é tratado como composição, sem acrescentar o saldo de estoque.

Os testes usam catálogos e notas fictícios e modelos simulados. Cobrem mudança de assunto, continuações, produtos negados ou ambíguos, consulta composta, ausência de fonte e tentativa de selecionar referências alheias. Isso valida os controles e os casos reproduzidos; não mede satisfação, qualidade geral de um modelo real nem tempo de entrega do WhatsApp. O provedor remoto recebe referências reduzidas, mas não usa o renderizador fechado do Ollama.

## Limpeza de código

A revisão da versão 2.45.1 removeu três funções internas sem referências no repositório (`gerar_segredo_sugerido`, `_webhook_exibicao` e `obter_pedido_por_numero`), a constante não utilizada `FINAIS`, nove importações sem uso e três vínculos locais desnecessários. As chamadas de criação de operador e abertura de caixa continuam sendo executadas no teste do aplicativo.

As referências foram conferidas no Python, nos arquivos do navegador, nos scripts, na documentação e no empacotamento. A geração de segredos continua no utilitário `gerar_segredos.py`; a consulta de pedidos em uso continua em `obter_pedido`. Rotas Flask, métodos expostos ao navegador e configurações de bibliotecas podem ser chamados dinamicamente: um alerta isolado de análise estática não justifica removê-los.

Para reproduzir a análise, use Pyflakes 3.4.0 nos diretórios `src` e `packaging` e nos scripts Python da raiz, em ambiente de desenvolvimento separado. Vulture 2.14 ajuda a levantar candidatos, mas suas conclusões precisam ser conferidas pelas referências. Essas ferramentas não são dependências do aplicativo distribuído. A validação da limpeza executa a suíte Python completa antes e depois, os testes JavaScript e o workflow do commit atual, incluindo compilação e testes dos executáveis com dados fictícios.

## Consolidação de recursos e manutenção

Na versão 2.45.2, `gestao.css` passou a reunir as regras de layout, conexão e tema, mantendo a ordem anterior da cascata. Painel e login usam a mesma fonte de estilos. `administracao.js` reúne contas e atualizações em um escopo privado, preservando autenticação, CSRF, confirmação e verificação de assinatura. O painel carrega três recursos a menos; isso não constitui uma medição de tempo de inicialização.

A imagem exploratória da marca e o simulador legado `src/main_teste.py` saíram da árvore atual; o histórico Git os conserva. A fonte vetorial, os ícones finais e os testes completos de pedidos permanecem. O README funciona como índice dos guias operacionais, reduzindo instruções duplicadas; a documentação acadêmica foi preservada.

A geração de hashes depois da assinatura está em `python packaging/distribuicao.py --hashes --distpath dist/v<versão>`. A opção exige os quatro executáveis e recalcula o manifesto somente para arquivos conhecidos, sem copiar novamente guias ou metadados. Para conferir a distribuição final, use `--verificar` em uma chamada separada. Os testes cobrem documentos preservados, executável ausente, exclusão de arquivos privados do manifesto, recursos servidos no painel/login, temas e operações administrativas no navegador.

## Validação do carrinho

A cotação e a gravação leem os produtos em lotes de até 400 IDs. Não há cache de preços ou estoque. Itens repetidos são somados antes de conferir o saldo, e valores monetários continuam usando Decimal e arredondamento por item. A cotação mantém um snapshot de leitura, enquanto a gravação mantém a transação de escrita existente.

Uma comparação local no Windows, com SQLite temporário e produtos fictícios, executou duas rodadas de aquecimento e sete amostras por condição. A referência foi o commit `139e6b1`; as saídas antigas e novas foram comparadas integralmente.

| Produtos distintos no carrinho | Consultas antes | Consultas depois | Mediana antes | Mediana depois |
| --- | ---: | ---: | ---: | ---: |
| 120 | 240 | 1 | 4,545 ms | 3,292 ms |
| 850 | 1.700 | 3 | 30,481 ms | 21,783 ms |

Essas medições cobrem a resolução dos itens em uma conexão aberta, não a compra completa, o Ollama, a rede ou a inicialização do aplicativo. Os testes automatizados usam a quantidade de consultas como limite de regressão, sem exigir tempos específicos do equipamento. Também simulam alteração concorrente de preços entre lotes.

## Consulta de endereço

A resposta ViaCEP precisa conter um objeto válido, o CEP solicitado, cidade e UF reconhecida. Campos inesperados não autorizam a entrega nem provocam uma falha interna. CEPs gerais podem ter rua e bairro vazios.

Endereços públicos válidos por CEP são reutilizados em memória por cinco minutos, com limite de 256 entradas. Nome, número e complemento não entram no cache. Cada chamada confere novamente a lista de cidades atendidas; erros e indisponibilidade não ficam em cache. A conexão tem prazos de conexão e leitura e não segue redirecionamentos.

## Comprovante após confirmação

Depois de salvar o pedido, o servidor responde com redirecionamento HTTP 303 para uma página de comprovante. Atualizar essa página faz somente uma leitura: não cria outra compra, não altera o estoque e não repete mensagens WhatsApp. O link original continua aceitando uma única compra.

O comprovante exige o token e a sessão assinada do mesmo navegador que confirmou o pedido. O cookie contém somente hash do token, ID, prazo e flags de confirmação; não contém nome, telefone ou endereço. São guardadas até cinco autorizações, por oito horas, sem renovação pela consulta. A página usa `no-store` e não oferece uma listagem pública de pedidos.

Outro navegador, sessão removida ou expirada e pedido indisponível recebem acesso indisponível. Reiniciar o aplicativo ou o servidor pode invalidar a sessão. Portanto, o cliente deve imprimir ou salvar o PDF se precisar guardar o comprovante. Uma conexão interrompida antes de o navegador receber a sessão também pode impedir a recuperação; o sistema mantém a proteção contra uma segunda confirmação.

O servidor também compara o cliente do pedido com o telefone vinculado ao link. Uma associação inconsistente no banco não libera o comprovante, mesmo se os demais identificadores coincidirem. Os testes de isolamento usam clientes, telefones e navegadores distintos e tentativas de troca de token e ID. Testes adicionais alteram associações internas em um banco fictício para verificar essa segunda barreira; isso não equivale a demonstrar uma invasão pública nem reproduz, por si só, um relato ocorrido em uma instalação específica.

## Testes

Na revisão 2.49.4, novas regressões cobrem revogação concorrente de administrador durante a preparação de alterações de contas, primeiro cadastro concorrente, custos ocultos para atendentes no avanço de pedidos, assinaturas Meta malformadas, desafio de verificação como texto simples e redução do token de verificação nos logs. A restauração verifica uma cópia isolada, incluindo capacidade de migração, chaves, índices únicos, referências e preservação do banco atual quando o backup é recusado. O esquema original da versão 2.2.0 também foi validado localmente; os testes automatizados incluem um esquema legado com migrações pendentes.

O OWASP ZAP 2.17.0 instalado foi executado em modo passivo contra uma loja fictícia exposta somente em `127.0.0.1:5030`, com escopo restrito, envio de formulários desativado e sem contas ou mensagens reais. O plano terminou com 57 verificações aprovadas, quatro avisos e zero bloqueios de risco alto ou controles essenciais. Os avisos foram: versão do servidor de desenvolvimento do laboratório (10036), permissão de estilos inline na CSP existente (10055) e identificações informativas de aplicação e sessão (10109 e 10112). A revisão não trata esses avisos como uma prova de exploração. O ajuste da política de estilos permanece uma melhoria própria da interface, e o cabeçalho do servidor de desenvolvimento não representa o executável de produção.

O scanner não exercita os privilégios internos nem a restauração: esses controles são verificados pelos testes com perfis e bancos fictícios. Os relatórios locais são gerados em `artifacts/zap-v2494.json` e `artifacts/zap-v2494.html`, sem entrar no Git. As regressões e a política ZAP também seguem na validação do GitHub; a análise passiva das páginas alcançadas não é certificação de ausência de falhas.

- `tests/test_carrinho_lote.py`: consultas, agrupamento, precisão, preços atuais, custos internos e snapshot concorrente.
- `tests/test_viacep.py`: respostas malformadas, recuperação após timeout, validade e limite do cache e regras de área de entrega.
- `tests/test_comprovante.py`: redirecionamento, atualização sem efeitos, isolamento entre navegadores, prazo, limite de sessão e pedido indisponível.
- As suítes existentes de compra, publicação, segurança, estoque, conversa e QA também são executadas, com dados fictícios e sem contas reais.
