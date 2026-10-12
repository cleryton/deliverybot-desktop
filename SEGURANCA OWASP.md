# Verificações OWASP do DeliveryBot

Esta referência organiza controles aplicáveis ao aplicativo usando o OWASP ASVS e as Cheat Sheets. Não constitui certificação ASVS nem garantia de ausência de vulnerabilidades. As verificações cobrem comportamentos específicos e devem evoluir com o projeto.

| Área | Controle e evidência |
| --- | --- |
| Validação de entradas | JSON UTF-8, campos únicos, números finitos, limite de 32 níveis e 25 mil nós; limites de corpo e uploads. Testes de entradas malformadas e excessivas. |
| Ambiguidade de parâmetros | Parâmetros duplicados de consulta rejeitados; formulários com campos duplicados não passam pelo CSRF. |
| Autenticação e autorização | Contas e funções verificadas no servidor, proteção contra tentativas de login, CSRF, origem e sessão; testes existentes de permissões e revogação. |
| XSS e injeção SQL | Escape na apresentação e consultas parametrizadas; os testes preservam nomes com apóstrofos e confirmam que HTML e SQL inseridos como texto não viram código. Não usamos bloqueios genéricos de palavras para nomes, produtos ou notas. |
| Isolamento público | Gateway permite apenas páginas e recursos públicos conhecidos e remove identidade de proxy; testes negam acesso ao painel com cabeçalhos forjados. |
| Destinos dos serviços | Protocolos esperados, HTTPS externo, credenciais na URL, espaços, controles e portas inválidas recusados; clientes não seguem redirecionamentos com credenciais. Serviços locais autorizados continuam funcionando. Não é uma implementação completa de proteção contra SSRF e DNS rebinding em destinos definidos pelo administrador. |
| Navegador e privacidade | CSP, prevenção de enquadramento, nosniff, isolamento de origem, cookies HttpOnly/SameSite/Secure em HTTPS, HSTS; redução de dados em logs e erros genéricos. |
| Dependências | Auditoria dos pins Python no PyPI e npm das dependências de produção; indisponibilidade da auditoria também bloqueia o check. |

## Varredura ZAP no Actions

O job de segurança cria um banco temporário com um produto e telefone fictícios, sem carregar o `.env` da loja. Publica apenas o gateway de teste em `127.0.0.1:5030`. O ZAP Baseline navega e analisa respostas passivamente; não usa contas reais, túnel externo, ataque ativo, instalação no cliente ou envio WhatsApp.

O workflow bloqueia falhas nos testes, avisos Python publicados no PyPI, vulnerabilidades npm altas/críticas, relatório ausente ou fora do escopo, alertas ZAP de risco alto e falta de controles essenciais de cookies, enquadramento, MIME ou CSP. Os demais alertas permanecem no relatório para revisão. CSP de estilos ainda permite `unsafe-inline` para compatibilidade com a interface atual; isso não autoriza scripts inline sem nonce. O relatório passivo não substitui revisão manual, testes autenticados nem verificação de todas as categorias ASVS. A ação ZAP é fixada por commit e a imagem oficial por digest; atualizações devem ser revisadas.

Docker é utilizado somente pelo runner Linux do Actions para o ZAP. O aplicativo continua sem exigir Docker, Python ou Node.js do cliente. Relatórios ficam nos artifacts por sete dias. A ação não abre issues ou publica comentários automaticamente.

## Acesso dos funcionários

O gateway dos funcionários também aplica vínculo dispositivo–conta Caixa, recusa contas administrativas, limita requisições e pareamento, mantém prazos de sessão no servidor e não os renova por consultas automáticas. Sangria e suprimento exigem autorização explícita. As permissões são verificadas novamente dentro da transação financeira, evitando gravação após revogação já confirmada. Campos inesperados são recusados e as notas do Obsidian não participam da autorização. Os testes em `tests/test_politica_terminal.py` cobrem cliente adulterado, outra conta, cookie reutilizado, inatividade, revogação concorrente e nota hostil. São controles e regressões específicas, sem declaração de certificação ou garantia de ausência de vulnerabilidades.

## Proteção do atendimento com IA

O aplicativo verifica sinais explícitos de alteração de regras, extração de informações internas e comandos privilegiados antes de chamar a IA. A proteção pausa apenas a conversa e requer revisão; frequência acima de 30 eventos/minuto e seis repetições consecutivas de texto com pelo menos 12 caracteres também pausam. Eventos duplicados não contam. Respostas com credenciais configuradas ou estrutura de prompt interno são descartadas, e mudanças na geração da conversa invalidam respostas em andamento mesmo após liberação. O controle também existe antes do transporte WhatsApp e preserva envios incertos.

Mensagens em quarentena ficam no histórico privado para a equipe, marcadas fora do contexto da IA; os registros de bloqueio guardam apenas motivo, contato e data. Somente o administrador libera a proteção, com CSRF e confirmação, e a retomada manual permanece separada. O aviso local de privacidade continua disponível. Exportação e remoção verificadas incluem os dados de proteção. O Obsidian recebe um guia operacional sem mensagens, contatos ou credenciais e não controla permissões.

Os testes em `tests/test_protecao_ia.py` usam IA e WhatsApp simulados para cobrir abusos, casos comerciais permitidos, duplicação, corrida entre pausa/liberação/inferência, fila, revisão e privacidade. As heurísticas não cobrem todos os idiomas, codificações ou ataques indiretos e podem gerar falsos positivos; não são garantia de ausência de prompt injection. As ferramentas comerciais e permissões continuam com suas próprias validações.

## Referências oficiais

- [OWASP LLM Prompt Injection Prevention](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

- [OWASP ASVS](https://owasp.org/projects/asvs)
- [Authorization: menor privilégio e verificação no servidor](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [Session Management: expiração e invalidação](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [Input Validation](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [REST Security](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html)
- [SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- [ZAP Baseline Scan](https://www.zaproxy.org/docs/docker/baseline-scan/)
