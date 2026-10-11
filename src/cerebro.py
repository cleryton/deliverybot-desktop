"""Cofre local de estilo, editável como um vault do Obsidian."""
from pathlib import Path

from . import config

_ARQUIVO_ESTILO = "Estilo de atendimento.md"
_MODELO = """---
tipo: estilo-de-atendimento
---
# Estilo de atendimento

Este arquivo personaliza somente o jeito de conversar. O DeliveryBot consulta estas orientações a cada atendimento.
Edite este texto no Obsidian ou em qualquer editor de Markdown. As alterações são aplicadas na próxima mensagem.

## Tom da loja
- Fale em português do Brasil, com simpatia, clareza e naturalidade.
- Seja acolhedor sem exagerar na intimidade ou nos emojis.
- Prefira respostas curtas, mas explique com calma quando a pessoa precisar.

## Como conduzir a conversa
- Responda primeiro ao que a pessoa perguntou.
- Faça uma pergunta por vez quando faltar uma informação para ajudar.
- Não repita saudações nem frases prontas em todas as mensagens.
- Se não souber responder, diga isso com honestidade e ofereça chamar a equipe.

## Exemplos aprovados pela loja
<!-- Adicione exemplos reais e fictícios de respostas no tom que prefere. Não coloque dados de clientes. -->

## Evitar
- Respostas frias, excessivamente formais ou que pareçam automáticas.
- Inventar preços, disponibilidade, promoções, prazos ou ações já realizadas.
- Pedir dados pessoais que não sejam necessários para o atendimento.
"""


def diretorio() -> Path:
    """Guarda o vault junto aos dados locais persistentes do aplicativo."""
    return Path(config.DATABASE_PATH).expanduser().resolve().parent / "Cerebro Obsidian"


def arquivo_estilo() -> Path:
    pasta = diretorio()
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ".obsidian").mkdir(exist_ok=True)
    arquivo = pasta / _ARQUIVO_ESTILO
    try:
        with arquivo.open("x", encoding="utf-8", newline="\n") as destino:
            destino.write(_MODELO)
    except FileExistsError:
        pass
    return arquivo


def situacao() -> dict:
    arquivo = arquivo_estilo()
    return {"pasta": str(arquivo.parent), "arquivo": str(arquivo), "cofre_obsidian": True}


def instrucoes_estilo() -> str:
    """Lê somente a nota editorial aprovada, sem importar conversas de clientes."""
    try:
        conteudo = arquivo_estilo().read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""
    if conteudo.startswith("---"):
        partes = conteudo.split("---", 2)
        if len(partes) == 3:
            conteudo = partes[2]
    conteudo = conteudo.strip()
    return conteudo[:6000]
