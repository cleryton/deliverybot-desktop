import concurrent.futures
from contextlib import closing
import sqlite3
import pytest

from src import config, estoque, pedidos, cardapio, preferencias
from src.db import init_db, get_conn


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "loja.db"))
    monkeypatch.setattr(config, "SEED_CATALOGO", False)
    for key in preferencias.CAMPOS | {"MODO_TESTE", "WHATSAPP_API_URL"}:
        monkeypatch.setattr(config, key, getattr(config, key))
    config.FORMAS_PAGAMENTO = "Pix,Dinheiro"
    config.WHATSAPP_PROVIDER = "TESTE"
    config.MODO_TESTE = True
    init_db()


def produto(**campos):
    return estoque.salvar_produto({"nome": "Camiseta", "categoria": "Vestuário", "preco": "49.90", "estoque": 5, **campos})


def comprar(p, quantidade=1, **kwargs):
    return pedidos.criar_pedido("5547999990000", "Ana", [{"produto_id": p["id"], "quantidade": quantidade}], "Pix", **kwargs)


def test_instalacao_nova_sem_lanches():
    assert estoque.listar_produtos() == []


def test_venda_baixa_estoque_e_esconde_esgotado():
    p = produto(estoque=2)
    pedido = comprar(p, 2)
    assert pedido["total_itens"] == 99.8
    assert estoque.listar_produtos()[0]["estoque"] == 0
    assert cardapio.listar_produtos_ativos() == []
    assert estoque.listar_movimentos()[0]["tipo"] == "VENDA"


def test_falha_de_um_item_desfaz_pedido_e_estoque():
    p = produto()
    with pytest.raises(ValueError):
        pedidos.criar_pedido("5547", "Teste", [{"produto_id": p["id"], "quantidade": 2}, {"produto_id": 999, "quantidade": 1}], "Pix")
    assert estoque.listar_produtos()[0]["estoque"] == 5
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) FROM pedidos").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 0


def test_itens_duplicados_sao_somados_antes_de_validar():
    p = produto(estoque=3)
    with pytest.raises(ValueError, match="insuficiente"):
        pedidos.criar_pedido("5547", "Ana", [{"produto_id": p["id"], "quantidade": 2}] * 2, "Pix")
    assert estoque.listar_produtos()[0]["estoque"] == 3


@pytest.mark.parametrize("qtd", [0, -1, 1.5, "abc", True, 1000000])
def test_quantidades_invalidas(qtd):
    with pytest.raises(ValueError):
        comprar(produto(), qtd)


def test_cancelamento_devolve_uma_vez_e_preserva_recibo():
    p = produto()
    pedido = comprar(p, 3)
    estoque.salvar_produto({**p, "nome": "Camiseta azul", "preco": 70, "ativo": True, "controlar_estoque": True}, p["id"])
    assert estoque.listar_produtos()[0]["estoque"] == 2
    historico = pedidos.obter_pedido(pedido["id"])
    assert historico["itens"][0]["produto_nome"] == "Camiseta"
    assert historico["itens"][0]["preco_unitario"] == 49.9
    pedidos.cancelar_pedido(pedido["id"])
    assert estoque.listar_produtos()[0]["estoque"] == 5
    with pytest.raises(ValueError):
        pedidos.cancelar_pedido(pedido["id"])
    assert estoque.listar_produtos()[0]["estoque"] == 5


def test_concorrencia_na_ultima_unidade():
    p = produto(estoque=1)
    def tentativa(_):
        try:
            return comprar(p)["id"]
        except ValueError:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(tentativa, [1, 2]))
    assert sum(r is not None for r in resultados) == 1
    assert estoque.listar_produtos()[0]["estoque"] == 0


def test_link_nao_pode_confirmar_duas_vezes():
    from src.links import gerar_link_pedido, link_valido
    p = produto()
    token = gerar_link_pedido("5547999990000").rsplit("/", 1)[-1]
    comprar(p, token=token)
    with pytest.raises(ValueError, match="link"):
        comprar(p, token=token)
    assert estoque.listar_produtos()[0]["estoque"] == 4
    assert not link_valido(token)[0]


def test_ajustes_codigo_unico_e_sem_controle():
    p = produto(sku="CAM-01")
    with pytest.raises(ValueError, match="código"):
        produto(sku="CAM-01")
    estoque.ajustar_estoque(p["id"], 3, "Fornecedor")
    estoque.ajustar_estoque(p["id"], -2, "Perda")
    with pytest.raises(ValueError):
        estoque.ajustar_estoque(p["id"], -7, "Perda")
    assert estoque.listar_produtos()[0]["estoque"] == 6
    livre = produto(nome="Serviço", controlar_estoque=False)
    comprar(livre, 20)
    assert next(p for p in estoque.listar_produtos() if p["id"] == livre["id"])["estoque"] is None


def test_preferencias_secretas_e_persistencia():
    preferencias.salvar({"NOME_RESTAURANTE": "Loja da Ana", "WAHA_API_KEY": "privado"})
    assert preferencias.obter()["NOME_RESTAURANTE"] == "Loja da Ana"
    assert "WAHA_API_KEY" not in preferencias.obter()
    preferencias.salvar({"WAHA_API_KEY": ""})
    assert config.WAHA_API_KEY == "privado"
    config.NOME_RESTAURANTE = "Outra"
    preferencias.carregar()
    assert config.NOME_RESTAURANTE == "Loja da Ana"
    assert "loja" in __import__('src.ia', fromlist=['_system_prompt'])._system_prompt().lower()


def test_api_autenticacao_csrf_e_pedido_pelo_formulario(monkeypatch):
    from src.app import app
    monkeypatch.setitem(app.config, "DESKTOP_TOKEN", "segredo-local")
    cliente = app.test_client()
    assert cliente.get("/gestao/api/produtos").status_code == 401
    assert cliente.get("/gestao?acesso=segredo-local", environ_overrides={"REMOTE_ADDR": "10.0.0.2"}).status_code == 401
    assert cliente.get("/gestao?acesso=segredo-local", headers={"Host": "evil.example"}).status_code == 401
    assert cliente.get("/gestao?acesso=segredo-local", follow_redirects=True).status_code == 200
    assert cliente.post("/gestao/api/produtos", json={}).status_code == 403
    with cliente.session_transaction() as sessao:
        csrf = sessao["csrf"]
    headers = {"X-CSRF-Token": csrf}
    assert cliente.post("/gestao/api/produtos", json=[], headers=headers).status_code == 400
    p = cliente.post("/gestao/api/produtos", json={"nome": "Notebook", "categoria": "Eletrônicos", "preco": 3000, "estoque": 1}, headers=headers).json
    resposta = cliente.post("/gestao/api/simular", json={"telefone": "5547999990000", "texto": "2"}, headers=headers).json
    caminho = resposta["caminho"]
    assert b'Notebook' in cliente.get(caminho).data
    r = cliente.post(caminho, data={"nome": "Ana", "forma_pagamento": "Pix", f'qtd_{p["id"]}': 1})
    assert r.status_code == 200
    assert cliente.post(caminho, data={f'qtd_{p["id"]}': 1}).status_code == 410
    backup = cliente.post("/gestao/api/backup", json={}, headers=headers).json["caminho"]
    from desktop import validar_backup
    validar_backup(backup)
    with closing(sqlite3.connect(backup)) as copia:
        assert copia.execute("SELECT estoque FROM produtos").fetchone()[0] == 0


def test_migracao_de_banco_antigo(tmp_path, monkeypatch):
    arquivo = tmp_path / "antigo.db"
    with sqlite3.connect(arquivo) as conn:
        conn.execute("CREATE TABLE produtos (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, categoria TEXT NOT NULL, descricao TEXT, preco REAL NOT NULL, ativo INTEGER DEFAULT 1)")
        conn.execute("INSERT INTO produtos VALUES (1, 'Produto antigo', 'Outros', '', 10, 1)")
    conn.close()
    monkeypatch.setattr(config, "DATABASE_PATH", str(arquivo))
    init_db()
    p = estoque.listar_produtos()[0]
    assert p["nome"] == "Produto antigo"
    assert p["estoque"] is None
    comprar(p)


def test_meta_recusa_payload_sem_assinatura(monkeypatch):
    import hashlib
    import hmac
    from src.app import app
    monkeypatch.setattr(config, "WHATSAPP_APP_SECRET", "app-secret")
    cliente = app.test_client()
    corpo = b'{}'
    assert cliente.post('/webhook', data=corpo, content_type='application/json').status_code == 403
    assinatura = 'sha256=' + hmac.new(b'app-secret', corpo, hashlib.sha256).hexdigest()
    assert cliente.post('/webhook', data=corpo, content_type='application/json', headers={'X-Hub-Signature-256': assinatura}).status_code == 200
    assert cliente.post('/webhook', data=b'{"alterado":true}', content_type='application/json', headers={'X-Hub-Signature-256': assinatura}).status_code == 403


def test_restauracao_preserva_copia_anterior(tmp_path, monkeypatch):
    from desktop import preparar_dados, validar_backup
    pasta = tmp_path / 'restauracao'
    pasta.mkdir()
    p = produto(estoque=5)
    with get_conn() as origem, closing(sqlite3.connect(pasta / 'deliverybot.db')) as destino:
        origem.backup(destino)
    estoque.ajustar_estoque(p['id'], 4, 'Reposição')
    with get_conn() as origem, closing(sqlite3.connect(pasta / 'restaurar.db')) as destino:
        origem.backup(destino)
    for chave in ['DATABASE_PATH', 'SEED_CATALOGO', 'DELIVERYBOT_ENV_FILE', 'NOME_RESTAURANTE', 'TELEFONE_RESTAURANTE', 'ENDERECO_RESTAURANTE', 'HORARIO_FUNCIONAMENTO', 'FLASK_DEBUG']:
        monkeypatch.setenv(chave, '')
    preparar_dados(pasta)
    assert not (pasta / 'restaurar.db').exists()
    with closing(sqlite3.connect(pasta / 'deliverybot.db')) as conn:
        assert conn.execute('SELECT estoque FROM produtos').fetchone()[0] == 9
    copia = next((pasta / 'backups').glob('antes-restauracao-*.db'))
    validar_backup(copia)
    with closing(sqlite3.connect(copia)) as conn:
        assert conn.execute('SELECT estoque FROM produtos').fetchone()[0] == 5
    invalido = tmp_path / 'outro.db'
    with sqlite3.connect(invalido) as conn:
        conn.execute('CREATE TABLE outro(id INTEGER)')
    conn.close()
    with pytest.raises(ValueError):
        validar_backup(invalido)
