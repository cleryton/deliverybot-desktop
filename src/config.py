import os
import secrets as _secrets_module

from dotenv import load_dotenv

load_dotenv(os.getenv("DELIVERYBOT_ENV_FILE") or None)


def _env_bool(nome: str, padrao: bool) -> bool:
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


# --- Ambiente / segurança geral ---
# FLASK_DEBUG=true só em desenvolvimento, NUNCA com o link do ngrok exposto
# na internet: o debugger do Flask em modo debug permite executar código
# arbitrário por quem encontrar uma página de erro. Padrão: desligado.
FLASK_DEBUG = _env_bool("FLASK_DEBUG", False)

# Segredo embutido na URL do webhook (/webhook/waha/<segredo> e
# /api/bot/mensagem/<segredo>) para que só quem conhece o segredo consiga
# mandar requisições que o bot aceita como legítimas. Gere um valor forte e
# mantenha em segredo -- trate como senha.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

# Login HTTP Basic do painel da cozinha (/cozinha).
#
# COZINHA_AUTH_MODO = "SENHA" (padrão): usa COZINHA_USUARIO e o HASH da
# senha (COZINHA_SENHA_HASH, nunca a senha em texto puro -- defina com
# 'python definir_senha_cozinha.py').
# COZINHA_AUTH_MODO = "WINDOWS": usa o usuário/senha da própria conta do
# Windows desta máquina (não precisa guardar senha nenhuma no .env), via
# src/auth_windows.py (requer pywin32).
#
# Sem configurar nenhum dos dois modos corretamente, o painel fica
# bloqueado por padrão -- mais seguro "esquecer de configurar" do que
# "esquecer de configurar e ficar aberto pra qualquer um".
COZINHA_AUTH_MODO = os.getenv("COZINHA_AUTH_MODO", "SENHA").strip().upper()
COZINHA_USUARIO = os.getenv("COZINHA_USUARIO", "").strip()
COZINHA_SENHA_HASH = os.getenv("COZINHA_SENHA_HASH", "").strip()

# Intervalo mínimo (segundos) entre duas mensagens do MESMO telefone que
# disparam uma chamada de IA. Mensagens mais rápidas que isso usam o menu
# fixo (sem custo) em vez de chamar a IA de novo -- protege contra gasto
# de crédito por flood/retry/abuso.
RATE_LIMIT_SEGUNDOS = float(os.getenv("RATE_LIMIT_SEGUNDOS", "2"))

# Tamanho máximo aceito no corpo de uma requisição HTTP (bytes). Evita que
# alguém mande um payload gigante pro webhook só para consumir recursos.
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(1 * 1024 * 1024)))  # 1 MB

# --- Provedor de WhatsApp: "TESTE" (padrão), "WAHA" ou "META" ---
# WAHA = WhatsApp HTTP API self-hosted via Docker (login por QR Code, sem
#        precisar de conta comercial verificada na Meta) -> ver README.
# META = WhatsApp Business Cloud API oficial (precisa de app + token da Meta).
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "TESTE").strip().upper()

# --- WhatsApp Business Cloud API (Meta) ---
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "").strip()
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "trocar_por_uma_palavra_secreta").strip()
# Versão do exemplo oficial disponibilizado no painel WhatsApp da Meta.
WHATSAPP_GRAPH_VERSION = "v25.0"
WHATSAPP_API_URL = f"https://graph.facebook.com/{WHATSAPP_GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"

# --- WAHA (WhatsApp HTTP API) ---
WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000").rstrip("/")
WAHA_SESSION = os.getenv("WAHA_SESSION", "default").strip()
WAHA_WEBHOOK_BASE_URL = os.getenv("WAHA_WEBHOOK_BASE_URL", "").strip().rstrip("/")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "").strip()  # usado como X-Api-Key nas chamadas ao WAHA
# Credenciais do dashboard/Swagger do servidor WAHA externo, se utilizado.
WAHA_DASHBOARD_USERNAME = os.getenv("WAHA_DASHBOARD_USERNAME", "admin").strip()
WAHA_DASHBOARD_PASSWORD = os.getenv("WAHA_DASHBOARD_PASSWORD", "").strip()

if WHATSAPP_PROVIDER in {"WAHA", "LOCAL"}:
    MODO_TESTE = False
elif WHATSAPP_PROVIDER == "META":
    MODO_TESTE = not (WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID)
else:
    MODO_TESTE = True

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000").rstrip("/")
TUNEL_MODO = os.getenv("TUNEL_MODO", "RAPIDO")
TUNEL_AUTOMATICO = os.getenv("TUNEL_AUTOMATICO", "NAO")
TUNEL_URL = os.getenv("TUNEL_URL", "").strip().rstrip("/")
TUNEL_TOKEN = os.getenv("TUNEL_TOKEN", "").strip()
TUNEL_PORTA = int(os.getenv("TUNEL_PORTA", "5051"))

# --- IA (atendimento "humano", sem menu numerado) ---
# IA_PROVIDER: "ANTHROPIC" (API paga, melhor qualidade), "OLLAMA" (modelo
# local gratuito, via https://ollama.com) ou vazio (IA desativada, usa o
# menu fixo de sempre -- custo zero, sem dependência externa).
IA_PROVIDER = os.getenv("IA_PROVIDER", "").strip().upper()

# Usado só se IA_PROVIDER=ANTHROPIC. Pegue sua chave em
# https://console.anthropic.com -- é uma API paga por token, separada de
# uma eventual assinatura do Claude.ai.
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5").strip()

# Usado só se IA_PROVIDER=OLLAMA. Precisa do Ollama instalado e rodando
# localmente (ollama serve) com o modelo já baixado (ex: ollama pull
# llama3.2:3b). Custo zero por mensagem.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip()
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "160"))
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m").strip()
OLLAMA_TIMEOUT_SEGUNDOS = int(os.getenv("OLLAMA_TIMEOUT_SEGUNDOS", "120"))
# Pré-carrega o modelo na memória assim que o Flask sobe, em vez de deixar a
# primeira mensagem de um cliente de verdade pagar esse custo (30-60s).
OLLAMA_AQUECER_AO_INICIAR = _env_bool("OLLAMA_AQUECER_AO_INICIAR", True)
CEREBRO_RECUPERACAO_AUTOMATICA = os.getenv('CEREBRO_RECUPERACAO_AUTOMATICA', 'NAO').strip().upper()
BOT_FILA_MAX_IDADE_SEGUNDOS = int(os.getenv("BOT_FILA_MAX_IDADE_SEGUNDOS", "300"))

# --- Restaurante ---
# Perfil individual do comércio; o padrão preserva instalações anteriores.
COMERCIO_SEGMENTO = os.getenv('COMERCIO_SEGMENTO', '')
COMERCIO_DESCRICAO = os.getenv('COMERCIO_DESCRICAO', '')
COMERCIO_MODELO = os.getenv('COMERCIO_MODELO', 'REVENDA')
COMERCIO_ESTOQUE_PADRAO = os.getenv('COMERCIO_ESTOQUE_PADRAO', 'SIM')
COMERCIO_CONFIGURADO = os.getenv('COMERCIO_CONFIGURADO', 'NAO')
NOME_RESTAURANTE = os.getenv("NOME_RESTAURANTE", "Barbaros Lanches")
TELEFONE_RESTAURANTE = os.getenv("TELEFONE_RESTAURANTE", "(47) 3000-0000")
ENDERECO_RESTAURANTE = os.getenv("ENDERECO_RESTAURANTE", "Rua das Hamburguerias, 123 - Centro")
HORARIO_FUNCIONAMENTO = os.getenv("HORARIO_FUNCIONAMENTO", "Terça a Domingo, das 18h às 23h30")
TAXA_ENTREGA = float(os.getenv("TAXA_ENTREGA", "6.00"))
CEP_RESTAURANTE = os.getenv("CEP_RESTAURANTE", "89460-000")
RAIO_ENTREGA_KM = float(os.getenv("RAIO_ENTREGA_KM", "6"))

# --- Banco de dados ---
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/deliverybot.db")
SEED_CATALOGO = _env_bool("SEED_CATALOGO", True)
FORMAS_PAGAMENTO = os.getenv("FORMAS_PAGAMENTO", "Dinheiro,Pix,Cartão de crédito,Cartão de débito")

# --- Operação ---
TEMPO_PREPARO_MIN = int(os.getenv("TEMPO_PREPARO_MIN", "40"))
VALIDADE_LINK_MIN = int(os.getenv("VALIDADE_LINK_MIN", "30"))


def gerar_segredo_sugerido() -> str:
    """Usado só pelo utilitário de linha de comando (ver gerar_segredos.py)
    para sugerir valores fortes ao preencher o .env."""
    return _secrets_module.token_urlsafe(24)


# Privacidade: prazos operacionais configuráveis; não definem obrigações fiscais.
LGPD_RESPONSAVEL = os.getenv("LGPD_RESPONSAVEL", "")
LGPD_CONTATO = os.getenv("LGPD_CONTATO", "")
LGPD_RETENCAO_PEDIDOS = os.getenv("LGPD_RETENCAO_PEDIDOS", "A loja conserva registros de pedidos durante os prazos necessários à operação e às obrigações legais aplicáveis. Consulte o responsável para conhecer o prazo adotado.")
LGPD_MENSAGENS_DIAS = int(os.getenv("LGPD_MENSAGENS_DIAS", "30"))
LGPD_IA_EXTERNA = os.getenv("LGPD_IA_EXTERNA", "NAO")
ADMIN_PERMITIR_REMOTO = _env_bool("ADMIN_PERMITIR_REMOTO", False)
