"""Limita o trabalho público de confirmação sem guardar links ou dados pessoais."""
from contextlib import contextmanager
from hashlib import sha256
import threading

from . import config
from .politica_terminal import Limites


class ConfirmacaoOcupada(Exception):
    def __init__(self, aguardar):
        super().__init__('Aguarde antes de tentar confirmar novamente.')
        self.aguardar = aguardar


class ProtecaoConfirmacao:
    def __init__(self):
        self.limites = Limites()
        self.vagas = threading.BoundedSemaphore(2)

    @contextmanager
    def reservar(self, token):
        # Cada banco tem sua própria cota; armazena somente resumos irreversíveis.
        banco = sha256(str(config.DATABASE_PATH).encode('utf-8')).digest()
        link = sha256(token.encode('utf-8')).digest()
        if not self.limites.consumir((banco, link), 8, 60):
            raise ConfirmacaoOcupada(60)
        if not self.limites.consumir(('global', banco), 60, 60):
            raise ConfirmacaoOcupada(60)
        if not self.vagas.acquire(blocking=False):
            raise ConfirmacaoOcupada(15)
        try:
            yield
        finally:
            self.vagas.release()


protecao = ProtecaoConfirmacao()
