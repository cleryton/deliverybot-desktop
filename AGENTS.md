# Instruções do projeto

## Commits e versões

O usuário pediu que cada pedido concluído seja registrado como uma versão.

Repositório: `https://github.com/cleryton/deliverybot-desktop`. Branch principal: `main`.

- Ao concluir um pedido que modifique arquivos versionados, valide a alteração e gere um commit. Isso inclui alterações de código, configuração e documentação.
- Use `VERSION` como referência. Incremente o patch por padrão, o minor para funcionalidades novas e o major para mudanças incompatíveis. Registre o resultado em `CHANGELOG.md`.
- Use mensagens em português no formato `vX.Y.Z - descrição da alteração` e crie uma tag local `vX.Y.Z` para o commit correspondente. Não mova tags existentes.
- A versão inicial deste repositório é `2.2.0`, que corresponde ao aplicativo já gerado. Ao gerar uma nova distribuição, sincronize também as versões do painel e do instalador.
- Antes do commit, revise os arquivos preparados e execute as verificações adequadas à mudança. Preserve alterações do usuário e evite incluir arquivos sem relação com o pedido.
- Cada commit deve ser acompanhado da execução de testes unitários pertinentes. Alterações de comportamento devem incluir testes que cubram o comportamento novo e as regressões relevantes; alterações apenas documentais podem executar os testes existentes relacionados. Informe o resultado e aguarde o Actions do commit atual antes da integração.
- Nunca versione `.env`, credenciais, sessões do WhatsApp, bancos de dados de uso real, logs, ambientes virtuais, dependências instaladas ou executáveis gerados. Use `.env.example` apenas com valores de exemplo.
- Informe na resposta final a versão, o hash do commit e as verificações realizadas. Se não houver mudança em arquivos versionados, não crie commit vazio; informe isso quando relevante.
- O usuário autorizou a criação e o envio inicial para um novo repositório no GitHub. Para envios futuros, siga a autorização vigente na conversa; o pedido de commits por si só não autoriza publicação de novas versões ou releases.

## Validação no GitHub

- A `main` exige o check `DeliveryBot / validacao obrigatoria`. Trabalhe em uma branch `codex/`, preserve o commit e a tag de versão e use pull request para integrar alterações.
- Nunca desative a proteção ou force um envio para contornar testes com falha. Corrija o problema e aguarde a validação do commit atual.
- O workflow valida versões e sintaxe, roda os testes Python e WhatsApp simulados, compila o aplicativo e o instalador Windows e testa o executável com dados fictícios.
- Relatórios de CI ficam nos artifacts do Actions por sete dias. A execução não publica releases nem instaladores e não conecta contas reais.

## Aplicativo

- Mantenha a experiência de instalação e uso sem exigir Docker, Node.js ou Python do usuário final.
- Preserve o cadastro de produtos genéricos, estoque, pedidos e dados existentes nas atualizações.
- Execute serviços auxiliares em segundo plano, sem janelas de terminal visíveis.
- Não envie mensagens reais pelo WhatsApp nem conecte contas reais durante testes sem autorização específica.
