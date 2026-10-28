"""Servidor exclusivo de QA: somente páginas do cliente e dados fictícios."""
from io import BytesIO
from pathlib import Path
import secrets
from urllib.parse import urlsplit

from flask import Flask, abort, jsonify, redirect, render_template, request, session
from PIL import Image, ImageDraw
from werkzeug.middleware.proxy_fix import ProxyFix

from . import config, seguranca
from .db import init_db, get_conn
from .politica_terminal import Limites

PUBLICOS={'pagina_pedido','enviar_pedido','comprovante_pedido','catalogo_cliente_pdf','pagina_minijogo','aviso_privacidade','foto_produto'}
ASSETS={'pedido.css','pedido.js','recibo.js','pong.css','pong-core.js','pong.js'}

ESTADOS_QA = {
    403: ('Sua sessão precisa ser renovada', 'Volte ao laboratório e abra novamente o pedido. Nenhum novo pedido foi confirmado nesta tentativa.'),
    404: ('Esta página não está disponível', 'Use o início do laboratório para acessar o catálogo de testes.'),
    405: ('Esta ação não está disponível', 'Abra a página pelo laboratório e use os botões do formulário.'),
    410: ('Este link já foi usado ou expirou', 'Se você já confirmou, não repita a compra. Para outro teste, comece um novo pedido no laboratório.'),
    413: ('Os dados enviados são muito grandes', 'O laboratório aceita somente o formulário de pedidos. Reduza os dados e tente novamente.'),
    429: ('Vamos fazer uma pequena pausa', 'Aguarde um minuto antes de tentar novamente. Se o limite continuar, peça ao responsável para reiniciar o laboratório.'),
    500: ('Não foi possível concluir esta etapa', 'Não reenvie o pedido sem conferir se houve confirmação. Anote o horário e informe o responsável pelo teste.'),
    503: ('O laboratório está temporariamente indisponível', 'Aguarde e tente abrir o início novamente. Se continuar, informe o responsável pelo teste.'),
}

def criar_app(pasta,base,chave_sessao):
    url=urlsplit(base)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.path not in {'','/'} or url.query or url.fragment:
        raise ValueError('Configure a origem HTTPS do ambiente QA.')
    if not isinstance(chave_sessao,str) or len(chave_sessao)<32:
        raise ValueError('Configure uma chave de sessão QA de pelo menos 32 caracteres.')
    pasta=Path(pasta)
    marcador=pasta/'.deliverybot-qa'
    if pasta.is_symlink() or (pasta.exists() and any(pasta.iterdir()) and not marcador.is_file()):
        raise ValueError('Escolha uma pasta vazia exclusiva para os dados fictícios de QA.')
    pasta.mkdir(parents=True,exist_ok=True)
    marcador.write_text('Somente dados ficticios de QA.',encoding='utf-8')
    config.DATABASE_PATH=str(pasta/'qa.db')
    config.WHATSAPP_PROVIDER='TESTE';config.MODO_TESTE=True
    config.IA_PROVIDER='';config.TUNEL_AUTOMATICO='NAO';config.SEED_CATALOGO=False
    config.FLASK_DEBUG=False;config.BASE_URL=base.rstrip('/')
    perfil_qa = {
        'COMERCIO_MODELO': 'PRODUCAO', 'COMERCIO_SEGMENTO': 'Lanchonete de testes',
        'COMERCIO_DESCRICAO': 'Lanchonete fictícia para testar lanches feitos sob encomenda, porções e bebidas. Nenhum item está à venda.',
        'COMERCIO_ESTOQUE_PADRAO': 'NAO', 'COMERCIO_CONFIGURADO': 'SIM',
        'NOME_RESTAURANTE': 'Lanchonete Demonstração',
        'TELEFONE_RESTAURANTE': '(00) 0000-0000',
        'ENDERECO_RESTAURANTE': 'Rua Fictícia, 123 — Bairro Demonstração (endereço de teste)',
        'CEP_RESTAURANTE': '00000-000', 'HORARIO_FUNCIONAMENTO': 'Horário fictício: das 18h às 23h',
        'FORMAS_PAGAMENTO': 'Dinheiro,Pix,Cartão de crédito,Cartão de débito',
        'TAXA_ENTREGA': 5.0, 'TEMPO_PREPARO_MIN': 20,
    }
    for campo, valor in perfil_qa.items():setattr(config, campo, valor)
    config.LGPD_RESPONSAVEL='Ambiente de testes DeliveryBot'
    config.LGPD_CONTATO='Use apenas dados fictícios. Dados descartáveis ao reiniciar a hospedagem.'
    for campo in ('WHATSAPP_TOKEN','WHATSAPP_APP_SECRET','WHATSAPP_PHONE_NUMBER_ID','WHATSAPP_BUSINESS_ACCOUNT_ID','WAHA_API_KEY','WEBHOOK_SECRET','ANTHROPIC_API_KEY','TUNEL_TOKEN'):
        setattr(config,campo,'')
    init_db(seed_cardapio=False)
    # Importar as funções existentes não inicia o desktop nem consumidores da fila.
    from .app import app as original, catalogo_do_comercio, dados_da_loja
    config.WHATSAPP_PROVIDER='TESTE';config.MODO_TESTE=True
    config.IA_PROVIDER='';config.TUNEL_AUTOMATICO='NAO'
    for campo, valor in perfil_qa.items():setattr(config, campo, valor)
    from . import estoque
    itens=[('X-salada','Lanche',22.00,False),('Hambúrguer vegetariano','Lanche',26.90,False),
           ('X-bacon','Lanche',25.00,False),('Cachorro-quente','Lanche',16.00,False),
           ('Batata frita','Acompanhamento',18.00,False),('Refrigerante lata','Bebida',6.00,True),
           ('Suco de caixinha','Bebida',7.00,True),('Brownie','Sobremesa',12.00,False)]
    with get_conn() as c:
        c.execute('BEGIN IMMEDIATE')
        for i,(nome,categoria,preco,controle) in enumerate(itens,1):
            sku='QA-DEMO-'+str(i)
            anterior=c.execute('SELECT id FROM produtos WHERE sku=?',(sku,)).fetchone()
            img=Image.new('RGB',(480,320),('#d9eee5','#fff0ce','#e6e9ff')[i%3])
            draw=ImageDraw.Draw(img);draw.rounded_rectangle((70,55,410,265),radius=36,fill='#ffffff')
            draw.text((160,120),'DEMO QA',fill='#14624e');draw.text((160,155),str(i),fill='#14624e')
            foto=BytesIO();img.save(foto,format='JPEG',quality=80)
            estoque.salvar_produto({'nome':'TESTE - '+nome,'categoria':categoria,'preco':preco,'sku':sku,
                'descricao':'Produto fictício para testar o catálogo e o pedido. Não está à venda.',
                'controlar_estoque':controle,'estoque':1000,'unidade':'un','ativo':True},
                produto_id=anterior['id'] if anterior else None,_foto=foto.getvalue(),_conn=c)
    app=Flask('deliverybot_qa',template_folder=str(Path(__file__).resolve().parents[1]/'web/templates'),
              static_folder=str(Path(__file__).resolve().parents[1]/'web/static'),static_url_path='/static')
    app.secret_key=chave_sessao
    app.config.update(MAX_CONTENT_LENGTH=1024*1024,TRUSTED_HOSTS=[url.hostname],SESSION_COOKIE_SECURE=True)
    app.wsgi_app=ProxyFix(app.wsgi_app,x_for=0,x_proto=1,x_host=0,x_port=0,x_prefix=0)
    seguranca.instalar(app)
    app.jinja_env.filters.update(original.jinja_env.filters)
    app.jinja_env.globals.update({k:v for k,v in original.jinja_env.globals.items() if k=='icone_categoria'})
    app.context_processor(lambda:{**catalogo_do_comercio(),**dados_da_loja(),'qa_mode':True})
    for regra in original.url_map.iter_rules():
        if regra.endpoint in PUBLICOS:
            app.add_url_rule(regra.rule,endpoint=regra.endpoint,view_func=original.view_functions[regra.endpoint],methods=regra.methods)
    limites=Limites()
    @app.before_request
    def isolar():
        if not config.MODO_TESTE or config.WHATSAPP_PROVIDER!='TESTE':abort(503)
        if request.endpoint=='static' and request.view_args.get('filename') not in ASSETS:abort(404)
        if request.endpoint in {'qa_novo','enviar_pedido'} and not limites.consumir('gravacoes',60,60):abort(429)
        if request.endpoint=='enviar_pedido':
            with get_conn() as c:
                if c.execute('SELECT COUNT(*) FROM pedidos').fetchone()[0]>=500:abort(429)
    @app.after_request
    def cabecalhos(r):
        r.headers['X-Robots-Tag']='noindex, nofollow'
        r.headers['Referrer-Policy']='same-origin'
        if r.status_code in ESTADOS_QA:
            titulo, orientacao = ESTADOS_QA[r.status_code]
            if r.status_code==410 and request.endpoint=='comprovante_pedido':
                titulo='Este comprovante não está disponível'
                orientacao='Não refaça o pedido para recuperar o comprovante. Ele exige a sessão do mesmo navegador. Para uma nova rodada fictícia, volte ao laboratório.'
            r.set_data(render_template('qa_estado.html', titulo=titulo, orientacao=orientacao, codigo=r.status_code))
            r.content_type='text/html; charset=utf-8'
            if r.status_code in {429,503}:r.headers.setdefault('Retry-After','60')
        return r
    @app.get('/')
    def qa_inicio():
        return render_template('qa_inicio.html')
    @app.get('/healthz')
    def qa_saude():return jsonify(ok=True,ambiente='QA',whatsapp='SIMULADO')
    @app.get('/robots.txt')
    def robots():return 'User-agent: *\nDisallow: /\n',200,{'Content-Type':'text/plain'}
    @app.post('/qa/novo')
    def qa_novo():
        if not seguranca.csrf_valido():abort(403)
        from .links import gerar_link_pedido,link_valido
        token=session.get('qa_link','')
        if token and link_valido(token)[0]:return redirect('/m/'+token)
        with get_conn() as c:
            if c.execute('SELECT COUNT(*) FROM links_pedido').fetchone()[0]>=1000:abort(429)
        # Identificador sintético: não é telefone de um participante.
        telefone='000'+''.join(secrets.choice('0123456789') for _ in range(12))
        token=gerar_link_pedido(telefone).rsplit('/',1)[-1]
        session['qa_link']=token
        return redirect('/m/'+token)
    @app.errorhandler(429)
    def excesso(_):return 'Limite temporário do laboratório QA. Aguarde e tente novamente. Os dados serão renovados ao reiniciar o serviço.',429,{'Retry-After':'60'}
    return app
