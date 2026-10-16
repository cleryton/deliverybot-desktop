# Entrega do código e preparação para a iniciação científica

## Agenda informada pelo professor

- **16/10/2026:** aula com verificação dos resumos dos grupos que desejarem orientação.
- **18/10/2026:** prazo informado para inscrição na iniciação científica, com envio do resumo expandido.

Confirmar horário, canal de envio e eventuais exigências adicionais com a instituição. Este documento organiza a entrega e não efetua inscrição nem agenda lembretes.

## 1 Código atualizado e histórico

Repositório: [cleryton/deliverybot-desktop](https://github.com/cleryton/deliverybot-desktop). O código desta preparação acadêmica ficará na [tag v2.40.0](https://github.com/cleryton/deliverybot-desktop/tree/v2.40.0); o [histórico dessa versão](https://github.com/cleryton/deliverybot-desktop/commits/v2.40.0) e a [comparação com v2.39.0](https://github.com/cleryton/deliverybot-desktop/compare/v2.39.0...v2.40.0) mostram as alterações. Conferir que a tag e os checks existem antes de enviar os links.

Evolução imediatamente anterior: [commit 70fb8d4 — acesso remoto controlado](https://github.com/cleryton/deliverybot-desktop/commit/70fb8d4b43c0c765298e3dabe2f277595872f63d), integrado pelo [PR 24](https://github.com/cleryton/deliverybot-desktop/pull/24). A evidência técnica dessa versão está identificada em [Evidências](EVIDENCIAS.md).

## 2 Descrição das alterações desta etapa

Foi acrescentado um instrumento de laboratório para preparar e analisar a avaliação A/B do contexto editorial. O plano possui 72 tentativas, metadados técnicos e estados explícitos, incluindo falha, timeout e bloqueio de proteção. O resumo calcula proporções com denominadores, duração separada por origem, concordância dos avaliadores e diferenças pareadas. Nenhum resultado de inferência real é criado automaticamente.

A documentação passou a explicitar perguntas, etapas de pesquisa, ameaças à validade, fronteiras de segurança e requisitos de Meta, caixa e acesso remoto. A monografia diferencia evidências técnicas já executadas de inferência e usabilidade ainda pendentes. Os resultados sintéticos dos testes do instrumento não são apresentados como respostas reais do modelo.

## 3 Principais trechos desenvolvidos

| Trecho | Explicação para a entrega |
| --- | --- |
| `packaging/avaliacao_tcc.py` — `planejar` | Cria as 72 posições do protocolo sem preenchimento de resultados, alternando a ordem das condições. Registra a versão e o commit declarados. |
| `packaging/avaliacao_tcc.py` — `_registro` e `_ambiente` | Conferem identidade do caso, tipos, medidas finitas, notas e metadados; impedem confundir pendência, erro ou bloqueio com resposta julgada. |
| `packaging/avaliacao_tcc.py` — `_condicao`, `percentil` e `analisar` | Mantêm falhas nos denominadores apropriados, separam resposta local/modelo/fallback e calculam P95 pelo método declarado. Pareiam A e B por caso e repetição, com elegibilidade explícita. |
| `tests/test_avaliacao_tcc.py` | Usa medidas artificiais para verificar contas, P95, privacidade da síntese, duplicação, campos inválidos e preservação de arquivos. Isso valida o instrumento, não a qualidade da IA. |
| `src/acesso_remoto.py` — `_responsavel`, `_validar`, `avancar` | Código da v2.39.0: confirma conta e autorização no servidor e novamente na transação antes de alterar o pedido. Mostrar como evidência de segurança operacional. |
| `src/fila.py` — `avancar_status` | Código da v2.39.0: confere estado conhecido e autorização antes de gravar. Só depois tenta notificar; o envio não faz parte da transação local. |

Consultar a [matriz de requisitos](ARQUITETURA_E_REQUISITOS.md), o [laboratório](LABORATORIO.md) e a [análise de ameaças](AMEACAS_E_DECISOES.md) para detalhamento e limites.

## 4 Roteiro opcional de vídeo de 3 a 4 minutos

1. Mostrar versão, commit, repositório e checks do Actions, sem abrir configurações com credenciais.
2. Em uma loja fictícia, mostrar a criação de pedido e o registro correspondente. Explicar que notas editoriais alteram contexto, não pesos do modelo ou regras comerciais.
3. Mostrar a tela de acesso remoto e a escolha de prazo/permissão, usando somente dados de demonstração e convite oculto. Explicar a revogação; não publicar o link de acesso.
4. Abrir o plano de avaliação ainda pendente e mostrar a separação A/B, metadados e regras de anotação. Se mostrar uma simulação do analisador, manter `origem: SIMULACAO` visível e dizer que os números são artificiais.
5. Encerrar com evidências técnicas existentes, coletas pendentes, limitações e próximos passos.

Este roteiro não é um vídeo gravado. Preferir capturas novas com dados fictícios; imagens antigas de testes de amigos podem conter nomes, contatos e conversas.

## 5 Preparar o resumo expandido

Usar o modelo da instituição já fornecido, com autoria, curso e orientação a preencher pelo grupo. O texto deve apresentar problema, objetivo, método, desenvolvimento, resultados técnicos verificáveis e conclusão proporcional às evidências. Não afirmar melhora na naturalidade, produtividade ou vendas enquanto a coleta correspondente estiver pendente.

Levar para a orientação de 16/10: rascunho do resumo expandido, pergunta e recorte, identificação da versão testada, tabela de evidências e protocolo de avaliação. Após a revisão, ajustar a versão final e conferir o envio exigido para a inscrição de 18/10. O resumo final ainda precisa ser preparado/revisado no arquivo da instituição; este material não substitui esse documento.
