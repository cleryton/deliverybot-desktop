# Instruções do projeto

## Commits e versões

O usuário pediu que cada pedido concluído seja registrado como uma versão.

Repositório: `https://github.com/cleryton/deliverybot-desktop`. Branch principal: `main`.

- Ao concluir um pedido que modifique arquivos versionados, valide a alteração e gere um commit. Isso inclui alterações de código, configuração e documentação.
- Use `VERSION` como referência. Incremente o patch por padrão, o minor para funcionalidades novas e o major para mudanças incompatíveis. Registre o resultado em `CHANGELOG.md`.
- Use mensagens em português no formato `vX.Y.Z - descrição da alteração` e crie uma tag local `vX.Y.Z` para o commit correspondente. Não mova tags existentes.
- A versão inicial deste repositório é `2.2.0`, que corresponde ao aplicativo já gerado. Ao gerar uma nova distribuição, sincronize também as versões do painel e do instalador.
- Antes do commit, revise os arquivos preparados e execute as verificações adequadas à mudança. Preserve alterações do usuário e evite incluir arquivos sem relação com o pedido.
- Nunca versione `.env`, credenciais, sessões do WhatsApp, bancos de dados de uso real, logs, ambientes virtuais, dependências instaladas ou executáveis gerados. Use `.env.example` apenas com valores de exemplo.
- Informe na resposta final a versão, o hash do commit e as verificações realizadas. Se não houver mudança em arquivos versionados, não crie commit vazio; informe isso quando relevante.
- O usuário autorizou a criação e o envio inicial para um novo repositório no GitHub. Para envios futuros, siga a autorização vigente na conversa; o pedido de commits por si só não autoriza publicação de novas versões ou releases.

## Aplicativo

- Mantenha a experiência de instalação e uso sem exigir Docker, Node.js ou Python do usuário final.
- Preserve o cadastro de produtos genéricos, estoque, pedidos e dados existentes nas atualizações.
- Execute serviços auxiliares em segundo plano, sem janelas de terminal visíveis.
- Não envie mensagens reais pelo WhatsApp nem conecte contas reais durante testes sem autorização específica.
