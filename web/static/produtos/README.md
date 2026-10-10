# Fotos dos produtos

Coloque aqui as fotos dos itens do cardápio (jpg, png ou webp).

Para usar uma foto em um produto, adicione o campo `"imagem"` nesse item no
`data/cardapio.json`, com o nome exato do arquivo salvo nesta pasta:

```json
{
  "nome": "X-Bacon",
  "categoria": "Lanche",
  "descricao": "Pão, blend 150g, queijo, bacon crocante e molho da casa",
  "preco": 25.00,
  "imagem": "x-bacon.jpg"
}
```

Depois de editar o `cardapio.json`, para a mudança valer é preciso que o
banco seja reconstruído (apague `data/deliverybot.db`, `data/deliverybot.db-wal`
e `data/deliverybot.db-shm`, e inicie o Flask de novo -- isso reseta pedidos
e histórico, então faça isso antes de começar a usar de verdade, não depois).

Produtos sem imagem cadastrada aparecem com um retrato ilustrado automático
(ícone + cor da categoria) em vez de uma foto quebrada -- não é obrigatório
ter foto de todos os itens.

Dica de tamanho: fotos quadradas (ex: 600×600px) ficam melhores no layout
atual. Comprima antes de subir (ex: squoosh.app) para a página carregar rápido
no celular do cliente.
