# Laboratório de avaliação reproduzível

Protocolo **DB-TCC-1**. Esta ferramenta prepara e analisa registros; **não executa Ollama**, não consulta a loja, não coleta conversas e não produz resultados de qualidade por conta própria. O protocolo de pesquisa continua sujeito à revisão do orientador.

## 1 Preparar a rodada

Em um checkout identificado, com Python 3.12 de desenvolvimento:

```powershell
.venv/Scripts/python.exe packaging/avaliacao_tcc.py --preparar --saida artifacts/tcc/rodada-01.json
```

O comando cria um arquivo novo com 72 posições pendentes: os casos C01–C12 de [Avaliação](AVALIACAO.md), condições A/B e três repetições. A ordem alterna A/B e B/A entre pares, com 18 pares de cada ordem. É um contrabalanceamento simples e explícito, não randomização nem controle de todos os efeitos de período. Não excluir casos desfavoráveis, acrescentar tentativas ou mudar o protocolo depois de observar os resultados. Uma modificação metodológica exige nova identificação e justificativa antes da rodada correspondente.

O arquivo registra versão, commit e alterações locais existentes ao preparar o plano. Esses dados são declarativos: conferir que a coleta usou o mesmo código, guardar comandos e horários e reiniciar a rodada se o código avaliado mudar. O plano não autentica uma execução futura. Em CI, diferenciar o SHA da branch do commit de merge temporário usado no teste de um pull request.

Uma posição é uma tentativa da entrada final do caso; não uma conversa inteira com quantidade variável de respostas. Preparações como revogar a nota no C08 ou introduzir histórico de restaurante antes do C12 não entram no tempo medido e devem ser idênticas no par A/B. Os casos C05/C12 são extensões do recorte principal, não uma terceira população comercial estudada.

## 2 Fixar os materiais

Preencher `ambiente` antes de medir: nome e digest do modelo, versão do Ollama, CPU, GPU (ou `Sem GPU`), RAM em GB, temperatura, janela de contexto e seed, ou `null` se não suportada. Usar o mesmo ambiente nas duas condições. Registrar as configurações efetivamente usadas, não valores recomendados genéricos.

Registrar SHA-256 em hexadecimal com 64 caracteres, sem prefixo, para digest do modelo, prompts A/B, catálogo e material editorial. Para um conjunto de notas, preparar um manifesto ordenado de nomes relativos e hashes dos arquivos fictícios, guardar esse manifesto e usar seu hash em `notas_sha256`. Os hashes não substituem a preservação dos materiais. Não usar credenciais ou dados reais nesses arquivos.

Como os casos utilizam perfis e estados diferentes, o catálogo e o material editorial devem conter snapshots identificados por caso. O manifesto deve incluir versões aprovadas/revogadas das notas, políticas fictícias e as referências esperadas. Os hashes de prompts identificam os templates A/B; preservar também as entradas, o histórico e a associação a cada caso. O ambiente global do JSON não comprova que esses materiais foram mantidos: a revisão do caderno e dos snapshots é parte da reprodução.

Separar aquecimento das tentativas e marcar `aquecimento_excluido: true` somente depois de fazê-lo. O analisador exige o campo, mas não tem como verificar a declaração. Prompts A/B diferem somente no contexto editorial; regras comerciais, catálogo, modelo e demais parâmetros permanecem iguais. Usar histórico controlado e reiniciar entre casos independentes, como definido no protocolo.

Guardar entradas, respostas fictícias e referências de correção separadamente, em armazenamento de pesquisa com acesso restrito. Não inserir textos, nomes de participantes, telefones, comentários ou tokens no JSON das medidas. Campos não previstos são recusados. O resumo exporta hashes dos materiais técnicos, sem repetir CPU, nome do modelo ou outros textos informados; a reprodução exige conservar o arquivo de coleta e o manifesto técnico local.

## 3 Registrar o que realmente ocorreu

| Estado | Uso e preenchimento |
| --- | --- |
| `PENDENTE` | Nenhuma tentativa medida. Todos os valores de medida e avaliação permanecem `null`. |
| `OK` | Houve uma resposta entregue, inclusive contingência. Informar tempo, chamada ao modelo e fallback; julgar fatos e riscos; obter notas dos dois avaliadores. `OK` não significa que a resposta era correta. |
| `ERRO` | Tentativa falhou sem resposta entregue. Informar duração e se chamou o modelo; `fallback: false`; fatos, riscos e notas ficam `null`. |
| `TIMEOUT` | O prazo definido no roteiro terminou sem resposta. Mesmos campos de erro; não excluir a tentativa. |
| `BLOQUEADA` | Uma proteção oficial impediu a resposta. Usar somente quando o bloqueio foi observado, não como explicação presumida para silêncio. Informar duração e chamada ao modelo; não atribuir notas a um texto inexistente. |

Medir `duracao_ms` com relógio monotônico, do envio da entrada ao resultado completo ou decisão de erro/bloqueio; registrar esse ponto no caderno de laboratório. A ferramenta aceita zero como medida, mas não prova resolução adequada do relógio. Ela não converte duração de teste unitário em latência do bot.

Em `riscos`, marcar ocorrências observadas de link não autorizado, vazamento ou alegação de operação não persistida. Em `factual_correto`, conferir a resposta contra a referência de catálogo e estado daquele caso. A ferramenta não decide automaticamente esses julgamentos. Uma proteção esperada pode resultar em `BLOQUEADA`: isso não deve ser confundido com defeito nem acerto de inferência.

Os avaliadores R01 e R02 atribuem separadamente notas inteiras de 1 a 5 para clareza, naturalidade e aderência ao segmento, conforme a rubrica do protocolo. Preparar uma cópia embaralhada de respostas sem condição A/B para a avaliação humana, mantendo a chave de associação restrita. O JSON do plano contém A/B e **não implementa cegamento automaticamente**. Não trocar as notas discordantes por consenso sem guardar os julgamentos originais; relatar eventual adjudicação separadamente.

`origem: COLETA` significa que o pesquisador declara ter medido os dados. `SIMULACAO` identifica medidas artificiais usadas para testar o instrumento. Nenhum dos valores autentica por si só a origem. Os testes automatizados deste repositório usam números sintéticos e não são evidências de qualidade da IA.

## 4 Analisar sem esconder falhas

```powershell
.venv/Scripts/python.exe packaging/avaliacao_tcc.py --analisar artifacts/tcc/rodada-01.json --saida artifacts/tcc/rodada-01-resumo.json
```

Código de saída: **0** = registro válido com todas as tentativas medidas; **1** = registro válido com tentativas pendentes; **2** = formato, medida, metadado ou caminho inválido. Código 0 não significa que B melhorou A, que não houve riscos ou que a hipótese foi confirmada. A ferramenta nunca sobrescreve um arquivo de saída existente. Use outro nome para nova síntese e preserve o original.

O relatório informa:

- Cobertura: 36 tentativas planejadas por condição, quantas foram medidas e quantas ficaram pendentes, com erros, timeouts e bloqueios separados.
- Respostas entregues por tentativas medidas (`conclusao`), correção factual por respostas entregues e correção factual por tentativas medidas. Os dois denominadores devem acompanhar qualquer comparação; bloqueios previstos exigem interpretação por caso.
- Frequência de contingência e de chamadas ao modelo, com numeradores e denominadores; ocorrências de risco somente nas respostas entregues e julgadas.
- Mediana e P95 de duração separados para resposta do modelo, resposta local, fallback, erro, timeout e bloqueio. Método R7: ordenar os valores e interpolar na posição zero-based `(n−1) × p`. Não descartar extremos. Sem amostras, os valores são `null`, não zero. Percentis em amostras pequenas são instáveis; o método está explicitado porque existem várias convenções ([NIST/SEMATECH](https://itl.nist.gov/div898/handbook/prc/section2/prc262.htm)).
- Médias descritivas das notas e proporção de concordância exata entre os dois avaliadores, por dimensão e condição. As notas são ordinais e a rubrica é exploratória; médias não provam intervalos iguais nem validade psicométrica. Concordância exata não é kappa nem elimina viés comum aos avaliadores.
- Diferença B−A por caso e repetição somente quando ambas as respostas foram geradas com chamada ao modelo, entregues e sem fallback. Informar quantos dos 36 pares ficaram elegíveis; essa seleção condiciona a interpretação. Comparações não elegíveis não viram zero e continuam nas contagens gerais.

O resumo não fornece p-valor, teste de significância, estimativa de produtividade ou conclusão causal. A análise estatística adicional, caso necessária, deve ser definida com o orientador antes da coleta, considerando o agrupamento por caso e as repetições. Resultados negativos, riscos e ausência de pares elegíveis também são resultados a discutir.

## 5 Preservar e entregar

Guardar o plano original, materiais fictícios, registro técnico, respostas revisadas, julgamentos individuais, síntese e hashes. Revisar tudo antes de publicar. `artifacts/` é ignorado pelo Git para evitar versionar dados de coleta por acidente; guardar uma cópia de pesquisa aprovada fora de caches temporários. As saídas do analisador ficam somente em `artifacts/tcc/`, não em código ou bancos.

Conferir: versão e commit do artefato; data e ambiente reais; condições equivalentes; ausência de alterações não registradas; cobertura e denominadores; origem `COLETA` versus `SIMULACAO`; tarefas ainda pendentes. Uma síntese numérica não substitui a discussão dos casos nem um procedimento ético institucional quando houver pessoas.
