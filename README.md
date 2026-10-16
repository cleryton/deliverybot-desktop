# DeliveryBot Desktop

Aplicativo Windows para cadastrar produtos de qualquer categoria, controlar estoque e receber pedidos pelo WhatsApp. Inclui atendimento humano, permissões por funcionário, backups criptografados e página de pedidos com túnel Cloudflare integrado.

O atendimento responde dúvidas simples diretamente com o cadastro, usa contexto recente na IA e apresenta links validados para cada cliente. O túnel confirma a página HTTPS antes de liberar os pedidos, acompanha reconexões e atualiza respostas pendentes para o endereço atual. O catálogo público tem busca, carrinho revisável e layout adaptado ao celular. Para manter links já enviados válidos entre reinícios, configure o domínio fixo em **Página de pedidos**.

## Instalar e usar

Dentro de `dist/`, consulte `LEIA-ME.txt` e abra a pasta da versão indicada em `VERSION`. Execute `Instalar-DeliveryBot.exe` para instalar ou `DeliveryBot.exe` para usar diretamente. O usuário final não precisa instalar Docker, Node.js ou Python. Para IA local, configure o Ollama em **WhatsApp e IA**. O seletor **Tema** permite usar modo claro, escuro ou acompanhar o Windows; a preferência continua após reabrir o aplicativo. Use **Guia de configuração** para seguir o tutorial básico.

Use o [guia do aplicativo](GUIA%20DO%20APLICATIVO.md) para configurar a loja, cadastrar produtos, conectar o WhatsApp e iniciar a página de pedidos. Os procedimentos de proteção dos dados estão em [Privacidade e segurança](PRIVACIDADE%20E%20SEGURAN%C3%87A.md).

Os dados, configurações, backups e sessão do WhatsApp do aplicativo ficam em `%LOCALAPPDATA%\DeliveryBot`, separados do código e da distribuição. Não apague essa pasta para atualizar o aplicativo. Para encerrar o atendimento, use **Sair do aplicativo** no painel ou **Sair e interromper atendimento** no ícone perto do relógio.

## O que existe nesta pasta

| Arquivo ou pasta | Finalidade |
| --- | --- |
| `dist/LEIA-ME.txt`, `dist/v<versão>/` | Indicação da versão pronta, aplicativo, instalador, metadados, hashes, guia e licenças. A limpeza mantém a atual e uma anterior íntegra. |
| `desktop.py`, `src/`, `web/`, `sql/`, `data/cardapio.json` | Código, interface, estrutura do banco e catálogo de exemplo usados pelo aplicativo e pelos testes. |
| `packaging/`, `DeliveryBot.spec`, `Compilar aplicativo.ps1` | Compilação, instalador, integridade e assinatura. |
| `whatsapp-native/`, `cloudflare/runtime/` | Código, dependências e componentes incluídos no executável. |
| `.venv/`, arquivos `requirements*.txt` | Ambiente e dependências para desenvolver, testar e compilar. |
| `tests/` | Verificações de pedidos, estoque, segurança e integrações. |
| `.env.example`, `definir_senha_cozinha.py`, `gerar_segredos.py`, `testar_ia.py` | Exemplos e utilitários para manutenção do modo servidor; não são exigidos para abrir o aplicativo instalado. |
| `.git/`, `AGENTS.md`, `VERSION`, `CHANGELOG.md`, `.gitignore` | Histórico Git, instruções, versões e exclusões de arquivos privados. |

As integrações com WAHA externo e Meta continuam disponíveis. Dependências de desenvolvimento, componentes incluídos no executável, código e catálogo de exemplo são necessários e permanecem separados dos dados de uso.

`build/`, `artifacts/`, `.pytest_cache/` e `__pycache__/` podem reaparecer ao compilar ou testar; são arquivos temporários, ignorados pelo Git. Não apague bancos, credenciais, backups ou sessões para limpar espaço.

Para manutenção, `python packaging/limpar_pasta.py` mostra o plano e `python packaging/limpar_pasta.py --aplicar` remove somente versões antigas e caches reconhecidos. É necessário ter uma distribuição atual completa e com integridade válida; a atual e a anterior válida são preservadas. Arquivos desconhecidos, distribuições futuras e diretórios com dados ou vínculos ficam de fora. Arquivos de testes em `artifacts/` precisam de revisão separada; não são apagados por essa ferramenta.

Uma página de pedidos não é hospedada em `<nome-da-loja>.whatsapp.com`. Use o endereço real gerado pela Cloudflare ou um domínio sob seu controle configurado em **Página de pedidos**. Respostas automáticas aceitam links privados gerados pelo aplicativo e links comerciais cadastrados; sites inventados pela IA são bloqueados. Links já enviados para endereços inexistentes não mudam: após atualizar, o cliente pode digitar **2** para receber um novo link.

## Desenvolvimento e compilação

Para compilar no Windows, o desenvolvedor precisa de Python 3.12 e Node.js/npm. Execute `Compilar aplicativo.ps1` no PowerShell: ele prepara as dependências, executa os testes, inclui os componentes WhatsApp e Cloudflare e gera os executáveis em `dist/v<versão>/`. A finalização copia guias e licenças, grava `VERSAO.json`, confere os hashes de todos esses arquivos e testa o executável com dados fictícios. O script faz uma compilação limpa para evitar módulos antigos em cache. Para reconferir uma distribuição, use `python packaging/distribuicao.py --verificar`.

Também é possível executar os testes com `.venv/Scripts/python.exe -m pytest -q` e os testes do componente WhatsApp com `npm test` dentro de `whatsapp-native`.

Para manutenção do modo servidor, copie `.env.example` para `.env`, configure as credenciais e execute `python -m src.app`. O provedor `TESTE` não envia mensagens reais. Não exponha o servidor de desenvolvimento nem o painel administrativo diretamente à internet; o gateway público do aplicativo limita as rotas acessíveis.

## Versões

A versão atual está em [VERSION](VERSION) e o histórico em [CHANGELOG.md](CHANGELOG.md). Cada pedido que alterar arquivos versionados gera um commit e uma tag conforme [AGENTS.md](AGENTS.md). Executáveis, dados pessoais, credenciais e dependências instaladas não são versionados.

Repositório: [cleryton/deliverybot-desktop](https://github.com/cleryton/deliverybot-desktop). Downloads publicados: [releases](https://github.com/cleryton/deliverybot-desktop/releases).

## Projeto acadêmico e TCC

As [medições de desempenho](docs/DESEMPENHO.md) descrevem as otimizações do painel, do contexto editorial e da importação do backend, com cenários fictícios, comandos reproduzíveis e limites dos resultados.

A [base para o TCC](docs/tcc/README.md) reúne texto acadêmico editável, arquitetura, requisitos ligados aos testes, protocolo de avaliação, referências e roteiro para a banca. O recorte diferencia validação comercial e geração de respostas com conhecimento editorial; identifica resultados técnicos existentes e as avaliações de IA e usabilidade ainda pendentes. `packaging/evidencias_tcc.py` resume relatórios JUnit em `artifacts/tcc/`, com hashes e contagens sem copiar nomes, mensagens ou saídas dos testes. Consulte as condições de reprodução e os limites do relatório antes de usar os números no trabalho.

O [laboratório DB-TCC-1](docs/tcc/LABORATORIO.md) prepara 72 tentativas A/B e analisa medidas registradas pelo pesquisador com `packaging/avaliacao_tcc.py`. Mantém falhas, timeouts e bloqueios separados, informa denominadores e não atribui respostas locais ou de fallback ao modelo. Não executa inferência nem fabrica resultados. O [material de entrega acadêmica](docs/tcc/ENTREGA_ACADEMICA.md) reúne links do código, descrição das mudanças, trechos principais e roteiro opcional de vídeo; o resumo expandido ainda exige revisão no modelo institucional.

## Aplicativo dos funcionários e caixa individual

O [DeliveryBot Funcionário](GUIA%20DO%20FUNCIONARIO.md) é um segundo aplicativo Windows para computadores da rede da loja. Registra pedidos manuais de balcão no mesmo banco e fila, com permissões de Caixa, pareamento de dispositivo, HTTPS e autenticação individual. Abertura, recebimentos, troco, sangria, suprimento e fechamento permitem conferir o dinheiro esperado, separando Pix e cartão. O responsável configura e acompanha em **Caixas dos funcionários**; o terminal acessa somente seus próprios pedidos e caixas. O Obsidian contém guias operacionais, sem armazenar valores financeiros ou executar operações.

### Pedidos pela conversa e memória editorial

O cliente pode escolher **PEDIDO PELO WHATSAPP** para comprar sem abrir o link. O rascunho é privado no SQLite, com validade de 30 minutos, resumo calculado pelo cadastro e confirmação explícita. A transação confere preço e saldo, registra pedido e fila, baixa somente estoque controlado e impede duplicação por repetição ou retentativa. Seleções ambíguas pedem a variação completa; alterações especiais devem ser encaminhadas a um atendente.

O cofre Obsidian inclui um guia operacional e o painel possui leitor de notas exclusivo do administrador. O Ollama usa a memória editorial como contexto; gravação comercial, preços e privacidade permanecem no aplicativo. Exportação e remoção de dados contemplam os rascunhos sem expor tokens.

## WhatsApp, HTTPS e mapa do atendimento

Ao salvar uma nova conexão LOCAL ou WAHA no aplicativo Windows, a preparação começa automaticamente. O túnel temporário fornece o endereço HTTPS; o aplicativo verifica DNS e destino antes de iniciar a sessão e liberar o QR Code no painel. Conectar WhatsApp repete a preparação em caso de falha. Domínio fixo exige configuração na Cloudflare. Mantenha o aplicativo aberto e a internet disponível para receber pedidos pelo link.

No cofre Obsidian, abra `Mapa do atendimento.md` ou a visualização em gráfico. O mapa liga os guias, o estilo e o conhecimento aprovado, e remove referências a conhecimento revogado ou vencido na próxima consulta do aplicativo. As notas existentes são preservadas. O mapa é gerado automaticamente; para mantê-lo manualmente, remova o comentário `DeliveryBot: mapa automático v1`. Os guias operacionais e o mapa não são enviados ao modelo e não executam pedidos ou conexões.

### Padrões individuais por segmento e atendimento

Configure **Meu comércio** com o segmento, a descrição e o modo de operação. O aplicativo prepara em `Atendimentos` o perfil adequado: restaurantes e alimentos, moda e acessórios, eletrônicos, oficinas e peças, lojas de produtos, produção e encomendas, serviços e agendamentos, produtos e serviços ou atendimento geral. O segmento cadastrado tem preferência; a descrição e o modo de operação servem como apoio. Uma pergunta de cliente não muda o segmento da loja.

Cada pasta contém `Perfil.md` e seis notas: **Recepção**, **Dúvidas**, **Escolha**, **Fechamento**, **Pós-venda** e **Atendimento humano**. Edite cada uma com seu tom, perguntas úteis e exemplos fictícios. O Ollama lê o perfil e a etapa relacionada à mensagem, além do estilo e do conhecimento pertinente; a classificação da etapa é aproximada e orienta somente a escrita. Pedidos e outras operações continuam no fluxo oficial do aplicativo.

Em **WhatsApp e IA**, confira o perfil ativo e clique em **Visualizar notas**. `Atendimentos/Como personalizar.md` explica a organização, e `Mapa do atendimento.md` conecta os padrões ativos no Graph. Para suspender uma nota, use `atendimento: false`; para limitar sua validade, acrescente `valido_ate: AAAA-MM-DD`. Preserve `categoria_atendimento` e `etapa_atendimento`. Identificação incorreta, validade vencida ou aprovação ambígua impedem o uso.

Ao mudar o perfil, as edições antigas ficam preservadas na pasta anterior e saem do contexto da nova categoria. Os backups criptografados incluem essas notas. A próxima resposta lê suas alterações sem treinar a rede neural. Não inclua conversas nem dados de clientes; preços, estoque, reservas e condições comerciais precisam de confirmação no cadastro ou pela equipe.

### Jogar enquanto espera

Após confirmar pelo site, abra **Jogar pingue-pongue** e toque em **Jogar**. No celular, arraste o dedo na mesa ou segure os botões de seta; no computador, use mouse, ↑/↓ ou W/S. A raquete verde é sua. A partida termina em cinco pontos e oferece dificuldade Leve ou Normal, pausa e reinício. Trocar de aba ou fechar a área do jogo pausa a partida; toque em Continuar para retomar.

**Abrir somente o jogo em outra aba** abre `/jogar` no mesmo endereço HTTPS da loja, sem o link pessoal do pedido. Essa página também pode ser reaberta enquanto o túnel estiver disponível. A partida roda no navegador, sem cadastro, cookies próprios, gravação do placar ou envio de dados a terceiros. O jogo não consulta o preparo: acompanhe as atualizações do pedido pelo WhatsApp. Sem JavaScript, o recibo e a confirmação continuam disponíveis.

### Verificar e recuperar Ollama e Obsidian

Em **WhatsApp e IA → Verificação e recuperação do atendimento**, use **Verificar e recuperar agora**. Para acompanhar quedas enquanto o aplicativo estiver aberto, marque **Recuperar Ollama automaticamente**. A opção começa desativada e é exclusiva do administrador no Desktop. A verificação ocorre a cada 30 segundos e informa se o serviço respondeu, se o modelo está instalado e se o estilo do cofre pode ser lido. Três falhas consecutivas de inferência também sinalizam um problema de preparação. O estado técnico não garante a qualidade de cada resposta.

A recuperação inicia somente o Ollama local instalado e prepara o modelo configurado já baixado, sem mudar o provedor de IA. Faz no máximo três tentativas consecutivas, com espera crescente entre elas. Desativar a opção, trocar o provedor/modelo ou encerrar o aplicativo impede novas ações pendentes. O botão manual permite reavaliar o problema após corrigir a instalação ou a memória disponível. Um modelo ausente precisa ser escolhido ou baixado pelo botão específico; serviço remoto exige intervenção na máquina correspondente.

No Obsidian, **Estado do funcionamento.md** mostra um resumo técnico sem caminhos, segredos, mensagens ou dados de clientes, e **Verificação e recuperação do atendimento.md** explica as ações e limitações. O mapa liga essas notas. Elas não são enviadas como conhecimento editorial ao modelo; o Ollama recebe um sinal oficial de estado e não pode executar comandos de notas. Para preservar uma edição manual da nota de estado, remova seu marcador automático.

A estrutura do cofre pode ser preparada com arquivos padrão ausentes; conteúdos existentes, notas revogadas, vazias ou inválidas são preservados para revisão. Se o cofre não puder ser lido, o atendimento usa as regras e o catálogo do aplicativo, sem presumir o conteúdo das notas. A recuperação não instala programas, baixa modelos, reinicia o computador, conecta contas WhatsApp ou reenvia mensagens. O túnel HTTPS mantém sua própria rotina de reconexão.
