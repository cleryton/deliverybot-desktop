# Delimitação e plano de pesquisa

Estado: construção e validação técnica existentes; avaliação comparativa de inferência e avaliação com participantes **a executar**. O orientador deve revisar o recorte antes da coleta. Não ampliar a conclusão para todos os recursos do aplicativo apenas porque a demonstração funciona.

## Perguntas e resultados verificáveis

| Pergunta | Objetivo e unidade observada | Evidência e critério proposto | Limite |
| --- | --- | --- | --- |
| Q1: a confirmação corresponde a uma operação comercial consistente? | Verificar uma tentativa de confirmação, repetição ou concorrência em dados fictícios. | Requisitos RF03–RF06, testes de transação, saldo e duplicação; nenhum caso executado com falha ou erro, com justificativa de ignorados. | Testes finitos não provam ausência de defeitos nem desempenho em produção. |
| Q2: notas editoriais favorecem adequação do texto sem degradar a informação comercial? | Comparar o mesmo caso/repetição sob A e B, no mesmo modelo e ambiente. | DB-TCC-1: correção factual, riscos, notas independentes e diferenças pareadas; examinar melhora, empate ou piora e cobertura. | Hipótese exploratória; não assumir benefício, significância ou causalidade. |
| Q3: um operador consegue completar tarefas essenciais? | Observar participante adulto em tarefa U01–U06 autorizada. | Conclusão, duração, erros, ajuda e relato de dificuldade, segundo o roteiro fixado. | Coleta com pessoas pendente; não confundir demonstração pelo autor com usabilidade medida. |
| Q4: acessos de menor privilégio ficam dentro das permissões concedidas? | Tentar operações nos limites entre público, remoto, caixa e responsável. | Matriz de ameaças e regressões negativas; acesso recusado e transação não executada nos cenários testados. | Escopo técnico selecionado; não constitui pentest completo, certificação ou conformidade legal. |

## Encadeamento do método

A organização segue a relação entre problema, objetivos, construção, demonstração, avaliação e comunicação apresentada por Peffers et al. (2007). O desenvolvimento já ocorreu incrementalmente; o plano sistematiza sua avaliação posterior, sem reescrever a história como se tivesse havido um experimento prévio.

| Etapa | Material produzido | Situação |
| --- | --- | --- |
| Problema e motivação | Introdução, perguntas Q1–Q4 e recorte em produção e revenda. | Motivação técnica definida; frequência do problema em comércios reais precisa de levantamento ou literatura. |
| Objetivos da solução | Requisitos, critérios e limites. | Especificados, sujeitos à revisão acadêmica. |
| Construção | Código, migrações, testes, commits e decisões de arquitetura. | Implementado com evolução rastreável. |
| Demonstração | Roteiro da banca e operações em dados fictícios. | Reproduzível; transporte real exige preparação separada. |
| Avaliação | JUnit/Actions, comparação A/B e tarefas de uso. | Técnica executada em rodadas identificadas; inferência e pessoas pendentes. |
| Comunicação | Monografia, resumo expandido, descrição da entrega e roteiro de vídeo. | Bases editáveis; autoria, resultados de pesquisa e formatação institucional ainda precisam de conclusão. |

## Congelar antes de medir

1. Aprovar pergunta, recorte, critérios e rubricas com o orientador.
2. Escolher tag e SHA do código; conferir diferenças locais. Não usar somente o nome da versão como identificação dos arquivos executados.
3. Fixar catálogo fictício, notas aprovadas, prompts, modelo, ambiente, histórico, timeout e aquecimento. Preservar os materiais e seus hashes.
4. Gerar o plano DB-TCC-1 e preparar o procedimento de avaliação independente. Registrar quem mede e quem julga, por códigos, sem publicar identificação pessoal.
5. Definir como registrar bloqueios previstos, falhas e intervenções; não excluir tentativas após ver seus resultados.
6. Executar a rodada, analisar e discutir falhas. Se o código for corrigido, iniciar outra rodada e manter a anterior identificada.

## Ameaças à validade da pesquisa

| Dimensão | Ameaça | Tratamento proposto e limitação residual |
| --- | --- | --- |
| Construção | Naturalidade e adequação são julgamentos subjetivos. | Rubrica explícita, dois avaliadores e divergências preservadas; instrumento exploratório ainda não validado. |
| Interna | Autor escolhe notas, casos ou melhores respostas após observar resultados. | Casos e plano fixados, tentativas completas e origem registrada; revisão externa reduz, sem eliminar, o viés. |
| Interna | A/B diferem em hardware, histórico, aquecimento ou regras. | Mesmo ambiente e materiais, alternância de ordem e histórico controlado; efeitos de período e variação de inferência permanecem. |
| Conclusão | Repetições do mesmo caso são tratadas como participantes independentes. | Relatar pares e casos, denominadores e distribuição; não usar os 72 textos como amostra independente da população. |
| Conclusão | Só respostas bem-sucedidas aparecem nas médias. | Falhas, timeouts, bloqueios e fallback separados; pares elegíveis e descartes explicados, sem substituir ausências por zero. |
| Externa | Dados fictícios e amostra pequena são generalizados para lojas reais. | Restringir conclusões ao laboratório e ao hardware testado; estudo de campo futuro exige outro desenho. |
| Reprodutibilidade | Artifacts expiram ou resultados ficam associados ao commit errado. | Guardar relatórios, hashes, comandos, referência do Actions e materiais antes da expiração; hashes não autenticam a coleta. |

## Critério de prontidão da entrega

O código pode ser entregue quando os checks da rodada escolhida passarem e as limitações estiverem registradas. A pesquisa só pode declarar comparação de IA ou usabilidade concluída quando essas coletas ocorrerem e puderem ser auditadas. Não preencher resultados com estimativas, testes sintéticos do analisador ou relatos informais de amigos sem protocolo.
