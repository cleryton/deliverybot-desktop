# Histórico de versões

## 2.10.0 — 2026-10-10

Consulta opcional de releases, download com origem e SHA-256 verificados, backup antes de atualizar e instalação condicionada à assinatura confiável. Preparação de distribuição e assinatura digital, com correções da integração do atendimento humano.

## 2.9.0 — 2026-10-10

Contas individuais de administradores e atendentes, permissões verificadas no servidor e na ponte nativa, senhas scrypt, revogação de sessões e auditoria sem conteúdo de mensagens.

## 2.8.0 — 2026-10-10

Estoque fracionado com precisão de três casas, famílias e variações, importação CSV com prévia e transação integral, custos históricos e relatórios por período. Validados 33 testes de catálogo, pedidos e aprimoramentos, incluindo cancelamento e ausência de importação parcial.

## 2.7.0 — 2026-10-10

Atendimento humano por conversa: comando ATENDENTE, leitura do histórico, pausa e retomada do bot, respostas manuais confirmadas pela fila persistente e proteção contra retomada com envios pendentes. Validado com serviços simulados.

## 2.6.0 — 2026-10-10

Backups automáticos portáteis criptografados, senha protegida no Windows, verificação de recuperação, destino e rotação configuráveis. Limpeza diária opcional da retenção, alertas de atraso e recuperação de horários perdidos. Testes de rotação e ausência da senha na cópia aprovados.

## 2.5.0 — 2026-10-10

Atendimento em segundo plano com ícone na área do relógio, opções de reabrir e encerrar, preservando os serviços ao fechar a janela. Validado o ciclo real da bandeja Windows, sem contas ou dados reais.

## 2.4.0 — 2026-10-10

Configuração inicial guiada com checklist da loja, privacidade, catálogo, WhatsApp, IA e confirmação de abertura do endereço público no celular. Teste temporário vinculado ao endereço configurado, sem expor dados ou segredos.

## 2.3.0 — 2026-10-10

- Área Privacidade e LGPD com identificação do responsável, canal de contato, aviso público, exportação, correção e remoção da identificação do cadastro.
- Retenção configurável das conversas, limpeza manual do histórico concluído e auditoria sem conteúdo pessoal.
- Backups portáveis com AES-256-GCM, senha derivada por scrypt e detecção de alteração; credenciais dos serviços excluídas da cópia portável. Cópias de recuperação automáticas protegidas pela conta Windows.
- Segredos das configurações protegidos com DPAPI no Windows; permissões da pasta de dados restritas à conta atual e SYSTEM.
- Servidor Desktop restrito ao computador; acesso administrativo remoto desligado por padrão; limitação de tentativas de senha e proteção CSRF também na cozinha e no pedido.
- Cabeçalhos contra exposição em cache, referências externas e execução de scripts não autorizados. Fontes externas removidas da cozinha.
- Dados pessoais reduzidos em logs e no histórico enviado à IA; envio a IA externa desligado por padrão e HTTPS exigido para serviços externos com dados ou credenciais.
- Aviso de privacidade no formulário de compra e no primeiro atendimento; comando PRIVACIDADE disponível sem depender de IA.
- Atualização das versões de Flask, Requests, python-dotenv, pytest, setuptools e wheel para corrigir avisos públicos de vulnerabilidades; utilitário de consulta ao PyPI disponível em `packaging/auditar_dependencias.py`.

Validação: 67 testes Python e 10 testes Node aprovados; janela, cadastro de privacidade, backup criptografado e API nativa verificados no executável. Consultas ao PyPI (49 pacotes fixados) e npm audit sem avisos conhecidos. Conexões simuladas, sem contas ou mensagens reais.

As medidas técnicas apoiam a proteção de dados. A loja continua responsável pela política de retenção, bases legais, identidade dos solicitantes, provedores e tratamento de incidentes; veja `PRIVACIDADE E SEGURANÇA.md`.

## 2.2.0 — 2026-10-10

Primeira versão registrada neste repositório, reunindo o aplicativo Windows já desenvolvido.

- Aplicativo e instalador Windows com painel de produtos, estoque, pedidos e configurações.
- Cadastro de produtos de qualquer categoria e controle de movimentações de estoque.
- WhatsApp integrado com QR Code e sessão persistente, sem instalação de Docker ou Node.js.
- Fila persistente de mensagens, proteção contra eventos duplicados e revisão de envios incertos.
- Botões para iniciar o Ollama, baixar modelos e ativar a IA local.
- Backup e restauração do banco, preservação dos dados nas atualizações e serviços em segundo plano.
- Política de commits e versões por pedido registrada em `AGENTS.md`.

Validação do aplicativo antes deste registro: 46 testes Python e 10 testes Node aprovados; abertura do executável e formulários verificados; QR Code real gerado sem parear uma conta nem enviar mensagens.
