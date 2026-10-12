"""Aplicativo Windows independente para registro manual e caixa do funcionário."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote,urlsplit


class ClienteSmoke:
    """Dados em memória, exclusivos do teste visual; nenhum serviço ou conta real."""
    def __init__(self):
        self.caixas=[];self.vendas=[]
    def entrar(self,*args):
        return {'usuario':{'id':1,'nome':'Funcionário fictício'},'loja':'Loja de teste'}
    def consultar(self,acao):
        if acao=='catalogo':
            return [{'id':1,'nome':'Produto de teste','variacao':'','categoria':'Fictícios','preco':12.30,'estoque':10,'fracionado':0,'unidade':'un'}]
        return {'caixas':self.caixas,'vendas':self.vendas}
    def cotar(self,itens,entrega='RETIRADA BALCAO'):
        return {'total_pedido':12.30,'itens':itens}
    def executar(self,acao,d):
        if acao=='abrir':
            self.caixas=[{'id':1,'fechado_em':None,'esperado_centavos':10000,'vendas_centavos':0,'recebimentos':{'PIX':0,'CARTAO':0}}]
        if acao=='vender':
            self.caixas[0].update(esperado_centavos=11230,vendas_centavos=1230)
            self.vendas=[{'id':1,'numero_pedido':'#12345678','nome':'Balcão fictício','total_pedido':12.30,'total_pago':12.30,'status':'RECEBIDO'}]
            return {'numero_pedido':'#12345678','pago':True,'troco_centavos':770}
        if acao=='fechar':
            self.caixas[0].update(fechado_em='2026-01-01 12:00:00',contado_centavos=11200,diferenca_centavos=-30)
            return {'diferenca_centavos':-30}
        return {'ok':True}
    def conferir(self,*args):
        return {'pendente':False}
    def sair(self):
        return {'ok':True}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke-test',type=Path)
    parser.add_argument('--window-smoke-test',action='store_true')
    args=parser.parse_args()
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    if args.smoke_test:
        from src.cliente_terminal import validar_conexao
        try:
            validar_conexao({'formato':1,'url':'http://localhost:5000'})
            raise AssertionError('URL insegura aceita')
        except ValueError:
            pass
        for nome in ('index.html','terminal.js','terminal.css'):
            assert (root/'web/funcionario'/nome).is_file()
        args.smoke_test.parent.mkdir(parents=True,exist_ok=True)
        from src.protecao_terminal import dpapi
        assert dpapi(dpapi(b'dados-ficticios'),True)==b'dados-ficticios'
        if not args.window_smoke_test:
            args.smoke_test.write_text(json.dumps({'ok':True,'recursos':True,'conexao_https':True,'credencial_windows':True,'sem_banco_local':True}),encoding='utf-8')
            return 0
    import webview
    from src.cliente_terminal import Cliente
    pasta=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'DeliveryBotFuncionario'
    cliente=ClienteSmoke() if args.smoke_test else Cliente(pasta)
    pagina=(root/'web/funcionario/index.html').resolve()
    class API:
        def _verificar(self):
            u=urlsplit(janela.get_current_url())
            esperado=urlsplit(janela.real_url or '')
            if u!=esperado or u.scheme not in {'http','file'} or (u.scheme=='http' and u.hostname!='127.0.0.1'):
                raise ValueError('Reabra o aplicativo do funcionário.')
        def importar(self):
            self._verificar()
            arquivos=janela.create_file_dialog(webview.FileDialog.OPEN,allow_multiple=False,file_types=('Acesso DeliveryBot (*.dbterminal)',))
            if not arquivos:
                return {'cancelado':True}
            p=Path(arquivos[0])
            if p.stat().st_size>32768:
                raise ValueError('Arquivo de acesso inválido.')
            return cliente.parear(json.loads(p.read_text(encoding='utf-8')))
        def entrar(self,login,senha):
            self._verificar()
            return cliente.entrar(login,senha)
        def consultar(self,acao):
            self._verificar()
            return cliente.consultar(acao)
        def cotar(self,itens,entrega='RETIRADA BALCAO'):
            self._verificar()
            return cliente.cotar(itens,entrega)
        def executar(self,acao,dados):
            self._verificar()
            return cliente.executar(acao,dados)
        def conferir(self,repetir=False):
            self._verificar()
            return cliente.conferir(repetir)
        def sair(self):
            self._verificar()
            return cliente.sair()
    janela=webview.create_window('DeliveryBot Funcionário — Pedidos e caixa',pagina.as_uri(),js_api=API(),width=1200,height=820,min_size=(850,600))
    resultado={'ok':True,'janela':True,'backend_simulado':True}
    def verificar():
        import time
        def esperar(js):
            limite=time.monotonic()+25
            while time.monotonic()<limite:
                if janela.evaluate_js(js):return
                time.sleep(.15)
            raise AssertionError('Prazo de teste visual excedido: '+js)
        try:
            esperar('!!window.pywebview?.api?.entrar')
            janela.evaluate_js("document.querySelector('#login-form').login.value='ficticio';document.querySelector('#login-form').senha.value='senha-ficticia';document.querySelector('#login-form button').click()")
            esperar("!document.querySelector('#painel').hidden && document.querySelector('#catalogo button')")
            janela.evaluate_js("document.querySelector('#abertura').abertura.value='100';document.querySelector('#abertura button').click()")
            esperar("!document.querySelector('#operacao').hidden && document.querySelector('#esperado').textContent.includes('100')")
            janela.evaluate_js("document.querySelector('#catalogo button').click();document.querySelector('#pedido-form').recebido.value='20';document.querySelector('#revisar').click()")
            esperar("!document.querySelector('#registrar').disabled && document.querySelector('#cotacao').textContent.includes('12,30')")
            janela.evaluate_js("window.confirm=()=>true;document.querySelector('#registrar').click()")
            esperar("document.querySelector('#pedidos').textContent.includes('#12345678') && document.querySelector('#esperado').textContent.includes('112,30')")
            assert janela.evaluate_js("document.querySelector('#aviso').textContent.includes('7,70')")
            janela.evaluate_js("document.querySelector('#fechamento').contado.value='112';document.querySelector('#fechamento button').click()")
            esperar("document.querySelector('#historico').textContent.includes('0,30') && document.querySelector('#operacao').hidden")
            resultado['fluxos']=['login_nativo','abertura','catalogo','cotacao','venda','troco','fechamento','historico']
        except Exception as e:
            resultado.update(ok=False,erro=str(e))
            try:resultado['diagnostico']=janela.evaluate_js("({url:location.href,aviso:document.querySelector('#aviso')?.textContent,cotacao:document.querySelector('#cotacao')?.textContent})")
            except Exception:pass
        finally:
            janela.destroy()
    webview.start(verificar if args.smoke_test else None,gui='edgechromium',private_mode=True)
    if args.smoke_test:
        args.smoke_test.write_text(json.dumps(resultado,ensure_ascii=False,indent=2),encoding='utf-8')
        return 0 if resultado['ok'] else 1
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as e:
        if sys.platform=='win32':
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'Não foi possível abrir o caixa. Confira o arquivo de acesso e o WebView2.\n\n'+str(e),'DeliveryBot Funcionário',0x10)
        raise
