# Evidências e reprodução

## Referência preservada v2.39.0

Tag **v2.39.0**, commit `70fb8d4b43c0c765298e3dabe2f277595872f63d`, [código do commit](https://github.com/cleryton/deliverybot-desktop/commit/70fb8d4b43c0c765298e3dabe2f277595872f63d), integrado pelo [PR 24](https://github.com/cleryton/deliverybot-desktop/pull/24). O [Actions de push](https://github.com/cleryton/deliverybot-desktop/actions/runs/38807190189) executou esse SHA; o consolidador registrou checkout sem alterações versionadas.

O artifact `relatorios-windows`, ID `12007352206`, contém o JUnit e sua síntese: **785 executados e aprovados; zero falhas, erros ou ignorados**. SHA-256 do JUnit: `1204e3fc95a003846b5591e5fda43304cece20469895f1492efcd86a09be1a14`. O total mistura testes unitários e de integração e pertence ao Windows do CI, não a todos os ambientes. Código/WhatsApp, OWASP/ZAP, compilação, instaladores e smoke dos executáveis passaram nos respectivos checks. Não se deduz cobertura integral, segurança absoluta ou eficácia da IA dessas aprovações.

Uma cópia local foi preservada em `artifacts/tcc/referencia-v2.39.0/`, ignorada pelo Git, com o ZIP e a síntese. Os artifacts do GitHub têm retenção limitada; manter outra cópia no armazenamento de pesquisa aprovado antes de limpar caches. Revisar o conteúdo completo antes de compartilhar; a síntese não copia mensagens dos testes.

O [Actions do pull request](https://github.com/cleryton/deliverybot-desktop/actions/runs/38807211721) também passou, mas seu checkout de teste usou o merge temporário `0420452245f6558dde51e8141340cfd8d1fa118c`. Não trocar esse SHA pelo da branch no relato dos metadados. Esta seção usa a execução de **push**, cujo checkout corresponde ao commit citado acima. A versão do novo laboratório deve ter sua própria rodada; resultados sintéticos do analisador não são inferência coletada.

## Referência já executada

Referência histórica **v2.33.0**, commit `679476fa2a752f00ed449fb1e5cf91d989e2d937`, integração pelo [PR 14](https://github.com/cleryton/deliverybot-desktop/pull/14). A execução do [Actions](https://github.com/cleryton/deliverybot-desktop/actions/runs/38194806722) concluiu os checks. Os artifacts têm retenção de sete dias; baixar os relatórios necessários ao TCC enquanto disponíveis e mantê-los em armazenamento de pesquisa aprovado.

| Evidência | Resultado registrado | Limite |
| --- | --- | --- |
| Suíte Python local | 516 aprovados, 1 ignorado por condição de vínculo simbólico no Windows. | Resultado daquele checkout e ambiente; mistura testes unitários e de integração. |
| JavaScript local | 35 aprovados. | Lógica de experiência e física do jogo, não validação completa de navegador por usuários. |
| ZAP no CI | 6 avisos, 0 bloqueios na política configurada. | Varredura passiva em gateway com dados fictícios; não teste ativo nem certificação. |
| Executável e instalador no CI | Compilação e smoke aprovados no check Windows. | Não demonstra compatibilidade com todos os computadores. |

Os relatórios locais ficaram em `artifacts/relatorios/v2.33.0/` e são ignorados pelo Git. Esta tabela é um registro histórico, não substitui os arquivos de execução nem representa a avaliação da versão atual. Os avisos incluem configuração de estilo CSP e informações do servidor de laboratório; consultar o relatório original e a [política OWASP](../../SEGURANCA%20OWASP.md) antes de interpretá-los.

## Reproduzir no ambiente de desenvolvimento Windows

Os comandos exigem Python e Node no ambiente de desenvolvimento, disponíveis no projeto local. Para reprodução em outro computador, criar o ambiente Python 3.12 e instalar `requirements-desktop.lock.txt`; instalar as dependências WhatsApp fixadas pelo `npm ci`. O usuário do aplicativo instalado não precisa dessas ferramentas. Não utilizar banco, cofre, credenciais ou sessão reais.

No PowerShell, a partir da raiz do projeto:

```powershell
$env:DELIVERYBOT_ENV_FILE = Join-Path $PWD 'artifacts/tcc/laboratorio.env'
$env:DATABASE_PATH = Join-Path $PWD 'artifacts/tcc/laboratorio.db'
$env:WHATSAPP_PROVIDER = 'TESTE'
$env:IA_PROVIDER = ''
$env:TUNEL_AUTOMATICO = 'NAO'
$env:SEED_CATALOGO = 'NAO'
git rev-parse HEAD
git status --short
.venv/Scripts/python.exe packaging/verificar_projeto.py
.venv/Scripts/python.exe -m pytest -q --junitxml=artifacts/tcc/python.xml
node --test tests/js/*.test.cjs
npm.cmd --prefix whatsapp-native test
.venv/Scripts/python.exe packaging/evidencias_tcc.py artifacts/tcc/python.xml --saida artifacts/tcc/evidencias.json
```

Verificar o código de saída de cada comando antes de continuar. Git status deve ser registrado: se o checkout tiver alterações, o hash do commit sozinho não identifica o código testado. O Actions executa o checkout da rodada com isolamento e é a referência para validar a integração. Em pull requests, conferir o SHA do merge temporário. Revisar alterações locais e não incluir configurações, dados ou arquivos sem relação com a entrega.

O consolidador lê **somente** os arquivos JUnit fornecidos; não abre bancos, notas, sessões nem arquivos de configuração. No JSON exporta contagens, soma das durações dos casos e SHA-256 do relatório, sem nomes de casos, mensagens de erro, caminhos ou saídas dos testes. O JUnit original pode conter informações do ambiente e precisa de revisão antes de compartilhamento.

O check Windows do Actions também consolida o JUnit daquela execução e inclui `artifacts/tcc/evidencias.json` no artifact `relatorios-windows`, sujeito à retenção de sete dias. O relatório pode ser gerado mesmo quando há falhas; seu campo `sem_falhas` e o check obrigatório precisam ser conferidos.

Código de saída do consolidador: 0 = relatório legível sem falhas/erros; 1 = relatório legível com falha/erro; 2 = entrada inválida ou problema de leitura/escrita. Um caso ignorado aparece em `ignorados` e torna `validacao_completa` falsa mesmo com código 0. Essa ferramenta resume a execução, não decide se uma justificativa para ignorar um teste é aceitável.

Os metadados de Git, versão, Python e sistema descrevem o **checkout e o ambiente no momento da consolidação**, não autenticam onde ou quando o JUnit foi produzido. Registrar ambiente de execução, comando e horário junto ao relatório original. Hashes permitem conferir integridade posterior, não autenticidade por si só. Relatórios diferentes podem conter os mesmos casos; a ferramenta mantém resultados separados e recusa cópias byte a byte para evitar soma duplicada. A duração dos testes não deve ser apresentada como tempo de resposta do bot.

## Registro mínimo de cada rodada

| Campo | Preenchimento |
| --- | --- |
| Versão e commit executados | [preencher; informar alterações locais] |
| Data e ambiente de execução | [preencher; sem usuário ou nome da máquina] |
| Comandos e códigos de saída | [preencher] |
| Relatórios e SHA-256 | [preencher a partir das evidências] |
| Falhas, erros e ignorados | [preencher e justificar] |
| URL do Actions do mesmo commit | [preencher] |
| Inferência real / estudo com pessoas | [executado ou pendente, com protocolo] |

Para a coleta de latência e qualidade, usar o [protocolo de avaliação](AVALIACAO.md). O projeto não liga Ollama, WhatsApp ou túnel real ao executar este consolidador.

O instrumento `packaging/avaliacao_tcc.py`, descrito no [laboratório](LABORATORIO.md), analisa medidas declaradas de outro tipo: tentativas A/B, julgamentos e durações do atendimento. Não misturar suas proporções com as contagens do JUnit. A origem `SIMULACAO` e os registros pendentes devem permanecer visíveis no relato; uma coleta válida e completa pode mostrar resultado negativo.
