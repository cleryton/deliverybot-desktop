# DeliveryBot Desktop

Aplicativo Windows para cadastrar produtos de qualquer categoria, controlar estoque e receber pedidos pelo WhatsApp. Inclui atendimento humano, permissões por funcionário, backups criptografados e página de pedidos com túnel Cloudflare integrado.

O atendimento responde dúvidas simples diretamente com o cadastro, usa contexto recente na IA e apresenta links validados para cada cliente. O túnel confirma a página HTTPS antes de liberar os pedidos, acompanha reconexões e atualiza respostas pendentes para o endereço atual. O catálogo público tem busca, carrinho revisável e layout adaptado ao celular. Para manter links já enviados válidos entre reinícios, configure o domínio fixo em **Página de pedidos**.

## Instalar e usar

Consultas locais conhecidas têm um consumidor reservado: uma saudação de outra pessoa pode ser atendida mesmo quando os dois consumidores gerais estão ocupados. Perguntas diretas compostas, como horário e endereço, usam o cadastro sem inferência. A IA atende somente assuntos do negócio; perguntas alheias ou sem relação clara recebem uma orientação local. As notas do Obsidian ajustam o atendimento, sem ampliar esse escopo. O tempo de geração do Ollama e a entrega pelo WhatsApp ainda dependem do computador e da conexão. O [laboratório QA](docs/HOSPEDAGEM%20QA.md) usa uma lanchonete inteiramente fictícia, separada da loja instalada.

Dentro de `dist/`, consulte `LEIA-ME.txt` para localizar a distribuição atual. Execute `Instalar-DeliveryBot.exe` para instalar ou `DeliveryBot.exe` para usar diretamente. O usuário final não precisa instalar Docker, Node.js ou Python. Para IA local, configure o Ollama em **WhatsApp e IA**. O seletor **Tema** permite usar modo claro, escuro ou acompanhar o Windows; a preferência continua após reabrir o aplicativo. Use **Guia de configuração** para seguir o tutorial básico.

Use o [guia do aplicativo](GUIA%20DO%20APLICATIVO.md) para configurar a loja, cadastrar produtos, conectar o WhatsApp e iniciar a página de pedidos. Os procedimentos de proteção dos dados estão em [Privacidade e segurança](PRIVACIDADE%20E%20SEGURAN%C3%87A.md).

Os dados, configurações, backups e sessão do WhatsApp do aplicativo ficam em `%LOCALAPPDATA%\DeliveryBot`, separados do código e da distribuição. Não apague essa pasta para atualizar o aplicativo. Para encerrar o atendimento, use **Sair do aplicativo** no painel ou **Sair e interromper atendimento** no ícone perto do relógio.

O menu separa tarefas diárias, preparação do atendimento e administração. Use **Encontrar uma tela** para localizar opções pelo nome ou por termos como WhatsApp, estoque e horário. A página inicial destaca o próximo passo e os atalhos do dia a dia. **Configurações** e **Meu comércio** avisam sobre alterações não salvas antes de trocar de tela ou atualizar. No pedido do cliente, as quantidades podem ser ajustadas diretamente no resumo, inclusive pelo celular.

O painel evita sobrepor consultas de publicação e atualização em conexões lentas e descarta respostas anteriores a uma alteração. O catálogo PDF público tem limites de frequência e de geração simultânea para preservar recursos. Alterações concorrentes de pedidos exigem conferir o estado atualizado antes de tentar novamente.

O atendimento da IA usa o segmento definido em **Meu comércio**. Uma lanchonete não passa a atender mecânica por conter uma peça antiga no catálogo. A operação mista permite as atividades cadastradas; notas do Obsidian não ampliam essa autorização. Perguntas vagas recebem orientação local. Consulte o [relatório do projeto](docs/tcc/RELATORIO_DO_PROJETO.md) para entender arquitetura, melhorias, módulos e limites.

No atendimento Ollama, o modelo escolhe somente ação, fontes e tom; o aplicativo valida a proposta e monta a resposta com informações autorizadas. Conhecimento factual do Obsidian exige aprovação e categoria explícita do perfil ativo. Notas alteradas durante a geração invalidam a resposta em andamento. Arquivos antigos são preservados para revisão, com orientação no leitor e no guia **Circuito comercial** do cofre. As notas não substituem preços, estoque, pagamentos ou funcionamento do cadastro. Esses controles não dispensam a revisão dos fatos pela equipe.

O foco do atendimento limita as referências ao produto e à informação perguntados. Perguntar ingredientes não libera preços ou pagamentos; mudar de produto encerra o contexto anterior. Uma continuação como “e o preço?” só retoma uma escolha inequívoca do cliente. Sem essa referência, o aplicativo pergunta qual produto, sem chamar o modelo nem ler notas. Perguntas sobre prazo de entrega não são respondidas com o horário de funcionamento. No provedor remoto, as referências e o histórico também são reduzidos; a geração de texto continua sujeita aos limites desse provedor.

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

A limpeza reconhece os builds dos dois aplicativos. Nos builds, documentos de texto e HTML só são descartáveis quando têm os nomes oficiais de diagnóstico do PyInstaller; arquivos como `clientes.txt` e `manual.html` são preservados. A conferência de uma distribuição também recusa vínculos em pastas intermediárias das fontes. Não remova `.env`, banco, cofre, sessões, backups ou alterações pendentes para fazer o Git parecer limpo: preserve primeiro o trabalho em uma recuperação local identificada.

Uma página de pedidos não é hospedada em `<nome-da-loja>.whatsapp.com`. Use o endereço real gerado pela Cloudflare ou um domínio sob seu controle configurado em **Página de pedidos**. Respostas automáticas aceitam links privados gerados pelo aplicativo e links comerciais cadastrados; sites inventados pela IA são bloqueados. Links já enviados para endereços inexistentes não mudam: após atualizar, o cliente pode digitar **2** para receber um novo link.

## Desenvolvimento e compilação

Para compilar no Windows, o desenvolvedor precisa de Python 3.12 e Node.js/npm. Execute `Compilar aplicativo.ps1` no PowerShell: ele prepara as dependências, executa os testes, inclui os componentes WhatsApp e Cloudflare e gera os executáveis em `dist/v<versão>/`. A finalização copia guias e licenças, grava `VERSAO.json`, confere os hashes de todos esses arquivos e testa o executável com dados fictícios. O script faz uma compilação limpa para evitar módulos antigos em cache. Para reconferir uma distribuição, use `python packaging/distribuicao.py --verificar`.

Também é possível executar os testes com `.venv/Scripts/python.exe -m pytest -q` e os testes do componente WhatsApp com `npm test` dentro de `whatsapp-native`.

Para manutenção do modo servidor, copie `.env.example` para `.env`, configure as credenciais e execute `python -m src.app`. O provedor `TESTE` não envia mensagens reais. Não exponha o servidor de desenvolvimento nem o painel administrativo diretamente à internet; o gateway público do aplicativo limita as rotas acessíveis.

## Versões

A versão atual está em [VERSION](VERSION) e o histórico em [CHANGELOG.md](CHANGELOG.md). Cada pedido que alterar arquivos versionados gera um commit e uma tag conforme [AGENTS.md](AGENTS.md). Executáveis, dados pessoais, credenciais e dependências instaladas não são versionados.

Repositório: [cleryton/deliverybot-desktop](https://github.com/cleryton/deliverybot-desktop). Downloads publicados: [releases](https://github.com/cleryton/deliverybot-desktop/releases).

## Marca

A marca escolhida combina caixa e balão de conversa em verde esmeralda e menta, para representar comércios de diferentes categorias. A fonte final é [web/static/marca.svg](web/static/marca.svg). Após editá-la, execute `python packaging/criar_icone.py`: o comando sincroniza a cópia do terminal independente e gera o ícone Windows em sete resoluções, de 16 a 256 pixels. Os testes conferem transparência e sincronização. A proposta exploratória e seu histórico de criação permanecem no Git.

## Projeto acadêmico e TCC

O [guia do código](docs/tcc/GUIA_DO_CODIGO.md) explica os módulos, fluxos e trechos principais e inclui um roteiro para apresentar o sistema.

As [medições de desempenho](docs/DESEMPENHO.md) descrevem as otimizações do painel, do contexto editorial e da importação do backend, com cenários fictícios, comandos reproduzíveis e limites dos resultados.

A [base para o TCC](docs/tcc/README.md) reúne texto acadêmico editável, arquitetura, requisitos ligados aos testes, protocolo de avaliação, referências e roteiro para a banca. O recorte diferencia validação comercial e geração de respostas com conhecimento editorial; identifica resultados técnicos existentes e as avaliações de IA e usabilidade ainda pendentes. `packaging/evidencias_tcc.py` resume relatórios JUnit em `artifacts/tcc/`, com hashes e contagens sem copiar nomes, mensagens ou saídas dos testes. Consulte as condições de reprodução e os limites do relatório antes de usar os números no trabalho.

O [laboratório DB-TCC-1](docs/tcc/LABORATORIO.md) prepara 72 tentativas A/B e analisa medidas registradas pelo pesquisador com `packaging/avaliacao_tcc.py`. Mantém falhas, timeouts e bloqueios separados, informa denominadores e não atribui respostas locais ou de fallback ao modelo. Não executa inferência nem fabrica resultados. O [material de entrega acadêmica](docs/tcc/ENTREGA_ACADEMICA.md) reúne links do código, descrição das mudanças, trechos principais e roteiro opcional de vídeo; o resumo expandido ainda exige revisão no modelo institucional.

## Aplicativo dos funcionários e caixa individual

O [guia do funcionário](GUIA%20DO%20FUNCIONARIO.md) explica pedidos manuais, pareamento por computador, autenticação individual e abertura/fechamento de caixa. O responsável acompanha as operações no painel; o terminal usa a rede privada da loja e acessa somente seus pedidos e caixas.

### Pedidos pela conversa e memória editorial

O cliente pode pedir pelo link ou escolher **PEDIDO PELO WHATSAPP**. Se o HTTPS continuar indisponível na tentativa de recuperação, o bot oferece o catálogo em PDF. Preços, saldo e confirmação continuam no fluxo do aplicativo. Consulte [operação comercial](docs/OPERACAO%20COMERCIAL.md) para filas, falhas de envio e prevenção de duplicações.

## WhatsApp, HTTPS e mapa do atendimento

O [guia do aplicativo](GUIA%20DO%20APLICATIVO.md) reúne configuração, conexão, domínio fixo e solução de problemas. Para a API oficial, veja [Meta: produção e custos](docs/META%20PRODUCAO%20E%20CUSTOS.md). A [gestão remota](docs/ACESSO%20REMOTO.md) possui autorização própria e rotas restritas.

### Padrões individuais por segmento e atendimento

Configure **Meu comércio** e personalize as notas aprovadas em **WhatsApp e IA → Visualizar notas**. O cofre Obsidian organiza estilo, conhecimento e etapas de atendimento; funciona como contexto editorial, sem treinar a rede neural nem conceder permissões. As regras de aprovação, validade, mudança de segmento e backups estão no [guia do aplicativo](GUIA%20DO%20APLICATIVO.md).

### Jogar enquanto espera

O recibo oferece pingue-pongue no navegador, com controles para celular e computador. A partida é local e o preparo continua sendo acompanhado pelo WhatsApp. Consulte os controles e limitações no [guia do aplicativo](GUIA%20DO%20APLICATIVO.md).

### Verificar e recuperar Ollama e Obsidian

O administrador pode verificar o atendimento e habilitar a recuperação automática do Ollama local. O [guia do aplicativo](GUIA%20DO%20APLICATIVO.md) detalha tentativas, pausas, modelos e preservação das notas. O estado técnico não garante a qualidade das respostas.
