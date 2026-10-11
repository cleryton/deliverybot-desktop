# DeliveryBot Desktop

Aplicativo Windows para cadastrar produtos de qualquer categoria, controlar estoque e receber pedidos pelo WhatsApp. Inclui atendimento humano, permissões por funcionário, backups criptografados e página de pedidos com túnel Cloudflare integrado.

O atendimento responde dúvidas simples diretamente com o cadastro, usa contexto recente na IA e apresenta links validados para cada cliente. O túnel confirma a página HTTPS antes de liberar os pedidos, acompanha reconexões e atualiza respostas pendentes para o endereço atual. O catálogo público tem busca, carrinho revisável e layout adaptado ao celular. Para manter links já enviados válidos entre reinícios, configure o domínio fixo em **Página de pedidos**.

## Instalar e usar

Dentro de `dist/`, consulte `LEIA-ME.txt` e abra a pasta da versão indicada em `VERSION`. Execute `Instalar-DeliveryBot.exe` para instalar ou `DeliveryBot.exe` para usar diretamente. O usuário final não precisa instalar Docker, Node.js ou Python. Para IA local, configure o Ollama em **WhatsApp e IA**. O seletor **Tema** permite usar modo claro, escuro ou acompanhar o Windows; a preferência continua após reabrir o aplicativo. Use **Guia de configuração** para seguir o tutorial básico.

Use o [guia do aplicativo](GUIA%20DO%20APLICATIVO.md) para configurar a loja, cadastrar produtos, conectar o WhatsApp e iniciar a página de pedidos. Os procedimentos de proteção dos dados estão em [Privacidade e segurança](PRIVACIDADE%20E%20SEGURAN%C3%87A.md).

Os dados, configurações, backups e sessão do WhatsApp do aplicativo ficam em `%LOCALAPPDATA%\DeliveryBot`, separados do código e da distribuição. Não apague essa pasta para atualizar o aplicativo. Para encerrar o atendimento, use **Sair do aplicativo** no painel ou **Sair e interromper atendimento** no ícone perto do relógio.

## O que existe nesta pasta

| Arquivo ou pasta | Finalidade |
| --- | --- |
| `dist/LEIA-ME.txt`, `dist/v<versão>/` | Indicação da versão pronta, aplicativo, instalador, metadados, hashes, guia e licenças. A limpeza mantém a atual e uma anterior íntegra. |
| `desktop.py`, `src/`, `web/`, `sql/`, `data/cardapio.json` | Código, interface, estrutura do banco e catálogo de exemplo usados pelo aplicativo e pelos testes. |
| `packaging/`, `DeliveryBot.spec`, `Compilar aplicativo.ps1` | Compilação, instalador, integridade e assinatura. |
| `whatsapp-native/`, `cloudflare/runtime/` | Código, dependências e componentes incluídos no executável. |
| `.venv/`, arquivos `requirements*.txt` | Ambiente e dependências para desenvolver, testar e compilar. |
| `tests/` | Verificações de pedidos, estoque, segurança e integrações. |
| `.env.example`, `definir_senha_cozinha.py`, `gerar_segredos.py`, `testar_ia.py` | Exemplos e utilitários para manutenção do modo servidor; não são exigidos para abrir o aplicativo instalado. |
| `.git/`, `AGENTS.md`, `VERSION`, `CHANGELOG.md`, `.gitignore` | Histórico Git, instruções, versões e exclusões de arquivos privados. |

As integrações com WAHA externo e Meta continuam disponíveis. Dependências de desenvolvimento, componentes incluídos no executável, código e catálogo de exemplo são necessários e permanecem separados dos dados de uso.

`build/`, `artifacts/`, `.pytest_cache/` e `__pycache__/` podem reaparecer ao compilar ou testar; são arquivos temporários, ignorados pelo Git. Não apague bancos, credenciais, backups ou sessões para limpar espaço.

Para manutenção, `python packaging/limpar_pasta.py` mostra o plano e `python packaging/limpar_pasta.py --aplicar` remove somente versões antigas e caches reconhecidos. É necessário ter uma distribuição atual completa e com integridade válida; a atual e a anterior válida são preservadas. Arquivos desconhecidos, distribuições futuras e diretórios com dados ou vínculos ficam de fora. Arquivos de testes em `artifacts/` precisam de revisão separada; não são apagados por essa ferramenta.

Uma página de pedidos não é hospedada em `<nome-da-loja>.whatsapp.com`. Use o endereço real gerado pela Cloudflare ou um domínio sob seu controle configurado em **Página de pedidos**. Respostas automáticas aceitam links privados gerados pelo aplicativo e links comerciais cadastrados; sites inventados pela IA são bloqueados. Links já enviados para endereços inexistentes não mudam: após atualizar, o cliente pode digitar **2** para receber um novo link.

## Desenvolvimento e compilação

Para compilar no Windows, o desenvolvedor precisa de Python 3.12 e Node.js/npm. Execute `Compilar aplicativo.ps1` no PowerShell: ele prepara as dependências, executa os testes, inclui os componentes WhatsApp e Cloudflare e gera os executáveis em `dist/v<versão>/`. A finalização copia guias e licenças, grava `VERSAO.json`, confere os hashes de todos esses arquivos e testa o executável com dados fictícios. O script faz uma compilação limpa para evitar módulos antigos em cache. Para reconferir uma distribuição, use `python packaging/distribuicao.py --verificar`.

Também é possível executar os testes com `.venv/Scripts/python.exe -m pytest -q` e os testes do componente WhatsApp com `npm test` dentro de `whatsapp-native`.

Para manutenção do modo servidor, copie `.env.example` para `.env`, configure as credenciais e execute `python -m src.app`. O provedor `TESTE` não envia mensagens reais. Não exponha o servidor de desenvolvimento nem o painel administrativo diretamente à internet; o gateway público do aplicativo limita as rotas acessíveis.

## Versões

A versão atual está em [VERSION](VERSION) e o histórico em [CHANGELOG.md](CHANGELOG.md). Cada pedido que alterar arquivos versionados gera um commit e uma tag conforme [AGENTS.md](AGENTS.md). Executáveis, dados pessoais, credenciais e dependências instaladas não são versionados.

Repositório: [cleryton/deliverybot-desktop](https://github.com/cleryton/deliverybot-desktop). Downloads publicados: [releases](https://github.com/cleryton/deliverybot-desktop/releases).
