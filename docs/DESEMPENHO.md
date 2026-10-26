# Desempenho do painel e do atendimento

## Otimizações editoriais da versão 2.45.3

Foram aceitas duas alterações: a descoberta de notas deixa de resolver novamente um caminho que será validado por `_ler`, e a classificação comercial normaliza cada campo uma vez antes de testar os padrões. A leitura segura continua recusando raiz/componentes vinculados, caminhos externos, falhas de resolução e conteúdo inválido. Não foi criado cache de notas, aprovação, permissões ou perfil entre chamadas; a releitura antes de compor o contexto permanece.

As rodadas gerais mostraram variação grande entre sessões. Por isso a comparação usa ordem alternada A/B e B/A no mesmo processo, com duas rodadas de aquecimento e saídas obrigatoriamente idênticas. A referência é a função do commit `e4ab796e3bfc1c5a11db1bc427a4c5a6751c8b11` (árvore v2.45.2); os demais helpers são os da variante. Isso isola a função e não compara dois executáveis completos. As medidas foram obtidas na cópia de trabalho antes do commit da nova versão.

| Cenário e repetição | P50 antes (ms) | P50 depois (ms) | P95 antes (ms) | P95 depois (ms) |
| --- | ---: | ---: | ---: | ---: |
| Contexto com 80 notas, B | 928,275 | 853,838 | 965,164 | 881,782 |
| Contexto com 80 notas, C | 943,861 | 869,701 | 956,935 | 925,846 |
| Lote de 200 classificações, A | 101,863 | 44,076 | 406,801 | 165,965 |
| Lote de 200 classificações, B | 386,416 | 157,258 | 419,296 | 165,639 |

O contexto teve redução de aproximadamente 7,9% a 8,0% na mediana nas duas rodadas de 16 amostras por condição. Na classificação, o lote foi aproximadamente 2,3 a 2,5 vezes mais rápido nas duas rodadas de 20 amostras; o cenário usa segmento genérico e uma descrição fictícia longa. Não representa uma chamada comum de toda loja. A variação dos tempos absolutos reforça o uso da comparação pareada. Não há garantia de redução equivalente no atendimento completo ou na inferência do modelo.

Os registros locais são `v2453-pares-b.json`, `v2453-pares-c.json`, `v2453-perfil-a.json` e `v2453-perfil-b.json` em `artifacts/desempenho/`. O hash do contexto fictício coincidiu nas comparações; o conteúdo das notas não é copiado para o relatório. A referência e os arquivos de coleta precisam ser preservados para reprodução. Não execute builds ou testes em paralelo com a medição.

Com as dependências e a referência Git disponíveis localmente, execute uma rodada por vez:

```powershell
.venv/Scripts/python.exe packaging/benchmark_desempenho.py --comparar-contexto --repeticoes 16 --saida artifacts/desempenho/contexto-rodada-nova.json
.venv/Scripts/python.exe packaging/benchmark_desempenho.py --comparar-perfil --repeticoes 20 --saida artifacts/desempenho/perfil-rodada-nova.json
.venv/Scripts/python.exe -m pytest tests/test_cerebro_contexto.py tests/test_padroes_atendimento.py tests/test_desempenho.py -q
```

Os modos são exclusivos e recusam um processo com backend já importado. Checkouts rasos podem precisar recuperar o histórico antes; o comparador não busca código pela rede. Use nomes de saída novos. Não há contas, mensagens reais ou inferência nesses cenários. Consulte o [guia do código](tcc/GUIA_DO_CODIGO.md) para explicar as responsabilidades e os trechos otimizados.

## Alterações da versão 2.40.3

A listagem administrativa passou a ler os últimos 200 pedidos e seus itens em duas consultas na mesma conexão e transação de leitura. O número de consultas deixa de crescer por pedido. A ordenação, os dados históricos do recibo e a remoção de custos para funcionários foram preservados. A transação mantém cabeçalhos e itens no mesmo snapshot, inclusive quando outra conexão altera dados durante a leitura.

O resumo do painel calcula contagens e totais no SQLite, sem carregar descrições, fotos e itens dos pedidos. Os indicadores usam uma transação de leitura consistente e preservam a ocultação das vendas para os perfis sem permissão. Foram acrescentados índices para itens por pedido, posição da fila e verificações da fila de mensagens por telefone. A inicialização instala os índices também nos bancos existentes; não recria tabelas ou apaga registros. A primeira execução pode levar mais tempo para indexar históricos grandes e os índices utilizam espaço adicional.

O contexto do Ollama continua relendo e revalidando as notas do Obsidian a cada resposta. A reconstrução do mapa para o Graph ficou fora desse caminho: ocorre na preparação inicial e nas consultas de estado, visualização e abertura do cofre pelo aplicativo. Alterações nas notas continuam valendo na resposta seguinte; as ligações derivadas do Graph são atualizadas nesses pontos de sincronização. Não foi criado cache de notas aprovadas ou de permissões.

A consulta de estado do cofre também passou a preparar o mapa uma vez por chamada, em vez de três. Os dados de estilo e caminho são obtidos da estrutura que acabou de ser preparada. Essa redução é coberta por teste de chamadas; não foi medida como um cenário de latência separado.

O SDK Anthropic passou a ser importado na primeira utilização desse provedor. A abertura do backend, o atendimento local e o Ollama dispensam esse carregamento. A importação é reaproveitada nas chamadas seguintes, e ausência da biblioteca ou de credencial mantém a falha controlada e o fallback existente.

## Método de medição

O comando `packaging/benchmark_desempenho.py` cria uma loja temporária, força provedor de teste, desativa IA e túnel e importa o aplicativo somente após configurar o isolamento. Não abre banco, cofre ou configuração de uso real; não inicia serviços nem envia mensagens. O arquivo de ambiente apontado é temporário e não contém credenciais. A saída registra versão, commit, presença de alterações versionadas, ambiente, tamanho da base e agregados, sem copiar respostas, nomes de arquivos do cofre ou consultas SQL.

O cenário de consultas contém 1.500 produtos, 3.000 pedidos, 15.000 itens e 80 notas fictícias. Cada operação passa por duas execuções de aquecimento, uma execução instrumentada para contar conexões e SELECTs e 15 amostras de duração sem a instrumentação. As verificações de conteúdo fazem parte do tempo medido. P50 é a mediana; P95 utiliza interpolação R7 na posição `(n−1)×0,95`. As operações são medidas sequencialmente. A gravação de pedidos é medida depois das consultas para preservar o tamanho inicial destas.

A importação do backend é medida separadamente em cinco processos novos, cada um com um banco vazio. O relógio começa imediatamente antes da importação de `src.app`: inclui a inicialização desse backend e do banco, mas não inclui o lançamento do interpretador, a janela desktop, o WebView ou a preparação dos serviços. Os testes não fazem inferência no Ollama nem chamadas à Meta.

Foram comparadas três hipóteses: consultas em lote e agregação com índices; separação do Graph; e importação tardia do SDK opcional. As duas primeiras tiveram rodada intermediária e duas rodadas completas antes/depois; a terceira teve cinco processos por condição. A busca foi limitada a essas hipóteses, sem alterar validações ou dependências. Trata-se da melhor variante segura medida neste recorte, não de um ótimo global.

## Resultados locais em 16 de outubro de 2026

Referência operacional: `main` no commit `ad486b8eefeb7964ee3abd9b17e7d74d79f416c9`, versão 2.40.2. As medidas da implementação otimizada foram obtidas na cópia de trabalho da v2.40.3 antes do commit. Os metadados registram alterações locais; o hash da referência sozinho não identifica a implementação otimizada. A máquina executou Windows e Python 3.12. Os JSONs originais estão em `artifacts/desempenho/`, fora do Git.

| Operação | P50 antes em ms | P50 depois em ms | P95 antes em ms | P95 depois em ms |
| --- | ---: | ---: | ---: | ---: |
| API com 200 pedidos | 1774,539 | 60,943 | 2127,599 | 68,314 |
| Resumo do painel | 97,305 | 46,377 | 126,944 | 50,645 |
| Contexto com 80 notas | 1572,719 | 557,015 | 1795,394 | 669,992 |
| Gravar um pedido | 23,479 | 17,751 | 26,458 | 20,684 |
| Importar backend com banco novo | 3699,046 | 1894,360 | 3829,583 | 1906,567 |

A tabela utiliza a primeira rodada completa de cada condição (`baseline-a.json`, `final-a.json`) e os dois arquivos `inicializacao-antes.json` / `inicializacao-depois.json`. Na repetição independente (`baseline-b.json` / `final-b.json`), as medianas foram: pedidos 1764,553 → 62,813 ms; resumo 94,976 → 43,059 ms; contexto 1346,777 → 697,021 ms; gravação 23,515 → 23,882 ms. O ganho das consultas e do contexto se repetiu. A gravação variou e não demonstrou ganho estável.

Na API de pedidos, conexões caíram de **207 para 7** e SELECTs de **407 para 8**, incluindo verificações administrativas. Na função de repositório isolada, são uma conexão e duas consultas para a lista preenchida. No resumo, conexões caíram de 9 para 7 e SELECTs de 10 para 9, com volume de linhas materializadas muito menor. As rodadas intermediárias `sql.json` e `cofre.json` preservam a comparação por hipótese. A importação do backend deixou de carregar o SDK Anthropic, conforme verificação em cada processo.

Esses valores descrevem o laboratório local. Disco, antivírus, concorrência, aquecimento, volume e distribuição de dados podem alterar os tempos. P95 com poucas amostras é uma estimativa descritiva; não há teste de significância ou garantia de prazo. A medição não representa latência de rede, processamento completo de WhatsApp, geração do modelo, renderização do navegador ou abertura total do executável. A validação do commit no Actions é uma evidência separada de correção e empacotamento, não uma reprodução desses tempos.

## Reprodução

No ambiente de desenvolvimento, com as dependências fixadas instaladas, execute da raiz do projeto:

```powershell
.venv/Scripts/python.exe packaging/benchmark_desempenho.py --saida artifacts/desempenho/rodada-nova.json --repeticoes 15
.venv/Scripts/python.exe packaging/benchmark_desempenho.py --inicializacao --saida artifacts/desempenho/inicializacao-nova.json --repeticoes 5
.venv/Scripts/python.exe -m pytest tests/test_desempenho.py -q
```

Execute uma rodada por vez, sem testes ou builds concorrentes, e use nomes novos: o comando recusa sobrescrita e destinos fora de `artifacts/desempenho/`. Registre o checkout e preserve os relatórios. Para comparar outra implementação, mantenha a mesma fixture, os parâmetros e o ambiente. O usuário do aplicativo instalado continua sem precisar de Python, Node.js ou Docker.

Os testes de regressão verificam igualdade dos pedidos, limites, snapshot durante escrita concorrente, custos históricos, ocultação de custos/vendas, indicadores vazios, instalação idempotente e uso dos índices, atualização e revogação das notas, Graph inicial e importação opcional do SDK. Não impõem limites frágeis de milissegundos na integração contínua.
