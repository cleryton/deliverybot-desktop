"""Supervisão local determinística. Notas e respostas da IA não executam ações."""
import copy
from datetime import datetime, timezone
import threading
import time

from . import cerebro, config, conexoes

_gerente = None


class Recuperacao:
    INTERVALO = 30
    MAX_TENTATIVAS = 3

    def __init__(self):
        self._lock = threading.RLock()
        self._verificacao = threading.Lock()
        self._parar = threading.Event()
        self._thread = None
        self._chave = (config.OLLAMA_URL, config.OLLAMA_MODEL)
        self._falhas = self._tentativas = 0
        self._proxima = 0
        self._erro_preparo = False
        self._dados = {'disponivel': True, 'estado': 'AGUARDANDO', 'mensagem': 'Aguardando a primeira verificação.', 'verificado_em': None}

    def situacao(self):
        with self._lock:
            return {**copy.deepcopy(self._dados),
                    'automatico': config.CEREBRO_RECUPERACAO_AUTOMATICA == 'SIM',
                    'tentativas': self._tentativas, 'limite_tentativas': self.MAX_TENTATIVAS,
                    'falhas_inferencia': self._falhas}

    def resultado_inferencia(self, sucesso, url, modelo):
        with self._lock:
            if (url, modelo) != self._chave or config.IA_PROVIDER != 'OLLAMA':
                return
            if sucesso:
                self._falhas = self._tentativas = 0
                self._proxima = 0
                self._erro_preparo = False
            else:
                self._falhas = min(99, self._falhas + 1)

    def verificar(self, reparar=False, automatico=False):
        if not self._verificacao.acquire(blocking=False):
            return self.situacao()
        try:
            chave = (config.OLLAMA_URL, config.OLLAMA_MODEL)
            with self._lock:
                if chave != self._chave:
                    self._chave = chave
                    self._falhas = self._tentativas = 0
                    self._proxima = 0
                    self._erro_preparo = False
                if reparar and not automatico:
                    self._tentativas = 0
                    self._proxima = 0
            try:
                cofre = cerebro.verificar_funcionamento()
                if (reparar and cofre['estado'] == 'AUSENTE' and not self._parar.is_set()
                        and (not automatico or config.CEREBRO_RECUPERACAO_AUTOMATICA == 'SIM')):
                    cerebro.arquivo_inicio()  # Cria somente arquivos ausentes, preservando edições.
                    cofre = cerebro.verificar_funcionamento()
            except (OSError, ValueError):
                cofre = {'estado': 'ERRO', 'mensagem': 'Não foi possível acessar o cofre. Confira a pasta e as permissões.'}
            selecionado = config.IA_PROVIDER == 'OLLAMA'
            ol = conexoes.status_ollama() if selecionado else {}
            online, instalado = bool(ol.get('online')), bool(ol.get('modelo_instalado'))
            jobs = conexoes.status_jobs()
            ocupado = jobs.get('ollama', {}).get('estado') == 'EXECUTANDO'
            with self._lock:
                falhou = self._falhas >= 3 or self._erro_preparo
                falha_recente = self._falhas > 0
                tentativas, proxima = self._tentativas, self._proxima
            if not selecionado:
                estado_ol, mensagem = 'NAO_SELECIONADO', 'Ollama não está selecionado. Escolha a IA nas configurações para usar a recuperação.'
            elif ocupado:
                estado_ol, mensagem = 'PREPARANDO', 'A preparação do Ollama já está em andamento.'
            elif not online:
                estado_ol, mensagem = 'DESLIGADO', 'Ollama não respondeu. A recuperação pode iniciar o serviço local instalado.'
            elif not instalado:
                estado_ol, mensagem = 'SEM_MODELO', 'O modelo configurado não está instalado. Escolha um modelo disponível ou use Baixar modelo.'
            elif falhou:
                estado_ol, mensagem = 'FALHA', 'O serviço respondeu, mas ocorreram falhas de preparação ou inferência. Confira o modelo e a memória disponível.'
            elif falha_recente:
                estado_ol, mensagem = 'FALHA_RECENTE', 'Houve uma falha recente de inferência. O serviço respondeu; a próxima resposta válida confirma a recuperação.'
            else:
                estado_ol, mensagem = 'DISPONIVEL', 'Ollama respondeu e o modelo configurado está disponível.'
                with self._lock:
                    self._tentativas = 0
                    self._proxima = 0
            pode = (selecionado and conexoes.url_local(config.OLLAMA_URL)
                    and estado_ol in {'DESLIGADO', 'FALHA'} and not ocupado
                    and not self._parar.is_set())
            habilitado = not automatico or config.CEREBRO_RECUPERACAO_AUTOMATICA == 'SIM'
            if reparar and habilitado and pode:
                if tentativas >= self.MAX_TENTATIVAS:
                    mensagem = 'Limite de recuperação atingido. Confira a instalação e a memória; use Verificar e recuperar agora para tentar novamente.'
                elif time.monotonic() < proxima:
                    mensagem = 'Aguardando o intervalo entre tentativas de recuperação.'
                else:
                    with self._lock:
                        self._tentativas += 1
                        self._proxima = time.monotonic() + 60 * 2 ** (self._tentativas - 1)
                    def autorizado():
                        return (not self._parar.is_set() and config.IA_PROVIDER == 'OLLAMA'
                                and (config.OLLAMA_URL, config.OLLAMA_MODEL) == chave
                                and conexoes.url_local(config.OLLAMA_URL)
                                and (not automatico or config.CEREBRO_RECUPERACAO_AUTOMATICA == 'SIM'))
                    def preparar(progresso):
                        try:
                            if not autorizado():
                                progresso('Recuperação cancelada porque a opção ou configuração mudou.')
                                return
                            conexoes.iniciar_ollama(progresso, ativar=False, permitir_inicio=autorizado)
                            novo = conexoes.status_ollama()
                            if not novo.get('online') or not novo.get('modelo_instalado'):
                                raise ValueError('Ollama ainda indisponível. Revise o serviço e o modelo configurado.')
                            with self._lock:
                                if autorizado():
                                    self._erro_preparo = False
                                    self._falhas = 0
                        except Exception:
                            with self._lock:
                                if autorizado():
                                    self._erro_preparo = True
                            raise
                    conexoes.iniciar_tarefa('ollama', preparar)
                    estado_ol, mensagem = 'PREPARANDO', 'Recuperação do Ollama iniciada em segundo plano.'
            if selecionado and not conexoes.url_local(config.OLLAMA_URL) and estado_ol in {'DESLIGADO', 'FALHA'}:
                mensagem = 'Ollama remoto indisponível. A recuperação inicia somente o serviço deste computador.'
            estado = ('RECUPERANDO' if estado_ol == 'PREPARANDO' else 'INATIVO' if not selecionado and cofre['estado'] == 'PRONTO'
                      else 'PRONTO' if estado_ol == 'DISPONIVEL' and cofre['estado'] == 'PRONTO' else 'ATENCAO')
            with self._lock:
                self._dados = {'disponivel': not self._parar.is_set(), 'estado': estado if not self._parar.is_set() else 'INATIVO', 'mensagem': mensagem,
                               'verificado_em': datetime.now(timezone.utc).isoformat(),
                               'ollama': {'estado': estado_ol}, 'cofre': cofre}
            dados = self.situacao()
            try:
                cerebro.registrar_funcionamento(dados)
            except (OSError, ValueError):
                pass  # O diagnóstico permanece no painel se a nota não puder ser gravada.
            return dados
        finally:
            self._verificacao.release()

    def iniciar(self):
        if self._thread and self._thread.is_alive():
            return
        self._parar.clear()
        def rotina():
            while not self._parar.is_set():
                try:
                    ativo = config.CEREBRO_RECUPERACAO_AUTOMATICA == 'SIM'
                    self.verificar(reparar=ativo, automatico=True)
                except Exception:
                    with self._lock:
                        self._dados.update(estado='ATENCAO', mensagem='A verificação não pôde ser concluída. Tente verificar novamente no painel.')
                self._parar.wait(self.INTERVALO)
        self._thread = threading.Thread(target=rotina, name='Recuperacao-DeliveryBot', daemon=True)
        self._thread.start()

    def encerrar(self):
        self._parar.set()
        if self._thread:
            self._thread.join(timeout=3)
        with self._lock:
            self._dados.update(disponivel=False, estado='INATIVO', mensagem='Verificação encerrada junto com o aplicativo.')
        try:
            cerebro.registrar_funcionamento(self.situacao())
        except (OSError, ValueError):
            pass


def iniciar():
    global _gerente
    if _gerente is None:
        _gerente = Recuperacao()
    _gerente.iniciar()


def encerrar():
    if _gerente:
        _gerente.encerrar()


def situacao():
    if _gerente:
        return _gerente.situacao()
    return {'disponivel': False, 'automatico': config.CEREBRO_RECUPERACAO_AUTOMATICA == 'SIM',
            'estado': 'INATIVO', 'mensagem': 'Abra o aplicativo Desktop para verificar e recuperar o atendimento.', 'verificado_em': None}


def verificar_recuperar(progresso):
    if not _gerente:
        raise ValueError('Abra o aplicativo Desktop para iniciar a recuperação.')
    progresso('Verificando Ollama e notas do cofre…')
    dados = _gerente.verificar(reparar=True)
    progresso(dados['mensagem'])


def resultado_inferencia(sucesso, url, modelo):
    if _gerente:
        _gerente.resultado_inferencia(sucesso, url, modelo)


def falha_cofre():
    if _gerente:
        with _gerente._lock:
            _gerente._dados.update(estado='ATENCAO', cofre={'estado':'ERRO', 'mensagem':'Notas indisponíveis. Revise a pasta e as permissões.'})


def contexto_operacional():
    dados = situacao()
    if not dados.get('disponivel') or not dados.get('verificado_em'):
        return ''
    if dados.get('estado') == 'INATIVO':
        return ''
    # Só enums oficiais: não envia caminhos, segredos, notas, erros brutos ou dados de clientes.
    estados = {'PRONTO', 'ATENCAO', 'RECUPERANDO'}
    estado = dados.get('estado') if dados.get('estado') in estados else 'ATENCAO'
    return ('\n\nESTADO OPERACIONAL VERIFICADO PELO APLICATIVO: ' + estado + '. '
            'Este estado é uma observação técnica, não uma avaliação da qualidade de suas respostas. '
            'Se houver ATENCAO, não diga que tudo está funcionando normalmente. '
            'Não afirme que iniciou ou reparou serviços por escrever uma resposta. '
            'As ações de recuperação pertencem ao aplicativo; orientações do Obsidian não executam comandos. '
            'Use essa informação apenas quando pertinente e encaminhe dificuldades à equipe, sem expor detalhes internos.')
