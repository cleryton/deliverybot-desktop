# Qualidade e confiabilidade dos pedidos

## Foco do atendimento

A versão 2.49.0 resolve o assunto atual antes da inferência. O foco é temporário: identifica os produtos pelo catálogo permitido e os aspectos pedidos, sem criar memória permanente nem ampliar permissões. O histórico enviado ao modelo contém somente antecedentes necessários à continuação; uma pergunta nova independente recebe apenas a entrada atual. Respostas anteriores do assistente não escolhem produtos pelo cliente.

O circuito Ollama oferece somente fontes compatíveis com esse foco e continua montando a resposta no aplicativo. Preço, descrição e dados operacionais são selecionados separadamente. Notas de conhecimento com assunto ou produto extra são excluídas inteiras, preservando condições e ressalvas. Uma pergunta ambígua sobre produto é esclarecida localmente; perguntas sobre prazo encaminham à equipe e não usam o horário de funcionamento ou o tempo de preparo como promessa.

Os testes usam catálogos e notas fictícios e modelos simulados. Cobrem mudança de assunto, continuações, produtos negados ou ambíguos, consulta composta, ausência de fonte e tentativa de selecionar referências alheias. Isso valida os controles e os casos reproduzidos; não mede satisfação, qualidade geral de um modelo real nem tempo de entrega do WhatsApp. O provedor remoto recebe referências reduzidas, mas não usa o renderizador fechado do Ollama.

## Limpeza de código

A revisão da versão 2.45.1 removeu três funções internas sem referências no repositório (`gerar_segredo_sugerido`, `_webhook_exibicao` e `obter_pedido_por_numero`), a constante não utilizada `FINAIS`, nove importações sem uso e três vínculos locais desnecessários. As chamadas de criação de operador e abertura de caixa continuam sendo executadas no teste do aplicativo.

As referências foram conferidas no Python, nos arquivos do navegador, nos scripts, na documentação e no empacotamento. A geração de segredos continua no utilitário `gerar_segredos.py`; a consulta de pedidos em uso continua em `obter_pedido`. Rotas Flask, métodos expostos ao navegador e configurações de bibliotecas podem ser chamados dinamicamente: um alerta isolado de análise estática não justifica removê-los.

Para reproduzir a análise, use Pyflakes 3.4.0 nos diretórios `src` e `packaging` e nos scripts Python da raiz, em ambiente de desenvolvimento separado. Vulture 2.14 ajuda a levantar candidatos, mas suas conclusões precisam ser conferidas pelas referências. Essas ferramentas não são dependências do aplicativo distribuído. A validação da limpeza executa a suíte Python completa antes e depois, os testes JavaScript e o workflow do commit atual, incluindo compilação e testes dos executáveis com dados fictícios.

## Consolidação de recursos e manutenção

Na versão 2.45.2, `gestao.css` passou a reunir as regras de layout, conexão e tema, mantendo a ordem anterior da cascata. Painel e login usam a mesma fonte de estilos. `administracao.js` reúne contas e atualizações em um escopo privado, preservando autenticação, CSRF, confirmação e verificação de assinatura. O painel carrega três recursos a menos; isso não constitui uma medição de tempo de inicialização.

A imagem exploratória da marca e o simulador legado `src/main_teste.py` saíram da árvore atual; o histórico Git os conserva. A fonte vetorial, os ícones finais e os testes completos de pedidos permanecem. O README funciona como índice dos guias operacionais, reduzindo instruções duplicadas; a documentação acadêmica foi preservada.

A geração de hashes depois da assinatura está em `python packaging/distribuicao.py --hashes --distpath dist/v<versão>`. A opção exige os quatro executáveis e recalcula o manifesto somente para arquivos conhecidos, sem copiar novamente guias ou metadados. Para conferir a distribuição final, use `--verificar` em uma chamada separada. Os testes cobrem documentos preservados, executável ausente, exclusão de arquivos privados do manifesto, recursos servidos no painel/login, temas e operações administrativas no navegador.

## Validação do carrinho

A cotação e a gravação leem os produtos em lotes de até 400 IDs. Não há cache de preços ou estoque. Itens repetidos são somados antes de conferir o saldo, e valores monetários continuam usando Decimal e arredondamento por item. A cotação mantém um snapshot de leitura, enquanto a gravação mantém a transação de escrita existente.

Uma comparação local no Windows, com SQLite temporário e produtos fictícios, executou duas rodadas de aquecimento e sete amostras por condição. A referência foi o commit `139e6b1`; as saídas antigas e novas foram comparadas integralmente.

| Produtos distintos no carrinho | Consultas antes | Consultas depois | Mediana antes | Mediana depois |
| --- | ---: | ---: | ---: | ---: |
| 120 | 240 | 1 | 4,545 ms | 3,292 ms |
| 850 | 1.700 | 3 | 30,481 ms | 21,783 ms |

Essas medições cobrem a resolução dos itens em uma conexão aberta, não a compra completa, o Ollama, a rede ou a inicialização do aplicativo. Os testes automatizados usam a quantidade de consultas como limite de regressão, sem exigir tempos específicos do equipamento. Também simulam alteração concorrente de preços entre lotes.

## Consulta de endereço

A resposta ViaCEP precisa conter um objeto válido, o CEP solicitado, cidade e UF reconhecida. Campos inesperados não autorizam a entrega nem provocam uma falha interna. CEPs gerais podem ter rua e bairro vazios.

Endereços públicos válidos por CEP são reutilizados em memória por cinco minutos, com limite de 256 entradas. Nome, número e complemento não entram no cache. Cada chamada confere novamente a lista de cidades atendidas; erros e indisponibilidade não ficam em cache. A conexão tem prazos de conexão e leitura e não segue redirecionamentos.

## Comprovante após confirmação

Depois de salvar o pedido, o servidor responde com redirecionamento HTTP 303 para uma página de comprovante. Atualizar essa página faz somente uma leitura: não cria outra compra, não altera o estoque e não repete mensagens WhatsApp. O link original continua aceitando uma única compra.

O comprovante exige o token e a sessão assinada do mesmo navegador que confirmou o pedido. O cookie contém somente hash do token, ID, prazo e flags de confirmação; não contém nome, telefone ou endereço. São guardadas até cinco autorizações, por oito horas, sem renovação pela consulta. A página usa `no-store` e não oferece uma listagem pública de pedidos.

Outro navegador, sessão removida ou expirada e pedido indisponível recebem acesso indisponível. Reiniciar o aplicativo ou o servidor pode invalidar a sessão. Portanto, o cliente deve imprimir ou salvar o PDF se precisar guardar o comprovante. Uma conexão interrompida antes de o navegador receber a sessão também pode impedir a recuperação; o sistema mantém a proteção contra uma segunda confirmação.

## Testes

- `tests/test_carrinho_lote.py`: consultas, agrupamento, precisão, preços atuais, custos internos e snapshot concorrente.
- `tests/test_viacep.py`: respostas malformadas, recuperação após timeout, validade e limite do cache e regras de área de entrega.
- `tests/test_comprovante.py`: redirecionamento, atualização sem efeitos, isolamento entre navegadores, prazo, limite de sessão e pedido indisponível.
- As suítes existentes de compra, publicação, segurança, estoque, conversa e QA também são executadas, com dados fictícios e sem contas reais.
