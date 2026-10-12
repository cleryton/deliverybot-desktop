# Evidências e reprodução

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
git rev-parse HEAD
git status --short
.venv/Scripts/python.exe packaging/verificar_projeto.py
.venv/Scripts/python.exe -m pytest -q --junitxml=artifacts/tcc/python.xml
whatsapp-native/runtime/node.exe --test tests/js/experiencia.test.cjs tests/js/pong.test.cjs
npm.cmd --prefix whatsapp-native test
.venv/Scripts/python.exe packaging/evidencias_tcc.py artifacts/tcc/python.xml --saida artifacts/tcc/evidencias.json
```

Verificar o código de saída de cada comando antes de continuar. Git status deve ser registrado: se o checkout tiver alterações, o hash do commit sozinho não identifica o código testado. O Actions executa o commit enviado, com isolamento do ambiente, e é a referência para validar a integração. Os dois documentos locais já editados pelo usuário não devem ser incluídos em commits de avaliação sem revisão.

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
