"""Configurações editáveis pela interface, preservando compatibilidade com .env."""
from urllib.parse import urlsplit

from . import config
from .db import get_conn
from .estoque import dinheiro, inteiro, texto, invalidar_catalogo

TEXTOS = {
    "NOME_RESTAURANTE": 160, "TELEFONE_RESTAURANTE": 40,
    "ENDERECO_RESTAURANTE": 300, "HORARIO_FUNCIONAMENTO": 300,
    "FORMAS_PAGAMENTO": 300, "CEP_RESTAURANTE": 9,
    "BASE_URL": 500, "WAHA_URL": 500, "WAHA_SESSION": 80,
    "WAHA_WEBHOOK_BASE_URL": 500,
    "WHATSAPP_PHONE_NUMBER_ID": 80, "OLLAMA_URL": 500, "OLLAMA_MODEL": 100,
    "ANTHROPIC_MODEL": 100,
}
SEGREDOS = {"WAHA_API_KEY", "WHATSAPP_TOKEN", "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN", "WEBHOOK_SECRET", "ANTHROPIC_API_KEY"}
ENUMS = {"WHATSAPP_PROVIDER": {"TESTE", "LOCAL", "WAHA", "META"}, "IA_PROVIDER": {"", "OLLAMA", "ANTHROPIC"}}
CAMPOS = set(TEXTOS) | SEGREDOS | set(ENUMS) | {"TAXA_ENTREGA", "TEMPO_PREPARO_MIN"}


def aplicar(valores):
    for chave, valor in valores.items():
        if chave in CAMPOS:
            if chave == "TAXA_ENTREGA":
                valor = float(valor)
            elif chave == "TEMPO_PREPARO_MIN":
                valor = int(valor)
            setattr(config, chave, valor)
    config.MODO_TESTE = config.WHATSAPP_PROVIDER == "TESTE" or (
        config.WHATSAPP_PROVIDER == "META" and not (config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID))
    config.WHATSAPP_API_URL = f"https://graph.facebook.com/v20.0/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    invalidar_catalogo()


def carregar():
    with get_conn() as conn:
        valores = {r["chave"]: r["valor"] for r in conn.execute("SELECT * FROM configuracoes")}
    aplicar(valores)


def obter():
    return {**{k: getattr(config, k) for k in CAMPOS - SEGREDOS},
            "segredos_configurados": {k: bool(getattr(config, k)) for k in SEGREDOS}}


def salvar(dados):
    valores = {}
    for chave, valor in dados.items():
        if chave not in CAMPOS:
            continue
        if chave in TEXTOS or chave in SEGREDOS:
            valor = texto(valor, chave, TEXTOS.get(chave, 2000), chave in {"NOME_RESTAURANTE", "FORMAS_PAGAMENTO"})
            if chave in SEGREDOS and not valor:
                continue  # Campo vazio preserva a credencial, nunca a devolvemos ao navegador.
            if chave.endswith("_URL") and not (chave == "WAHA_WEBHOOK_BASE_URL" and not valor):
                partes = urlsplit(valor)
                if partes.scheme not in {"http", "https"} or not partes.hostname or partes.username or partes.query or partes.fragment:
                    raise ValueError(f"{chave}: informe um endereço http:// ou https:// sem credenciais ou parâmetros.")
                valor = valor.rstrip("/")
        elif chave in ENUMS:
            if valor not in ENUMS[chave]:
                raise ValueError(f"{chave}: opção inválida.")
        elif chave == "TAXA_ENTREGA":
            valor = dinheiro(valor, "Taxa de entrega")
        else:
            valor = inteiro(valor, "Tempo estimado", 1)
        valores[chave] = valor
    completos = {k: valores.get(k, getattr(config, k)) for k in CAMPOS}
    if completos["WHATSAPP_PROVIDER"] == "META" and not all(completos[k] for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET")):
        raise ValueError("Preencha token, ID do número, token de verificação e segredo do aplicativo para usar a Meta.")
    if completos["IA_PROVIDER"] == "ANTHROPIC" and not completos["ANTHROPIC_API_KEY"]:
        raise ValueError("Preencha a chave da Anthropic para ativar a IA.")
    with get_conn() as conn:
        for chave, valor in valores.items():
            conn.execute("INSERT INTO configuracoes (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, str(valor)))
    aplicar(valores)
    return obter()
