"""Foco efêmero do atendimento, extraído somente da consulta e do catálogo.

Não decide permissões, não executa pedidos e não consulta dados persistidos.
Continuações fechadas retomam somente uma referência inequívoca do cliente.
"""
from dataclasses import dataclass, field
import re
import unicodedata


def _normalizar(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(texto or ''))
                           if not unicodedata.combining(c)
                           and unicodedata.category(c) != 'Cf').casefold().split())


def _eventos_anteriores(mensagens, pergunta):
    """Desagrupa entradas sem herdar linhas de assuntos anteriores à atual."""
    turnos = [{'role': m.get('role'), 'content': str(m.get('content') or '')}
              for m in mensagens or () if isinstance(m, dict)
              and m.get('role') in {'user', 'assistant'}]
    for turno in reversed(turnos):
        if turno['role'] != 'user':
            continue
        atual = turno['content'].strip()
        if _normalizar(atual) == _normalizar(pergunta):
            turno['content'] = ''
        elif pergunta and atual.endswith('\n' + pergunta.strip()):
            turno['content'] = atual[:-(len(pergunta.strip()) + 1)]
        break
    return [linha.strip() for turno in turnos if turno['role'] == 'user'
            for linha in turno['content'].splitlines() if linha.strip()]


@dataclass(frozen=True)
class Foco:
    consulta: str
    assunto: str = 'geral'
    aspectos: frozenset[str] = frozenset()
    produto_ids: tuple[int, ...] = ()
    esclarecer: str = ''
    retomada: bool = False
    _entrada: str = field(default='', repr=False)
    _antecedentes: tuple[str, ...] = field(default=(), repr=False)

    def historico(self, mensagens):
        """Retorna até quatro antecedentes do cliente, sem acrescentar a atual.

        A resposta do assistente não identifica o produto escolhido pelo cliente.
        Uma lista de mensagens diferente do retrato original não herda o foco.
        """
        if not self.retomada or not self._antecedentes:
            return []
        entradas = _eventos_anteriores(mensagens, self._entrada)
        esperadas = self._antecedentes
        if tuple(entradas[-len(esperadas):]) != esperadas:
            return []
        necessarias = esperadas if len(esperadas) <= 4 else (esperadas[0], *esperadas[-3:])
        return [{'role': 'user', 'content': texto} for texto in necessarias]


_PADROES = {
    'horario': r'\b(?:horarios?|funcionamento|abre|abrem|fecha|fecham|abert[oa]s?|fechad[oa]s?|que horas)\b',
    'endereco': r'\b(?:enderecos?|localizacao|onde fica|onde voces ficam)\b',
    'contato': r'\b(?:telefones?|contato|falar com a loja)\b',
    'pagamento': r'\b(?:pagamentos?|pagar|pago|pix|cartao|cartoes|dinheiro|credito|debito|boleto|vale refeicao|vale alimentacao)\b',
    'entrega': r'\b(?:entregas?|entregam|entrega[mr]|frete|retirada|retirar|retira|preparo|pronto|chegar|chega)\b',
    'prazo': r'\b(?:prazos?|demora|tempo|minutos?|quanto leva|quanto falta)\b',
    'preco': r'\b(?:precos?|valores?|custa|custam|quanto fica|custo|taxas?|frete)\b',
    'descricao': r'\b(?:ingredientes?|composicao|descricao|detalhes?|contem|alergenos?|lactose|gluten|tamanhos?|cores?|sabores?|compatibilidade|diferenca|comparar|compare)\b',
    'garantia': r'\b(?:garantias?)\b',
    'troca': r'\b(?:trocas?|trocar|devolver|devolucao|reembolso)\b',
    'disponibilidade': r'\b(?:tem|vendem|oferecem|disponivel|disponiveis|disponibilidade|estoque|saldo|esgotad[oa]|acabou)\b',
    'catalogo': r'\b(?:catalogo|cardapio|quais produtos|quais opcoes|ver produtos|conhecer os produtos)\b',
    'pedido': r'\b(?:fazer (?:um |meu |o )?pedido|quero comprar|quero pedir|link(?: do pedido)?|encomendar)\b',
    'promocao': r'\b(?:promocao|promocoes|ofertas?|descontos?)\b',
}
_PADROES = {chave: re.compile(expressao) for chave, expressao in _PADROES.items()}
_OPERACIONAIS = frozenset({'horario', 'endereco', 'contato', 'pagamento', 'entrega'})
_CONTINUACAO = re.compile(
    r'(?:(?:e|mas e|e sobre) )?(?:(?:qual|quais) (?:e |sao )?)?(?:(?:o|a|os|as) )?'
    r'(?:preco|valor|quanto custa|quanto fica|ingredientes|composicao|descricao|detalhes|'
    r'garantia|tamanho|cor|cores|sabor|sabores|disponibilidade)'
    r'(?: (?:dele|dela|deles|delas|desse|dessa|deste|desta|desse produto|dessa opcao|do produto))?'
    r'|(?:e )?(?:quanto custa|quanto fica|tem outro|tem outra|me explique melhor|nao entendi|pode explicar|tem lactose|tem gluten)'
)
_NEGACAO = re.compile(r'\b(?:nao (?:quero|gostaria|preciso|prefiro|desejo|vou)|'
                       r'dispenso|retire|remova|sem|nem|nao(?! (?:tem|ha|vendem?|oferecem?|contem|serve)\b))\b')
_AFIRMACAO = re.compile(r'\b(?:quero|gostaria|preciso|prefiro|desejo|vou|escolho)\b')


def _aspectos(texto):
    aspectos = {nome for nome, expressao in _PADROES.items() if expressao.search(texto)}
    horario_entrega = re.search(
        r'\b(?:horario|horarios) (?:de|da|para|pra) (?:entrega|retirada|preparo)\b|'
        r'\bque horas (?:chega|entrega|fica pronto|posso retirar)\b', texto)
    if horario_entrega:
        aspectos.update({'entrega', 'prazo'})
        if not re.search(r'\b(?:funcionamento|abre|abrem|fecha|fecham)\b', texto):
            aspectos.discard('horario')
    if re.search(r'\bendereco (?:de|da|para) entrega\b', texto):
        aspectos.discard('endereco')
        aspectos.add('entrega')
    return frozenset(aspectos)


def _nomes(produtos):
    nomes = []
    for indice, produto in enumerate(produtos or (), 1):
        if not isinstance(produto, dict):
            continue
        rotulo = str(produto.get('nome') or '').strip()
        nome = re.sub(r'^(?:teste|demo|ficticio)\s*[-:]\s*', '', _normalizar(rotulo))
        palavras = re.findall(r'[a-z0-9]+', nome)
        if palavras:
            nomes.append((indice, rotulo, tuple(palavras),
                          re.compile(r'\b' + r'[\s_-]*'.join(map(re.escape, palavras)) + r'\b')))
    return tuple(nomes)


def _produtos_citados(texto, nomes):
    padroes = {}
    for indice, _, _, padrao in nomes:
        if padrao.pattern not in padroes:
            padroes[padrao.pattern] = (padrao, [])
        padroes[padrao.pattern][1].append(indice)
    intervalos = {}
    for padrao, indices in padroes.values():
        for encontrado in padrao.finditer(texto):
            intervalos.setdefault((encontrado.start(), encontrado.end()), []).extend(indices)
    # O nome mais longo prevalece quando contém outro nome. Agrupar padrões e
    # varrer intervalos evita comparar cada ocorrência com todas as demais.
    completos = []
    maior_fim = -1
    for (inicio, fim), indices in sorted(intervalos.items(), key=lambda m: (m[0][0], -m[0][1])):
        if fim <= maior_fim:
            continue
        completos.append((inicio, fim, indices))
        maior_fim = fim
    positivos = []
    vistos = set()
    for inicio, _, indices in completos:
        prefixo = texto[:inicio]
        trecho = re.split(r'[,;.!?]|\bmas\b', prefixo)[-1]
        negacoes = list(_NEGACAO.finditer(trecho))
        afirmacoes = list(_AFIRMACAO.finditer(trecho))
        negado = bool(negacoes and (not afirmacoes or negacoes[-1].end() >= afirmacoes[-1].start()))
        # "não quero" contém o verbo positivo; ele não anula sua própria negação.
        if negacoes and afirmacoes and re.search(r'\bnao\s+$', trecho[:afirmacoes[-1].start()]):
            negado = True
        if not negado:
            positivos.extend(indice for indice in indices if indice not in vistos)
            vistos.update(indices)
    return tuple(positivos), bool(intervalos)


def _continuacao(texto):
    return bool(_CONTINUACAO.fullmatch(texto.strip('.!? ')))


def _assunto(aspectos, ids):
    if ids:
        return 'produto'
    if 'catalogo' in aspectos:
        return 'catalogo'
    operacionais = aspectos & _OPERACIONAIS
    if len(operacionais) == 1:
        return next(iter(operacionais))
    if aspectos & {'garantia', 'troca'}:
        return 'politica'
    if aspectos & {'preco', 'descricao', 'disponibilidade'}:
        return 'produto'
    return 'geral'


def resolver(pergunta, produtos, mensagens=()) -> Foco:
    """Descreve o foco sem ampliar escopo nem autorizar qualquer operação."""
    pergunta = str(pergunta or '').strip()
    atual = _normalizar(pergunta).strip('.!? ')
    nomes = _nomes(produtos)
    aspectos = _aspectos(atual)
    ids, mencionados = _produtos_citados(atual, nomes)
    retomada = False
    antecedentes = ()
    esclarecer = ''
    consulta = pergunta
    # Uma pergunta operacional atual não retoma um produto antigo.
    if not ids and not (aspectos & _OPERACIONAIS) and _continuacao(atual):
        entradas = _eventos_anteriores(mensagens, pergunta)
        for posicao in range(len(entradas) - 1, -1, -1):
            anterior = _normalizar(entradas[posicao]).strip('.!? ')
            anteriores, citados = _produtos_citados(anterior, nomes)
            if len(anteriores) == 1:
                ids = anteriores
                retomada = True
                antecedentes = tuple(entradas[posicao:])
                rotulo = next(rotulo for indice, rotulo, _, _ in nomes if indice == ids[0])
                consulta = pergunta.rstrip('.!? ') + ' — produto: ' + rotulo
                break
            # "sim"/"esse" podem responder a uma oferta ambígua do assistente.
            # Não os use para saltar de volta a uma seleção mais antiga.
            if citados or not _continuacao(anterior):
                break
        if not retomada:
            esclarecer = 'De qual produto você quer saber?'
    if not ids and mencionados:
        esclarecer = 'Qual produto você quer consultar agora?'
    taxa_da_operacao = 'entrega' in aspectos and not (aspectos & {'descricao', 'disponibilidade'})
    if (not ids and not esclarecer and aspectos & {'preco', 'descricao', 'disponibilidade'}
            and 'catalogo' not in aspectos and not taxa_da_operacao):
        esclarecer = 'De qual produto você quer saber?'
    chaves = [''.join(chave) for indice, _, chave, _ in nomes if indice in ids]
    if len(ids) > 1 and len(set(chaves)) == 1:
        esclarecer = 'Qual variação do produto você quer consultar?'
    return Foco(consulta, _assunto(aspectos, ids), aspectos, ids, esclarecer, retomada,
                pergunta, antecedentes)
