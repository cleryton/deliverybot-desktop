"""Registro manual e livro de caixa por operador, com transações e centavos inteiros."""
import hashlib
import json
import re
import secrets
import unicodedata
from decimal import Decimal, InvalidOperation

from . import config, estoque, pedidos
from .db import get_conn


def centavos(valor):
    try:
        n = Decimal(str(valor).replace(',', '.'))
        if not n.is_finite() or not 0 <= n <= 99999999 or n != n.quantize(Decimal('.01')):
            raise InvalidOperation
        return int(n * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Informe um valor monetário positivo ou zero, com até duas casas decimais.') from None


def _aberto(c, uid):
    r = c.execute('SELECT * FROM caixas WHERE operador_id=? AND fechado_em IS NULL', (uid,)).fetchone()
    if not r:
        raise ValueError('Abra seu caixa antes de registrar vendas ou movimentações.')
    return dict(r)


def _saldo(c, turno):
    return turno['abertura_centavos'] + c.execute("SELECT COALESCE(SUM(valor_centavos),0) FROM movimentos_caixa WHERE caixa_id=? AND forma='DINHEIRO'", (turno['id'],)).fetchone()[0]


def _operacao(uid, chave, dados, funcao):
    if not isinstance(chave, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{16,80}', chave):
        raise ValueError('Identificador de operação inválido.')
    assinatura = hashlib.sha256(json.dumps(dados, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        ator = c.execute('SELECT perfil,ativo FROM operadores WHERE id=?', (uid,)).fetchone()
        if not ator or not ator['ativo'] or ator['perfil'] not in {'ADMIN', 'CAIXA'}:
            raise ValueError('Conta não autorizada para o caixa.')
        from .politica_terminal import exigir_gravacao
        exigir_gravacao(c, uid, dados['acao'])
        anterior = c.execute('SELECT * FROM operacoes_caixa WHERE operador_id=? AND chave=?', (uid, chave)).fetchone()
        if anterior:
            if anterior['assinatura'] != assinatura:
                raise ValueError('A operação já existe com dados diferentes. Consulte o resultado antes de tentar novamente.')
            return json.loads(anterior['resultado'])
        resultado = funcao(c)
        c.execute('INSERT INTO operacoes_caixa(operador_id,chave,assinatura,resultado) VALUES(?,?,?,?)', (uid, chave, assinatura, json.dumps(resultado)))
        c.execute('INSERT INTO auditoria_operadores(operador_id,acao,objeto) VALUES(?,?,?)', (uid, 'CAIXA_' + dados['acao'], str(resultado.get('pedido_id', resultado.get('caixa_id', '')))))
    estoque.invalidar_catalogo()
    return resultado


def abrir(uid, d):
    valor = centavos(d.get('abertura'))
    def executar(c):
        if c.execute('SELECT 1 FROM caixas WHERE operador_id=? AND fechado_em IS NULL', (uid,)).fetchone():
            raise ValueError('Você já tem um caixa aberto.')
        tid = c.execute('INSERT INTO caixas(operador_id,abertura_centavos) VALUES(?,?)', (uid, valor)).lastrowid
        return {'caixa_id': tid}
    return _operacao(uid, d.get('chave'), {'acao': 'ABRIR', 'abertura': valor}, executar)


def _forma_configurada(meio):
    if not isinstance(meio, str) or meio not in {'DINHEIRO', 'PIX', 'CARTAO'}:
        raise ValueError('Escolha Dinheiro, Pix ou Cartão.')
    formas = [v.strip() for v in config.FORMAS_PAGAMENTO.split(',') if v.strip()]
    if not formas:
        raise ValueError('O responsável precisa configurar as formas de pagamento.')
    grupos = {
        'dinheiro': 'DINHEIRO', 'pix': 'PIX', 'cartao': 'CARTAO',
        'cartao de credito': 'CARTAO', 'cartao de debito': 'CARTAO',
        'cartao credito': 'CARTAO', 'cartao debito': 'CARTAO',
        'credito': 'CARTAO', 'debito': 'CARTAO',
    }
    for forma in formas:
        normalizada = ''.join(c for c in unicodedata.normalize('NFKD', forma.casefold())
                              if not unicodedata.combining(c))
        if grupos.get(' '.join(normalizada.split())) == meio:
            # O terminal usa cartão genérico; preserva o primeiro rótulo de
            # crédito/débito realmente cadastrado, sem inventar outra opção.
            return forma
    raise ValueError('Esta forma de pagamento não está configurada pela loja.')


def _receber(c, turno, pedido, d):
    forma = d.get('forma')
    rotulo = _forma_configurada(forma)
    total = centavos(pedido['total_pedido'])
    recebido = centavos(d.get('recebido')) if forma == 'DINHEIRO' else total
    if recebido < total:
        raise ValueError('O dinheiro recebido é menor que o total do pedido.')
    if recebido - total > _saldo(c, turno):
        raise ValueError('O caixa não tem dinheiro suficiente para o troco. Registre suprimento ou escolha outro pagamento.')
    c.execute('INSERT INTO movimentos_caixa(caixa_id,pedido_id,tipo,forma,valor_centavos,recebido_centavos,troco_centavos) VALUES(?,?,\'VENDA\',?,?,?,?)', (turno['id'], pedido['id'], forma, total, recebido, recebido-total))
    c.execute('UPDATE pedidos SET total_pago=?,forma_pagamento=?,atualizado_em=datetime(\'now\') WHERE id=?', (total / 100, rotulo, pedido['id']))
    return {'recebido_centavos': recebido, 'troco_centavos': recebido-total}


def vender(uid, d):
    if not isinstance(d.get('itens'), list) or not 1 <= len(d['itens']) <= 200:
        raise ValueError('Escolha de 1 a 200 itens do catálogo.')
    if not isinstance(d.get('pago'), bool):
        raise ValueError('Informe se o pagamento foi recebido.')
    nome = estoque.texto(d.get('nome', 'Cliente do balcão'), 'Nome', 160, True)
    entrega=d.get('entrega','RETIRADA BALCAO')
    if entrega not in {'RETIRADA BALCAO','ENTREGA'}:
        raise ValueError('Escolha retirada ou entrega.')
    endereco=estoque.texto(d.get('endereco',''),'Endereço',400,entrega=='ENTREGA')
    # Não é necessário coletar telefone no balcão; identificador interno não é contato WhatsApp.
    def executar(c):
        turno = _aberto(c, uid)
        total, itens = pedidos._resolver_itens(c, d['itens'])
        cotacao = pedidos._cotacao(total, itens, entrega)
        if d.get('cotacao') != cotacao:
            raise pedidos.CotacaoAlterada('O catálogo mudou. Revise o resumo e confirme novamente.')
        forma = _forma_configurada(d.get('forma'))
        p = pedidos.criar_pedido('balcao:' + secrets.token_hex(16), nome, d['itens'], forma, forma_entrega=entrega,endereco=endereco,_conn=c)
        c.execute("UPDATE pedidos SET origem='Balcão manual' WHERE id=?", (p['id'],))
        c.execute('INSERT INTO vendas_balcao(pedido_id,operador_id,caixa_id) VALUES(?,?,?)', (p['id'], uid, turno['id']))
        pagamento = _receber(c, turno, p, d) if d['pago'] else {}
        return {'caixa_id': turno['id'], 'pedido_id': p['id'], 'numero_pedido':p['numero_pedido'], 'total_centavos':centavos(p['total_pedido']), 'pago':d['pago'], **pagamento}
    return _operacao(uid, d.get('chave'), {'acao':'VENDER', **{k:d.get(k) for k in ('nome','itens','cotacao','pago','forma','recebido','entrega','endereco')}}, executar)


def receber(uid, pedido_id, d):
    def executar(c):
        turno = _aberto(c, uid)
        venda = c.execute('SELECT * FROM vendas_balcao WHERE pedido_id=? AND operador_id=?', (pedido_id, uid)).fetchone()
        p = pedidos.obter_pedido(pedido_id, _conn=c) if venda else None
        if not p or p['status']=='CANCELADO':
            raise ValueError('Pedido não disponível para este funcionário.')
        if c.execute("SELECT 1 FROM movimentos_caixa WHERE pedido_id=? AND tipo='VENDA'", (pedido_id,)).fetchone():
            raise ValueError('Este pedido já teve o recebimento registrado.')
        return {'caixa_id':turno['id'], 'pedido_id':pedido_id, **_receber(c, turno, p, d)}
    return _operacao(uid, d.get('chave'), {'acao':'RECEBER','pedido_id':pedido_id,'forma':d.get('forma'),'recebido':d.get('recebido')}, executar)


def movimentar(uid, d):
    tipo = d.get('tipo')
    if tipo not in {'SANGRIA', 'SUPRIMENTO'}:
        raise ValueError('Escolha sangria ou suprimento.')
    valor = centavos(d.get('valor'))
    if not valor:
        raise ValueError('A movimentação precisa ter valor maior que zero.')
    motivo = estoque.texto(d.get('motivo', ''), 'Motivo', 300, True)
    def executar(c):
        turno = _aberto(c, uid)
        if tipo == 'SANGRIA' and valor > _saldo(c, turno):
            raise ValueError('A retirada é maior que o dinheiro esperado no caixa.')
        c.execute('INSERT INTO movimentos_caixa(caixa_id,tipo,forma,valor_centavos,motivo) VALUES(?,?,\'DINHEIRO\',?,?)', (turno['id'], tipo, -valor if tipo=='SANGRIA' else valor, motivo))
        return {'caixa_id': turno['id']}
    return _operacao(uid, d.get('chave'), {'acao':tipo, 'valor':valor, 'motivo':motivo}, executar)


def fechar(uid, d):
    contado = centavos(d.get('contado'))
    def executar(c):
        turno = _aberto(c, uid)
        esperado = _saldo(c, turno)
        c.execute("UPDATE caixas SET fechado_em=datetime('now'),contado_centavos=?,esperado_centavos=?,diferenca_centavos=? WHERE id=?", (contado, esperado, contado-esperado, turno['id']))
        return {'caixa_id':turno['id'], 'esperado_centavos':esperado, 'contado_centavos':contado, 'diferenca_centavos':contado-esperado}
    return _operacao(uid, d.get('chave'), {'acao':'FECHAR', 'contado':contado}, executar)


def consultar(uid=None,detalhar=True):
    with get_conn() as c:
        turnos = [dict(r) for r in c.execute('SELECT t.*,o.nome AS funcionario FROM caixas t JOIN operadores o ON o.id=t.operador_id ' + ('WHERE t.operador_id=? ' if uid is not None else '') + 'ORDER BY (t.fechado_em IS NULL) DESC,t.id DESC LIMIT 100', (uid,) if uid is not None else ())]
        for t in turnos:
            t['esperado_centavos'] = t['esperado_centavos'] if t['fechado_em'] else _saldo(c,t)
            t['recebimentos'] = {f:c.execute("SELECT COALESCE(SUM(valor_centavos),0) FROM movimentos_caixa WHERE caixa_id=? AND forma=? AND tipo IN ('VENDA','ESTORNO')", (t['id'],f)).fetchone()[0] for f in ('DINHEIRO','PIX','CARTAO')}
            if detalhar:
                t['movimentos'] = [dict(r) for r in c.execute('SELECT * FROM movimentos_caixa WHERE caixa_id=? ORDER BY id DESC LIMIT 50', (t['id'],))]
            vendas_turno = c.execute("SELECT p.total_pedido,p.total_pago FROM vendas_balcao v JOIN pedidos p ON p.id=v.pedido_id WHERE v.caixa_id=? AND p.status!='CANCELADO'", (t['id'],)).fetchall()
            t['vendas_centavos'] = sum(centavos(v['total_pedido']) for v in vendas_turno)
            t['pendente_centavos'] = sum(centavos(v['total_pedido']) - centavos(v['total_pago']) for v in vendas_turno)
        return turnos


def fechar_pelo_admin(admin_id,tid,d):
    contado=centavos(d.get('contado'))
    def executar(c):
        if c.execute('SELECT perfil FROM operadores WHERE id=?',(admin_id,)).fetchone()['perfil']!='ADMIN':
            raise ValueError('Somente o responsável pode conferir outro caixa.')
        r=c.execute('SELECT * FROM caixas WHERE id=? AND fechado_em IS NULL',(tid,)).fetchone()
        if not r:
            raise ValueError('Caixa já fechado ou não encontrado.')
        t=dict(r)
        esperado=_saldo(c,t)
        c.execute("UPDATE caixas SET fechado_em=datetime('now'),contado_centavos=?,esperado_centavos=?,diferenca_centavos=? WHERE id=?",(contado,esperado,contado-esperado,tid))
        return {'caixa_id':tid,'esperado_centavos':esperado,'contado_centavos':contado,'diferenca_centavos':contado-esperado}
    return _operacao(admin_id,d.get('chave'),{'acao':'FECHAR_ADMIN','caixa_id':tid,'contado':contado},executar)


def vendas(uid):
    with get_conn() as c:
        return [dict(r) for r in c.execute('SELECT p.id,p.numero_pedido,p.status,p.total_pedido,p.total_pago,c.nome AS nome FROM vendas_balcao v JOIN pedidos p ON p.id=v.pedido_id JOIN clientes c ON c.id=p.cliente_id WHERE v.operador_id=? ORDER BY p.id DESC LIMIT 100', (uid,))]


def resultado(uid, chave):
    with get_conn() as c:
        r=c.execute('SELECT resultado FROM operacoes_caixa WHERE operador_id=? AND chave=?',(uid,chave)).fetchone()
        return json.loads(r['resultado']) if r else None


def estornar(admin_id, pedido_id, d):
    if d.get('devolucao_confirmada') is not True:
        raise ValueError('Confirme que o valor foi devolvido ao cliente. O aplicativo não transfere pagamentos.')
    def executar(c):
        ator=c.execute('SELECT perfil FROM operadores WHERE id=?',(admin_id,)).fetchone()
        if ator['perfil']!='ADMIN':
            raise ValueError('Somente o administrador pode estornar.')
        m=c.execute("SELECT m.*,t.abertura_centavos,t.fechado_em FROM movimentos_caixa m JOIN caixas t ON t.id=m.caixa_id WHERE pedido_id=? AND tipo='VENDA'",(pedido_id,)).fetchone()
        if not m or m['fechado_em']:
            raise ValueError('Estorno disponível somente no caixa original ainda aberto. Caixas fechados preservam a conferência.')
        if m['forma']=='DINHEIRO' and m['valor_centavos']>_saldo(c,{'id':m['caixa_id'],'abertura_centavos':m['abertura_centavos']}):
            raise ValueError('Registre suprimento no caixa original antes de devolver este valor.')
        pedidos.cancelar_pedido(pedido_id,_conn=c,_estorno_caixa=True)
        c.execute("UPDATE pedidos SET total_pago=0 WHERE id=?",(pedido_id,))
        c.execute("INSERT INTO movimentos_caixa(caixa_id,pedido_id,tipo,forma,valor_centavos,motivo) VALUES(?,?,'ESTORNO',?,?,'Devolução confirmada pelo administrador')",(m['caixa_id'],pedido_id,m['forma'],-m['valor_centavos']))
        return {'pedido_id':pedido_id,'caixa_id':m['caixa_id']}
    return _operacao(admin_id,d.get('chave'),{'acao':'ESTORNAR','pedido_id':pedido_id},executar)
