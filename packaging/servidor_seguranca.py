"""Alvo ZAP limitado ao loopback e dados descartáveis; não inicia integrações."""
import os
from pathlib import Path
import sys
import tempfile
from werkzeug.serving import run_simple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    artifacts = ROOT / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='owasp-', dir=artifacts) as directory:
        env = Path(directory) / 'teste.env'
        env.write_text('', encoding='utf-8')
        os.environ.update(DELIVERYBOT_ENV_FILE=str(env), DATABASE_PATH=str(Path(directory)/'teste.db'),
                          WHATSAPP_PROVIDER='TESTE', MODO_TESTE='SIM', SEED_CATALOGO='NAO', IA_PROVIDER='',
                          OLLAMA_AQUECER_AO_INICIAR='NAO', FLASK_DEBUG='NAO',
                          BASE_URL='http://127.0.0.1:5030', NOME_RESTAURANTE='Loja fictícia OWASP')
        from src.app import app
        from src import estoque, config
        from src.links import gerar_link_pedido
        from src.publicacao import PaginaPublica
        assert config.WHATSAPP_PROVIDER=='TESTE' and not config.IA_PROVIDER
        estoque.salvar_produto({'nome':"Produto fictício D'Ávila",'categoria':'Teste','preco':'10','controlar_estoque':False})
        (artifacts/'zap-target.txt').write_text(gerar_link_pedido('5500000000000'), encoding='utf-8')
        gateway = PaginaPublica(app, lambda: 'http://127.0.0.1:5030')
        run_simple('127.0.0.1', 5030, gateway, threaded=True, use_reloader=False, use_debugger=False)


if __name__=='__main__':
    main()
