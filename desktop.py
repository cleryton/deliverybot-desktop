"""Entrada do aplicativo Windows. Execute diretamente ou empacote com PyInstaller."""
import argparse
from contextlib import closing
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import tempfile
import threading


def validar_backup(caminho):
    with closing(sqlite3.connect(Path(caminho).resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        conn.execute("PRAGMA trusted_schema=OFF")
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('trigger','view')").fetchone():
            raise ValueError("O arquivo possui estruturas que não fazem parte do backup do DeliveryBot.")
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("O arquivo de backup está corrompido.")
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"produtos", "pedidos", "clientes", "itens_pedido", "fila_preparo", "links_pedido"} <= tabelas:
            raise ValueError("Escolha um banco de dados do DeliveryBot (.db).")
        for tabela, colunas in {"produtos": {"id", "nome", "preco", "ativo", "categoria"},
                               "pedidos": {"id", "cliente_id", "numero_pedido", "status"}}.items():
            existentes = {r[1] for r in conn.execute(f"PRAGMA table_info({tabela})")}
            if not colunas <= existentes:
                raise ValueError("O backup não tem o formato esperado.")


def preparar_dados(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    banco = pasta / "deliverybot.db"
    # Configurar antes de importar módulos do aplicativo.
    os.environ["DATABASE_PATH"] = str(banco)
    os.environ["SEED_CATALOGO"] = "false"
    os.environ["DELIVERYBOT_ENV_FILE"] = str(pasta / ".env")
    for chave, valor in {"NOME_RESTAURANTE": "Minha loja", "TELEFONE_RESTAURANTE": "",
                         "ENDERECO_RESTAURANTE": "", "HORARIO_FUNCIONAMENTO": "Informe o horário da loja",
                         "FLASK_DEBUG": "false"}.items():
        os.environ.setdefault(chave, valor)
    from src import seguranca
    seguranca.proteger_pasta(pasta)
    pendente = pasta / "restaurar.db"
    if pendente.exists():
        validar_backup(pendente)
        if banco.exists():
            from datetime import datetime
            copias = pasta / "backups"
            copias.mkdir(exist_ok=True)
            from src.backups import criar_local
            criar_local(banco, copias / ("antes-restauracao-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".dbot-local"))
        # Conexões estão fechadas: os sidecars antigos não podem acompanhar o banco novo.
        for sufixo in ("-wal", "-shm"):
            banco.with_name(banco.name + sufixo).unlink(missing_ok=True)
        os.replace(pendente, banco)
    from logging.handlers import RotatingFileHandler
    logging.basicConfig(handlers=[RotatingFileHandler(pasta / "deliverybot.log", maxBytes=1024*1024, backupCount=3, encoding="utf-8")], level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    seguranca.configurar_logs()
    return banco


def smoke_test(destino, janela=False):
    """Verifica o executável sem tocar no estoque do usuário."""
    with tempfile.TemporaryDirectory(prefix="deliverybot-check-") as temporario:
        pasta = Path(temporario)
        preparar_dados(pasta)
        from src.app import app
        from src import estoque, config
        from src import perfil_comercio
        (pasta / 'perfil-instalacao.json').write_text(json.dumps({'nome':'Loja teste', 'segmento':'Comércio misto', 'descricao':'Produtos e serviços para testes fictícios.', 'modelo':'MISTO', 'controlar_estoque':True}), encoding='utf-8')
        assert perfil_comercio.importar_instalacao(pasta)
        assert perfil_comercio.obter()['configurado'] and not (pasta / 'perfil-instalacao.json').exists()
        from src.preferencias import salvar
        from waitress import create_server
        import webview
        token = secrets.token_urlsafe(32)
        app.config["DESKTOP_TOKEN"] = token
        salvar({"WEBHOOK_SECRET": secrets.token_urlsafe(32)})
        client = app.test_client()
        assert client.get("/gestao/api/produtos").status_code == 401
        assert client.get("/gestao?acesso=" + token, follow_redirects=True).status_code == 200
        assert client.get('/static/tutorial.js').status_code == 200
        assert len(client.get('/gestao/api/preparacao').json['tutorial']) == 8
        produto = estoque.salvar_produto({"nome": "Camiseta teste", "categoria": "Vestuário", "preco": "49.90", "estoque": 5})
        from io import BytesIO
        from PIL import Image
        from src import fotos
        foto_teste = BytesIO()
        Image.new('RGB', (24, 24), 'blue').save(foto_teste, format='PNG')
        foto_teste.seek(0)
        produto = estoque.salvar_produto({**produto, 'controlar_estoque': True, 'ativo': True}, produto['id'], _foto=fotos.normalizar(foto_teste))
        assert client.get("/gestao/api/produtos").json[0]["id"] == produto["id"]
        # Confere também os recursos públicos incluídos no executável, sem publicar
        # um túnel ou conectar contas reais durante a verificação da distribuição.
        from src.links import gerar_link_pedido
        from src.publicacao import PaginaPublica
        from werkzeug.test import Client
        from werkzeug.wrappers import Response
        caminho_pedido = '/m/' + gerar_link_pedido('5511999990000').rsplit('/', 1)[-1]
        publico = Client(PaginaPublica(app, lambda: 'https://loja-ficticia.example'), Response)
        assert publico.get(caminho_pedido).status_code == 200
        assert publico.get('/static/pedido.css').status_code == 200
        assert publico.get('/static/pedido.js').status_code == 200
        assert publico.get('/static/gestao.js').status_code == 404
        assert publico.get('/static/tutorial.js').status_code == 404
        assert publico.get(produto['foto_url']).mimetype == 'image/jpeg'
        assert produto['foto_url'].encode() in publico.get(caminho_pedido).data
        pdf_cliente = publico.get(caminho_pedido + '/catalogo.pdf')
        assert pdf_cliente.status_code == 200 and pdf_cliente.data.startswith(b'%PDF-')
        from src.documentos_estoque import ler, aplicar
        from werkzeug.datastructures import FileStorage
        revisao = ler(FileStorage(stream=BytesIO(b'nome;categoria;preco;sku;unidade;estoque\nCaderno;Papelaria;15.90;QA-PDF;un;2'),filename='estoque.csv'),'smoke')
        assert aplicar({'token':revisao['token'],'produtos':revisao['produtos']},'smoke')['nota_salva']
        # Exercita também o leitor nativo de PDF incluído na distribuição.
        from src.documentos_estoque import _ler_pdf
        assert 'Camiseta' in _ler_pdf(pdf_cliente.data)[0]
        resultado = {"ok": True, "janela": False, "catalogo": True, "recursos": True, "pagina_cliente": True, "fotos": True, "documentos_pdf": True, "perfil_comercio": True}
        if janela:
            # Serviços simulados: o teste da janela não conecta contas nem baixa modelos.
            from src import conexoes, whatsapp_local
            salvar({"WHATSAPP_PROVIDER": "LOCAL", "IA_PROVIDER": "", "OLLAMA_MODEL": "modelo-teste"})
            conexoes._tags = lambda url: ["modelo-teste:latest"]
            def ollama_simulado(progresso):
                salvar({"IA_PROVIDER": "OLLAMA"})
                progresso("Ollama pronto (serviço simulado).")
            conexoes.iniciar_ollama = ollama_simulado
            servidor = create_server(app, host="127.0.0.1", port=0)
            from src import publicacao
            # Interface do túnel simulada; a verificação nativa nunca publica dados.
            pagina_teste = publicacao.Publicacao(app)
            publicacao._gerente = pagina_teste
            def iniciar_pagina_simulada():
                pagina_teste.ativo = True
                pagina_teste._status('ONLINE', 'Conector simulado.', 'https://loja-ficticia.trycloudflare.com')
                return pagina_teste.situacao()
            pagina_teste.iniciar = iniciar_pagina_simulada
            thread = threading.Thread(target=servidor.run, daemon=True)
            thread.start()
            os.environ["DELIVERYBOT_PORT"] = str(servidor.effective_port)
            whatsapp_local.iniciar(teste=True)
            class APITeste:
                def verificar(self):
                    from src.operadores import validar_sessao_nativa
                    validar_sessao_nativa(app,window)
                    return {"ok": True}
            window = webview.create_window("DeliveryBot · Verificação", f"http://127.0.0.1:{servidor.effective_port}/gestao?acesso={token}", hidden=True, js_api=APITeste())
            def verificar():
                try:
                    if not window.events.loaded.wait(30):
                        raise RuntimeError("A janela não carregou em 30 segundos.")
                    # Espera o carregamento inicial das chamadas fetch da interface.
                    import time
                    for _ in range(100):
                        if window.evaluate_js("document.querySelector('#loja-nome')?.textContent === 'Minha loja' && document.querySelectorAll('#product-list tr').length === 1"):
                            resultado["janela"] = True
                            break
                        time.sleep(.1)
                    if not resultado["janela"]:
                        raise RuntimeError("A interface não carregou os produtos.")
                    resultado["titulo"] = window.evaluate_js("document.title")
                    def esperar(expressao):
                        for _ in range(150):
                            if window.evaluate_js(expressao):
                                return
                            time.sleep(.1)
                        raise RuntimeError("Verificação da interface falhou: " + expressao)
                    window.evaluate_js("const s=document.querySelector('[data-theme-picker]');s.value='escuro';s.dispatchEvent(new Event('change'))")
                    esperar("document.documentElement.dataset.theme === 'dark' && !document.querySelector('[data-theme-picker]').disabled")
                    cores = window.evaluate_js("({fundo:getComputedStyle(document.body).backgroundColor,card:getComputedStyle(document.querySelector('.card')).backgroundColor,tema:document.documentElement.dataset.theme})")
                    assert cores == {'fundo':'rgb(17, 27, 23)','card':'rgb(27, 42, 35)','tema':'dark'}, f'Cores do tema escuro: {cores}'
                    window.evaluate_js("location.reload()")
                    esperar("document.readyState === 'complete' && document.documentElement.dataset.themeChoice === 'escuro' && document.documentElement.dataset.theme === 'dark' && document.querySelector('#loja-nome')?.textContent === 'Minha loja' && document.querySelectorAll('#product-list tr').length === 1")
                    window.evaluate_js("document.querySelector('[data-action=novo]').click(); const f=document.querySelector('#product-form'); f.elements.nome.value='Caderno UI'; f.elements.categoria.value='Papelaria'; f.elements.preco.value='12.50'; f.elements.estoque.value='4'; f.querySelector('button[type=submit]').click();")
                    esperar("!document.querySelector('#product-dialog').open && document.querySelectorAll('#product-list tr').length === 2")
                    window.evaluate_js("document.querySelector('[data-page=produtos]').click()")
                    esperar("!document.querySelector('#page-produtos').hidden")
                    window.evaluate_js("document.querySelector('[data-stock=\"2\"]').click(); const f=document.querySelector('#stock-form'); f.elements.quantidade.value='3'; f.elements.motivo.value='Teste de reposição'; f.querySelector('.primary').click();")
                    esperar("!document.querySelector('#stock-dialog').open && document.querySelector('#product-list').textContent.includes('7 un')")
                    window.evaluate_js("document.querySelector('[data-page=configuracoes]').click()")
                    esperar("document.querySelector('[name=NOME_RESTAURANTE]') !== null")
                    window.evaluate_js("document.querySelector('[name=NOME_RESTAURANTE]').value='Loja UI'; document.querySelector('#settings-form .primary').click();")
                    esperar("document.querySelector('#loja-nome').textContent === 'Loja UI'")
                    window.evaluate_js("document.querySelector('[data-page=bot]').click(); const f=document.querySelector('#bot-form'); f.elements.texto.value='4'; f.querySelector('.primary').click();")
                    esperar("document.querySelector('#chat').textContent.includes('Caderno UI')")
                    resultado["formularios"] = ["cadastro", "reposicao", "configuracoes", "catalogo_bot"]
                    window.evaluate_js("document.querySelector('[data-page=privacidade]').click()")
                    esperar("!document.querySelector('#page-privacidade').hidden && document.querySelector('[name=LGPD_MENSAGENS_DIAS]').value === '30'")
                    window.evaluate_js("const f=document.querySelector('#privacy-settings');f.elements.LGPD_RESPONSAVEL.value='Loja UI';f.elements.LGPD_CONTATO.value='privacidade@example.com';f.querySelector('button[type=submit]').click();")
                    esperar("document.querySelector('#privacy-note').textContent.includes('Responsável e contato configurados')")
                    window.evaluate_js("document.querySelector('[data-page=inicio]').click();document.querySelector('[data-action=backup]').click();const f=document.querySelector('#backup-form');f.elements.senha.value='senha-ficticia-para-backup';f.elements.confirmacao.value='senha-ficticia-para-backup';f.querySelector('button[type=submit]').click();")
                    esperar("!document.querySelector('#backup-dialog').open && document.querySelector('#backup-result').textContent.includes('.dbot')")
                    window.evaluate_js("window.pywebview.api.verificar().then(r=>document.body.dataset.apiNative=r.ok?'ok':'erro')")
                    esperar("document.body.dataset.apiNative === 'ok'")
                    resultado["privacidade"] = ["configuracao_responsavel", "backup_criptografado", "api_nativa_com_csp"]
                    window.evaluate_js("document.querySelector('[data-page=conexoes]').click()")
                    esperar("document.querySelector('#wa-badge').textContent === 'Disponível'")
                    window.evaluate_js("document.querySelector('#wa-connect').click()")
                    esperar("!document.querySelector('#wa-qr-area').hidden && document.querySelector('#wa-qr').naturalWidth > 0")
                    conexoes._waha("POST", "/test/connect")
                    window.evaluate_js("document.querySelector('[data-action=conexoes-atualizar]').click()")
                    esperar("document.querySelector('#wa-badge').textContent === 'Conectado'")
                    window.evaluate_js("document.querySelector('#ol-start').click()")
                    esperar("document.querySelector('#ol-badge').textContent === 'Ativo no bot'")
                    assert config.IA_PROVIDER == "OLLAMA"
                    assert config.WHATSAPP_PROVIDER == "LOCAL"
                    resultado["conexoes_simuladas"] = ["componente_integrado_sem_docker", "configurar_webhook", "exibir_qr", "iniciar_e_ativar_ollama"]
                    window.evaluate_js("document.querySelector('[data-page=publicacao]').click()")
                    esperar("!document.querySelector('#page-publicacao').hidden && !document.querySelector('#public-start').disabled")
                    window.evaluate_js("document.querySelector('#public-auto').checked=true;document.querySelector('#public-start').click()")
                    esperar("document.querySelector('#public-state').textContent==='Conector ligado' && document.querySelector('#public-url').value.includes('loja-ficticia.trycloudflare.com')")
                    assert config.TUNEL_AUTOMATICO == 'SIM', 'A preferência de início automático não foi salva.'
                    window.evaluate_js("document.querySelector('#public-test').click()")
                    esperar("document.querySelector('#public-test-link').value.includes('/diagnostico/')")
                    pagina_teste.encerrar()
                    resultado['pagina_publica'] = ['iniciar_pelo_painel', 'inicio_automatico_salvo', 'endereco_atual', 'teste_no_celular']
                    window.evaluate_js("document.querySelector('[data-page=atualizacoes]').click()")
                    esperar("!document.querySelector('#page-atualizacoes').hidden && document.querySelector('#update-current').textContent !== '' && document.querySelector('#update-install').disabled")
                    window.evaluate_js("document.querySelector('[data-page=operadores]').click();const f=document.querySelector('#operator-form');f.elements.nome.value='Administrador UI';f.elements.login.value='admin.ui';f.elements.senha.value='senha-ficticia-ui-123';f.querySelector('button').click();")
                    esperar("document.querySelector('#operator-list').textContent.includes('Administrador UI')")
                    window.evaluate_js("const f=document.querySelector('#operator-form');f.elements.nome.value='Atendente UI';f.elements.login.value='vendas.ui';f.elements.senha.value='senha-ficticia-ui-123';f.elements.perfil.value='ATENDENTE';f.querySelector('button').click();")
                    esperar("document.querySelector('#operator-list').textContent.includes('Atendente UI')")
                    window.evaluate_js("document.querySelector('#operator-logout').click()")
                    esperar("document.querySelector('form[action=\"/gestao/login\"]') !== null")
                    esperar("document.documentElement.dataset.theme === 'dark' && getComputedStyle(document.querySelector('.login-card')).backgroundColor === 'rgb(27, 42, 35)'")
                    window.evaluate_js("const f=document.querySelector('form');f.elements.login.value='vendas.ui';f.elements.senha.value='senha-ficticia-ui-123';f.querySelector('button[type=submit]').click();")
                    esperar("document.body.dataset.admin === 'false' && document.querySelector('#product-list')?.textContent.includes('Caderno UI')")
                    assert window.evaluate_js("getComputedStyle(document.querySelector('[data-page=configuracoes]')).display === 'none'")
                    window.evaluate_js("window.pywebview.api.verificar().then(()=>document.body.dataset.permissao='permitido',()=>document.body.dataset.permissao='negado')")
                    esperar("document.body.dataset.permissao === 'negado'")
                    window.evaluate_js("fetch('/gestao/api/configuracoes').then(r=>document.body.dataset.httpPermissao=String(r.status))")
                    esperar("document.body.dataset.httpPermissao === '403'")
                    window.evaluate_js("const s=document.querySelector('[data-theme-picker]');s.value='claro';s.dispatchEvent(new Event('change'))")
                    esperar("document.documentElement.dataset.theme === 'light' && !document.querySelector('[data-theme-picker]').disabled")
                    assert window.evaluate_js("getComputedStyle(document.body).backgroundColor === 'rgb(246, 248, 247)'")
                    window.evaluate_js("const s=document.querySelector('[data-theme-picker]');s.value='sistema';s.dispatchEvent(new Event('change'))")
                    esperar("document.documentElement.dataset.themeChoice === 'sistema' && !document.querySelector('[data-theme-picker]').disabled")
                    assert window.evaluate_js("document.documentElement.dataset.theme === (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')")
                    resultado['aparencia']=['escuro','claro','seguir_windows','preferencia_apos_reabrir_pagina','login_escuro','atendente_pode_alterar']
                    resultado['funcionarios']=['cadastro_admin','cadastro_atendente','troca_de_conta','permissoes_http','permissoes_nativas']
                    resultado['atualizacoes']=['versao_embutida','instalacao_sem_assinatura_bloqueada']
                except Exception as exc:
                    resultado.update(ok=False, erro=str(exc) or type(exc).__name__)
                    try:
                        resultado['diagnostico_janela'] = window.evaluate_js("({url:location.pathname,carregamento:document.readyState,tema:document.documentElement.dataset.theme,escolha:document.documentElement.dataset.themeChoice,fundo:document.body?getComputedStyle(document.body).backgroundColor:null})")
                    except Exception:
                        pass
                finally:
                    window.destroy()
            try:
                webview.start(verificar, gui="edgechromium", private_mode=True)
            finally:
                servidor.close()
                thread.join(timeout=5)
                whatsapp_local.encerrar()
                pagina_teste.encerrar()
                publicacao._gerente = None
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
        logging.shutdown()
        return 0 if resultado["ok"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", metavar="ARQUIVO")
    parser.add_argument("--window-smoke-test", action="store_true")
    args = parser.parse_args()
    if args.smoke_test:
        return smoke_test(args.smoke_test, args.window_smoke_test)
    pasta = Path(os.getenv("DELIVERYBOT_DATA_DIR") or Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "DeliveryBot")
    pasta.mkdir(parents=True, exist_ok=True)
    trava = open(pasta / "aplicativo.lock", "a+b")
    servidor = None
    thread = None
    bandeja = None
    try:
        if sys.platform == "win32":
            import msvcrt
            trava.seek(0)
            if not trava.read(1):
                trava.write(b"0")
                trava.flush()
            trava.seek(0)
            try:
                msvcrt.locking(trava.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError("O DeliveryBot já está aberto. Procure a janela na barra de tarefas.") from None
        preparar_dados(pasta)
        from src.app import app
        from src import config
        from src.preferencias import salvar
        from src.gestao import criar_backup
        from src import perfil_comercio
        try:
            perfil_comercio.importar_instalacao(pasta)
        except (ValueError, OSError):
            logging.getLogger(__name__).warning('Perfil inicial não aplicado. Configure Meu comércio no painel.')
        from src import processamento
        from src import conexoes, whatsapp_local
        from waitress import create_server
        import webview
        if not config.WEBHOOK_SECRET:
            salvar({"WEBHOOK_SECRET": secrets.token_urlsafe(32)})
        # A conexão antiga por Docker local passa para o componente incluído no app.
        if config.WHATSAPP_PROVIDER == "WAHA" and conexoes.url_local(config.WAHA_URL):
            salvar({"WHATSAPP_PROVIDER": "LOCAL"})
        token = secrets.token_urlsafe(32)
        app.config["DESKTOP_TOKEN"] = token
        port = int(os.getenv("DELIVERYBOT_PORT", "5000"))
        servidor = create_server(app, host="127.0.0.1", port=port, threads=8)
        thread = threading.Thread(target=servidor.run, name="DeliveryBot-HTTP", daemon=True)
        thread.start()
        from src import publicacao
        publicacao.preparar(app)
        processamento.iniciar()
        from src import rotinas
        rotinas.iniciar()
        if config.WHATSAPP_PROVIDER in {"LOCAL", "WAHA"}:
            preparar_whatsapp = (conexoes.iniciar_whatsapp_local
                                 if config.WHATSAPP_PROVIDER == "LOCAL"
                                 else conexoes.conectar_whatsapp)
            conexoes.iniciar_tarefa("whatsapp", preparar_whatsapp)
        if config.IA_PROVIDER == "OLLAMA" and conexoes.url_local(config.OLLAMA_URL):
            conexoes.iniciar_tarefa("ollama", conexoes.iniciar_ollama)
        class API:
            def instalar_atualizacao(self):
                self._verificar()
                from src import atualizacoes
                atualizacoes.instalar()
                bandeja.sair()
            def sair_aplicativo(self):
                self._verificar(administrador=False)
                bandeja.sair()
            def _verificar(self, administrador=True):
                from urllib.parse import urlsplit
                url = urlsplit(window.get_current_url())
                if url.netloc != f"127.0.0.1:{port}" or url.path != "/gestao":
                    raise ValueError("Reabra o painel administrativo para realizar esta operação.")
                from src.operadores import validar_sessao_nativa
                validar_sessao_nativa(app,window,administrador)
            def abrir_pasta(self):
                self._verificar()
                os.startfile(str(pasta))
            def abrir_cerebro(self):
                self._verificar()
                from src import cerebro
                from urllib.parse import quote
                nota = cerebro.arquivo_inicio()
                uri = "obsidian://open?path=" + quote(str(nota), safe="")
                try:
                    os.startfile(uri)
                    return {"ok": True, "aplicativo": "obsidian"}
                except OSError:
                    os.startfile(str(nota.parent))
                    return {"ok": True, "aplicativo": "explorador"}
            def salvar_exportacao(self, relatorio):
                self._verificar()
                arquivos = window.create_file_dialog(webview.FileDialog.SAVE, save_filename="dados-do-titular.json", file_types=("Relatório JSON (*.json)",))
                if not arquivos:
                    return {"cancelado": True}
                arquivo = arquivos[0] if isinstance(arquivos, (tuple, list)) else arquivos
                with open(arquivo, "w", encoding="utf-8") as saida:
                    json.dump(relatorio, saida, ensure_ascii=False, indent=2)
                return {"ok": True}
            def salvar_diagnostico(self):
                self._verificar()
                from src.diagnosticos import coletar
                relatorio = coletar()
                arquivos = window.create_file_dialog(webview.FileDialog.SAVE, save_filename="diagnostico-deliverybot.json", file_types=("Relatório JSON (*.json)",))
                if not arquivos:
                    return {"cancelado": True}
                arquivo = arquivos[0] if isinstance(arquivos, (tuple, list)) else arquivos
                with open(arquivo, "w", encoding="utf-8") as saida:
                    json.dump(relatorio, saida, ensure_ascii=False, indent=2)
                return {"ok": True}
            def restaurar_backup(self, senha):
                self._verificar()
                arquivos = window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False, file_types=("Backup DeliveryBot (*.dbot;*.dbot-local;*.db)",))
                if not arquivos:
                    return {"cancelado": True}
                try:
                    temporario = pasta / "restaurar.tmp"
                    from src import backups
                    arquivo = Path(arquivos[0])
                    if arquivo.suffix != ".db":
                        dados = backups.abrir_arquivo(arquivo, senha)
                        with closing(sqlite3.connect(":memory:")) as origem, closing(sqlite3.connect(temporario)) as copia:
                            origem.deserialize(dados)
                            origem.backup(copia)
                    else:
                        validar_backup(arquivo)
                        with closing(sqlite3.connect(arquivo.resolve().as_uri() + "?mode=ro", uri=True)) as origem, closing(sqlite3.connect(temporario)) as copia:
                            origem.backup(copia)
                    validar_backup(temporario)
                    criar_backup(senha)
                    # Notas antigas dos backups seguem válidas; somente os novos contêm o snapshot do cofre.
                    from src import backups, cerebro
                    with closing(sqlite3.connect(temporario)) as banco_restaurado:
                        snapshot = backups.snapshot_no_banco(banco_restaurado)
                        banco_restaurado.execute("DROP TABLE IF EXISTS deliverybot_cerebro_snapshot")
                        banco_restaurado.commit()
                    cofre_anterior = cerebro.snapshot() if snapshot is not None else None
                    if snapshot is not None:
                        cerebro.restaurar_snapshot(snapshot)
                    try:
                        # SQLite backup também funciona se o arquivo escolhido estiver em WAL.
                        os.replace(temporario, pasta / "restaurar.db")
                    except Exception:
                        if cofre_anterior is not None:
                            cerebro.restaurar_snapshot(cofre_anterior)
                        raise
                    bandeja.sair()
                    return {"ok": True}
                except Exception as exc:
                    temporario.unlink(missing_ok=True)
                    return {"erro": "Não foi possível restaurar. Confira a senha, o formato do backup e a conta Windows da cópia de recuperação."}
        window = webview.create_window("DeliveryBot — Gestão da loja", f"http://127.0.0.1:{port}/gestao?acesso={token}",
                                       js_api=API(), width=1280, height=850, min_size=(850,600), background_color="#f6f8f7")
        from src.bandeja import Bandeja
        bandeja = Bandeja(window)
        bandeja.iniciar()
        window.events.closing += bandeja.ao_fechar
        webview.start(gui="edgechromium", private_mode=True)
        return 0
    except Exception as exc:
        logging.exception("Falha ao abrir o aplicativo")
        mensagem = f"Não foi possível abrir o DeliveryBot.\n\n{exc}\n\nSe a porta 5000 estiver ocupada, feche o servidor antigo do DeliveryBot.\nVerifique também o Microsoft Edge WebView2 Runtime.\n\nLogs: {pasta / 'deliverybot.log'}"
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, mensagem, "DeliveryBot", 0x10)
        else:
            print(mensagem, file=sys.stderr)
        return 1
    finally:
        if bandeja:
            bandeja.parar()
        if servidor:
            from src import publicacao
            if publicacao._gerente:
                publicacao._gerente.encerrar()
            from src import rotinas
            rotinas.encerrar()
            servidor.close()
            from src import processamento
            processamento.encerrar()
            from src import whatsapp_local
            whatsapp_local.encerrar()
        if thread:
            thread.join(timeout=5)
        trava.close()


if __name__ == "__main__":
    raise SystemExit(main())
