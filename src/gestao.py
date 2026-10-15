"""Painel administrativo compartilhado pelo aplicativo e pelo servidor."""
import hmac
from concurrent.futures import ThreadPoolExecutor
import secrets
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for, send_file

from . import bot, cardapio, config, estoque, fila, pedidos, preferencias, recibo, whatsapp
from .db import get_conn
from . import conexoes, processamento, publicacao, aparencia, cerebro, perfil_comercio, recuperacao
from . import seguranca, privacidade, backups, operadores, fotos

bp = Blueprint("gestao", __name__)


def _local():
    # Host também é verificado para impedir DNS rebinding contra o servidor local.
    return seguranca.local()


def acesso_base():
    from .app import _exigir_autenticacao_cozinha
    token = current_app.config.get("DESKTOP_TOKEN")
    if token:
        return _local() and seguranca.igual(session.get("desktop", ""), token)
    if not seguranca.acesso_administrativo():
        return False
    return _exigir_autenticacao_cozinha()


def autorizado():
    return acesso_base() and (not operadores.existem() or operadores.usuario() is not None)


def protegido(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not autorizado():
            return jsonify(erro="Acesso restrito ao administrador."), 401
        if request.method != "GET":
            if not seguranca.csrf_valido():
                return jsonify(erro="Sessão expirada. Reabra o painel."), 403
        if not operadores.permitido(request.path,request.method):
            return jsonify(erro='Seu perfil não permite esta operação.'),403
        ator=operadores.usuario()
        resultado=view(*args, **kwargs)
        if request.method!='GET' and current_app.make_response(resultado).status_code<400:
            operadores.auditar(request.endpoint, next(iter(kwargs.values()),None),usuario_id=ator['id'] if ator else None)
        return resultado
    return wrapper


def dados_json():
    dados = request.get_json()
    if not isinstance(dados, dict):
        raise ValueError("Envie os dados em formato válido.")
    return dados


@bp.get('/gestao/api/meta/situacao')
@protegido
def meta_situacao():
    from .meta_oficial import situacao
    return jsonify(situacao())


@bp.post('/gestao/api/meta/verificar')
@protegido
def meta_verificar():
    from .meta_oficial import verificar
    return jsonify(verificar(dados_json()))


@bp.post('/gestao/api/meta/migrar')
@protegido
def meta_migrar():
    from .meta_oficial import migrar
    return jsonify(migrar(dados_json()))


@bp.post('/gestao/api/meta/numeros')
@protegido
def meta_numeros():
    from .meta_configuracao import consultar
    return jsonify(consultar(dados_json()))


@bp.post('/gestao/api/meta/conectar')
@protegido
def meta_conectar():
    from .meta_configuracao import conectar
    return jsonify(conectar(dados_json()))


@bp.post('/gestao/api/meta/webhook')
@protegido
def meta_webhook():
    from .meta_configuracao import configurar_webhook
    if dados_json().get('confirmar') is not True:
        raise ValueError('Confirme a configuração do webhook da sua conta Meta.')
    return jsonify(configurar_webhook())


@bp.route('/gestao/api/meta/custos', methods=['GET', 'PUT'])
@protegido
def meta_custos():
    from . import meta_custos as custos
    if request.method == 'PUT':
        return jsonify(custos.configurar(dados_json()))
    return jsonify(custos.relatorio(request.args.get('mes'), request.args.get('ambiente', 'TODOS')))


@bp.get('/gestao/api/meta/tarifas')
@protegido
def meta_tarifas():
    from .meta_custos import configuracao
    return jsonify(configuracao())


def dados_produto():
    if request.mimetype != 'multipart/form-data':
        return dados_json(), None
    try:
        from .validacao_http import ler_json
        dados = ler_json(request.form.get('dados', ''))
    except (ValueError, TypeError):
        raise ValueError('Envie os dados do produto em formato válido.') from None
    if not isinstance(dados, dict):
        raise ValueError('Envie os dados do produto em formato válido.')
    arquivos = request.files.getlist('foto')
    if len(arquivos) > 1 or set(request.files) - {'foto'}:
        raise ValueError('Escolha apenas uma foto por produto.')
    foto = fotos.normalizar(arquivos[0].stream) if arquivos else None
    return dados, foto


@bp.errorhandler(ValueError)
def erro_validacao(exc):
    return jsonify(erro=str(exc)), 400


@bp.after_request
def cabecalhos(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@bp.route("/gestao")
def painel():
    token = current_app.config.get("DESKTOP_TOKEN")
    recebido = request.args.get("acesso", "")
    if token and _local() and recebido and seguranca.igual(recebido, token):
        session.clear()
        session["desktop"] = token
        session["csrf"] = secrets.token_urlsafe(32)
        session.permanent = True
        return redirect(url_for("gestao.painel"))
    if not autorizado():
        if acesso_base():
            return pagina_login()
        return "Abra o aplicativo DeliveryBot ou entre com a conta administrativa.", 401, {"WWW-Authenticate": 'Basic realm="DeliveryBot"'}
    session.setdefault("csrf", secrets.token_urlsafe(32))
    u = operadores.usuario()
    if u and u['perfil'] == 'CAIXA':
        return render_template('operadores_caixa.html', csrf=session['csrf'])
    return render_template("gestao.html", csrf=session["csrf"], administrador=operadores.admin(),
                           tema=aparencia.tema(),
                           perfil_pendente=config.COMERCIO_CONFIGURADO != 'SIM',
                           provedor_whatsapp=config.WHATSAPP_PROVIDER if token else "")


def pagina_login(erro=None,status=200):
    response=current_app.make_response((render_template('operadores_login.html',csrf=seguranca.csrf(),erro=erro,tema=aparencia.tema()),status))
    # Formulários nativos com no-referrer podem enviar Origin:null. Esta página
    # preserva a origem local, sem enviar referer para outros sites.
    response.headers['Referrer-Policy']='same-origin'
    return response


@bp.route('/gestao/api/aparencia', methods=['GET', 'PUT'])
def aparencia_api():
    # Disponível também na tela de login: exige acesso local autenticado ao app.
    # A preferência é cosmética e não concede acesso às operações da loja.
    if not acesso_base():
        return jsonify(erro='Acesso restrito ao aplicativo.'), 401
    if request.method == 'PUT':
        if not seguranca.csrf_valido():
            return jsonify(erro='Sessão expirada. Reabra o painel.'), 403
        aparencia.salvar(dados_json().get('tema'))
    return jsonify(tema=aparencia.tema())


@bp.post('/gestao/login')
def login_operador():
    if not acesso_base() or not seguranca.csrf_valido():
        return 'Reabra o painel para entrar.',403
    if seguranca.login_bloqueado():
        return 'Muitas tentativas. Aguarde cinco minutos.',429
    ok=operadores.entrar(request.form.get('login'),request.form.get('senha'))
    seguranca.registrar_login(ok)
    if not ok:
        return pagina_login('Login ou senha inválidos.',401)
    return redirect('/gestao')


@bp.post('/gestao/sair')
def sair_operador():
    if not autorizado() or not seguranca.csrf_valido():
        return 'Sessão inválida.',403
    operadores.auditar('SAIR')
    session.pop('operador_id',None);session.pop('operador_versao',None)
    return redirect('/gestao')


@bp.route('/gestao/api/operadores',methods=['GET','POST'])
@protegido
def operadores_api():
    return jsonify(operadores.listar() if request.method=='GET' else operadores.criar(dados_json()))


@bp.put('/gestao/api/operadores/<int:uid>')
@protegido
def alterar_operador(uid):
    operadores.alterar(uid,dados_json())
    return jsonify(ok=True)


@bp.get('/gestao/api/operadores/me')
@protegido
def operador_atual():
    return jsonify(usuario=operadores.usuario(),administrador=operadores.admin(),contas_ativas=operadores.existem())


@bp.route('/gestao/api/terminal',methods=['GET','PUT'])
@protegido
def terminal_api():
    from . import terminal
    if request.method=='PUT':
        if not current_app.config.get('DESKTOP_TOKEN'):
            raise ValueError('Configure a rede dos funcionários no aplicativo Windows do responsável.')
        terminal.configurar(dados_json())
    return jsonify(terminal.situacao())


@bp.post('/gestao/api/terminal/dispositivos/<int:did>/revogar')
@protegido
def terminal_revogar(did):
    from . import terminal
    terminal.revogar(did)
    return jsonify(ok=True)


@bp.put('/gestao/api/terminal/dispositivos/<int:did>/autorizacao')
@protegido
def terminal_autorizar(did):
    from .politica_terminal import autorizar
    autorizar(did,dados_json())
    return jsonify(ok=True)


@bp.get('/gestao/api/caixas')
@protegido
def caixas_api():
    from . import caixa
    return jsonify(caixa.consultar())


@bp.post('/gestao/api/caixas/pedidos/<int:pid>/estornar')
@protegido
def caixa_estornar(pid):
    from . import caixa
    u=operadores.usuario()
    if not u or u['perfil']!='ADMIN':
        raise ValueError('Entre com uma conta administradora para registrar o estorno.')
    return jsonify(caixa.estornar(u['id'],pid,dados_json()))


@bp.post('/gestao/api/caixas/<int:tid>/fechar')
@protegido
def caixa_fechar_admin(tid):
    from . import caixa
    u=operadores.usuario()
    if not u or u['perfil']!='ADMIN':
        raise ValueError('Entre com sua conta administradora para conferir outro caixa.')
    return jsonify(caixa.fechar_pelo_admin(u['id'],tid,dados_json()))


@bp.route('/gestao/api/atualizacoes',methods=['GET','PUT','POST'])
@protegido
def atualizacoes_api():
    from . import atualizacoes
    if request.method=='PUT':
        atualizacoes.configurar(dados_json())
    elif request.method=='POST':
        d=dados_json()
        if d.get('acao')=='consultar':
            funcao=atualizacoes.consultar
        elif d.get('acao')=='baixar':
            senha=d.get('senha')
            backups._chave(senha,b'0'*16)
            funcao=lambda progresso:atualizacoes.baixar(senha,progresso)
        else:
            raise ValueError('Operação de atualização inválida.')
        return jsonify(conexoes.iniciar_tarefa('atualizacoes',funcao)),202
    return jsonify(**atualizacoes.situacao(),tarefa=conexoes.status_jobs().get('atualizacoes'))


@bp.get('/gestao/api/operadores/auditoria')
@protegido
def auditoria_operadores():
    return jsonify(operadores.auditoria())


@bp.route("/gestao/api/resumo")
@protegido
def resumo():
    produtos = estoque.listar_produtos()
    with get_conn() as conn:
        total = dict(conn.execute(
            "SELECT COUNT(*) AS pedidos, COALESCE(SUM(total_pedido),0) AS vendas FROM pedidos WHERE status != 'CANCELADO'").fetchone())
    if not operadores.admin():
        total['vendas']=0
    return jsonify(produtos=len(produtos), ativos=sum(p["ativo"] for p in produtos),
                   baixos=sum(p["ativo"] and p["estoque"] is not None and p["estoque"] <= p["estoque_minimo"] for p in produtos),
                   pendentes=len(fila.listar_fila()), **total, nome=config.NOME_RESTAURANTE,
                   comercio={k: v for k, v in perfil_comercio.obter().items() if k != 'descricao'},
                   produtos_controlados=sum(p['estoque'] is not None for p in produtos),
                   modo_teste=config.MODO_TESTE, whatsapp=config.WHATSAPP_PROVIDER,
                   privacidade_configurada=bool(config.LGPD_RESPONSAVEL and config.LGPD_CONTATO),
                   base_url=publicacao.endereco(), pasta=str(Path(config.DATABASE_PATH).resolve().parent),
                   webhook_waha="Endereço privado de recebimento configurado." if config.WEBHOOK_SECRET else "Configure a conexão do WhatsApp.")


def _webhook_exibicao():
    try:
        return conexoes.url_webhook()
    except ValueError:
        return "Informe o endereço do aplicativo visto pelo WAHA em Configurações."


@bp.route('/gestao/api/comercio', methods=['GET', 'PUT'])
@protegido
def comercio_api():
    return jsonify(perfil_comercio.obter() if request.method == 'GET' else perfil_comercio.salvar(dados_json()))


@bp.route("/gestao/api/produtos", methods=["GET", "POST"])
@protegido
def produtos():
    if request.method == "GET":
        produtos=estoque.listar_produtos()
        if not operadores.admin():
            for p in produtos:
                p.pop('custo',None)
        return jsonify(produtos)
    dados, foto = dados_produto()
    return jsonify(estoque.salvar_produto(dados, _foto=foto)), 201


@bp.route("/gestao/api/produtos/<int:produto_id>", methods=["PUT"])
@protegido
def editar_produto(produto_id):
    dados, foto = dados_produto()
    return jsonify(estoque.salvar_produto(dados, produto_id, _foto=foto))


@bp.route("/gestao/api/produtos/<int:produto_id>/estoque", methods=["POST"])
@protegido
def movimentar(produto_id):
    dados = dados_json()
    estoque.ajustar_estoque(produto_id, dados.get("quantidade"), dados.get("motivo", ""))
    return jsonify(ok=True)


@bp.route("/gestao/api/movimentos")
@protegido
def movimentos():
    return jsonify(estoque.listar_movimentos())


@bp.route("/gestao/api/pedidos")
@protegido
def listar_pedidos():
    with get_conn() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM pedidos ORDER BY id DESC LIMIT 200")]
    resultado=[pedidos.obter_pedido(i) for i in ids]
    if not operadores.admin():
        for p in resultado:
            for item in p['itens']:
                item.pop('custo_unitario',None)
    return jsonify(resultado)


@bp.route("/gestao/api/pedidos/<int:pedido_id>/avancar", methods=["POST"])
@protegido
def avancar(pedido_id):
    return jsonify(fila.avancar_status(pedido_id))


@bp.route("/gestao/api/pedidos/<int:pedido_id>/cancelar", methods=["POST"])
@protegido
def cancelar(pedido_id):
    pedido = pedidos.cancelar_pedido(pedido_id)
    if pedido['origem'] == 'Balcão manual':
        return jsonify(pedido)
    try:
        mensagem = recibo.montar_mensagem_status(pedido, "CANCELADO")
        whatsapp.enviar_mensagem(pedido["cliente_telefone"], mensagem)
        pedidos.registrar_mensagem(pedido["cliente_telefone"], "SAIDA", mensagem)
    except Exception:
        current_app.logger.exception("Cancelamento salvo; notificação falhou")
        pedido["aviso"] = "Cancelamento salvo. Não foi possível notificar o cliente pelo WhatsApp."
    return jsonify(pedido)


@bp.route("/gestao/api/configuracoes", methods=["GET", "PUT"])
@protegido
def configuracoes():
    if request.method == "GET":
        return jsonify(preferencias.obter())
    dados = dados_json()
    campos_conexao = {'WHATSAPP_PROVIDER', 'WAHA_URL', 'WAHA_API_KEY', 'WAHA_SESSION', 'WAHA_WEBHOOK_BASE_URL'}
    antes = {k: getattr(config, k) for k in campos_conexao}
    if campos_conexao.intersection(dados) and conexoes.status_jobs().get('whatsapp', {}).get('estado') == 'EXECUTANDO':
        raise ValueError('Aguarde a preparação do WhatsApp antes de alterar sua configuração.')
    resultado = preferencias.salvar(dados)
    if request.method == "PUT" and config.WHATSAPP_PROVIDER != "LOCAL":
        conexoes.whatsapp_local.encerrar()
    alterada = any(antes[k] != getattr(config, k) for k in campos_conexao)
    if alterada and config.WHATSAPP_PROVIDER in {'LOCAL', 'WAHA'} and _local() and current_app.config.get('DESKTOP_TOKEN'):
        funcao = conexoes.iniciar_whatsapp_local if config.WHATSAPP_PROVIDER == 'LOCAL' else conexoes.conectar_whatsapp
        resultado['preparacao_whatsapp'] = conexoes.iniciar_tarefa('whatsapp', funcao)
    return jsonify(resultado)


@bp.route('/gestao/api/pagina-publica', methods=['GET', 'PUT', 'POST'])
@protegido
def pagina_publica():
    if request.method != 'GET':
        gerente = publicacao._gerente
        if gerente is None:
            raise ValueError('Abra o aplicativo Windows para usar o túnel integrado.')
        dados = dados_json()
        if request.method == 'PUT':
            if gerente.ativo:
                raise ValueError('Pare a página pública antes de alterar o modo ou a configuração.')
            preferencias.salvar({k: v for k, v in dados.items() if k.startswith('TUNEL_')})
        elif dados.get('acao') == 'iniciar':
            gerente.iniciar()
        elif dados.get('acao') == 'parar':
            gerente.encerrar()
        else:
            raise ValueError('Ação inválida para a página pública.')
    return jsonify(**publicacao.situacao(), automatico=config.TUNEL_AUTOMATICO == 'SIM',
                   dominio=config.TUNEL_URL, modo_configurado=config.TUNEL_MODO,
                   porta_configurada=config.TUNEL_PORTA,
                   token_configurado=bool(config.TUNEL_TOKEN))


@bp.route("/gestao/api/simular", methods=["POST"])
@protegido
def simular():
    dados = dados_json()
    telefone = whatsapp._numero_limpo(estoque.texto(dados.get("telefone", ""), "Telefone", 40, True))
    if not 10 <= len(telefone) <= 15:
        raise ValueError("Informe o telefone com DDI e DDD, por exemplo 5547999990000.")
    mensagem = estoque.texto(dados.get("texto", ""), "Mensagem", 2000, True)
    resposta = bot._processar_mensagem_menu_fixo(telefone, mensagem)
    return jsonify(resposta=resposta, caminho="/m/" + resposta.rsplit("/", 1)[-1] if mensagem == "2" else None)


def criar_backup(senha):
    return backups.criar(senha)


@bp.post('/gestao/api/produtos/importar')
@protegido
def importar_catalogo():
    from .catalogo_avancado import importar
    return jsonify(importar(dados_json()))


def _dono_documento():
    import hashlib
    return hashlib.sha256((session.get('csrf','') + ':' + str(session.get('operador_id',''))).encode()).hexdigest()


@bp.post('/gestao/api/documentos/ler')
@protegido
def ler_documento():
    from .documentos_estoque import ler
    arquivos = request.files.getlist('arquivo')
    if len(arquivos) != 1 or set(request.files) != {'arquivo'}:
        raise ValueError('Escolha um único documento de produtos ou estoque.')
    return jsonify(ler(arquivos[0], _dono_documento(), request.form.get('modelo','').strip(), request.form.get('tipo','lista')))


@bp.post('/gestao/api/documentos/lancar')
@protegido
def lancar_documento():
    from .documentos_estoque import aplicar
    return jsonify(aplicar(dados_json(), _dono_documento()))


@bp.post('/gestao/api/documentos/nota')
@protegido
def salvar_nota_documento():
    from .documentos_estoque import salvar_nota
    return jsonify(salvar_nota(dados_json().get('token'), _dono_documento()))


@bp.get('/gestao/api/catalogo.pdf')
@protegido
def catalogo_pdf():
    from io import BytesIO
    from .catalogo_pdf import gerar
    return send_file(BytesIO(gerar(request.args.get('quantidades') == 'sim')),mimetype='application/pdf',
        as_attachment=True,download_name='Catalogo-DeliveryBot.pdf')


@bp.get('/gestao/api/relatorios')
@protegido
def relatorios_api():
    from .catalogo_avancado import relatorio
    return jsonify(relatorio(request.args.get('inicio'),request.args.get('fim')))


@bp.get('/gestao/api/diagnostico')
@protegido
def diagnostico_api():
    if not operadores.admin():
        return jsonify(erro='Somente um administrador pode gerar o diagnóstico.'), 403
    from .diagnosticos import coletar
    return jsonify(coletar())


@bp.route('/gestao/api/humano',methods=['GET','POST'])
@protegido
def humano_api():
    from . import humano
    if request.method=='GET':
        if request.args.get('telefone'):
            return jsonify(humano.conversa(request.args['telefone']))
        return jsonify(humano.listar())
    d=dados_json()
    if d.get('acao')=='responder':
        return jsonify(humano.responder(d))
    humano.controlar(d.get('telefone',''),d.get('acao'))
    return jsonify(ok=True)


@bp.post('/gestao/api/protecao-ia/liberar')
@protegido
def liberar_protecao_ia():
    from . import protecao_ia
    u=operadores.usuario()
    if not u or u['perfil']!='ADMIN':
        return jsonify(erro='Entre com a conta administradora para revisar o bloqueio.'),403
    d=dados_json()
    if d.get('confirmar_revisao') is not True:
        raise ValueError('Confirme a revisão da conversa antes de liberar.')
    protecao_ia.liberar(d.get('telefone',''))
    return jsonify(ok=True)


@bp.route('/gestao/api/rotinas', methods=['GET','PUT','POST'])
@protegido
def rotinas_api():
    from . import rotinas
    if request.method=='PUT':
        return jsonify(rotinas.configurar(dados_json()))
    if request.method=='POST':
        return jsonify(conexoes.iniciar_tarefa('rotinas', lambda progresso: progresso('Rotinas verificadas.' if rotinas.executar(True) else 'Confira o aviso das rotinas.'))),202
    return jsonify(rotinas.situacao())


@bp.route("/gestao/api/backup", methods=["POST"])
@protegido
def backup():
    return jsonify(caminho=criar_backup(dados_json().get("senha")))


@bp.route("/gestao/api/privacidade")
@protegido
def privacidade_status():
    return jsonify(privacidade.situacao())


@bp.route("/gestao/api/privacidade/<acao>", methods=["POST"])
@protegido
def privacidade_acao(acao):
    acoes = {"exportar": privacidade.exportar, "corrigir": privacidade.corrigir, "remover": privacidade.remover_identificacao}
    dados = dados_json()
    if acao == "limpar":
        if dados.get("confirmar_limpeza") is not True:
            raise ValueError("Confirme a limpeza do histórico fora do prazo.")
        return jsonify(privacidade.limpar_historico())
    if acao not in acoes:
        raise ValueError("Operação de privacidade inválida.")
    return jsonify(acoes[acao](dados))


@bp.route("/gestao/api/conexoes")
@protegido
def status_conexoes():
    try:
        cofre = cerebro.situacao()
    except (OSError, ValueError):
        cofre = {'pasta':'', 'notas_contexto':0, 'erro':'O cofre precisa de revisão. Veja a verificação do atendimento.'}
    with ThreadPoolExecutor(max_workers=2) as executor:
        wa = executor.submit(conexoes.status_whatsapp)
        ol = executor.submit(conexoes.status_ollama)
        return jsonify(whatsapp=wa.result(), ollama=ol.result(), tarefas=conexoes.status_jobs(),
                       fila=processamento.situacao(), provedor=config.WHATSAPP_PROVIDER,
                       cerebro=cofre, recuperacao=recuperacao.situacao(),
                       pode_iniciar_local=bool(_local() and current_app.config.get("DESKTOP_TOKEN")),
                       whatsapp_local=config.WHATSAPP_PROVIDER in {"TESTE", "LOCAL"},
                       endereco_publico=publicacao.endereco(),
                       pagina_publica=publicacao.situacao(),
                       links_publicos=bool(publicacao.endereco()) and not conexoes.url_local(publicacao.endereco()))


@bp.route("/gestao/api/conexoes/qr")
@protegido
def qr_conexao():
    if conexoes.status_jobs().get('whatsapp', {}).get('estado') == 'EXECUTANDO' or (publicacao._gerente and publicacao.situacao()['estado'] != 'ONLINE'):
        raise ValueError('Aguarde a validação do endereço HTTPS antes de escanear o QR Code. Clique em Conectar WhatsApp para preparar tudo automaticamente.')
    return jsonify(conexoes.qr_whatsapp())


@bp.route('/gestao/api/cerebro/visualizar')
@protegido
def visualizar_cerebro():
    return jsonify(cerebro.visualizacao())


@bp.route('/gestao/api/cerebro/recuperacao', methods=['PUT'])
@protegido
def configurar_recuperacao():
    if not (_local() and current_app.config.get('DESKTOP_TOKEN') and recuperacao.situacao()['disponivel']):
        return jsonify(erro='Abra o aplicativo Desktop para configurar a recuperação.'), 403
    dados = dados_json()
    if type(dados.get('automatico')) is not bool:
        raise ValueError('Escolha se a recuperação automática deve ficar ativada.')
    preferencias.salvar({'CEREBRO_RECUPERACAO_AUTOMATICA':'SIM' if dados['automatico'] else 'NAO'})
    return jsonify(recuperacao.situacao())


@bp.route("/gestao/api/conexoes/<acao>", methods=["POST"])
@protegido
def controlar_conexao(acao):
    acoes = {"whatsapp-iniciar": ("whatsapp", conexoes.iniciar_whatsapp_local),
             "whatsapp-conectar": ("whatsapp", conexoes.conectar_whatsapp),
             "ollama-iniciar": ("ollama", conexoes.iniciar_ollama),
             "cerebro-recuperar": ("recuperacao", recuperacao.verificar_recuperar),
             "ollama-baixar": ("ollama", conexoes.baixar_modelo)}
    if acao in {"whatsapp-iniciar", "ollama-iniciar", "cerebro-recuperar"} and not (_local() and current_app.config.get("DESKTOP_TOKEN")):
        return jsonify(erro="Abra o aplicativo Desktop neste computador para iniciar um serviço local."), 403
    if acao == "whatsapp-pausar":
        if conexoes.status_jobs().get("whatsapp", {}).get("estado") == "EXECUTANDO":
            raise ValueError("Aguarde a preparação da conexão antes de pausar.")
        conexoes.pausar_whatsapp()
        return jsonify(ok=True)
    if acao not in acoes:
        raise ValueError("Ação de conexão inválida.")
    nome, funcao = acoes[acao]
    return jsonify(conexoes.iniciar_tarefa(nome, funcao)), 202


@bp.route("/gestao/api/conexoes/mensagens/<int:tarefa_id>/<acao>", methods=["POST"])
@protegido
def resolver_mensagem(tarefa_id, acao):
    if acao == "reenviar":
        processamento.reenviar(tarefa_id)
    elif acao == "ignorar":
        processamento.ignorar(tarefa_id)
    else:
        raise ValueError("Ação inválida.")
    return jsonify(ok=True)
