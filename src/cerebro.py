"""Cofre local e curado de estilo e conhecimento, compatível com Obsidian."""
import json
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from pathlib import PurePosixPath

from . import config

_ARQUIVO_ESTILO = "Estilo de atendimento.md"
_ARQUIVO_LOJA = "Informações da loja.md"
_ARQUIVO_FAQ = "Perguntas frequentes.md"
_LIMITE_NOTA = 4000
_LIMITE_TOTAL = 14000
_MAX_NOTAS_EXTRAS = 12
_MAX_ARQUIVOS_BACKUP = 256
_MAX_BACKUP_BYTES = 16 * 1024 * 1024
_MAX_LEITURA_NOTA = 64 * 1024
_MAX_NOTAS_POR_PERGUNTA = 6

_NOTAS_INICIAIS = {
    "Início.md": """---
tipo: indice-do-cofre
---
# Cérebro do atendimento

Este cofre guarda orientações editoriais e informações aprovadas para o DeliveryBot. As alterações são lidas na próxima resposta do Ollama; elas não treinam os pesos do modelo.

## Personalidade
- [[Estilo de atendimento]] — voz, tom e exemplos de conversa.

## Conhecimento aprovado
- [[Informações da loja]] — horários, entrega e políticas confirmadas.
- [[Perguntas frequentes]] — respostas curtas revisadas pela equipe.
- Para adicionar outros assuntos, crie uma nota em `Conhecimento` usando `Modelos/Conhecimento aprovado.md` e marque `atendimento: true` no frontmatter.

## Privacidade e precisão
- Não inclua nomes, telefones, endereços residenciais, pedidos ou conversas de clientes.
- Mantenha informações objetivas e atuais; indique a fonte e a data de revisão.
- Cadastro de produtos, preços, estoque, pedidos, segurança e privacidade do aplicativo sempre prevalecem sobre estas notas.
- O cofre fica neste computador. Sincronização do Obsidian com terceiros é configurada e controlada pelo usuário.
""",
    _ARQUIVO_ESTILO: """---
tipo: estilo-de-atendimento
---
# Estilo de atendimento

Este arquivo ajusta somente a voz da loja. Edite no Obsidian ou em outro editor de Markdown; a próxima resposta do Ollama já lê a versão atual.

## Personalidade da marca
- Próxima, esperta, gentil e segura do que sabe.
- Demonstra que entendeu o momento da pessoa, sem presumir intimidade.
- Usa português brasileiro cotidiano. Contrações como “pra” e “tá” cabem quando soarem naturais.
- Traz entusiasmo verdadeiro ao falar dos produtos, sem transformar tudo em propaganda.

## Ritmo e conversa
- Responde primeiro ao que a pessoa quis dizer.
- Para pedidos simples, prefere uma ou duas frases; explica com paciência quando necessário.
- Varia o começo e o ritmo das respostas; evita saudações e frases automáticas repetidas.
- Faz uma pergunta por vez, só quando a resposta ajudar a avançar.
- Usa humor leve apenas quando o contexto convidar. Em reclamações, atrasos, pagamentos ou dados pessoais, prioriza respeito e clareza.

## Expressões e exemplos aprovados
<!-- Escreva exemplos fictícios ou sem dados pessoais para mostrar o tom que prefere. -->

## Evitar
- Gírias forçadas, excesso de emojis, entusiasmo artificial, intimidade presumida e linguagem corporativa.
- Inventar preço, disponibilidade, promoção, prazo ou ação realizada.
- Pedir dados pessoais desnecessários.
""",
    _ARQUIVO_LOJA: """---
tipo: informacoes-da-loja
atendimento: true
---
# Informações da loja

<!-- Use apenas fatos aprovados pela equipe. Preencha e revise antes do uso. Não duplique produtos, preços ou estoque: o catálogo do aplicativo é a fonte oficial. -->

## Horários e canais
<!-- Informe dias, horários e canais oficiais. -->

## Entrega e retirada
<!-- Informe regiões, taxas, prazos e condições confirmadas. -->

## Pagamentos e políticas
<!-- Informe formas de pagamento, trocas ou outras políticas confirmadas. -->

## Fonte e revisão
<!-- Responsável pela revisão: | Revisado em (AAAA-MM-DD): -->
""",
    _ARQUIVO_FAQ: """---
tipo: perguntas-frequentes
atendimento: true
---
# Perguntas frequentes

<!-- Adicione somente respostas aprovadas, uma pergunta por seção. Indique quando a resposta deve ser confirmada por uma pessoa. -->

## Exemplo de estrutura
<!--
### A loja entrega no meu bairro?
Resposta aprovada, incluindo condições e próximo passo.
Fonte: política de entrega. Revisado em: AAAA-MM-DD.
-->

## Revisão
<!-- Responsável: | Revisado em (AAAA-MM-DD): -->
""",
}

_MODELO_CONHECIMENTO = """---
tipo: conhecimento-aprovado
atendimento: false
prioridade: 3
tags: [assunto, palavras-chave]
---
# Título do assunto

<!-- Comece com atendimento: true no frontmatter quando a equipe revisar este conteúdo e aprovar seu uso pelo bot. -->

## Informação aprovada

## Fonte e revisão
- Fonte:
- Responsável:
- Revisado em (AAAA-MM-DD):

<!-- Opcional: adicione valido_ate: AAAA-MM-DD no frontmatter para suspender automaticamente o uso após essa data. Prioridade aceita 1 a 5; 5 é a maior. Tags ajudam a encontrar esta nota pela dúvida do cliente. -->

<!-- Não inclua dados ou conversas de clientes. Produtos, preços e estoque devem ser consultados no cadastro do aplicativo. -->
"""


def diretorio() -> Path:
    """Guarda o vault junto aos dados persistentes do aplicativo."""
    return Path(config.DATABASE_PATH).expanduser().resolve().parent / "Cerebro Obsidian"


def arquivo_inicio() -> Path:
    return _preparar() / "Início.md"


def _criar_se_ausente(caminho: Path, conteudo: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        with caminho.open("x", encoding="utf-8", newline="\n") as destino:
            destino.write(conteudo)
    except FileExistsError:
        pass


def _preparar() -> Path:
    pasta = diretorio()
    for caminho in (pasta, pasta/'Conhecimento', pasta/'Modelos', pasta/'.obsidian'):
        if caminho.is_symlink() or (hasattr(caminho, 'is_junction') and caminho.is_junction()):
            raise ValueError('O cofre Obsidian não pode usar atalhos para pastas externas.')
    pasta.mkdir(parents=True, exist_ok=True)
    conhecimento = pasta / "Conhecimento"
    modelos = pasta / "Modelos"
    conhecimento.mkdir(exist_ok=True)
    modelos.mkdir(exist_ok=True)
    (pasta / ".obsidian").mkdir(exist_ok=True)
    for nome, conteudo in _NOTAS_INICIAIS.items():
        _criar_se_ausente(pasta / nome, conteudo)
    _criar_se_ausente(modelos / "Conhecimento aprovado.md", _MODELO_CONHECIMENTO)
    _criar_se_ausente(modelos / 'Lista de estoque.md', '''---
tipo: lista-de-estoque
atendimento: false
---
# Lista para importar no aplicativo

Preencha uma linha por produto e salve a nota. Em Produtos e estoque, escolha este arquivo Markdown para ler e revisar.
Use preco para preço de venda e custo para preço de compra. Para atualizar um produto existente, preencha o SKU já cadastrado e a mesma unidade.

| nome | categoria | preco | custo | sku | unidade | estoque | fracionado |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  | un |  | nao |

O lançamento será feito somente após a revisão no aplicativo. Esta nota não substitui o saldo atual do sistema.
''')
    configuracao = pasta / ".obsidian" / "app.json"
    _criar_se_ausente(configuracao, json.dumps({
        "newFileLocation": "folder",
        "newFileFolderPath": "Conhecimento",
        "attachmentFolderPath": "Anexos",
    }, ensure_ascii=False, indent=2) + "\n")
    return pasta


def arquivo_estilo() -> Path:
    return _preparar() / _ARQUIVO_ESTILO


def registrar_documento_estoque(token: str, linhas: str) -> Path:
    """Registro operacional separado das notas consultadas pelo atendimento."""
    import hashlib
    raiz = diretorio()
    pasta = raiz / 'Documentos de estoque'
    for caminho in (raiz, pasta):
        if caminho.is_symlink() or (hasattr(caminho, 'is_junction') and caminho.is_junction()):
            raise ValueError('A pasta de documentos não pode ser um atalho para outra pasta.')
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{30,64}', token) or not isinstance(linhas,str) or len(linhas.encode('utf-8')) > 60000:
        raise ValueError('Registro de estoque inválido.')
    _preparar()
    pasta.mkdir(exist_ok=True)
    destino = pasta / ('Importação-' + hashlib.sha256(token.encode()).hexdigest()[:24] + '.md')
    if destino.is_symlink() or (hasattr(destino, 'is_junction') and destino.is_junction()):
        raise ValueError('Destino do registro inválido.')
    conteudo = ('---\ntipo: registro-de-estoque\natendimento: false\n---\n# Lançamento de estoque revisado\n\n'
        'Este registro é um histórico da importação. O saldo atual, os preços e os produtos devem ser consultados no aplicativo.\n\n'
        + linhas + '\n')
    _criar_se_ausente(destino, conteudo)
    return destino


def situacao() -> dict:
    pasta = _preparar()
    estilo = instrucoes_estilo()
    ativos = bool(estilo) + len(_notas_aprovadas(pasta))
    return {
        "pasta": str(pasta),
        "arquivo": str(arquivo_inicio()),
        "cofre_obsidian": True,
        "notas_contexto": ativos,
        "consulta_por_assunto": True,
        "limite_contexto": _LIMITE_TOTAL,
    }


def _remover_frontmatter(conteudo: str) -> tuple[str, str]:
    bloco = re.match(r"\A\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", conteudo, re.DOTALL)
    return (bloco[1], conteudo[bloco.end():]) if bloco else ("", conteudo)


def _limpar(conteudo: str) -> str:
    conteudo = re.sub(r"<!--.*?-->", "", conteudo, flags=re.DOTALL)
    linhas = conteudo.strip().splitlines()
    if linhas and linhas[0].lstrip().startswith("# "):
        linhas = linhas[1:]
    resultado = []
    for indice, linha in enumerate(linhas):
        if re.match(r"^\s*#{1,6}\s+", linha):
            proximo = indice + 1
            while proximo < len(linhas) and not re.match(r"^\s*#{1,6}\s+", linhas[proximo]):
                if linhas[proximo].strip():
                    break
                proximo += 1
            if proximo == len(linhas) or re.match(r"^\s*#{1,6}\s+", linhas[proximo]):
                continue
        resultado.append(linha)
    return "\n".join(resultado).strip()


def _ler(caminho: Path) -> tuple[str, str]:
    try:
        raiz = diretorio()
        if raiz.is_symlink() or (hasattr(raiz, 'is_junction') and raiz.is_junction()):
            return "", ""
        relativo = caminho.relative_to(raiz)
        atual = raiz
        for parte in relativo.parts:
            atual = atual / parte
            if atual.is_symlink() or (hasattr(atual, 'is_junction') and atual.is_junction()):
                return "", ""
        caminho.resolve().relative_to(raiz.resolve())
        with caminho.open('rb') as arquivo:
            dados = arquivo.read(_MAX_LEITURA_NOTA + 1)
        if len(dados) > _MAX_LEITURA_NOTA or b'\x00' in dados:
            return "", ""
        conteudo = dados.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    except (OSError, UnicodeError, ValueError):
        return "", ""
    metadados, corpo = _remover_frontmatter(conteudo)
    return metadados, _limpar(corpo)[:_LIMITE_NOTA]


def _metadado(metadados: str, chave: str) -> str:
    valores = re.findall(r'^' + re.escape(chave) + r'[ \t]*:[ \t]*([^\r\n]*)$', metadados, re.M | re.I)
    return valores[0].strip() if len(valores) == 1 else ''


def _aprovada(metadados: str) -> bool:
    if _metadado(metadados, 'atendimento').casefold() != 'true':
        return False
    if re.search(r'^valido_ate[ \t]*:', metadados, re.M | re.I):
        try:
            validade = _metadado(metadados, 'valido_ate')
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', validade) or date.fromisoformat(validade) < date.today():
                return False
        except ValueError:
            return False
    return True


def _termos(texto: str) -> set[str]:
    texto = ''.join(c for c in unicodedata.normalize('NFKD', texto.casefold()) if not unicodedata.combining(c))
    ignorados = {'para', 'como', 'voces', 'queria', 'quero', 'gostaria', 'sobre', 'qual', 'quais', 'porque', 'posso', 'pode', 'essa', 'esse', 'isso', 'tenho', 'loja', 'produto', 'produtos', 'pedido', 'pedidos'}
    return {t for t in re.findall(r'[a-z]{3,}', texto[:16000]) if t not in ignorados}


def _prioridade(metadados: str) -> int:
    valor = _metadado(metadados, 'prioridade')
    return int(valor) if valor in {'1', '2', '3', '4', '5'} else 3


def _tags(metadados: str) -> str:
    """Aceita tanto a lista inline quanto a lista editada nas propriedades do Obsidian."""
    campos = list(re.finditer(r'^tags[ \t]*:[ \t]*([^\n]*)$', metadados, re.M | re.I))
    if len(campos) != 1:
        return ''
    if campos[0][1].strip():
        return campos[0][1].strip()
    valores = []
    for linha in metadados[campos[0].end():].splitlines():
        if not linha.strip():
            continue
        item = re.fullmatch(r'[ \t]*-[ \t]+(.+)', linha)
        if not item:
            break
        valores.append(item[1])
    return ' '.join(valores)


def _notas_aprovadas(pasta: Path) -> list[Path]:
    candidatas = [pasta / _ARQUIVO_LOJA, pasta / _ARQUIVO_FAQ]
    base = pasta / "Conhecimento"
    if base.is_dir():
        try:
            extras = sorted(base.rglob("*.md"), key=lambda p: str(p).casefold())
        except OSError:
            extras = []
        candidatas.extend(p for p in extras[:_MAX_ARQUIVOS_BACKUP] if not p.is_symlink())
    aprovadas = []
    raiz = pasta.resolve()
    for caminho in candidatas:
        if caminho.is_symlink() or not caminho.is_file():
            continue
        try:
            caminho.resolve().relative_to(raiz)
        except (OSError, ValueError):
            continue
        metadados, corpo = _ler(caminho)
        if corpo and _aprovada(metadados):
            aprovadas.append(caminho)
    return aprovadas


def instrucoes_estilo() -> str:
    """Mantém uma API simples para leitores que precisam somente da voz."""
    _, conteudo = _ler(arquivo_estilo())
    return conteudo


def instrucoes_contexto(pergunta: str = '') -> str:
    """Seleciona conhecimento aprovado pelo assunto; nunca grava a pergunta no cofre."""
    pasta = _preparar()
    secoes = []
    _, estilo = _ler(pasta / _ARQUIVO_ESTILO)
    if estilo:
        secoes.append(("Estilo de atendimento", estilo))
    termos = _termos(pergunta)
    candidatas = []
    for caminho in _notas_aprovadas(pasta):
        metadados, corpo = _ler(caminho)
        if corpo and _aprovada(metadados):
            rotulo = caminho.relative_to(pasta).as_posix()[:120]
            titulo = _termos(caminho.stem + ' ' + _tags(metadados))
            afinidade = 4 * len(termos & titulo) + len(termos & _termos(corpo))
            if termos and not afinidade and caminho.name not in {_ARQUIVO_LOJA, _ARQUIVO_FAQ}:
                continue
            candidatas.append((afinidade, _prioridade(metadados), rotulo, corpo))
    candidatas.sort(key=lambda nota: (-nota[0], -nota[1], nota[2].casefold()))
    if termos:
        candidatas = candidatas[:_MAX_NOTAS_POR_PERGUNTA]
    else:
        candidatas = candidatas[:_MAX_NOTAS_EXTRAS + 2]
    secoes.extend((rotulo, corpo) for _, _, rotulo, corpo in candidatas)
    partes = []
    restante = _LIMITE_TOTAL
    for rotulo, conteudo in secoes:
        cabecalho = ('\n\n' if partes else '') + f'### {rotulo}\n'
        trecho = conteudo[:max(0, restante - len(cabecalho))]
        if not trecho:
            break
        partes.append(cabecalho + trecho)
        restante -= len(cabecalho) + len(trecho)
        if restante <= 0:
            break
    return ''.join(partes)


def snapshot() -> dict[str, bytes]:
    """Retorna somente notas e a configuração básica do vault para backup cifrado."""
    pasta = _preparar()
    arquivos = []
    try:
        arquivos.extend(p for p in pasta.rglob("*.md") if not p.is_symlink())
    except OSError as exc:
        raise ValueError("Não foi possível ler as notas do cofre Obsidian.") from exc
    app_json = pasta / ".obsidian" / "app.json"
    if app_json.is_file() and not app_json.is_symlink():
        arquivos.append(app_json)
    raiz = pasta.resolve()
    resultado: dict[str, bytes] = {}
    total = 0
    for arquivo in sorted(set(arquivos), key=lambda p: str(p).casefold()):
        try:
            arquivo.resolve().relative_to(raiz)
            relativo = arquivo.relative_to(pasta).as_posix()
            conteudo = arquivo.read_bytes()
        except (OSError, ValueError) as exc:
            raise ValueError("Não foi possível ler uma nota do cofre para o backup.") from exc
        total += len(conteudo)
        if len(resultado) >= _MAX_ARQUIVOS_BACKUP or total > _MAX_BACKUP_BYTES:
            raise ValueError("O cofre ultrapassou o limite de 256 arquivos ou 16 MB para backup. Remova anexos e notas que não usa e tente novamente.")
        resultado[relativo] = conteudo
    return _validar_snapshot(resultado)


def _validar_snapshot(arquivos: dict[str, bytes]) -> dict[str, bytes]:
    if not isinstance(arquivos, dict) or len(arquivos) > _MAX_ARQUIVOS_BACKUP:
        raise ValueError("O backup do cofre tem um formato inválido.")
    validados = {}
    total = 0
    for relativo, conteudo in arquivos.items():
        if not isinstance(relativo, str) or "\\" in relativo or "\x00" in relativo:
            raise ValueError("O backup contém um caminho de nota inválido.")
        caminho = PurePosixPath(relativo)
        if caminho.is_absolute() or any(parte in {"", ".", ".."} for parte in caminho.parts):
            raise ValueError("O backup contém um caminho de nota inválido.")
        if relativo != ".obsidian/app.json" and caminho.suffix.casefold() != ".md":
            raise ValueError("O backup contém um arquivo que não é uma nota Markdown.")
        if any(not re.fullmatch(r"[^<>:\"|?*]+", parte) or parte.endswith((".", " ")) for parte in caminho.parts):
            raise ValueError("O backup contém um nome de arquivo incompatível com o Windows.")
        if not isinstance(conteudo, bytes):
            raise ValueError("O backup contém uma nota inválida.")
        if len(conteudo) > _MAX_BACKUP_BYTES or b"\x00" in conteudo:
            raise ValueError("O backup contém uma nota inválida ou grande demais.")
        try:
            texto = conteudo.decode("utf-8")
            if relativo == ".obsidian/app.json" and not isinstance(json.loads(texto), dict):
                raise ValueError
        except (UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("O backup contém uma nota ou configuração Obsidian inválida.") from exc
        total += len(conteudo)
        if total > _MAX_BACKUP_BYTES:
            raise ValueError("O backup do cofre ultrapassa 16 MB.")
        validados[caminho.as_posix()] = conteudo
    return validados


def restaurar_snapshot(arquivos: dict[str, bytes]) -> int:
    """Aplica as notas do backup com rollback em caso de erro, preservando notas extras."""
    validados = _validar_snapshot(arquivos)
    raiz = _preparar().resolve()
    preparados: dict[Path, bytes | None] = {}
    substituidos: list[Path] = []
    try:
        for relativo, conteudo in validados.items():
            destino = raiz.joinpath(*PurePosixPath(relativo).parts)
            destino.parent.mkdir(parents=True, exist_ok=True)
            atual = raiz
            for parte in PurePosixPath(relativo).parts[:-1]:
                atual = atual / parte
                if atual.is_symlink():
                    raise ValueError("O cofre contém um link simbólico em um caminho de restauração.")
            destino.resolve(strict=False).relative_to(raiz)
            if destino.is_symlink():
                raise ValueError("O cofre contém um link simbólico em um caminho de restauração.")
            anterior = destino.read_bytes() if destino.is_file() else None
            preparados[destino] = anterior
        for destino, conteudo in ((raiz.joinpath(*PurePosixPath(relativo).parts), conteudo) for relativo, conteudo in validados.items()):
            substituidos.append(destino)
            with destino.open("wb") as arquivo:
                arquivo.write(conteudo)
                arquivo.flush()
                os.fsync(arquivo.fileno())
    except Exception:
        for destino in reversed(substituidos):
            anterior = preparados[destino]
            if anterior is None:
                destino.unlink(missing_ok=True)
            else:
                with destino.open("wb") as arquivo:
                    arquivo.write(anterior)
                    arquivo.flush()
                    os.fsync(arquivo.fileno())
        raise
    return len(validados)
