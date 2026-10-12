# Texto base da monografia

Título: DeliveryBot: desenvolvimento e avaliação de um aplicativo de atendimento e gestão de pedidos com inteligência artificial local e conhecimento editorial

Autor: [preencher] · Curso: [preencher] · Instituição: [preencher] · Orientador: [preencher]

## Resumo provisório

Este trabalho apresenta o desenvolvimento do DeliveryBot, um aplicativo desktop para atendimento conversacional e gestão de pedidos em pequenos comércios. A solução reúne catálogo, estoque opcional por produto, pedidos pelo navegador ou pela conversa, interface administrativa e recursos de proteção de dados. A personalização do atendimento utiliza notas Markdown compatíveis com Obsidian como contexto editorial para modelos executados pelo Ollama. Preços, disponibilidade e confirmação são verificados por regras da aplicação, independentemente da geração de texto. A pesquisa propõe uma abordagem de construção e avaliação de artefato, com testes automatizados, cenários de falha e protocolo de comparação de respostas. As evidências técnicas existentes demonstram comportamentos cobertos pelos testes, mas não estabelecem desempenho em produção ou satisfação de usuários. A avaliação de inferência e a avaliação com participantes deverão ser executadas e incluídas na versão final do trabalho.

Palavras-chave: atendimento conversacional; gestão de pedidos; inteligência artificial local; conhecimento editorial; engenharia de software.

Atualizar o resumo após concluir a coleta. Esta versão não contém resultados experimentais de usabilidade ou qualidade da IA.

## 1 Introdução

Em operações comerciais realizadas por mensagens, informações de catálogo, disponibilidade e andamento de pedidos precisam ser consultadas e registradas com consistência. Quando o atendimento e o registro da venda ocorrem em ferramentas distintas, a equipe pode precisar repetir tarefas ou conferir manualmente as informações. Essa situação motiva investigar uma aplicação que reúna atendimento e gestão, sem exigir configuração técnica recorrente do operador. Trata-se de uma motivação do projeto; a frequência e o impacto desse problema em comércios reais precisam de pesquisa bibliográfica ou levantamento de campo.

Modelos de linguagem podem produzir textos contextualizados, mas uma resposta plausível não comprova que uma operação foi executada. Um sistema de pedidos precisa conferir produtos, valores, dados essenciais e confirmação do cliente. Por isso, o DeliveryBot separa a geração da resposta da gravação comercial. A aplicação também diferencia produção sob demanda e revenda: a existência de um produto no catálogo não implica, necessariamente, controle de quantidade de unidades prontas.

O projeto foi desenvolvido como aplicativo Windows, com componentes auxiliares executados em segundo plano. A operação contempla cadastro, atendimento, montagem do pedido, confirmação e acompanhamento. A personalização editorial é feita por notas revisáveis, permitindo examinar quais orientações podem integrar o contexto de geração.

### 1.1 Problema de pesquisa

Como integrar atendimento conversacional personalizado e registro consistente de pedidos em um aplicativo desktop acessível ao operador, com controle sobre o conhecimento utilizado pela IA e avaliação verificável de seu funcionamento?

### 1.2 Objetivo geral

Desenvolver e avaliar um aplicativo desktop que integre atendimento conversacional, conhecimento editorial revisado e gestão de pedidos, preservando validações determinísticas nas operações comerciais.

### 1.3 Objetivos específicos

- Modelar perfis de comércio com estoque opcional por produto.
- Implementar pedidos pelo navegador e pela conversa com confirmação explícita e prevenção de duplicação.
- Organizar conhecimento editorial por segmento e etapa de atendimento, usando somente notas aprovadas e válidas.
- Disponibilizar diagnóstico de serviços, preparação do endereço público e recuperação limitada de falhas.
- Verificar controles de acesso, proteção dos dados e integridade das operações com testes automatizados.
- Comparar respostas com e sem conhecimento editorial e avaliar tarefas de uso em ambiente controlado.

### 1.4 Justificativa e recorte

A relevância técnica está na integração e na verificabilidade do artefato: informações comerciais têm origem identificável, orientações editoriais podem ser revisadas e operações possuem testes de regressão. A utilidade prática é uma hipótese a avaliar. Não se afirma originalidade de modelos de linguagem, do Obsidian ou de sistemas de pedidos isoladamente.

O recorte principal considera um operador Windows e dois cenários fictícios: comércio de produção sob demanda e comércio de revenda. Recursos como importação de documentos, catálogo PDF e minijogo são complementares e não constituem o eixo da pesquisa. Não fazem parte do recorte emissão fiscal, pagamento eletrônico liquidado, treinamento de modelo, operação em larga escala ou validação de todos os setores comerciais.

## 2 Fundamentação teórica

### 2.1 Pesquisa orientada à construção de artefatos

Peffers et al. (2007) propõem uma metodologia de pesquisa em Design Science que relaciona problema, objetivos da solução, construção, demonstração, avaliação e comunicação. Esse encadeamento orienta a proposta: o aplicativo é o artefato, os cenários demonstram seu funcionamento e as medidas permitem discutir sua adequação. A execução histórica do desenvolvimento foi incremental; o presente protocolo organiza uma avaliação a posteriori. Não se presume que todas as etapas de uma pesquisa formal já tenham sido realizadas.

### 2.2 Atendimento conversacional e contexto editorial

Ollama disponibiliza interfaces para inferência com modelos locais. Na solução, a aplicação compõe o contexto de geração a partir de regras, informações autorizadas e notas pertinentes à mensagem. A seleção de notas utiliza critérios textuais e metadados, sem exigir banco vetorial. Esse mecanismo é contextualização com recuperação editorial; não é ajuste fino ou aprendizado automático a partir de conversas.

A documentação do Obsidian descreve o Graph como representação das relações entre notas e links. No DeliveryBot, esse gráfico auxilia a revisão humana do conhecimento. O gráfico não representa conexões neuronais nem é executado como algoritmo de decisão comercial.

### 2.3 Consistência e segurança

Transações e verificações de repetição são aplicadas ao registro de pedidos para que a confirmação corresponda a uma operação persistida. O atendimento recebe os valores calculados pelo cadastro, enquanto o modelo não é considerado fonte oficial de estoque ou preço.

O OWASP ASVS oferece uma referência para verificar controles técnicos de aplicações web. O projeto usa testes de entradas, sessão, autorização, CSRF e exposição de rotas, além de análise passiva com ZAP. Essa cobertura não equivale a auditoria integral do ASVS. O ZAP Baseline observa respostas e rastreia páginas; não executa uma varredura ativa de invasão.

### 2.4 Dados pessoais na pesquisa

O guia da ANPD sobre fins acadêmicos orienta o tratamento de dados em estudos e pesquisas. Para este trabalho, o protocolo prioriza dados fictícios e coleta mínima. Caso participem pessoas, a instituição deverá orientar o procedimento aplicável, a base de tratamento e a necessidade de apreciação ética. Recursos técnicos de exportação, remoção e backup não substituem a definição institucional das responsabilidades.

As fontes e os endereços consultados estão em [Referências](REFERENCIAS.md). Complementar a fundamentação com estudos acadêmicos de atendimento conversacional e avaliação de interação humano-computador selecionados com o orientador.

## 3 Metodologia

A proposta é uma pesquisa aplicada, orientada ao desenvolvimento e à avaliação de um artefato de software. A avaliação técnica é experimental em ambiente controlado; eventual estudo com usuários terá caráter exploratório. Essas classificações descrevem o plano, sujeito à aprovação do orientador.

O processo compreende delimitação do problema, especificação de requisitos, desenvolvimento incremental, demonstração em dados fictícios, avaliação e comunicação. Os requisitos são vinculados a módulos e testes na [matriz de rastreabilidade](ARQUITETURA_E_REQUISITOS.md). O histórico Git permite identificar os estados avaliados e as alterações realizadas.

A avaliação combina três camadas. A primeira verifica comportamento funcional e falhas por testes automatizados. A segunda compara respostas geradas sob condições controladas, variando a presença de conhecimento editorial. A terceira observa tarefas de configuração, cadastro e acompanhamento de pedido. O [protocolo](AVALIACAO.md) define tarefas, medidas, critérios e limitações. As camadas ainda não executadas devem permanecer identificadas como planejamento.

## 4 Desenvolvimento

O aplicativo utiliza Python, Flask, SQLite e interface HTML, CSS e JavaScript em uma janela desktop. Os componentes WhatsApp e Cloudflare são distribuídos junto ao executável, sem exigir ferramentas de desenvolvimento na máquina do operador. O Ollama é um serviço separado, cuja instalação e modelo precisam estar disponíveis para usar inferência local.

O painel administrativo opera com permissões e proteção de sessão. Um gateway restringe o que pode ser alcançado pelo endereço público. O túnel temporário é verificado antes de liberar a página, porém sua disponibilidade depende da rede e do provedor. Um domínio fixo exige configuração externa e não é criado no domínio do WhatsApp.

Pedidos podem ser montados em um formulário ou no fluxo conversacional. No fluxo da conversa, a aplicação mantém um rascunho com validade, solicita dados essenciais, calcula o resumo e aguarda confirmação explícita. A persistência confere novamente valores e saldo. Produção sob demanda pode manter itens sem controle de unidades; itens controlados continuam sujeitos à disponibilidade.

O cofre editorial mantém estilo, conhecimento e padrões de segmento e etapa. A aplicação limita a leitura, verifica aprovação e validade e preserva edições existentes. Os guias operacionais não autorizam comandos do sistema. Falhas do serviço de IA têm tratamento de contingência; a recuperação opcional inicia somente um Ollama local instalado e prepara um modelo já disponível, com tentativas limitadas.

Os diagramas e os módulos concretos estão em [Arquitetura e requisitos](ARQUITETURA_E_REQUISITOS.md).

## 5 Resultados e discussão preliminar

Na referência técnica v2.33.0, a validação local registrou 516 testes Python aprovados e um ignorado, além de 35 testes JavaScript. O Actions do commit de referência concluiu os checks exigidos. O ZAP apresentou seis avisos e nenhum bloqueio segundo a política configurada. Os links, o commit e as condições de reprodução estão em [Evidências](EVIDENCIAS.md). Esses números pertencem àquela versão e não devem ser reutilizados como resultado de outra execução.

Os testes cobrem, entre outros comportamentos, pedidos não duplicados, separação entre produção e estoque controlado, recusa de links inventados, seleção de notas aprovadas e controles de acesso. A aprovação demonstra que os casos executados atenderam às asserções; não demonstra ausência de todos os defeitos.

Resultados de comparação de respostas: **pendentes de coleta**. Resultados de tarefas com participantes: **pendentes de coleta**. Não há evidência apresentada de aumento de vendas, redução de tempo em operação real ou satisfação estatisticamente representativa.

### 5.1 Ameaças à validade

O autor participa do desenvolvimento e pode influenciar a avaliação; a revisão por outra pessoa e a comparação cega de respostas reduzem esse viés. Os dados fictícios podem simplificar mensagens reais. Hardware, modelo, configuração e aquecimento afetam duração e qualidade da inferência. A disponibilidade de um túnel temporário não representa hospedagem com garantia de serviço. Resultados de poucos participantes, se coletados, permitem identificar problemas de uso, mas não generalizar para todo comércio.

## 6 Considerações finais provisórias

O artefato reúne atendimento, gestão e conhecimento editorial com validações comerciais independentes do modelo. Há uma base de testes e um processo de integração que permitem rastrear a evolução. A conclusão sobre adequação ao público depende da avaliação proposta, especialmente da comparação de respostas e das tarefas de uso. A versão final deverá substituir esta conclusão provisória por uma síntese baseada nas medidas coletadas e explicitar os limites observados.

Como continuidade, podem ser investigadas avaliação de diferentes modelos, hospedagem com maior estabilidade, revisão sistemática do conhecimento e ampliação do estudo de usabilidade. Qualquer evolução deve manter confirmação de operações, proteção dos dados e evidências de regressão.
