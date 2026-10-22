"""Permissão temporária para reler recibos na sessão que confirmou o pedido.

O cookie assinado contém apenas hashes dos tokens, IDs, prazo e flags; nunca
nome, telefone, endereço ou o próprio link de compra. Não autoriza operações.
"""
from hashlib import sha256
from time import time

from flask import session

DURACAO = 8*60*60
LIMITE = 5


def _validos():
    valores = session.get('comprovantes', {})
    if not isinstance(valores,dict):return {}
    agora = time()
    return {k:v for k,v in valores.items() if isinstance(k,str) and len(k)==64
            and isinstance(v,dict) and type(v.get('id')) is int and v['id']>0
            and type(v.get('ate')) in {int,float} and agora<v['ate']<=agora+DURACAO
            and type(v.get('teste')) is bool and type(v.get('notificado')) is bool}


def registrar(token,pedido_id,modo_teste,notificado):
    registros = _validos()
    chave = sha256(token.encode()).hexdigest()
    registros.pop(chave,None)
    registros = dict(sorted(registros.items(),key=lambda item:item[1]['ate'])[-(LIMITE-1):])
    registros[chave] = {'id':pedido_id,'ate':int(time())+DURACAO,'teste':bool(modo_teste),'notificado':bool(notificado)}
    session['comprovantes'] = registros


def consultar(token,pedido_id):
    registro = _validos().get(sha256(token.encode()).hexdigest())
    return registro if registro and registro['id']==pedido_id else None
