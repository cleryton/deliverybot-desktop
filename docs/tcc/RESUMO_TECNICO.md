# DeliveryBot — resumo técnico do trabalho

Referência: versão 2.45.3 · 26/10/2026. Material de apresentação do projeto; não substitui o modelo institucional de resumo expandido.

## Objetivo

O DeliveryBot reúne atendimento pelo WhatsApp, catálogo, pedidos e gestão comercial em um aplicativo Windows. O projeto aborda a dificuldade de manter mensagens, produtos, disponibilidade e registros de venda organizados em pequenos comércios. A proposta permite adaptar a operação a restaurantes, lojas, oficinas, produção sob encomenda e serviços, conforme o cadastro de cada estabelecimento.

## Como a solução funciona

O responsável configura a loja, cadastra produtos e conecta o WhatsApp local ou a API oficial da Meta. O cliente pode consultar informações, escolher pelo site ou montar o pedido na própria conversa. O aplicativo calcula os valores e exige confirmação antes de registrar a compra. Quando a página HTTPS continua indisponível no fluxo de recuperação, pode oferecer o catálogo em PDF e orientar a continuidade pelo WhatsApp.

O Ollama, quando configurado, ajuda a produzir respostas em linguagem natural. As notas aprovadas do Obsidian fornecem estilo e conhecimento editorial pertinente à pergunta. Esse mecanismo consulta contexto; não treina a rede neural. Preços, estoque, pagamentos, permissões e gravação de pedidos continuam sob regras do aplicativo.

## Recursos implementados

- Catálogo genérico com fotos, variações, unidades e quantidades fracionadas. Produtos preparados sob demanda podem dispensar controle de saldo.
- Pedidos pelo site ou pela conversa, resumo para confirmação, recibo, acompanhamento de preparo e atendimento humano.
- Página pública com túnel HTTPS, verificação de destino, reconexão e integração de webhook.
- Aplicativo independente para funcionários da rede da loja, com registro manual, caixa individual, recebimentos e conferência de dinheiro esperado.
- Perfis de acesso, autorização por dispositivo, proteção de sessões, limites de entrada, bloqueios de conversas suspeitas, auditoria e medidas de privacidade.
- Importação conferida de produtos por PDF/planilha, catálogo em PDF, backups criptografados e recuperação operacional.
- Instalação sem exigir Docker, Node.js ou Python do usuário final. O Ollama é configurado separadamente quando a IA local for utilizada.

## Organização técnica

| Camada | Papel |
| --- | --- |
| Aplicativo e interface | Python, WebView e HTML/CSS/JavaScript apresentam o painel e o terminal do funcionário |
| Backend e domínio | Rotas Flask encaminham solicitações para regras de catálogo, pedidos, estoque, caixa e atendimento |
| Persistência | SQLite mantém registros, estados de fila, rascunhos, autorizações e auditoria; transações controlam operações comerciais |
| Integrações | Componente WhatsApp local, Meta, túnel e Ollama colaboram com o backend; a publicação usa rotas permitidas |
| Conhecimento editorial | Notas revisadas são selecionadas por assunto, aprovação e validade, com limites de leitura e tamanho |

A arquitetura separa texto gerado de decisão comercial. O terminal do funcionário comunica-se por uma API HTTPS autorizada; não abre diretamente o arquivo do banco pela rede. A fila persistente diferencia mensagens pendentes, preparação, envio, conclusão e situações que exigem conferência, reduzindo o risco de repetir envios incertos.

## Melhorias e resultados medidos

A revisão eliminou uma resolução de caminho duplicada na descoberta de notas e passou a normalizar cada campo do perfil comercial uma única vez por classificação. Foram mantidas a leitura segura, a releitura das notas e as validações de aprovação e validade.

| Medição local | Antes | Depois |
| --- | ---: | ---: |
| Contexto com 80 notas fictícias, mediana da rodada C | 943,861 ms | 869,701 ms |
| Lote de 200 classificações com descrição longa, mediana da rodada B | 386,416 ms | 157,258 ms |

Em duas rodadas, a mediana do contexto caiu aproximadamente 7,9% a 8,0%. A classificação do cenário longo ficou cerca de 2,3 a 2,5 vezes mais rápida. A comparação alternou referência e variante no mesmo processo e exigiu saídas idênticas. Esses números não representam a latência total do WhatsApp, a inferência do Ollama, a renderização ou a abertura completa do executável; tempos absolutos variaram entre sessões.

## Validação e limites

O projeto usa testes automatizados com dados fictícios para domínio, permissões, privacidade, concorrência, mensagens, documentos e interfaces. O workflow do GitHub verifica código e versões, segurança, testes simulados e compilação/teste dos executáveis Windows antes da integração. Essa evidência técnica não substitui avaliação de usabilidade, qualidade das respostas por participantes ou homologação de contas reais.

Recursos externos dependem da rede e dos serviços disponíveis; a página ligada ao computador da loja depende desse computador em funcionamento. A IA pode errar e precisa de regras, supervisão e encaminhamento humano. Os registros de caixa não executam transferências financeiras. As medidas técnicas de privacidade exigem procedimentos adequados do responsável na operação real.

## Contribuição e materiais de apoio

O trabalho integra gestão transacional e atendimento com conhecimento editorial revisado, mantendo decisões comerciais fora da geração de texto. A próxima etapa é avaliar usabilidade, adequação das respostas e homologação operacional, com coleta separada dos testes automatizados.

Materiais completos: [Guia do código](GUIA_DO_CODIGO.md), [Desempenho](../DESEMPENHO.md) e [Evidências](EVIDENCIAS.md).
