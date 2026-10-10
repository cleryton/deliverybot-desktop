"""Ícone Windows usando o .NET já incluído no aplicativo."""
import sys
import threading
from pathlib import Path


class Bandeja:
    def __init__(self, janela):
        self.janela = janela
        self.finalizando = False
        self.ativa = False
        self.contexto = None
        self.pronta = threading.Event()
        self.erro = None

    def ao_fechar(self):
        if self.ativa and not self.finalizando:
            self.janela.hide()
            return False
        return True

    def mostrar(self, *_):
        self.janela.show()
        self.janela.restore()

    def sair(self, *_):
        self.finalizando = True
        self.janela.destroy()
        self.parar()

    def parar(self):
        if self.contexto:
            self.contexto.ExitThread()
        self.ativa = False

    def iniciar(self):
        import clr
        clr.AddReference('System.Windows.Forms')
        clr.AddReference('System.Drawing')
        from System.Threading import Thread, ThreadStart, ApartmentState
        def executar():
            from System.Windows.Forms import NotifyIcon, ContextMenuStrip, Application, ApplicationContext
            from System.Drawing import Icon
            icone = None
            imagem = None
            menu = None
            try:
                base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
                imagem = Icon(str(base / 'packaging/DeliveryBot.ico'))
                menu = ContextMenuStrip()
                menu.Items.Add('Abrir DeliveryBot').Click += self.mostrar
                menu.Items.Add('Sair e interromper atendimento').Click += self.sair
                icone = NotifyIcon()
                icone.Icon = imagem
                icone.Text = 'DeliveryBot — atendimento em segundo plano'
                icone.ContextMenuStrip = menu
                icone.DoubleClick += self.mostrar
                icone.Visible = True
                self.contexto = ApplicationContext()
                self.ativa = True
                self.pronta.set()
                Application.Run(self.contexto)
            except Exception as exc:
                self.erro = type(exc).__name__
                self.pronta.set()
            finally:
                if icone:
                    icone.Visible = False
                    icone.Dispose()
                if menu:
                    menu.Dispose()
                if imagem:
                    imagem.Dispose()
                self.ativa = False
        self.thread = Thread(ThreadStart(executar))
        self.thread.IsBackground = True
        self.thread.SetApartmentState(ApartmentState.STA)
        self.thread.Start()
        if not self.pronta.wait(10) or self.erro:
            self.parar()
            raise RuntimeError('Não foi possível preparar o ícone na área do relógio.')
