"""Limites do PDF público; não armazena tokens nem altera os PDFs internos."""
from contextlib import contextmanager
import hashlib
import threading

from .politica_terminal import Limites


class CatalogoOcupado(Exception):
    def __init__(self, aguardar):
        super().__init__('Aguarde antes de baixar o catálogo novamente.')
        self.aguardar = aguardar


class ProtecaoCatalogo:
    def __init__(self):
        self.limites = Limites()
        self.vagas = threading.BoundedSemaphore(2)

    @contextmanager
    def reservar(self, token):
        # A rota valida o link antes de reservar. Os contadores retêm apenas
        # hashes em janelas de um minuto, com o limite de memória de Limites.
        chave = hashlib.sha256(token.encode('utf-8')).digest()
        if not self.limites.consumir(('link', chave), 3, 60):
            raise CatalogoOcupado(60)
        if not self.limites.consumir('global', 30, 60):
            raise CatalogoOcupado(60)
        if not self.vagas.acquire(blocking=False):
            raise CatalogoOcupado(15)
        try:
            yield
        finally:
            self.vagas.release()


protecao = ProtecaoCatalogo()
