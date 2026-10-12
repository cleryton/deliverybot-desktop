"""Permissões determinísticas da estação; notas e modelos nunca autorizam acesso."""
import secrets
import threading
import time

from flask import g, has_request_context

from .db import get_conn
from . import estoque

OCIOSIDADE = 15 * 60
DURACAO = 8 * 60 * 60


class AcessoNegado(Exception):
    pass


def conta_caixa(c, uid):
    r = c.execute("SELECT id FROM operadores WHERE id=? AND ativo=1 AND perfil='CAIXA'", (uid,)).fetchone()
    if not r:
        raise ValueError('Selecione uma conta Caixa ativa. A conta administradora não usa o terminal.')


def dados_autorizacao(d):
    uid = estoque.inteiro(d.get('operador_id'), 'Funcionário', 1)
    if type(d.get('movimentar', False)) is not bool:
        raise ValueError('Informe se permite sangria e suprimento.')
    return uid, bool(d.get('movimentar', False))


def autorizar(did, d):
    uid, mover = dados_autorizacao(d)
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        conta_caixa(c, uid)
        if not c.execute('SELECT 1 FROM terminal_dispositivos WHERE id=? AND ativo=1', (did,)).fetchone():
            raise ValueError('Computador revogado ou não encontrado. Gere um novo acesso.')
        c.execute('INSERT INTO terminal_autorizacoes VALUES(?,?,?,?) ON CONFLICT(dispositivo_id) DO UPDATE SET operador_id=excluded.operador_id,movimentar=excluded.movimentar,versao=excluded.versao',
                  (did, uid, int(mover), secrets.token_hex(24)))


def exigir_gravacao(c, uid, acao):
    """Revalida dentro da transação financeira, inclusive após uma revogação concorrente."""
    a = g.get('terminal_autorizacao') if has_request_context() else None
    if a is None:
        return  # A administração local continua com suas próprias verificações.
    r = c.execute("SELECT a.*,o.versao AS conta_versao,o.ativo,o.perfil,d.ativo AS dispositivo_ativo,t.ativo AS gateway_ativo FROM terminal_autorizacoes a JOIN operadores o ON o.id=a.operador_id JOIN terminal_dispositivos d ON d.id=a.dispositivo_id JOIN terminal_config t ON t.id=1 WHERE a.dispositivo_id=?", (a['dispositivo_id'],)).fetchone()
    if (not r or r['operador_id'] != uid or not r['ativo'] or r['perfil'] != 'CAIXA'
            or not r['dispositivo_ativo'] or not r['gateway_ativo'] or r['versao'] != a['versao']
            or r['conta_versao'] != a['conta_versao'] or time.monotonic() >= a['prazo']):
        raise AcessoNegado('A autorização mudou ou expirou. Entre novamente com a conta vinculada.')
    if acao in {'SANGRIA', 'SUPRIMENTO'} and not r['movimentar']:
        raise AcessoNegado('Sangria e suprimento precisam da autorização do responsável.')


class Sessoes:
    """Prazos no servidor; leitura automática não renova o tempo de inatividade."""
    def __init__(self):
        self.itens = {}
        self.trava = threading.Lock()

    def criar(self, did, uid, versao):
        agora = time.monotonic()
        with self.trava:
            self.itens = {k: v for k, v in self.itens.items() if min(v['ultimo'] + OCIOSIDADE, v['fim']) > agora}
            if len(self.itens) >= 512:
                raise AcessoNegado('Limite de sessões atingido. Encerre acessos antigos e tente novamente.')
            chave = secrets.token_hex(32)
            self.itens[chave] = dict(dispositivo=did, operador=uid, versao=versao, ultimo=agora, fim=agora+DURACAO)
            return chave

    def validar(self, chave, did, uid, versao, interativa=False):
        agora = time.monotonic()
        with self.trava:
            s = self.itens.get(chave)
            if not s or (s['dispositivo'], s['operador'], s['versao']) != (did, uid, versao):
                return None
            if min(s['ultimo'] + OCIOSIDADE, s['fim']) <= agora:
                self.itens.pop(chave, None)
                return None
            if interativa:
                s['ultimo'] = agora
            return min(s['ultimo'] + OCIOSIDADE, s['fim'])

    def sair(self, chave):
        with self.trava:
            self.itens.pop(chave, None)


class Limites:
    """Contadores de memória com tamanho e duração limitados, sem confiar em cabeçalhos de IP."""
    def __init__(self):
        self.itens = {}
        self.trava = threading.Lock()

    def consumir(self, chave, maximo, janela):
        agora = time.monotonic()
        with self.trava:
            self.itens = {k: v for k, v in self.itens.items() if v[1] > agora}
            n, fim = self.itens.get(chave, (0, agora+janela))
            if n >= maximo or (chave not in self.itens and len(self.itens) >= 2048):
                return False
            self.itens[chave] = (n+1, fim)
            return True
