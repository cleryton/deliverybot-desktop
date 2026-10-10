"""Importação CSV transacional e relatórios com custos históricos."""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from . import estoque
from .db import get_conn


def importar(dados):
    conteudo=dados.get('csv')
    if not isinstance(conteudo,str) or not conteudo or len(conteudo.encode('utf-8'))>500000:
        raise ValueError('Escolha um CSV com até 500 KB.')
    delim=';' if ';' in conteudo.splitlines()[0] else ','
    leitor=csv.DictReader(io.StringIO(conteudo.lstrip('\ufeff')),delimiter=delim)
    if not {'nome','categoria','preco'}<=set(leitor.fieldnames or []):
        raise ValueError('O CSV precisa das colunas nome, categoria e preco.')
    linhas=list(leitor)
    if not 1<=len(linhas)<=1000:
        raise ValueError('Importe de 1 a 1000 produtos por arquivo.')
    resultado=[]
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        for n,linha in enumerate(linhas,2):
            d={k:v.strip() for k,v in linha.items() if k is not None and v is not None}
            for k in ('fracionado','ativo','controlar_estoque'):
                if k in d:
                    if d[k].casefold() not in {'sim','nao','não','1','0','true','false'}:
                        raise ValueError(f'Linha {n}: {k} deve ser sim ou nao.')
                    d[k]=d[k].casefold() in {'sim','1','true'}
            d.setdefault('estoque',0)
            d.setdefault('estoque_minimo',0)
            try:
                p=estoque.salvar_produto(d,_conn=c)
            except ValueError as exc:
                raise ValueError(f'Linha {n}: {exc}') from None
            resultado.append({'nome':estoque.nome_completo(p),'sku':p['sku'],'estoque':p['estoque']})
        if dados.get('confirmar') is not True:
            c.rollback()
    return {'quantidade':len(resultado),'produtos':resultado[:20],'importado':dados.get('confirmar') is True}


def relatorio(inicio,fim):
    try:
        a=date.fromisoformat(inicio)
        b=date.fromisoformat(fim)
        if a>b or (b-a).days>366:
            raise ValueError
    except (TypeError,ValueError):
        raise ValueError('Escolha datas válidas, com intervalo de até 366 dias.') from None
    with get_conn() as c:
        itens=[dict(r) for r in c.execute("SELECT i.*,p.criado_em,p.total_pedido FROM itens_pedido i JOIN pedidos p ON p.id=i.pedido_id WHERE p.status!='CANCELADO' AND p.criado_em>=? AND p.criado_em<?",(a.isoformat(),(b+timedelta(days=1)).isoformat()))]
        total=dict(c.execute("SELECT COUNT(*) AS pedidos,COALESCE(SUM(total_pedido),0) AS vendas FROM pedidos WHERE status!='CANCELADO' AND criado_em>=? AND criado_em<?",(a.isoformat(),(b+timedelta(days=1)).isoformat())).fetchone())
    receita=Decimal('0'); custo=Decimal('0'); sem_custo=0; conhecidos=Decimal('0'); produtos={}
    for i in itens:
        valor=(Decimal(str(i['quantidade']))*Decimal(str(i['preco_unitario']))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        receita+=valor
        if i['custo_unitario'] is None:
            sem_custo+=1
        else:
            conhecidos+=valor
            custo+=(Decimal(str(i['quantidade']))*Decimal(str(i['custo_unitario']))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        p=produtos.setdefault(i['produto_id'],{'nome':i['nome_produto'],'quantidade':0,'vendas':0})
        p['quantidade']=estoque.somar(p['quantidade'],i['quantidade'])
        p['vendas']=float(Decimal(str(p['vendas']))+valor)
    return {**total,'inicio':inicio,'fim':fim,'receita_produtos':float(receita),'custos_registrados':float(custo),
            'margem_parcial':float(conhecidos-custo),'itens_sem_custo':sem_custo,
            'produtos':sorted(produtos.values(),key=lambda p:p['vendas'],reverse=True)}
