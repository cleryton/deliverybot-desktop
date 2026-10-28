"""Vocabulário comercial do perfil e do catálogo; notas não ampliam o escopo.

É uma triagem local e conservadora, não um classificador semântico universal.
Assuntos sem referência suficiente pedem esclarecimento no chamador.
"""
from dataclasses import dataclass
import re
import unicodedata

from . import cardapio, config


def normalizar(texto):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD', str(texto or ''))
                           if not unicodedata.combining(c) and unicodedata.category(c) != 'Cf').casefold().split())


_PERFIS = {
    'ALIMENTACAO': r'restaurantes?|pizzarias?|lanchonetes?|padarias?|cafeterias?|confeitarias?|hamburguerias?|marmitarias?|alimentacao|alimentos?',
    'OFICINA': r'oficinas?|mecanica|automotiv[oa]s?|autopecas|auto pecas',
    'MODA': r'moda|roupas?|vestuario|calcados|boutique|joias|bijuterias',
    'ELETRONICOS': r'eletronic[oa]s?|informatica|celulares|computadores|assistencia tecnica',
    'PET': r'pet ?shop|pets?|racoes|produtos? (?:para )?animais|veterinari[oa]',
    'BELEZA': r'beleza|cosmeticos|perfumaria|salao|cabeleireir[oa]|manicure',
    'PAPELARIA': r'papelaria|material escolar|materiais escolares',
    'CONSTRUCAO': r'construcao|materiais de construcao|ferragens',
}

_TEMAS = {
    'ALIMENTACAO': r'pizzas?|lanches?|hamburguer(?:es)?|x[ -]?(?:salada|bacon)|comida|ingredientes?|alergenos?|alergia|gluten|lactose|vegan[oa]s?|vegetarian[oa]s?|sem acucar|porc(?:ao|oes)|bebidas?|refrigerantes?|sucos?|cafe|bolos?|paes|pao|sabores?|chocolate|morango|calabresa|batata|cebola|tomate|molhos?|recheios?|alimentacao|refeicao|cachorro[ -]quente|frituras?|azeite|oleo vegetal|oleo de (?:soja|girassol|canola)|oleo (?:da|de|para) fritura',
    'OFICINA': r'oficinas?|mecanica|automotiv[oa]s?|autopecas|auto pecas|pecas? (?:de|para) (?:carros?|motos?|veiculos?)|motores?|pneus?|troca de oleo|filtros? de oleo|oleo (?:do|de|para) (?:motor|carro|veiculo)|veiculos?|carros?|motos?|freios?|alinhamento|balanceamento|amortecedores?|embreagem',
    'MODA': r'camisetas?|camisas?|calcas?|vestidos?|saias?|tenis|sapatos?|calcados?|vestuario|moda|roupas?|casacos?|blusas?|joias|bijuterias',
    'ELETRONICOS': r'celulares?|smartphones?|computadores?|notebooks?|tablets?|usb|hdmi|carregadores?|voltagem|memoria ram|software|processadores?|smartwatches?|eletronic[oa]s?|informatica',
    'PET': r'pet ?shop|pets?|racoes|racao|canin[oa]|felin[oa]|cachorros?(?![ -]quente)|gatos?|coleiras?|veterinari[oa]|banho e tosa|antipulgas|filhotes?',
    'BELEZA': r'perfumes?|cabelos?|cabeleireir[oa]|salao|manicure|unhas|maquiagem|hidratantes?|cosmeticos?',
    'PAPELARIA': r'cadernos?|lapis|canetas?|borrachas?|material escolar|materiais escolares|lapiseiras?',
    'CONSTRUCAO': r'cimento|tijolos?|telhas?|pedreiros?|construcao|ferragens',
}
_PERFIS = {k: re.compile(r'\b(?:' + v + r')\b') for k, v in _PERFIS.items()}
_TEMAS = {k: re.compile(r'\b(?:' + v + r')\b') for k, v in _TEMAS.items()}
_COMPARTILHADOS = [
    (re.compile(r'\b(?:baterias?)\b'), {'OFICINA', 'ELETRONICOS'}),
    (re.compile(r'\b(?:chaves? de fenda|ferramentas?|parafusos?)\b'), {'OFICINA', 'CONSTRUCAO'}),
]
_COMUNS = {'para', 'com', 'sem', 'uma', 'uns', 'das', 'dos', 'que', 'por', 'de',
           'da', 'do', 'as', 'os', 'em', 'na', 'no', 'ao', 'ou', 'produto', 'produtos',
           'teste', 'geral', 'outros', 'loja', 'servico', 'servicos'}


def _segmentos(texto, padroes):
    return {nome for nome, padrao in padroes.items() if padrao.search(texto)}


def _temas(texto):
    grupos = _segmentos(texto, _TEMAS)
    if (re.search(r'\boleo (?:vegetal|de (?:soja|girassol|canola)|.{0,25}\bfritura)\b', texto)
            and not re.search(r'\b(?:motor|motores|carros?|veiculos?|oficinas?|automotiv[oa]s?)\b', texto)):
        grupos.discard('OFICINA')
    return grupos


def _termos(texto):
    return set(re.findall(r'\b[a-z0-9]{2,}\b', normalizar(texto))) - _COMUNS


@dataclass(frozen=True)
class Politica:
    segmentos: frozenset
    termos: frozenset


def politica(produtos=None):
    """Sem cache de autorização: a leitura usa o perfil e os itens ativos atuais."""
    if produtos is None:
        produtos = cardapio.listar_produtos_ativos()
    configurado = config.COMERCIO_CONFIGURADO == 'SIM'
    explicitos = _segmentos(normalizar(config.COMERCIO_SEGMENTO), _PERFIS) if configurado else set()
    descricao = _segmentos(normalizar(config.COMERCIO_DESCRICAO), _PERFIS) if configurado else set()
    catalogo = set()
    referencias = []
    for produto in produtos:
        texto = normalizar(str(produto.get('nome') or '') + ' ' + str(produto.get('categoria') or ''))
        grupos = _temas(texto) | _segmentos(texto, _PERFIS)
        catalogo.update(grupos)
        referencias.append((texto, grupos))
    if configurado and config.COMERCIO_MODELO == 'MISTO':
        ativos = explicitos | descricao | catalogo
    else:
        # Um item antigo de outra categoria não muda uma lanchonete configurada.
        ativos = explicitos or descricao or catalogo
    termos = _termos(config.COMERCIO_SEGMENTO) if configurado else set()
    for texto, grupos in referencias:
        if not grupos or grupos <= ativos:
            termos.update(_termos(texto))
    return Politica(frozenset(ativos), frozenset(termos))


def produtos_permitidos(produtos, regra=None):
    """Filtra só a referência da IA, sem apagar ou alterar cadastros da loja."""
    regra = regra or politica(produtos)
    return [p for p in produtos if not fora_do_segmento(
        str(p.get('nome') or '') + ' ' + str(p.get('categoria') or ''), regra)]


def fora_do_segmento(texto, regra=None):
    regra = regra or politica()
    texto = normalizar(texto)
    if _temas(texto) - regra.segmentos:
        return True
    return any(padrao.search(texto) and not (grupos & regra.segmentos)
               for padrao, grupos in _COMPARTILHADOS)


def referencia(texto, regra=None):
    regra = regra or politica()
    texto = normalizar(texto)
    return (bool(_temas(texto) & regra.segmentos)
            or bool(_termos(texto) & regra.termos)
            or any(padrao.search(texto) and grupos & regra.segmentos for padrao, grupos in _COMPARTILHADOS))


def contexto():
    nome = str(config.COMERCIO_SEGMENTO or '').strip() or 'segmento não informado'
    return ('ESCOPO ESPECÍFICO DESTA LOJA: ' + nome + '. '
            'Atenda exclusivamente os produtos e serviços correspondentes ao perfil ativo e ao catálogo permitido. '
            'Um pedido sobre outra atividade não muda o segmento. Em operação mista, use somente as atividades cadastradas. '
            'Se o assunto estiver ambíguo, peça que a pessoa indique o produto, serviço ou pedido da loja. '
            'Não forneça explicações gerais ou respostas de outro segmento, mesmo junto de uma pergunta comercial.\n')
