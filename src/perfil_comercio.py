"""Perfil individual, com estoque opcional por item e preservação de cadastros."""
import json
from pathlib import Path

from . import config, preferencias
from .db import get_conn
from .estoque import texto

MODELOS = {
    'REVENDA': ('Produtos', 'Você revende itens disponíveis em quantidade.', True),
    'PRODUCAO': ('Cardápio e encomendas', 'Você prepara ou produz depois que o cliente pede.', False),
    'SERVICOS': ('Serviços', 'Você oferece serviços e define o que pode ser contratado.', False),
    'MISTO': ('Produtos e serviços', 'Você combina produtos, produção ou prestação de serviços.', True),
}


def obter():
    titulo, explicacao, _ = MODELOS.get(config.COMERCIO_MODELO, MODELOS['REVENDA'])
    return {'nome': config.NOME_RESTAURANTE, 'segmento': config.COMERCIO_SEGMENTO,
            'descricao': config.COMERCIO_DESCRICAO, 'modelo': config.COMERCIO_MODELO,
            'controlar_estoque': config.COMERCIO_ESTOQUE_PADRAO == 'SIM',
            'configurado': config.COMERCIO_CONFIGURADO == 'SIM',
            'titulo_catalogo': titulo, 'explicacao': explicacao}


def salvar(dados):
    if not isinstance(dados, dict):
        raise ValueError('Informe os dados do comércio.')
    nome = texto(dados.get('nome', ''), 'Nome do comércio', 160, True)
    segmento = texto(dados.get('segmento', ''), 'Segmento', 120, True)
    descricao = texto(dados.get('descricao', ''), 'Descrição do comércio', 1200, True)
    modelo = dados.get('modelo')
    if not isinstance(modelo, str) or modelo not in MODELOS:
        raise ValueError('Escolha revenda, produção, serviços ou uma operação mista.')
    controle = dados.get('controlar_estoque', MODELOS[modelo][2])
    if not isinstance(controle, bool):
        raise ValueError('Informe se os novos itens devem controlar estoque.')
    preferencias.salvar({'NOME_RESTAURANTE': nome, 'COMERCIO_SEGMENTO': segmento,
                        'COMERCIO_DESCRICAO': descricao, 'COMERCIO_MODELO': modelo,
                        'COMERCIO_ESTOQUE_PADRAO': 'SIM' if controle else 'NAO',
                        'COMERCIO_CONFIGURADO': 'SIM'})
    return obter()


def importar_instalacao(pasta):
    """Consome a configuração local do instalador somente em uma loja nova."""
    arquivo = Path(pasta) / 'perfil-instalacao.json'
    if not arquivo.exists():
        return False
    if arquivo.is_symlink() or (hasattr(arquivo, 'is_junction') and arquivo.is_junction()) or arquivo.stat().st_size > 12000:
        raise ValueError('Configuração inicial inválida. Configure Meu comércio no aplicativo.')
    with get_conn() as conn:
        existente = (config.COMERCIO_CONFIGURADO == 'SIM'
                     or conn.execute('SELECT 1 FROM produtos LIMIT 1').fetchone()
                     or conn.execute('SELECT 1 FROM pedidos LIMIT 1').fetchone()
                     or conn.execute('SELECT 1 FROM configuracoes LIMIT 1').fetchone())
    if existente:
        arquivo.unlink()
        return False
    try:
        dados = json.loads(arquivo.read_text(encoding='utf-8-sig'))
    except (ValueError, UnicodeError):
        raise ValueError('Configuração inicial inválida. Configure Meu comércio no aplicativo.') from None
    salvar(dados)
    arquivo.unlink()
    return True
