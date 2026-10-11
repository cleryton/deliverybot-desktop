"""Configurações editáveis pela interface, preservando compatibilidade com .env."""
from urllib.parse import urlsplit

from . import config
from .db import get_conn
from .estoque import dinheiro, inteiro, texto, invalidar_catalogo
from .seguranca import proteger_segredo, revelar_segredo

TEXTOS = {
    'COMERCIO_SEGMENTO': 120, 'COMERCIO_DESCRICAO': 1200,
    "NOME_RESTAURANTE": 160, "TELEFONE_RESTAURANTE": 40,
    "ENDERECO_RESTAURANTE": 300, "HORARIO_FUNCIONAMENTO": 300,
    "FORMAS_PAGAMENTO": 300, "CEP_RESTAURANTE": 9,
    "BASE_URL": 500, "WAHA_URL": 500, "WAHA_SESSION": 80,
    "TUNEL_URL": 500,
    "WAHA_WEBHOOK_BASE_URL": 500,
    "WHATSAPP_PHONE_NUMBER_ID": 80, "OLLAMA_URL": 500, "OLLAMA_MODEL": 100,
    "ANTHROPIC_MODEL": 100,
    "LGPD_RESPONSAVEL": 160, "LGPD_CONTATO": 200, "LGPD_RETENCAO_PEDIDOS": 1000,
}
SEGREDOS = {"WAHA_API_KEY", "WHATSAPP_TOKEN", "WHATSAPP_APP_SECRET", "WHATSAPP_VERIFY_TOKEN", "WEBHOOK_SECRET", "ANTHROPIC_API_KEY", "TUNEL_TOKEN"}
ENUMS = {"WHATSAPP_PROVIDER": {"TESTE", "LOCAL", "WAHA", "META"}, "IA_PROVIDER": {"", "OLLAMA", "ANTHROPIC"}, "LGPD_IA_EXTERNA": {"NAO", "SIM"}, "TUNEL_MODO": {"RAPIDO", "FIXO"}, "TUNEL_AUTOMATICO": {"NAO", "SIM"},
         'COMERCIO_MODELO': {'REVENDA', 'PRODUCAO', 'SERVICOS', 'MISTO'},
         'COMERCIO_ESTOQUE_PADRAO': {'SIM', 'NAO'}, 'COMERCIO_CONFIGURADO': {'SIM', 'NAO'},
         'CEREBRO_RECUPERACAO_AUTOMATICA': {'SIM', 'NAO'}}
CAMPOS = set(TEXTOS) | SEGREDOS | set(ENUMS) | {"TAXA_ENTREGA", "TEMPO_PREPARO_MIN", "LGPD_MENSAGENS_DIAS", "TUNEL_PORTA"}


def aplicar(valores):
    for chave, valor in valores.items():
        if chave in CAMPOS:
            if chave == "TAXA_ENTREGA":
                valor = float(valor)
            elif chave in {"TEMPO_PREPARO_MIN", "LGPD_MENSAGENS_DIAS", "TUNEL_PORTA"}:
                valor = int(valor)
            setattr(config, chave, valor)
    config.MODO_TESTE = config.WHATSAPP_PROVIDER == "TESTE" or (
        config.WHATSAPP_PROVIDER == "META" and not (config.WHATSAPP_TOKEN and config.WHATSAPP_PHONE_NUMBER_ID))
    config.WHATSAPP_API_URL = f"https://graph.facebook.com/v20.0/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
    invalidar_catalogo()


def carregar():
    with get_conn() as conn:
        valores = {r["chave"]: r["valor"] for r in conn.execute("SELECT * FROM configuracoes")}
        for chave in SEGREDOS & valores.keys():
            armazenado = valores[chave]
            try:
                valores[chave] = revelar_segredo(armazenado)
            except ValueError:
                # Uma conta Windows diferente não consegue usar a credencial antiga.
                valores[chave] = ""
            protegido = proteger_segredo(valores[chave])
            if valores[chave] and protegido != armazenado and not armazenado.startswith("dpapi:v1:"):
                conn.execute("UPDATE configuracoes SET valor=? WHERE chave=?", (protegido, chave))
    aplicar(valores)


def obter():
    return {**{k: getattr(config, k) for k in CAMPOS - SEGREDOS},
            "segredos_configurados": {k: bool(getattr(config, k)) for k in SEGREDOS}}


def salvar(dados):
    if any(k.startswith('TUNEL_') for k in dados):
        from .publicacao import situacao
        if situacao()['ativo']:
            raise ValueError('Pare a página pública antes de alterar suas configurações.')
    valores = {}
    for chave, valor in dados.items():
        if chave not in CAMPOS:
            continue
        if chave in TEXTOS or chave in SEGREDOS:
            valor = texto(valor, chave, TEXTOS.get(chave, 2000), chave in {"NOME_RESTAURANTE", "FORMAS_PAGAMENTO"})
            if chave in SEGREDOS and not valor:
                continue  # Campo vazio preserva a credencial, nunca a devolvemos ao navegador.
            if chave == 'TUNEL_TOKEN' and not valor.isalnum() and any(c.isspace() or ord(c) < 32 for c in valor):
                raise ValueError('Cole somente o token do conector, sem o comando de instalação.')
            if chave.endswith("_URL") and not (chave in {"WAHA_WEBHOOK_BASE_URL", "TUNEL_URL"} and not valor):
                partes = urlsplit(valor)
                if partes.scheme not in {"http", "https"} or not partes.hostname or partes.username or partes.query or partes.fragment:
                    raise ValueError(f"{chave}: informe um endereço http:// ou https:// sem credenciais ou parâmetros.")
                valor = valor.rstrip("/")
            if chave == 'TUNEL_URL' and valor:
                from .publicacao import validar_dominio
                valor = validar_dominio(valor)
        elif chave in ENUMS:
            if valor not in ENUMS[chave]:
                raise ValueError(f"{chave}: opção inválida.")
        elif chave == "TAXA_ENTREGA":
            valor = dinheiro(valor, "Taxa de entrega")
        elif chave == "LGPD_MENSAGENS_DIAS":
            valor = inteiro(valor, "Retenção de conversas", 1)
            if valor > 365:
                raise ValueError("Retenção de conversas: use de 1 a 365 dias.")
        elif chave == 'TUNEL_PORTA':
            valor = inteiro(valor, 'Porta da página pública', 1024)
            if valor > 65535:
                raise ValueError('Porta da página pública: use de 1024 a 65535.')
        else:
            valor = inteiro(valor, "Tempo estimado", 1)
        valores[chave] = valor
    completos = {k: valores.get(k, getattr(config, k)) for k in CAMPOS}
    if completos['TUNEL_AUTOMATICO'] == 'SIM' and completos['TUNEL_MODO'] == 'FIXO' and not all(completos[k] for k in ('TUNEL_URL','TUNEL_TOKEN')):
        raise ValueError('Informe domínio HTTPS e token do túnel fixo antes de ativar o início automático.')
    if completos["WHATSAPP_PROVIDER"] == "META" and not all(completos[k] for k in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET")):
        raise ValueError("Preencha token, ID do número, token de verificação e segredo do aplicativo para usar a Meta.")
    if completos["IA_PROVIDER"] == "ANTHROPIC" and not completos["ANTHROPIC_API_KEY"]:
        raise ValueError("Preencha a chave da Anthropic para ativar a IA.")
    with get_conn() as conn:
        for chave, valor in valores.items():
            armazenado = proteger_segredo(str(valor)) if chave in SEGREDOS else str(valor)
            conn.execute("INSERT INTO configuracoes (chave, valor) VALUES (?, ?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (chave, armazenado))
    aplicar(valores)
    return obter()
