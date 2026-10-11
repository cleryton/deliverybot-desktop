-- Entidades mínimas do banco (Tema 09 - DeliveryBot):
-- clientes, produtos, pedidos, itens_pedido, fila_preparo, mensagens

CREATE TABLE IF NOT EXISTS clientes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT NOT NULL,
    telefone      TEXT NOT NULL UNIQUE,      -- número do WhatsApp (com DDI/DDD)
    cep           TEXT,
    endereco      TEXT,
    chat_id       TEXT,                      -- chatId original do WAHA (@c.us ou @lid), p/ responder sem depender de cache em memória
    waha_session  TEXT,                      -- nome da sessão do WAHA que recebeu a última mensagem desse cliente
    criado_em     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS produtos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT NOT NULL,
    categoria     TEXT NOT NULL,             -- lanche, bebida, sobremesa...
    descricao     TEXT,
    preco         REAL NOT NULL,
    ativo         INTEGER NOT NULL DEFAULT 1,
    imagem        TEXT                      -- nome do arquivo em web/static/produtos/, opcional
);

CREATE TABLE IF NOT EXISTS fotos_produto (
    produto_id INTEGER PRIMARY KEY REFERENCES produtos(id) ON DELETE CASCADE,
    hash TEXT NOT NULL,
    dados BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fotos_produto_hash ON fotos_produto(hash);

CREATE TABLE IF NOT EXISTS documentos_estoque (
    token TEXT PRIMARY KEY,
    dono TEXT NOT NULL,
    origem_hash TEXT NOT NULL,
    produtos TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now')),
    concluido INTEGER NOT NULL DEFAULT 0,
    nota TEXT NOT NULL DEFAULT '',
    nota_salva INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_documento_aplicado ON documentos_estoque(origem_hash) WHERE concluido=1;

CREATE TABLE IF NOT EXISTS pedidos (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_pedido       TEXT NOT NULL UNIQUE,     -- ex: #21535858, exibido ao cliente
    cliente_id          INTEGER NOT NULL REFERENCES clientes(id),
    origem              TEXT NOT NULL DEFAULT 'Bot Atendimento',
    forma_entrega       TEXT NOT NULL,            -- 'RETIRADA BALCAO' ou 'ENTREGA'
    tempo_estimado_min  INTEGER NOT NULL,
    forma_pagamento     TEXT NOT NULL,
    total_itens         REAL NOT NULL,
    total_pedido        REAL NOT NULL,
    total_pago          REAL NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'RECEBIDO',
    -- RECEBIDO -> CONFIRMADO -> EM_PREPARO -> PRONTO -> ENTREGUE/RETIRADO -> CANCELADO
    criado_em           TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id     INTEGER NOT NULL REFERENCES pedidos(id),
    produto_id    INTEGER NOT NULL REFERENCES produtos(id),
    quantidade    INTEGER NOT NULL,
    preco_unitario REAL NOT NULL,
    observacao    TEXT
);

CREATE TABLE IF NOT EXISTS fila_preparo (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id     INTEGER NOT NULL UNIQUE REFERENCES pedidos(id),
    posicao       INTEGER NOT NULL,
    status        TEXT NOT NULL DEFAULT 'AGUARDANDO',
    -- AGUARDANDO -> EM_PREPARO -> PRONTO -> RETIRADO
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS mensagens (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    telefone      TEXT NOT NULL,
    direcao       TEXT NOT NULL,           -- 'ENTRADA' (cliente -> bot) ou 'SAIDA' (bot -> cliente)
    conteudo      TEXT NOT NULL,
    criado_em     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Usado pela IA pra montar o histórico da conversa (SELECT ... WHERE telefone = ?
-- ORDER BY id DESC LIMIT N) -- sem isso, essa consulta faz full scan da tabela
-- inteira a cada mensagem recebida.
CREATE INDEX IF NOT EXISTS idx_mensagens_telefone_id ON mensagens(telefone, id);

-- Link único de pedido: cada token só pode gerar UM pedido.
CREATE TABLE IF NOT EXISTS links_pedido (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    token         TEXT NOT NULL UNIQUE,
    telefone      TEXT NOT NULL,
    usado         INTEGER NOT NULL DEFAULT 0,
    pedido_id     INTEGER REFERENCES pedidos(id),
    expira_em     TEXT NOT NULL,
    criado_em     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Estado da conversa do bot por telefone (reservado para uso futuro do menu
-- fixo; a IA não depende desta tabela).
CREATE TABLE IF NOT EXISTS sessoes_bot (
    telefone      TEXT PRIMARY KEY,
    estado        TEXT NOT NULL DEFAULT 'MENU',
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Rascunho privado da compra pelo chat; nunca é usado como memória da IA.
CREATE TABLE IF NOT EXISTS carrinhos_conversa (
    telefone TEXT PRIMARY KEY,
    token TEXT NOT NULL UNIQUE,
    dados TEXT NOT NULL DEFAULT '{}',
    pedido_id INTEGER REFERENCES pedidos(id),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS movimentos_estoque (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER NOT NULL REFERENCES produtos(id),
    pedido_id INTEGER REFERENCES pedidos(id),
    tipo TEXT NOT NULL,
    quantidade INTEGER NOT NULL,
    saldo INTEGER,
    motivo TEXT NOT NULL,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_movimentos_produto ON movimentos_estoque(produto_id, id);

CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

-- Recebimento rápido do webhook e deduplicação de retentativas do provedor.
CREATE TABLE IF NOT EXISTS tarefas_bot (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    origem TEXT NOT NULL,
    chave TEXT NOT NULL,
    telefone TEXT NOT NULL,
    texto TEXT NOT NULL,
    chat_id TEXT,
    sessao TEXT,
    resposta TEXT,
    entrada_registrada INTEGER NOT NULL DEFAULT 0,
    estado TEXT NOT NULL DEFAULT 'PENDENTE',
    tentativas INTEGER NOT NULL DEFAULT 0,
    erro TEXT,
    recebido_em TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(origem, chave)
);
CREATE INDEX IF NOT EXISTS idx_tarefas_estado ON tarefas_bot(estado, id);

-- Auditoria sem telefone, conteúdo de conversa, credenciais ou endereço.
CREATE TABLE IF NOT EXISTS auditoria_privacidade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    acao TEXT NOT NULL,
    cliente_id INTEGER,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS testes_publicos (
    token_hash TEXT PRIMARY KEY,
    base_url TEXT NOT NULL,
    expira_em TEXT NOT NULL,
    recebido_em TEXT
);

CREATE TABLE IF NOT EXISTS rotinas (
    id INTEGER PRIMARY KEY CHECK(id=1), backup_ativo INTEGER NOT NULL DEFAULT 0,
    horas INTEGER NOT NULL DEFAULT 24, quantidade INTEGER NOT NULL DEFAULT 7,
    senha TEXT NOT NULL DEFAULT '', pasta TEXT NOT NULL DEFAULT '',
    limpar INTEGER NOT NULL DEFAULT 0, ultima_copia TEXT, ultima_limpeza TEXT, erro TEXT
);
INSERT OR IGNORE INTO rotinas(id) VALUES(1);

CREATE TABLE IF NOT EXISTS atendimentos_humanos (
    telefone TEXT PRIMARY KEY, estado TEXT NOT NULL,
    solicitado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS operadores (
    id INTEGER PRIMARY KEY, nome TEXT NOT NULL, login TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL, perfil TEXT NOT NULL, ativo INTEGER NOT NULL DEFAULT 1,
    versao TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auditoria_operadores (
    id INTEGER PRIMARY KEY, operador_id INTEGER, acao TEXT NOT NULL, objeto TEXT,
    criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS atualizacoes (
    id INTEGER PRIMARY KEY CHECK(id=1), automatica INTEGER NOT NULL DEFAULT 0,
    ultima_consulta REAL NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO atualizacoes(id) VALUES(1);
