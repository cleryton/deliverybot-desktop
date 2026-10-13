"""Estimativas por mensagem a partir de eventos assinados; não substitui a fatura Meta."""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from . import config
from .db import get_conn

CATEGORIAS = ('marketing', 'utility', 'authentication', 'authentication_international', 'service')
FUSO = timezone(timedelta(hours=-3))


def agora():
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc(d):
    return d.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def micros(valor, nome='Valor'):
    if isinstance(valor, bool) or not isinstance(valor, (str, int, float)):
        raise ValueError(f'{nome}: informe um valor em reais.')
    try:
        d = Decimal(str(valor).replace(',', '.'))
        if not d.is_finite() or d < 0 or d > 100000000 or d * 1000000 != (d * 1000000).to_integral_value():
            raise ValueError()
        return int(d * 1000000)
    except (InvalidOperation, ValueError):
        raise ValueError(f'{nome}: use um valor positivo com até seis casas decimais.') from None


def guardar_numero(c, numero, ambiente, waba=''):
    if numero:
        c.execute('INSERT INTO meta_numeros(numero_id,ambiente,waba_id) VALUES(?,?,?) '
                  'ON CONFLICT(numero_id) DO UPDATE SET ambiente=excluded.ambiente,waba_id=excluded.waba_id',
                  (numero, ambiente, waba))


def _perfil(c, numero, waba):
    if numero == config.WHATSAPP_PHONE_NUMBER_ID:
        if config.WHATSAPP_BUSINESS_ACCOUNT_ID and waba != config.WHATSAPP_BUSINESS_ACCOUNT_ID:
            return None
        guardar_numero(c, numero, config.WHATSAPP_META_AMBIENTE, config.WHATSAPP_BUSINESS_ACCOUNT_ID)
    perfil = c.execute('SELECT * FROM meta_numeros WHERE numero_id=?', (numero,)).fetchone()
    return perfil if perfil and (not perfil['waba_id'] or perfil['waba_id'] == waba) else None


def registrar_envio(retorno):
    if not isinstance(retorno, dict) or not isinstance(retorno.get('messages'), list):
        return
    with get_conn() as c:
        guardar_numero(c, config.WHATSAPP_PHONE_NUMBER_ID, config.WHATSAPP_META_AMBIENTE, config.WHATSAPP_BUSINESS_ACCOUNT_ID)
        for mensagem in retorno['messages'][:100]:
            ident = mensagem.get('id') if isinstance(mensagem, dict) else None
            if not isinstance(ident, str) or not 1 <= len(ident) <= 512:
                continue
            c.execute('INSERT OR IGNORE INTO meta_mensagens_custo(numero_id,chave,ambiente,enviado_em,estado) VALUES(?,?,?,?,?)',
                      (config.WHATSAPP_PHONE_NUMBER_ID, hashlib.sha256(ident.encode()).hexdigest(),
                       config.WHATSAPP_META_AMBIENTE, utc(agora()), 'sent'))


def registrar_status(payload):
    """Idempotente e sem dados do destinatário; confirma custos somente depois da entrega."""
    if not isinstance(payload.get('entry'), list):
        return 0
    total = 0
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        for entry in payload['entry'][:100]:
            if not isinstance(entry, dict) or not isinstance(entry.get('changes'), list):
                continue
            for change in entry['changes'][:100]:
                if not isinstance(change, dict) or change.get('field') != 'messages':
                    continue
                value = change.get('value')
                if not isinstance(value, dict) or not isinstance(value.get('metadata'), dict):
                    continue
                numero = value['metadata'].get('phone_number_id')
                if not isinstance(numero, str) or not numero:
                    continue
                perfil = _perfil(c, numero, entry.get('id'))
                if not perfil or not isinstance(value.get('statuses'), list):
                    continue
                for s in value['statuses'][:100]:
                    if not isinstance(s, dict) or s.get('status') not in {'sent', 'delivered', 'read', 'failed'}:
                        continue
                    ident, timestamp = s.get('id'), s.get('timestamp')
                    if not isinstance(ident, str) or not 1 <= len(ident) <= 512 or not isinstance(timestamp, str) or not re.fullmatch(r'\d{9,11}', timestamp):
                        continue
                    try:
                        instante = datetime.fromtimestamp(int(timestamp), timezone.utc)
                    except (ValueError, OSError, OverflowError):
                        continue
                    if instante > agora() + timedelta(minutes=5):
                        continue
                    chave = hashlib.sha256(ident.encode()).hexdigest()
                    c.execute('INSERT OR IGNORE INTO meta_mensagens_custo(numero_id,chave,ambiente,enviado_em,estado) VALUES(?,?,?,?,?)',
                              (numero, chave, perfil['ambiente'], utc(instante), s['status']))
                    anterior = dict(c.execute('SELECT * FROM meta_mensagens_custo WHERE numero_id=? AND chave=?', (numero, chave)).fetchone())
                    entregue = anterior['entregue_em']
                    if s['status'] in {'delivered', 'read'}:
                        entregue = min(entregue, utc(instante)) if entregue else utc(instante)
                    ordem = {'sent': 0, 'failed': 1, 'delivered': 2, 'read': 3}
                    estado = max((anterior['estado'], s['status']), key=ordem.get)
                    categoria, modelo, cobravel = anterior['categoria'], anterior['modelo'], anterior['cobravel']
                    precificado = anterior['precificado_em']
                    pricing = s.get('pricing')
                    if isinstance(pricing, dict) and s['status'] in {'delivered', 'read'} and (not precificado or utc(instante) >= precificado):
                        cat = pricing.get('category')
                        mod = pricing.get('pricing_model')
                        if isinstance(cat, str) and len(cat) <= 80:
                            categoria = cat
                        if isinstance(mod, str) and len(mod) <= 30:
                            modelo = mod
                        if isinstance(pricing.get('billable'), bool):
                            cobravel = int(pricing['billable'])
                            precificado = utc(instante)
                    destino = s.get('recipient_id')
                    mercado = anterior['mercado']
                    if not mercado and isinstance(destino, str) and re.fullmatch(r'\d{10,15}', destino):
                        mercado = 'BR' if destino.startswith('55') else 'OUTRO'
                    custo = anterior['estimativa_micros']
                    mudou = categoria != anterior['categoria'] or cobravel != anterior['cobravel'] or modelo != anterior['modelo']
                    if not entregue:
                        custo = None
                    elif cobravel == 0:
                        custo = 0
                    elif cobravel == 1 and modelo == 'PMP' and mercado == 'BR':
                        if custo is None or mudou or entregue != anterior['entregue_em']:
                            tarifa = c.execute('SELECT valor_micros FROM meta_tarifas WHERE categoria=? AND vigente_em<=? ORDER BY vigente_em DESC,id DESC LIMIT 1', (categoria, entregue)).fetchone()
                            custo = tarifa[0] if tarifa else None
                    else:
                        custo = None
                    c.execute('UPDATE meta_mensagens_custo SET entregue_em=?,estado=?,categoria=?,mercado=?,modelo=?,cobravel=?,estimativa_micros=?,precificado_em=? WHERE numero_id=? AND chave=?',
                              (entregue, estado, categoria, mercado, modelo, cobravel, custo, precificado, numero, chave))
                    total += 1
    return total


def configuracao():
    with get_conn() as c:
        tarifas = {}
        for categoria in CATEGORIAS:
            t = c.execute('SELECT valor_micros,vigente_em FROM meta_tarifas WHERE categoria=? AND vigente_em<=? ORDER BY vigente_em DESC,id DESC LIMIT 1', (categoria, utc(agora()))).fetchone()
            tarifas[categoria] = {'valor': format(Decimal(t[0]) / 1000000, '.6f'), 'vigente_em': t[1]} if t else None
        orcamento = dict(c.execute('SELECT limite_micros,alerta_percentual FROM meta_orcamento WHERE id=1').fetchone())
    return {'tarifas': tarifas, 'orcamento': {**orcamento, 'limite': format(Decimal(orcamento['limite_micros']) / 1000000, '.2f')}, 'moeda': 'BRL', 'mercado': 'BR'}


def configurar(dados):
    tarifas = dados.get('tarifas', {})
    if not isinstance(tarifas, dict) or set(tarifas) - set(CATEGORIAS):
        raise ValueError('Categoria de tarifa inválida.')
    valores = {k: micros(v, 'Tarifa') for k, v in tarifas.items() if v not in (None, '')}
    if any(v > 1000000000 for v in valores.values()):
        raise ValueError('Tarifa por mensagem: use no máximo R$ 1.000.')
    limite = micros(dados.get('limite', configuracao()['orcamento']['limite']), 'Orçamento')
    if limite % 10000:
        raise ValueError('Orçamento mensal: use no máximo duas casas decimais.')
    alerta = dados.get('alerta_percentual', configuracao()['orcamento']['alerta_percentual'])
    if isinstance(alerta, bool) or not isinstance(alerta, int) or not 1 <= alerta <= 100:
        raise ValueError('Percentual de aviso: use um inteiro de 1 a 100.')
    with get_conn() as c:
        for cat, valor in valores.items():
            c.execute('INSERT INTO meta_tarifas(categoria,valor_micros,vigente_em) VALUES(?,?,?)', (cat, valor, utc(agora())))
        c.execute('UPDATE meta_orcamento SET limite_micros=?,alerta_percentual=? WHERE id=1', (limite, alerta))
    return configuracao()


def _periodo(mes):
    if not isinstance(mes, str) or not re.fullmatch(r'\d{4}-\d{2}', mes):
        raise ValueError('Informe o mês no formato AAAA-MM.')
    try:
        inicio = datetime.strptime(mes, '%Y-%m').replace(tzinfo=FUSO)
        fim = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
    except (ValueError, OverflowError):
        raise ValueError('Mês inválido.') from None
    return utc(inicio), utc(fim)


def relatorio(mes=None, ambiente='TODOS'):
    mes = mes or agora().astimezone(FUSO).strftime('%Y-%m')
    inicio, fim = _periodo(mes)
    if ambiente not in {'TODOS', 'TESTE', 'PRODUCAO'}:
        raise ValueError('Ambiente inválido.')
    filtro = 'COALESCE(entregue_em,enviado_em)>=? AND COALESCE(entregue_em,enviado_em)<?'
    args = [inicio, fim]
    selecionado = filtro
    if ambiente != 'TODOS':
        selecionado += ' AND ambiente=?'
        args.append(ambiente)
    with get_conn() as c:
        grupos = [dict(r) for r in c.execute(f'''SELECT ambiente,categoria,mercado,COUNT(*) AS enviadas,
            SUM(entregue_em IS NOT NULL) AS entregues,
            SUM(entregue_em IS NOT NULL AND cobravel=1) AS cobraveis,
            SUM(entregue_em IS NOT NULL AND cobravel=0) AS gratuitas,
            SUM(entregue_em IS NOT NULL AND estimativa_micros IS NULL) AS sem_estimativa,
            SUM(estado='failed' AND entregue_em IS NULL) AS falhas,
            COALESCE(SUM(estimativa_micros),0) AS estimativa_micros
            FROM meta_mensagens_custo WHERE {selecionado} GROUP BY ambiente,categoria,mercado''', args)]
        ultimas = [dict(r) for r in c.execute(f'''SELECT substr(chave,1,12) AS referencia,numero_id,ambiente,
            enviado_em,entregue_em,estado,categoria,mercado,cobravel,estimativa_micros
            FROM meta_mensagens_custo WHERE {selecionado} ORDER BY COALESCE(entregue_em,enviado_em) DESC LIMIT 50''', args)]
        producao = c.execute(f"SELECT COALESCE(SUM(estimativa_micros),0),COALESCE(SUM(entregue_em IS NOT NULL AND estimativa_micros IS NULL),0) FROM meta_mensagens_custo WHERE {filtro} AND ambiente='PRODUCAO'", (inicio, fim)).fetchone()
        gasto = producao[0]
    campos = ('enviadas', 'entregues', 'cobraveis', 'gratuitas', 'sem_estimativa', 'falhas', 'estimativa_micros')
    totais = {k: sum(g[k] or 0 for g in grupos) for k in campos}
    cfg = configuracao()
    orcamento = cfg['orcamento']
    limite = orcamento['limite_micros']
    orcamento.update(gasto_micros=gasto, incompleto=bool(producao[1]), nivel='DESATIVADO' if not limite else 'EXCEDIDO' if gasto >= limite else 'ATENCAO' if gasto * 100 >= limite * orcamento['alerta_percentual'] else 'NORMAL')
    return {'mes': mes, 'ambiente': ambiente, 'moeda': 'BRL', 'fuso': 'America/Sao_Paulo (UTC-3)',
            'totais': totais, 'categorias': grupos, 'mensagens': ultimas, 'orcamento': orcamento,
            'incompleto': totais['sem_estimativa'] > 0,
            'aviso': 'Estimativa em reais com as tarifas cadastradas para o Brasil. Não é a fatura Meta. Mensagens de teste ficam fora do orçamento de produção; tarifas ausentes e outros mercados deixam a estimativa incompleta. Sem impostos, câmbio ou taxas de outros provedores.'}
