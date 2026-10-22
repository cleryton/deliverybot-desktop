# Qualidade e confiabilidade dos pedidos

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
