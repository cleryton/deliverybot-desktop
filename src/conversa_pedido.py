"""Compra pelo chat: rascunho privado, resumo oficial e confirmação transacional.

O modelo e as notas do Obsidian não escrevem pedidos nem definem valores.
O reconhecimento local pede esclarecimento para produtos ambíguos.
"""
import json
import re
import secrets
from decimal import Decimal

from . import cardapio, config, pedidos, recibo
from .db import get_conn
from .estoque import medida, nome_completo, somar, listar_produtos


def normalizar(texto):
    from .ia import normalizar_texto
    return normalizar_texto(texto)


def dinheiro(valor):
    return 'R$ ' + f'{valor:.2f}'.replace('.', ',')


def _ler(telefone):
    with get_conn() as conn:
        row = conn.execute("SELECT *, atualizado_em > datetime('now','-30 minutes') AS valido FROM carrinhos_conversa WHERE telefone=?", (telefone,)).fetchone()
        conn.execute("DELETE FROM carrinhos_conversa WHERE atualizado_em <= datetime('now','-30 minutes')")
    return dict(row) if row else None


def _salvar(telefone, token, dados):
    with get_conn() as conn:
        conn.execute("INSERT INTO carrinhos_conversa(telefone,token,dados) VALUES (?,?,?) ON CONFLICT(telefone) DO UPDATE SET token=excluded.token,dados=excluded.dados,pedido_id=NULL,atualizado_em=datetime('now') WHERE carrinhos_conversa.pedido_id IS NULL OR carrinhos_conversa.token!=excluded.token", (telefone, token, json.dumps(dados, ensure_ascii=False)))


def _apagar(telefone):
    with get_conn() as conn:
        conn.execute('DELETE FROM carrinhos_conversa WHERE telefone=?', (telefone,))


def _pedido_chat(texto):
    if re.search(r'\bnao quero (?:pedir|comprar|fazer (?:um )?pedido|pedido pelo)', normalizar(texto)):
        return False
    return bool(re.search(r'\b(?:sem (?:o )?link|nao (?:quero|consigo|vou)\b.{0,30}\blink|pedido pelo (?:whats|whatsapp|chat)|pedir (?:por aqui|pelo whatsapp)|comprar por aqui|pedido por aqui)\b', normalizar(texto)))


def _limpar_nome(texto):
    return ' '.join(re.sub(r'[^\w]+', ' ', normalizar(texto)).split())


def _padrao(nome):
    # Plural simples: "calabresas grandes" encontra "Calabresa · Grande".
    return r'(?<!\w)' + r'\s+'.join(re.escape(p) + ('s?' if not p.endswith('s') else '') for p in _limpar_nome(nome).split()) + r'(?!\w)'


def _identificar(trecho, produtos):
    limpo = _limpar_nome(trecho)
    candidatos = []
    for produto in produtos:
        for nome in {produto['nome'], nome_completo(produto)}:
            match = re.search(_padrao(nome), limpo)
            if match:
                candidatos.append((len(match[0]), produto, match))
    if not candidatos:
        raise ValueError('Não encontrei esse produto. Use o nome e a variação do catálogo; digite CATÁLOGO para consultar.')
    maior = max(c[0] for c in candidatos)
    selecionados = {c[1]['id']:c for c in candidatos if c[0]==maior}
    if len(selecionados)>1:
        opcoes = '; '.join(nome_completo(c[1]) for c in list(selecionados.values())[:8])
        raise ValueError('Qual variação você quer? ' + opcoes + '. Informe também a quantidade.')
    _, produto, match = next(iter(selecionados.values()))
    resto = (limpo[:match.start()]+' '+limpo[match.end():]).strip()
    # Quantidades não participam da correspondência do nome.
    resto = re.sub(r'\b\d+\b', '', resto)
    palavras = set(resto.split())
    permitidas = {'quero','queria','gostaria','de','do','da','um','uma','dois','duas','tres','quatro','cinco',
                  'adicionar','adicione','adiciona','mais','levar','vou','pedir','pedido','por','favor',
                  'pizza','pizzas','produto','produtos','un','unidade','unidades','kg','quilo','quilos','g','litro','litros',
                  'remover','remove','retirar','alterar','corrigir','para','x'}
    if palavras-permitidas:
        raise ValueError('Não consegui conferir todos os detalhes desse item. Envie quantidade, nome e variação, sem observações. Para alterações especiais, digite ATENDENTE.')
    return produto


def _itens(texto, produtos):
    # Protege o "e" que faz parte de um nome, antes de separar vários itens.
    protegido = normalizar(texto)
    for p in produtos:
        for nome in {normalizar(p['nome']), normalizar(nome_completo(p))}:
            if ' e ' in nome:
                protegido = protegido.replace(nome, nome.replace(' e ', ' __E__ '))
    partes = [p.strip().replace('__E__', 'e') for p in re.split(r'(?<!\d),|;|\n|\s+e\s+', protegido) if p.strip()]
    if not 1<=len(partes)<=30:
        raise ValueError('Envie até 30 itens por mensagem.')
    resultado = []
    for parte in partes:
        produto = _identificar(parte, produtos)
        # Só a quantidade antes do produto; "Coca-Cola 2 litros" não vira 2 unidades.
        consulta = re.sub(r'[^\w.,]+',' ',parte)
        nomes = [re.search(_padrao(nome), consulta) for nome in {produto['nome'],nome_completo(produto)}]
        nomes = [m for m in nomes if m]
        prefixo = consulta[:min(m.start() for m in nomes)]
        if re.search(r'[-−]\s*\d', parte[:len(prefixo)]):
            raise ValueError('A quantidade deve ser positiva.')
        numeros = re.findall(r'(?<!\w)\d+(?:[,.]\d+)?', prefixo)
        if len(numeros)>1:
            raise ValueError('Informe uma quantidade por item.')
        palavras = {'um':1,'uma':1,'dois':2,'duas':2,'tres':3,'quatro':4,'cinco':5}
        quantidade = numeros[0].replace(',','.') if numeros else next((v for k,v in palavras.items() if re.search(r'\b'+k+r'\b', prefixo)),1)
        quantidade = medida(quantidade, 'Quantidade', bool(produto.get('fracionado')), .001 if produto.get('fracionado') else 1)
        resultado.append({'produto_id':produto['id'],'quantidade':quantidade})
    return resultado


def _pagamento(texto):
    t = normalizar(texto)
    if re.search(r'\b(?:nao|nem)\b',t):
        return None
    candidatos = []
    for forma in (f.strip() for f in config.FORMAS_PAGAMENTO.split(',') if f.strip()):
        chave = normalizar(forma)
        termos = [chave]
        if 'credito' in chave:
            termos.append('credito')
        elif 'debito' in chave:
            termos.append('debito')
        if any(re.search(r'(?<!\w)'+re.escape(k)+r'(?!\w)', t) for k in termos):
            candidatos.append(forma)
    return candidatos[0] if len(candidatos)==1 else None


def _confirmacao(texto):
    t = normalizar(texto).strip(' .!')
    if re.search(r'\b(?:nao|nem|cancelar|quanto|posso|se|talvez|mais)\b|\?', t):
        return False
    return bool(re.fullmatch(r'(?:sim|confirmar|confirmo|confirme|confirmado|pode confirmar|confirmo (?:o |meu )?pedido)(?:[,; ]+(?:vou pagar|pagarei|pago|pagamento)(?: em| com)? [\w ]+)?', t))


def _resumo(dados):
    q=dados['cotacao']
    linhas=['Confira antes de confirmar:']
    for i in q['itens']:
        linhas.append(f"• {i['quantidade']:g} × {i['nome']} — {dinheiro(i['subtotal'])}")
    linhas.extend([f"Cliente: {dados['nome']}", 'Recebimento: '+('Entrega' if dados['entrega']=='ENTREGA' else 'Retirada na loja')])
    if dados['entrega']=='ENTREGA':
        linhas.append('Endereço: '+dados['endereco'])
        linhas.append('Taxa de entrega: '+dinheiro(q['taxa_entrega']))
    linhas.extend(['Pagamento: '+dados['pagamento'], 'Total: '+dinheiro(q['total_pedido']),
                   'Ainda não foi enviado à loja. Digite CONFIRMAR para concluir ou informe uma alteração. Para desistir, digite CANCELAR.'])
    return '\n'.join(linhas)


def _avancar(dados):
    if not dados['itens']:
        return 'Vamos fazer por aqui! Quais produtos e quantidades você quer? Use o nome e a variação do catálogo. Exemplo: 2 Calabresa Grande e 1 Coca-Cola 2 litros. Digite CATÁLOGO para consultar ou CANCELAR para sair.'
    if not dados.get('nome'):
        return 'Anotei os itens. Como podemos te chamar?'
    if not dados.get('entrega'):
        return 'Você prefere entrega ou retirada na loja?'
    if dados['entrega']=='ENTREGA' and not dados.get('endereco'):
        return 'Qual é o endereço da entrega, com rua, número e bairro? Informe só os dados necessários para esta compra.'
    if not dados.get('pagamento'):
        return 'Como prefere pagar? Opções cadastradas: '+config.FORMAS_PAGAMENTO+'.'
    dados['cotacao']=pedidos.cotacao(dados['itens'],dados['entrega'])
    return _resumo(dados)


def _concluido(pedido):
    return (recibo.montar_mensagem_confirmacao(pedido)+'\n\n'+recibo.montar_recibo(pedido)
            +'\n\nPagamento combinado: '+pedido['forma_pagamento']+'. O recebimento do pagamento será conferido pela equipe.')


def responder(telefone, texto):
    """None permite continuar a conversa normal. Nunca chama um transporte real."""
    t=normalizar(texto).strip(' .!')
    if t in {'9','privacidade','lgpd','meus dados','menu','ajuda','oi','ola','obrigado','obrigada'}:
        return None
    row=_ler(telefone)
    produtos=listar_produtos()  # Permite remover também itens que acabaram ou foram desativados.
    iniciar=_pedido_chat(texto)
    # Uma seleção concreta pode iniciar o chat, mas perguntas de preço não.
    if not row and re.match(r'^(?:quero|queria|gostaria de|vou levar)\s+',t):
        iniciar = iniciar or any(re.search(_padrao(p['nome']), _limpar_nome(texto)) for p in produtos)
    if row and not row['valido']:
        _apagar(telefone)
        if not iniciar:
            return 'O rascunho expirou após 30 minutos. Para começar de novo, diga PEDIDO PELO WHATSAPP.' if _confirmacao(texto) else None
        row=None
    if row and row['pedido_id']:
        if _confirmacao(texto):
            return _concluido(pedidos.obter_pedido(row['pedido_id']))
        if not iniciar and not re.match(r'^(?:quero|queria|gostaria de|vou levar)\s+',t):
            return None
        row=None
        iniciar=True
    if row and re.search(r'\b(?:quero|manda|envia|prefiro)\b.{0,25}\blink\b',t) and not _pedido_chat(texto):
        _apagar(telefone)
        return None
    if not row and not iniciar:
        return None
    token=row['token'] if row else secrets.token_urlsafe(32)
    dados=json.loads(row['dados']) if row else {'itens':[]}
    if t in {'cancelar','cancelar pedido','cancelar meu pedido','desistir','desisti'}:
        _apagar(telefone)
        return 'Descartei este rascunho. Nenhum pedido foi enviado à loja.'
    if t in {'4','catalogo','cardapio'}:
        return cardapio.texto_cardapio()+'\n\nEnvie os produtos com quantidade e variação para continuar por aqui.'
    if dados.get('cotacao') and _confirmacao(texto):
        pagamento=_pagamento(texto)
        if pagamento and pagamento!=dados['pagamento']:
            dados['pagamento']=pagamento
            dados.pop('cotacao',None)
        else:
            try:
                pedido=pedidos.criar_pedido(telefone,dados['nome'],dados['itens'],dados['pagamento'],dados['entrega'],endereco=dados.get('endereco',''),conversa=token)
            except pedidos.CotacaoAlterada:
                dados.pop('cotacao',None)
                resposta='O cadastro mudou desde o resumo. Revise os valores atualizados:\n\n'+_avancar(dados)
                _salvar(telefone,token,dados)
                return resposta
            except ValueError as exc:
                dados.pop('cotacao',None)
                _salvar(telefone,token,dados)
                return str(exc)+' Altere os itens ou digite CANCELAR. Nenhum pedido foi enviado.'
            return _concluido(pedido)
    elif _confirmacao(texto):
        # Confirmação sem resumo nunca cria a compra.
        resposta=_avancar(dados)
        _salvar(telefone,token,dados)
        return resposta
    else:
        mudou=False
        pagamento=_pagamento(texto)
        if pagamento:
            dados['pagamento']=pagamento
            mudou=True
        if re.fullmatch(r'(?:quero |prefiro |vou )?(?:retirada|retirar|retirar na loja|buscar na loja|retirada na loja|balcao)',t):
            dados['entrega']='RETIRADA BALCAO'
            dados.pop('endereco',None)
            mudou=True
        elif re.fullmatch(r'(?:quero |prefiro )?(?:entrega|entregar|que entregue|entrega em casa)',t):
            dados['entrega']='ENTREGA'
            mudou=True
        nome=re.match(r'^(?:meu nome (?:e|é)|nome)\s*:?\s*(.+)',texto, re.I)
        endereco=re.match(r'^(?:endereco|endereço)\s*:?\s*(.+)',texto, re.I)
        if nome or (dados['itens'] and not dados.get('nome') and not mudou):
            valor=(nome[1] if nome else texto).strip()
            if not re.fullmatch(r"[\wÀ-ÿ '\-]{2,160}",valor) or re.search(r'\d',valor):
                return 'Informe seu nome, sem números, links ou outros dados pessoais.'
            dados['nome']=valor
            mudou=True
        elif endereco or (dados.get('entrega')=='ENTREGA' and not dados.get('endereco') and not mudou):
            valor=(endereco[1] if endereco else texto).strip()
            if not 8<=len(valor)<=400 or re.search(r'https?://|www\.|[\x00-\x1f]',valor,re.I):
                return 'Informe rua, número e bairro, sem links. Se precisar, digite ATENDENTE.'
            dados['endereco']=valor
            mudou=True
        if not mudou and not _pedido_chat(texto):
            try:
                itens=_itens(texto,produtos)
                existentes={i['produto_id']:i['quantidade'] for i in dados['itens']}
                remover=bool(re.match(r'^(?:remover|remove|retirar)\b',t))
                definir=bool(re.match(r'^(?:alterar|corrigir)\b',t))
                for i in itens:
                    id_=i['produto_id']
                    if remover:
                        existentes.pop(id_,None)
                    else:
                        soma=somar(existentes.get(id_,0),i['quantidade'])
                        existentes[id_]=i['quantidade'] if definir else int(soma) if isinstance(i['quantidade'],int) else soma
                if len(existentes)>30 or any(Decimal(str(q))>999999 for q in existentes.values()):
                    raise ValueError('Limite de itens ou quantidade excedido.')
                novos=[{'produto_id':id_,'quantidade':q} for id_,q in existentes.items()]
                if novos:
                    pedidos.cotacao(novos,dados.get('entrega','RETIRADA BALCAO'))
                dados['itens']=novos
                mudou=True
            except ValueError as exc:
                if not row:
                    _salvar(telefone,token,dados)
                return str(exc)+' O rascunho foi mantido. Nenhum pedido foi enviado.'
        if mudou:
            dados.pop('cotacao',None)
    try:
        resposta=_avancar(dados)
    except ValueError as exc:
        dados.pop('cotacao',None)
        resposta=str(exc)+' Altere os itens ou digite CANCELAR. Nenhum pedido foi enviado.'
    _salvar(telefone,token,dados)
    return resposta
