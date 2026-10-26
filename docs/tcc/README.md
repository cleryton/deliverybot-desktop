# DeliveryBot como projeto de TCC

Este material organiza o aplicativo como um artefato de pesquisa aplicada em desenvolvimento de software. É uma base editável para discutir com o orientador, escrever a monografia e conduzir a avaliação. Nome, curso, instituição e orientador serão preenchidos pelo autor. A formatação final deve seguir o manual da instituição.

**Título sugerido:** DeliveryBot: desenvolvimento e avaliação de um aplicativo de atendimento e gestão de pedidos com inteligência artificial local e conhecimento editorial.

**Contribuição proposta:** integrar gestão transacional, atendimento conversacional e personalização por notas revisadas em uma aplicação desktop, mantendo as decisões comerciais verificáveis fora da geração de texto. A contribuição será avaliada por correção funcional, recuperação de falhas, adequação das respostas e facilidade de uso.

| Material | Uso |
| --- | --- |
| [Resumo técnico do trabalho](RESUMO_TECNICO.md) | Objetivo, solução, recursos, arquitetura, melhorias medidas e limites da avaliação. |
| [Guia de leitura e explicação do código](GUIA_DO_CODIGO.md) | Fluxos, 56 módulos Python, interfaces, banco, instalação, seis trechos reais e roteiro de apresentação. |
| [Base da monografia](MONOGRAFIA.md) | Introdução, objetivos, fundamentação, metodologia, desenvolvimento e discussão inicial. |
| [Arquitetura e requisitos](ARQUITETURA_E_REQUISITOS.md) | Diagramas e rastreabilidade entre requisito, código e teste. |
| [Protocolo de avaliação](AVALIACAO.md) | Casos fictícios, comparação das respostas, métricas e formulário de observação. |
| [Plano de pesquisa](PLANO_DE_PESQUISA.md) | Perguntas, objetivos, critérios, etapas do método e ameaças à validade. |
| [Laboratório reproduzível](LABORATORIO.md) | Plano de 72 tentativas e análise A/B com medidas explícitas, sem coleta automática. |
| [Ameaças e decisões](AMEACAS_E_DECISOES.md) | Fronteiras entre cliente, remoto, caixa e responsável, com testes negativos. |
| [Relatório técnico de entrega](ENTREGA_ACADEMICA.md) | Síntese do projeto, rastreabilidade dos commits, justificativas, explicação das implementações, resultados e roteiro de demonstração. |
| [Evidências técnicas](EVIDENCIAS.md) | Reprodução dos testes, limites dos resultados e histórico verificável. |
| [Apresentação à banca](APRESENTACAO.md) | Roteiro da demonstração e perguntas técnicas. |
| [Referências](REFERENCIAS.md) | Fontes primárias consultadas e pontos em que fundamentam o trabalho. |

## Como concluir o trabalho

1. Validar pergunta, recorte e critérios com o orientador. Usar uma loja fictícia de produção e uma de revenda, mantendo os demais segmentos como extensão.
2. Executar a validação técnica no checkout escolhido e guardar os relatórios junto à versão e ao commit.
3. Preparar o [laboratório DB-TCC-1](LABORATORIO.md), fixar materiais e executar a comparação controlada definida no protocolo; anotar modelo, hardware e configuração. O analisador calcula as métricas declaradas, mas os resultados de inferência ainda precisam ser coletados.
4. Se houver participantes, acertar previamente com a instituição o procedimento ético e a proteção dos dados; usar somente tarefas fictícias. A avaliação com pessoas ainda está pendente.
5. Preencher resultados, discutir falhas e limitações e revisar a monografia. Substituir todos os campos marcados como pendentes antes da entrega.

O Obsidian organiza conhecimento textual e relações entre notas. O Ollama executa um modelo já treinado e recebe contexto aprovado. Editar o cofre altera esse contexto; não modifica os pesos do modelo. A validação de pedidos continua no código e no banco de dados.

O trabalho não pressupõe melhoria de vendas, redução de tempo ou satisfação comprovada. Essas conclusões dependem de medidas. Também não apresenta certificação OWASP, conformidade legal automática, integração oficial de todos os provedores WhatsApp ou disponibilidade contínua da internet.
