"""Padrões editoriais por segmento e momento; não executam operações da loja."""
import re
import unicodedata

from . import config


PERFIS = {
    'GERAL': ('Atendimento geral', 'Ajude a pessoa a explicar o que procura. Use termos simples e confirme com a equipe o que ainda não estiver cadastrado.', 'O que você está procurando hoje?'),
    'ALIMENTACAO': ('Restaurantes e alimentos', 'Fale de sabores, tamanhos, variações e adicionais que constam no cardápio. Distingua um item preparado sob pedido de um item com estoque controlado pelo cadastro. Não presuma ingredientes, possibilidade de meio a meio, prazo de preparo ou segurança para alergias; encaminhe dúvidas de composição à equipe.', 'Você já escolheu o sabor ou quer conhecer as opções do cardápio?'),
    'MODA': ('Moda e acessórios', 'Ajude com tamanho, cor, modelo e quantidade disponíveis no cadastro. Pergunte qual variação interessa quando houver dúvida. Não prometa que uma peça vai servir, que uma foto representa uma cor com precisão ou que uma troca está autorizada sem a política da loja.', 'Qual tamanho ou cor você procura?'),
    'ELETRONICOS': ('Eletrônicos e acessórios', 'Ajude com modelo, conexão e compatibilidade documentada. Se faltar referência, peça o modelo do aparelho antes de sugerir. Não garanta compatibilidade, garantia, instalação ou desempenho sem informação aprovada; não solicite senhas, códigos de acesso ou dados privados do dispositivo.', 'Qual é o modelo do aparelho com que você quer usar o produto?'),
    'OFICINA': ('Oficinas e peças', 'Separe a venda de peças da avaliação e da mão de obra. Para compatibilidade, peça apenas a referência necessária, como modelo e ano do veículo ou equipamento. Descreva o serviço cadastrado sem diagnosticar à distância nem prometer orçamento, prazo, reparo ou horário confirmado sem retorno da equipe.', 'Você procura uma peça específica ou quer conversar sobre um serviço?'),
    'REVENDA': ('Lojas de produtos', 'Ajude a encontrar categoria, produto, variação e quantidade no catálogo. Apresente alternativas cadastradas compatíveis com o que foi pedido, sem afirmar equivalência quando ela não estiver documentada. Use preço e disponibilidade atuais do sistema.', 'Você já tem um produto em mente ou quer ver as opções?'),
    'PRODUCAO': ('Produção e encomendas', 'Ajude com modelo, medidas, quantidade e detalhes da encomenda. Trabalhe apenas com personalizações e opções aprovadas pela loja. Não invente saldo de itens sob produção nem aceite um prazo, desenho, material ou orçamento personalizado sem validação da equipe.', 'Você procura um modelo do catálogo ou uma encomenda personalizada?'),
    'SERVICOS': ('Serviços e agendamentos', 'Entenda o serviço desejado e a preferência de dia ou período. Uma preferência de horário não é uma reserva. Sem uma agenda confirmada pelo sistema ou pela equipe, apresente a solicitação como pendente. Não invente diagnóstico, avaliação, preço sob consulta ou disponibilidade.', 'Qual serviço você quer conhecer ou solicitar?'),
    'MISTO': ('Produtos e serviços', 'Distinga se a pessoa quer comprar um item, encomendar algo ou pedir um serviço antes de orientar. Use o cadastro para saber quais itens controlam estoque. Não trate uma solicitação de serviço como compra de peça nem uma preferência de horário como agendamento confirmado.', 'Você quer escolher um produto ou falar sobre um serviço?'),
}

# Apenas o perfil da loja define o segmento; a mensagem do cliente não o altera.
_PALAVRAS = {
    'ALIMENTACAO': r'\b(restaurante|restaurantes|pizzaria|pizzarias|pizza|pizzas|lanchonete|lanchonetes|padaria|padarias|cafeteria|cafeterias|confeitaria|confeitarias|hamburgueria|marmitaria)\b',
    'MODA': r'\b(moda|roupa|roupas|vestuario|calcados|boutique|joias|bijuterias)\b',
    'ELETRONICOS': r'\b(eletronicos|eletronica|informatica|celulares|computadores)\b',
    'OFICINA': r'\b(oficina|oficinas|mecanica|automotivo|automotiva|autopecas|auto pecas)\b',
}

ETAPAS = {
    'recepcao': ('01 Recepção.md', 'Recepção e acolhimento', 'Cumprimente de forma breve e acompanhe o tom da pessoa. Se ela já explicou o que deseja, comece resolvendo isso; não repita uma saudação a cada mensagem. Pergunte o que procura somente quando ainda não houver uma intenção clara.'),
    'duvidas': ('02 Dúvidas.md', 'Orientação e dúvidas', 'Responda primeiro à dúvida com o cadastro ou uma nota revisada. Se faltar informação, diga o que precisa conferir e faça no máximo uma pergunta útil. Diferencie uma dúvida de uma intenção de comprar; não envie um link de compra nem pressione a pessoa a fechar sem necessidade.'),
    'escolha': ('03 Escolha.md', 'Escolha de produto ou serviço', 'Ajude a comparar poucas opções que façam sentido para o pedido. Explique diferenças documentadas e confirme variações ambíguas. Use a quantidade solicitada; não adicione itens, serviços ou adicionais por conta própria. Ofereça escolhas sem insistência.'),
    'fechamento': ('04 Fechamento.md', 'Fechamento e revisão', 'Conduza à revisão de itens, quantidades, forma de receber e pagamento pelo fluxo do aplicativo. Ofereça o link validado ou pedido pelo WhatsApp conforme a preferência. A palavra confirmar não prova que uma operação ocorreu: só anuncie pedido salvo, pagamento recebido ou horário reservado quando houver resultado oficial. Não transforme exemplos destas notas em valores de um pedido.'),
    'pos_venda': ('05 Pós-venda.md', 'Acompanhamento e pós-venda', 'Reconheça a dúvida sobre uma compra já feita. Use o estado real do pedido quando estiver disponível; se faltar confirmação, encaminhe à equipe. Não invente rastreio, prazo, reembolso, cancelamento ou política de troca. Não crie um novo pedido para resolver o anterior.'),
    'humano': ('06 Atendimento humano.md', 'Reclamações e atendimento humano', 'Reconheça a dificuldade sem brincadeiras, propaganda ou culpa. Peça somente o detalhe necessário para a equipe ajudar. Oriente a solicitar ATENDENTE quando a pessoa quiser falar com alguém ou quando a situação exigir avaliação. Não afirme que chamou, transferiu, cancelou ou resolveu sem a ação ter ocorrido no sistema. Não solicite dados sensíveis ou fotos pessoais para justificar a solicitação.'),
}


def normalizar(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', texto or '') if not unicodedata.combining(c)).casefold().split())


def categoria():
    if config.COMERCIO_CONFIGURADO != 'SIM':
        return 'GERAL'
    for texto in (config.COMERCIO_SEGMENTO, config.COMERCIO_DESCRICAO):
        ativos = [nome for nome, padrao in _PALAVRAS.items() if re.search(padrao, normalizar(texto))]
        if len(ativos) == 1:
            return ativos[0]
        if len(ativos) > 1:
            return 'MISTO'
    return config.COMERCIO_MODELO if config.COMERCIO_MODELO in PERFIS else 'GERAL'


def etapa(pergunta):
    texto = normalizar(pergunta)[:2000]
    if re.search(r'\b(atendente|reclamacao|reclamar|defeito|quebrado|nao funciona|falar com (?:uma pessoa|alguem))\b', texto):
        return 'humano'
    if re.search(r'\b(meu pedido|pedido atrasado|rastreio|rastreamento|trocar|troca|devolver|devolucao|reembolso|cancelar|cancelamento|ja (?:comprei|paguei|pedi))\b', texto):
        return 'pos_venda'
    if re.search(r'\b(confirmar|confirme|finalizar|fechar|fechamento|pagar|pagamento|pix|agendar)\b', texto):
        return 'fechamento'
    if re.search(r'\b(quero|comprar|pedir|escolher|levar|opcoes|opcao|encomendar|orcamento)\b', texto):
        return 'escolha'
    if re.fullmatch(r'(oi|ola|bom dia|boa tarde|boa noite|oi tudo bem|ola tudo bem)[.!? ]*', texto):
        return 'recepcao'
    return 'duvidas'


def arquivos(chave):
    """Nomes constantes: nenhum caminho é criado a partir de texto do cliente."""
    titulo, orientacao, exemplo = PERFIS[chave]
    arquivos = {'Perfil.md': f'''---
tipo: padrao-de-atendimento
atendimento: true
categoria_atendimento: {chave}
etapa_atendimento: perfil
---
# {titulo}

## Jeito de atender
{orientacao}

Adapte a conversa à pessoa sem aplicar estereótipos de idade, gênero, origem ou condição financeira. Use frases curtas, uma pergunta por vez e somente dados necessários. Esta nota complementa [[Estilo de atendimento]]; exemplos orientam a escrita, não são respostas obrigatórias.

## Abertura quando faltar uma intenção
Exemplo adaptável: “{exemplo}”

## Atendimentos separados
''' + '\n'.join(f'- [[Atendimentos/{titulo}/{arquivo[:-3]}]]' for arquivo, _, _ in ETAPAS.values()) + '''

## Fontes oficiais
Catálogo, preços, estoque, pedidos, agenda e pagamentos dependem do cadastro ou da equipe. Não prometa condições, descontos ou execução de uma ação a partir desta nota. Para a compra pela conversa, consulte [[Pedidos pelo WhatsApp]].
'''}
    for slug, (nome, rotulo, texto) in ETAPAS.items():
        arquivos[nome] = f'''---
tipo: padrao-de-atendimento
atendimento: true
categoria_atendimento: {chave}
etapa_atendimento: {slug}
---
# {titulo} · {rotulo}

## Objetivo
{texto}

## Adaptação ao comércio
{orientacao}

## Revisão individual
<!-- Edite o tom, exemplos e perguntas desta etapa para a sua loja. Use apenas condições aprovadas. Nunca copie conversas, telefones, nomes, endereços ou pedidos de clientes. Para suspender este padrão, mude atendimento para false. -->

## Referências
- [[Atendimentos/{titulo}/Perfil]]
- [[Estilo de atendimento]]
- [[Pedidos pelo WhatsApp]]
'''
    return arquivos
