# Relatório técnico de desenvolvimento do DeliveryBot

**Finalidade:** apresentar ao professor o código atualizado, os registros de evolução e a explicação das principais implementações. Este relatório acompanha o projeto de TCC e a preparação para a iniciação científica.

**Autores:** [preencher] · **Curso e instituição:** [preencher] · **Orientação:** [preencher]

**Versão documental:** 2.40.2 · **Data:** 15/10/2026 · **Situação acadêmica:** desenvolvimento e validação técnica realizados; avaliação empírica das respostas ainda pendente.

## 1 Síntese do trabalho

O DeliveryBot integra cadastro de produtos, registro de pedidos e atendimento pelo WhatsApp em um aplicativo desktop. O Ollama executa o modelo de linguagem; as notas organizadas no Obsidian fornecem contexto editorial aprovado. A validação de preços, permissões e transações permanece no código e no banco de dados. Essa separação permite personalizar a comunicação sem atribuir ao texto gerado a autoridade para confirmar uma operação comercial.

A etapa acadêmica acrescentou um instrumento independente para planejar e analisar a comparação das respostas com e sem contexto editorial. Foram definidos casos, condições, medidas e critérios de exclusão. O trabalho apresenta evidências de funcionamento do software e um protocolo de pesquisa; a eficácia da personalização deverá ser verificada por coleta própria.

## 2 Código e rastreabilidade

| Item solicitado | Evidência de entrega |
| --- | --- |
| Código atualizado | [Repositório](https://github.com/cleryton/deliverybot-desktop) e [código identificado pela tag v2.40.2](https://github.com/cleryton/deliverybot-desktop/tree/v2.40.2). |
| Commits no GitHub | [Histórico da versão](https://github.com/cleryton/deliverybot-desktop/commits/v2.40.2) e [comparação com v2.39.0](https://github.com/cleryton/deliverybot-desktop/compare/v2.39.0...v2.40.2). |
| Descrição das alterações | Seção 3 deste relatório e [histórico de versões](../../CHANGELOG.md). |
| Explicação dos trechos | Seção 4, [arquitetura e requisitos](ARQUITETURA_E_REQUISITOS.md) e [laboratório](LABORATORIO.md). |
| Validação automatizada | [Actions da branch de entrega](https://github.com/cleryton/deliverybot-desktop/actions?query=branch%3Acodex%2Fentrega-academica-profissional) e [registro das evidências](EVIDENCIAS.md). Conferir o SHA do checkout em cada execução. |
| Demonstração opcional | Roteiro da seção 7; gravação ainda pendente. |

Os commits [faae21c](https://github.com/cleryton/deliverybot-desktop/commit/faae21ce7ad68f06d28d0cc9a27b9f1b9accf2a4) e [753db1f](https://github.com/cleryton/deliverybot-desktop/commit/753db1f9599d4ebfeae5d7ebd2d1638d54d952d0), integrados pelo [PR 25](https://github.com/cleryton/deliverybot-desktop/pull/25), identificam a implementação do laboratório e o refinamento dos cenários. A versão 2.40.2 profissionaliza a documentação de entrega e incorpora o registro verificável da validação da versão 2.40.1.

## 3 Alterações e justificativas

### 3.1 Avaliação reproduzível

O módulo `packaging/avaliacao_tcc.py` prepara um plano com 12 casos, duas condições e três repetições, totalizando 72 tentativas. A condição A utiliza regras e catálogo; a condição B acrescenta notas editoriais aprovadas. A ordem é alternada para reduzir a concentração de uma condição no início da execução. Modelo, ambiente, parâmetros e materiais precisam ser registrados antes da coleta.

O analisador diferencia respostas entregues, pendências, erros, timeouts e bloqueios. Calcula proporções com denominadores explícitos, mediana e percentil 95 das durações, concordância exata e diferenças pareadas nos registros elegíveis. A distinção entre resposta local, resposta do modelo e fallback evita atribuir ao modelo um resultado produzido por outra etapa do sistema.

### 3.2 Preservação das evidências

O laboratório recusa registros duplicados, campos desconhecidos, medidas inválidas e sobrescrita dos arquivos de saída. A síntese contém agregados e identificadores de integridade, sem reproduzir respostas ou textos livres do ambiente. O registro original exige armazenamento e revisão próprios. A marcação de coleta ou simulação é declarada pelo pesquisador e não autentica a origem das medidas.

### 3.3 Estrutura acadêmica

A documentação conecta problema, objetivos, perguntas de pesquisa, requisitos, decisões de arquitetura e critérios de avaliação. A monografia distingue resultados técnicos existentes de inferência real e avaliação com participantes ainda pendentes. A análise de ameaças registra controles implementados, testes e riscos residuais. O plano de pesquisa explicita limitações que precisam acompanhar a interpretação dos resultados.

## 4 Explicação das principais implementações

### 4.1 Preparação do experimento

Em `packaging/avaliacao_tcc.py`, a função `planejar` constrói as posições do protocolo DB-TCC-1 e mantém as medidas inicialmente vazias. A identidade de cada tentativa combina caso, condição e repetição. Essa organização permite conferir a completude do plano sem preencher resultados artificialmente.

### 4.2 Validação e análise das medidas

As funções `_ambiente` e `_registro` verificam metadados, tipos e estados permitidos. Uma tentativa pendente não recebe nota; uma falha não é tratada como resposta avaliada. As funções `_condicao`, `percentil` e `analisar` consolidam as medidas, aplicam o método R7 para o P95 e pareiam as condições somente quando ambas atendem aos critérios definidos no protocolo. As diferenças são descritivas e não demonstram causalidade ou significância estatística.

### 4.3 Testes do instrumento

O arquivo `tests/test_avaliacao_tcc.py` utiliza medidas artificiais para verificar planejamento, cálculos, elegibilidade dos pares, entradas inválidas, privacidade da síntese e preservação de arquivos. A simulação valida o funcionamento do analisador. A qualidade das respostas do Ollama depende de uma coleta posterior com o modelo identificado.

### 4.4 Autorização nas operações comerciais

Na implementação operacional da v2.39.0, `src/acesso_remoto.py` verifica conta e autorização no servidor e repete a verificação na transação antes de avançar um pedido. Em `src/fila.py`, `avancar_status` confere o estado esperado e a autorização antes da gravação. A tentativa de notificação ocorre depois da transação local. Essas verificações reduzem alterações indevidas e conflitos entre solicitações concorrentes; a disponibilidade do provedor externo continua sendo uma dependência.

## 5 Resultados técnicos e limites

A referência preservada da v2.40.1 corresponde ao commit `753db1f9599d4ebfeae5d7ebd2d1638d54d952d0` e ao [Actions de push 38837977393](https://github.com/cleryton/deliverybot-desktop/actions/runs/38837977393). O relatório Windows registra **825 testes Python aprovados, sem falhas, erros ou ignorados**. Os checks de código, WhatsApp simulado, segurança, compilação e smoke dos executáveis também concluíram com sucesso. A [evidência detalhada](EVIDENCIAS.md) identifica o artifact e o hash do JUnit.

Esse total inclui testes unitários e de integração. O resultado pertence ao checkout e ao ambiente registrados; não representa uma medida de satisfação, naturalidade, produtividade, cobertura integral ou segurança absoluta. A validação de uma nova versão deve ser identificada pelo próprio commit e pelos respectivos checks.

| Dimensão | Situação | Critério para conclusão |
| --- | --- | --- |
| Funcionamento técnico da v2.40.1 | Executado e registrado | Relatórios e checks vinculados ao SHA testado. |
| Instrumento de análise | Implementado e testado | Plano, validação de entradas e cálculos cobertos por testes. |
| Qualidade das respostas A/B | Coleta pendente | Executar DB-TCC-1, registrar falhas e realizar julgamentos previstos. |
| Usabilidade com participantes | Planejada | Alinhar procedimento institucional antes do recrutamento e da coleta. |
| Resumo expandido | Preparação pendente | Preencher o modelo institucional e submeter à orientação. |

## 6 Limitações e continuidade

O Obsidian organiza contexto textual e o Ollama executa um modelo previamente treinado. A edição das notas não modifica os pesos do modelo. O protocolo possui número limitado de casos e repetições; seus resultados descritivos não permitem generalizar para todos os comércios, modelos ou equipamentos. A análise de segurança se limita aos controles e verificações executados.

As próximas etapas são fixar versão, modelo e materiais; realizar a coleta A/B; discutir resultados favoráveis e desfavoráveis; e revisar a monografia com o orientador. Autoria, curso, instituição e orientação permanecem a preencher pelo grupo. A apresentação final seguirá o manual da instituição.

## 7 Roteiro de demonstração

| Duração aproximada | Conteúdo e evidência |
| --- | --- |
| 0:00 a 0:30 | Apresentar problema, objetivo, versão, commits e checks do Actions. |
| 0:30 a 1:30 | Em loja fictícia, registrar um pedido e mostrar a persistência. Explicar o papel das notas editoriais e das regras comerciais. |
| 1:30 a 2:15 | Demonstrar prazo, permissão e revogação do acesso remoto com dados fictícios e convite oculto. |
| 2:15 a 3:15 | Mostrar o plano A/B e a separação entre pendência, falha e resposta avaliada. Identificar explicitamente qualquer simulação. |
| 3:15 a 4:00 | Apresentar os testes realizados, as limitações e a coleta ainda necessária. |

A gravação permanece opcional e ainda não foi produzida. Usar novas capturas com dados fictícios e manter credenciais e convites fora da imagem.

## 8 Encaminhamento acadêmico

Conforme a comunicação recebida do professor, **16/10/2026** é a aula destinada à verificação dos resumos para orientação, e **18/10/2026** é o prazo de inscrição informado para a iniciação científica, com envio do resumo expandido. Confirmar horário e canal de submissão com a instituição.

Para a orientação, reunir o rascunho no modelo fornecido, a pergunta de pesquisa, o recorte, a versão testada, as evidências e o protocolo. O resumo deve relatar resultados técnicos verificáveis e uma conclusão proporcional a eles. Melhorias em atendimento, vendas ou produtividade dependem das respectivas medidas. Este relatório acompanha a entrega de desenvolvimento; o resumo expandido precisa ser concluído no modelo institucional.
