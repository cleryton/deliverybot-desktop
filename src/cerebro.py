"""Cofre local e curado de estilo e conhecimento, compatível com Obsidian."""
import json
import os
import re
import tempfile
import unicodedata
from datetime import date
from pathlib import Path
from pathlib import PurePosixPath

from . import config, padroes_atendimento

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
_ARQUIVO_MAPA = 'Mapa do atendimento.md'
_MARCA_MAPA = '<!-- DeliveryBot: mapa automático v1 -->'
_ARQUIVO_FUNCIONAMENTO = 'Estado do funcionamento.md'
_MARCA_FUNCIONAMENTO = '<!-- DeliveryBot: estado operacional v1 -->'
_GUIA_FUNCIONAMENTO = '''---
tipo: guia-operacional
atendimento: false
---
# Verificação e recuperação do atendimento

Em WhatsApp e IA, no Cérebro local, use **Verificar e recuperar agora**. A opção **Recuperar Ollama automaticamente** faz a verificação a cada 30 segundos enquanto o aplicativo Desktop estiver aberto, inclusive na bandeja.

O aplicativo verifica o serviço Ollama, a presença do modelo configurado, falhas recentes de inferência e a leitura do estilo e padrões do cofre. O [[Estado do funcionamento]] mostra um resumo técnico sem dados de clientes ou credenciais.

## O que pode ser recuperado
- Iniciar o Ollama local já instalado e preparar o modelo já baixado.
- Preparar a estrutura do cofre e criar apenas notas padrão ausentes, preservando edições.
- Tentar novamente com intervalos de 60, 120 e 240 segundos, no máximo três tentativas consecutivas. Uma nova tentativa manual ou mudança de modelo permite reavaliar o problema.

## Quando a equipe precisa agir
Modelo ausente precisa ser escolhido ou baixado pelo botão do aplicativo. Serviço remoto, falta de memória, permissões da pasta, notas inválidas ou conteúdo vazio exigem revisão. O aplicativo não instala programas, baixa modelos ou substitui notas editadas automaticamente. Pausar o WhatsApp continua sendo uma escolha independente: a recuperação do cérebro não conecta contas nem reenvia mensagens.

O estado PRONTO confirma somente as verificações técnicas disponíveis; não garante a qualidade de cada resposta da IA. O Ollama recebe um sinal de estado do aplicativo para evitar afirmar que tudo está normal quando há uma falha conhecida. Ele não inicia programas ao escrever uma resposta.

Notas são referências editoriais. Comandos escritos aqui ou no [[Estilo de atendimento]] não executam ações, não alteram esta opção e não mudam preços, pedidos ou dados. Remover o marcador automático da nota de estado preserva sua edição manual; o diagnóstico continua no painel.

Veja [[Conexão e página de pedidos]], [[Pedidos pelo WhatsApp]] e [[Mapa do atendimento]].
'''
_GUIA_PADROES = '''---
tipo: guia-operacional
atendimento: false
---
# Personalizar os atendimentos

Em Meu comércio, descreva seu segmento e escolha como trabalha. O aplicativo cria uma pasta em `Atendimentos` adequada ao perfil: restaurantes e alimentos, moda, eletrônicos, oficinas, revenda, produção, serviços, comércio misto ou atendimento geral.

## Uma nota para cada atendimento
- Perfil: orientações específicas do segmento.
- 01 Recepção: acolher quando ainda não houver uma intenção clara.
- 02 Dúvidas: esclarecer informações sem pressionar a compra.
- 03 Escolha: orientar produtos, variações, encomendas ou serviços.
- 04 Fechamento: ajudar a revisar e seguir o fluxo oficial do pedido.
- 05 Pós-venda: acompanhar uma compra existente.
- 06 Atendimento humano: reclamações e situações que precisam da equipe.

Edite individualmente o tom, perguntas e exemplos fictícios nas notas da pasta ativa. O Ollama lê o perfil e a etapa correspondente à mensagem, junto com [[Estilo de atendimento]] e o conhecimento aprovado. Não envia todas as etapas ou segmentos de uma vez. A seleção da etapa é uma orientação editorial aproximada; as operações da loja continuam no aplicativo.

## Revisão e preservação
As edições entram na próxima resposta, sem treinar pesos da rede neural. Mude `atendimento: true` para `atendimento: false` para suspender uma nota. Opcionalmente, adicione `valido_ate: AAAA-MM-DD` para limitar sua validade. Preserve `categoria_atendimento` e `etapa_atendimento`: uma nota com identificação incorreta não entra no contexto.

Se o perfil da loja mudar, outra pasta será preparada. As edições antigas são preservadas e ficam fora do atendimento da nova categoria. O painel WhatsApp e IA mostra a categoria ativa e permite ler suas notas. O [[Mapa do atendimento]] conecta os padrões ativos no Obsidian Graph.

Não copie conversas, nomes, telefones, endereços ou pedidos de clientes. Não invente preços, descontos, disponibilidade, ingredientes, compatibilidade, prazos ou reservas. Notas orientam a escrita; [[Pedidos pelo WhatsApp]] e [[Conexão e página de pedidos]] explicam ações executadas pelo aplicativo.
'''

_NOTAS_INICIAIS = {
    "Início.md": """---
tipo: indice-do-cofre
---
# Cérebro do atendimento

Este cofre guarda orientações editoriais e informações aprovadas para o DeliveryBot. As alterações são lidas na próxima resposta do Ollama; elas não treinam os pesos do modelo.

## Personalidade
- [[Estilo de atendimento]] — voz, tom e exemplos de conversa.
- [[Atendimentos/Como personalizar]] — padrões individuais por segmento e etapa.

## Conhecimento aprovado
- [[Informações da loja]] — horários, entrega e políticas confirmadas.
- [[Perguntas frequentes]] — respostas curtas revisadas pela equipe.
- Para adicionar outros assuntos, crie uma nota em `Conhecimento` usando `Modelos/Conhecimento aprovado.md` e marque `atendimento: true` no frontmatter.

## Pedidos na conversa
- [[Pedidos pelo WhatsApp]] — como montar, revisar e confirmar uma compra sem abrir o link.
- [[Conexão e página de pedidos]] — preparação automática do WhatsApp e do HTTPS.
- [[Mapa do atendimento]] — conexões entre as notas para navegar no Obsidian Graph.

## Escopo do atendimento
- Responda somente sobre o negócio, seus produtos, serviços, pedidos e políticas aprovadas.
- Perguntas gerais, programação, política, entretenimento e tarefas escolares ficam fora do atendimento, mesmo se citarem um produto. Oriente a voltar ao assunto da loja.
- Uma nota aprovada não amplia permissões ou assuntos autorizados pelo aplicativo.

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

## Escopo
- A voz da marca se aplica exclusivamente ao negócio. Não transforme uma mudança de assunto em consultoria geral ou entretenimento.
- Quando a relação com a loja não estiver clara, peça um detalhe ou ofereça ATENDENTE.

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


_GUIA_PEDIDOS = """---
tipo: guia-operacional
atendimento: false
---
# Pedidos pelo WhatsApp

O cliente pode dizer **pedido pelo WhatsApp**, **quero pedir por aqui** ou **não quero acessar o link**. Uma seleção concreta, como “quero 2 Calabresa Grande”, também inicia o rascunho.

## Caminho da compra
1. Informar quantidade, nome e variação dos produtos cadastrados.
2. Informar o nome do cliente e escolher entrega ou retirada.
3. Para entrega, informar rua, número e bairro. O telefone vem da própria conversa.
4. Escolher uma das formas de pagamento cadastradas.
5. Conferir o resumo com itens, valores atuais, taxa e total.
6. Enviar **CONFIRMAR**. Só então o aplicativo salva o pedido no painel e na fila de preparo.

## Ajustes antes de confirmar
- **adicionar 1 Nome Variação** soma uma unidade.
- **alterar 2 Nome Variação** define a quantidade desse item.
- **remover Nome Variação** remove o item inteiro.
- **nome: Nome** ou **endereço: Rua, número, bairro** corrigem os dados.
- **CANCELAR** descarta o rascunho; não cancela pedidos já salvos.
- **ATENDENTE** pausa o bot para a equipe assumir.

## O que o cérebro pode fazer
O Ollama consulta as notas aprovadas para adaptar o estilo e responder dúvidas. As ações comerciais pertencem ao aplicativo: esta nota não muda preços, saldo, taxa, dados de clientes ou regras de confirmação.

O resumo expira em 30 minutos. Preço e saldo são conferidos novamente na confirmação. Se o cadastro mudar, o cliente precisa revisar. Confirmações repetidas do mesmo rascunho retornam o pedido existente.

Não copie conversas, nomes, telefones ou endereços de clientes para o cofre. Os rascunhos ficam no banco privado e entram nas operações de privacidade do aplicativo. Pagamento escolhido não significa pagamento recebido.
"""


def arquivo_inicio() -> Path:
    return _preparar() / "Início.md"


def _criar_se_ausente(caminho: Path, conteudo: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    try:
        with caminho.open("x", encoding="utf-8", newline="\n") as destino:
            destino.write(conteudo)
    except FileExistsError:
        pass


def _preparar(*, sincronizar_mapa=True) -> Path:
    pasta = diretorio()
    categoria = padroes_atendimento.categoria()
    padroes = pasta / 'Atendimentos' / padroes_atendimento.PERFIS[categoria][0]
    for caminho in (pasta, pasta/'Conhecimento', pasta/'Modelos', pasta/'.obsidian', pasta/'Atendimentos', padroes):
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
    _criar_se_ausente(pasta / 'Atendimentos/Como personalizar.md', _GUIA_PADROES)
    _criar_se_ausente(pasta / 'Verificação e recuperação do atendimento.md', _GUIA_FUNCIONAMENTO)
    _criar_se_ausente(pasta / _ARQUIVO_FUNCIONAMENTO, '---\ntipo: estado-operacional\natendimento: false\n---\n' + _MARCA_FUNCIONAMENTO + '\n# Estado do funcionamento\n\nAguardando a verificação pelo aplicativo Desktop. Consulte [[Verificação e recuperação do atendimento]].\n')
    for nome, conteudo in padroes_atendimento.arquivos(categoria).items():
        _criar_se_ausente(padroes / nome, conteudo)
    _criar_se_ausente(pasta / 'Pedidos pelo WhatsApp.md', _GUIA_PEDIDOS)
    _criar_se_ausente(pasta / 'Continuidade do atendimento humano.md', '''---
tipo: guia-operacional
atendimento: false
---
# Continuidade do atendimento humano

Em Atendimento humano, abra a conversa e escolha Assumir antes de enviar uma resposta manual. Confirme cada envio ao cliente. Durante a pausa, mensagens novas recebidas pelo aplicativo ficam no histórico privado da equipe sem esperar o bot ou o envio WhatsApp. Atualizar renova também a conversa aberta.

Ao assumir, entradas automáticas pendentes são preservadas para a equipe e retiradas da fila. Mensagens recebidas durante a pausa não são reproduzidas quando o bot retorna nem entram no contexto da IA. PRIVACIDADE continua com resposta local.

Se aparecer um aviso de envios automáticos para conferir, a equipe pode continuar respondendo manualmente. Antes de Retomar bot, confira em WhatsApp e IA se a mensagem já chegou e resolva a pendência. Não reenvie sem essa conferência. Envios incertos são preservados e a ordem dos envios manuais continua sendo respeitada. Um envio em andamento impede a troca de atendimento.

Uma pausa de segurança exige também revisão administrativa. Consulte [[Proteção das conversas com IA]], [[Segurança dos funcionários]] e [[Mapa do atendimento]]. Esta nota é apenas orientação; não autoriza operações. Não copie dados ou mensagens de clientes para o cofre.
''')
    _criar_se_ausente(pasta / 'Proteção das conversas com IA.md', '''---
tipo: guia-operacional
atendimento: false
---
# Proteção das conversas com IA

O aplicativo pausa somente a conversa com sinais explícitos de alteração das regras, extração de credenciais ou dados internos, comandos privilegiados, mais de trinta mensagens por minuto ou seis repetições consecutivas de texto com pelo menos doze caracteres. Reentrega do mesmo evento não soma tentativas. Perguntas normais sobre produtos, pagamento, suporte e senha do Wi-Fi não são bloqueadas por palavras isoladas.

As regras são verificadas antes da IA, das respostas rápidas e dos pedidos pela conversa. A saída também é verificada antes do envio: credenciais configuradas, estrutura do prompt interno e resposta anterior a uma pausa são descartadas. Uma inferência já iniciada pode terminar, mas sua resposta fica impedida de sair mesmo se a equipe já tiver liberado a conversa. O serviço Ollama continua disponível para outros contatos.

## Revisar com uma pessoa
Em Atendimento humano, veja o motivo da pausa e abra a conversa. Mensagens recebidas durante a proteção ficam no histórico privado para a equipe, mas não são usadas como contexto do modelo. O funcionário pode assumir e responder manualmente pelos controles existentes. Somente o administrador pode confirmar Revisar e liberar IA. Depois, a equipe decide quando Retomar bot. Liberar não reenvia respostas canceladas nem aprova instruções suspeitas.

PRIVACIDADE e LGPD continuam com resposta local durante o bloqueio. As informações de proteção entram na exportação verificada do titular e na remoção da identificação. Não copie contatos, mensagens suspeitas ou credenciais para o cofre. Esta nota explica os controles; editá-la não desbloqueia conversas.

As regras detectam sinais conhecidos e podem exigir revisão de um caso legítimo. Não cobrem todas as variações, idiomas, conteúdos codificados ou ataques indiretos; não substituem a validação das ferramentas e permissões. Envios já iniciados não podem ser desfeitos e permanecem disponíveis para conferência na fila.

Consulte [[Segurança dos funcionários]], [[Pedidos pelo WhatsApp]] e [[Mapa do atendimento]].
''')
    _criar_se_ausente(pasta / 'Segurança dos funcionários.md', '''---
tipo: guia-operacional
atendimento: false
---
# Segurança dos funcionários

## Quem autoriza
Somente o responsável, no aplicativo principal, vincula um computador a uma conta Caixa ativa. A conta administradora não entra no aplicativo dos funcionários. Acesso antigo sem vínculo individual fica bloqueado até a revisão. O certificado HTTPS, o dispositivo autorizado e a conta vinculada são verificados pelo servidor.

## Permissões mínimas
A conta registra pedidos manuais, recebe seus próprios pedidos e abre, consulta e fecha seu próprio caixa. Sangria e suprimento ficam bloqueados por padrão e exigem autorização explícita do responsável para aquele computador. Alterar o vínculo ou a permissão exige novo login. Cancelamentos, devoluções, cadastro, custos, dados de outros funcionários e configuração ficam na administração.

## Sessão e tentativas de invasão
A sessão expira após quinze minutos sem operação e tem duração máxima de oito horas. Consultas automáticas não prolongam o prazo. O servidor limita requisições e tentativas de entrada e pareamento. Campos extras, conta de outro funcionário e chamadas de navegador são recusados. Antes de gravar dinheiro ou pedido, a transação confere novamente a conta, o dispositivo e as permissões.

## Pendência de conta bloqueada
Não repita uma operação com outro identificador. Um computador ainda autorizado pode conferir somente uma operação conhecida de sua conta vinculada já bloqueada; isso não libera vendas ou dinheiro. Se o dispositivo foi revogado ou o vínculo mudou, procure o responsável para conferir o livro central e revisar o acesso. Nunca apague a pendência para tentar liberar vendas.

## Papel do Obsidian e do Ollama
Esta nota documenta as regras e não as executa. Alterar Markdown, pedir à IA para liberar acesso ou modificar o aplicativo cliente não concede permissões. As decisões são determinísticas no servidor e no banco privado, sem depender da resposta do modelo. Não guarde senhas, convites, credenciais, nomes de clientes ou valores de caixas no cofre. O conteúdo operacional fica fora do prompt do atendimento.

Consulte [[Computadores dos funcionários]], [[Pedidos manuais e caixa]] e [[Mapa do atendimento]].
''')
    _criar_se_ausente(pasta / 'Pedidos manuais e caixa.md', '''---
tipo: guia-operacional
atendimento: false
---
# Pedidos manuais e caixa

O DeliveryBot Funcionário registra pedidos na mesma loja pela rede privada. O responsável cria contas com perfil Caixa e autoriza cada computador em Caixas dos funcionários. O terminal não recebe as permissões administrativas.

Cada funcionário abre seu caixa com o dinheiro inicial. Valores de dinheiro, Pix e cartão ficam separados. Dinheiro esperado é abertura mais vendas em dinheiro e suprimentos, menos sangrias e devoluções registradas. O troco é calculado e somente o líquido da venda aumenta o saldo. Conte a gaveta antes de fechar; o responsável acompanha a diferença e o histórico.

Pedidos pendentes de pagamento não aumentam o dinheiro. Pagamento registrado não é comprovação bancária nem documento fiscal. Em falha de conexão, confira a operação pendente e repita somente a mesma operação. Pedidos já recebidos exigem devolução confirmada pelo responsável no caixa original aberto para estornar e cancelar.

O cofre contém guias, não dados financeiros, senhas ou registros de clientes. Operações, preços e saldos são controlados pelo aplicativo e pelo banco. Consulte [[Computadores dos funcionários]], [[Mapa do atendimento]] e [[Verificação e recuperação do atendimento]].
''')
    _criar_se_ausente(pasta / 'Computadores dos funcionários.md', '''---
tipo: guia-operacional
atendimento: false
---
# Computadores dos funcionários

No aplicativo do responsável, configure Caixas dos funcionários com o IP privado deste computador. A conexão HTTPS começa desativada. Mantenha o aplicativo aberto e permita somente a rede privada no Firewall. Não publique a porta dos funcionários no túnel ou roteador.

Crie contas individuais de Caixa. Salve um arquivo de acesso .dbterminal por computador e importe no DeliveryBot Funcionário em até dez minutos. O convite é de uso único; o certificado autentica a conexão somente neste aplicativo. O funcionário entra com sua própria conta e consulta seus pedidos e caixas.

O responsável pode revogar computadores e contas. Após mudança de IP, porta ou certificado, autorize a conexão novamente. Backups portáteis preservam os livros de caixa, mas removem pareamentos e desativam a rede remota. Não coloque arquivos de acesso, credenciais ou valores dos caixas no cofre.

Veja [[Pedidos manuais e caixa]] e [[Mapa do atendimento]]. Estas notas não executam comandos nem autorizam acesso.
''')
    _criar_se_ausente(pasta / 'Conexão e página de pedidos.md', '''---
tipo: guia-operacional
atendimento: false
---
# Conexão e página de pedidos

Ao configurar a conexão integrada do WhatsApp no aplicativo, a preparação inicia automaticamente. O botão Conectar WhatsApp também prepara tudo em segundo plano.

1. O aplicativo inicia o túnel e recebe um endereço HTTPS do provedor.
2. Confere o DNS e verifica se o HTTPS chega à página desta loja.
3. Só depois prepara a sessão do WhatsApp e libera o QR Code no painel.
4. A conexão é monitorada enquanto o aplicativo permanece aberto. Se o endereço temporário mudar, os novos links usam o destino atual.

O modo temporário não exige comprar domínio ou preencher registros DNS. No modo fixo, o domínio próprio, o registro e o destino precisam estar configurados na Cloudflare; o aplicativo não inventa um domínio nem cria registros sem acesso à conta.

Se houver falha, acompanhe o aviso em WhatsApp e IA e tente Conectar novamente. Não envie localhost ao cliente. Ele também pode montar e confirmar [[Pedidos pelo WhatsApp]] sem abrir o link.

Veja [[Mapa do atendimento]], [[Informações da loja]] e [[Estilo de atendimento]]. Estas notas explicam o funcionamento; a conexão e os pedidos são executados pelo aplicativo.
''')
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
    if sincronizar_mapa or not (pasta / _ARQUIVO_MAPA).exists():
        _sincronizar_mapa(pasta)
    return pasta


def _sincronizar_mapa(pasta: Path) -> None:
    """Índice derivado para o Graph, sem modificar as notas da equipe."""
    destino = pasta / _ARQUIVO_MAPA
    if destino.is_symlink() or (hasattr(destino, 'is_junction') and destino.is_junction()):
        return
    try:
        anterior = destino.read_text(encoding='utf-8') if destino.exists() and destino.stat().st_size <= _MAX_LEITURA_NOTA else ''
        if destino.exists() and _MARCA_MAPA not in anterior:
            return  # A equipe assumiu a edição deste mapa.
        grupos = {
            'Voz e informações da loja': [pasta / n for n in _NOTAS_INICIAIS],
            'Operação no aplicativo': [pasta / 'Pedidos pelo WhatsApp.md', pasta / 'Pedidos manuais e caixa.md', pasta / 'Computadores dos funcionários.md', pasta / 'Segurança dos funcionários.md', pasta / 'Continuidade do atendimento humano.md', pasta / 'Proteção das conversas com IA.md', pasta / 'Conexão e página de pedidos.md', pasta / 'Verificação e recuperação do atendimento.md', pasta / _ARQUIVO_FUNCIONAMENTO],
            'Modelos para revisão': [pasta / 'Modelos/Conhecimento aprovado.md', pasta / 'Modelos/Lista de estoque.md'],
            'Conhecimento revisado': _notas_aprovadas(pasta),
            'Padrões de atendimento ativos': [pasta / 'Atendimentos/Como personalizar.md', *_padroes_aprovados(pasta)],
        }
        linhas = ['---', 'tipo: mapa-do-cofre', 'atendimento: false', '---', _MARCA_MAPA,
                  '# Mapa do atendimento', '',
                  'Mapa atualizado pelo aplicativo. Edite as notas de origem para mudar o atendimento. As linhas no Obsidian Graph representam links entre notas, não treinamento do modelo.', '']
        vistos = set()
        for titulo, caminhos in grupos.items():
            links = []
            for caminho in caminhos:
                relativo = caminho.relative_to(pasta).with_suffix('').as_posix()
                if relativo in vistos or re.search(r'[\[\]|#^\r\n]', relativo) or not _ler(caminho)[1]:
                    continue
                vistos.add(relativo)
                links.append(f'- [[{relativo}]]')
            if links:
                linhas.extend(['## ' + titulo, *links, ''])
        conteudo = '\n'.join(linhas)
        if conteudo != anterior:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=pasta, suffix='.tmp', delete=False) as arquivo:
                temporario = Path(arquivo.name)
                arquivo.write(conteudo)
            try:
                os.replace(temporario, destino)
            finally:
                temporario.unlink(missing_ok=True)
    except OSError:
        pass  # Um cofre aberto somente para leitura não interrompe o bot.


def arquivo_estilo() -> Path:
    return _preparar() / _ARQUIVO_ESTILO


def arquivo_funcionamento() -> Path:
    return _preparar() / _ARQUIVO_FUNCIONAMENTO


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
    _, estilo = _ler(pasta / _ARQUIVO_ESTILO)
    categoria = padroes_atendimento.categoria()
    padroes = _padroes_aprovados(pasta)
    ativos = bool(estilo) + len(_notas_aprovadas(pasta)) + len(padroes)
    return {
        "pasta": str(pasta),
        "arquivo": str(pasta / 'Início.md'),
        "cofre_obsidian": True,
        "notas_contexto": ativos,
        "consulta_por_assunto": True,
        "limite_contexto": _LIMITE_TOTAL,
        "atendimento": {"categoria": categoria, "titulo": padroes_atendimento.PERFIS[categoria][0], "padroes": len(padroes)},
    }


def _remover_frontmatter(conteudo: str) -> tuple[str, str]:
    bloco = re.match(r"\A\ufeff?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", conteudo, re.DOTALL)
    return (bloco[1], conteudo[bloco.end():]) if bloco else ("", conteudo)


def verificar_funcionamento() -> dict:
    """Diagnóstico de leitura; não cria nem corrige o conteúdo das notas."""
    pasta = diretorio()
    categoria = padroes_atendimento.categoria()
    perfil = pasta / 'Atendimentos' / padroes_atendimento.PERFIS[categoria][0]
    for caminho in (pasta, pasta/'Conhecimento', pasta/'Atendimentos', perfil, pasta/_ARQUIVO_ESTILO):
        if caminho.is_symlink() or (hasattr(caminho, 'is_junction') and caminho.is_junction()):
            return {'estado': 'ERRO', 'mensagem': 'O cofre contém um vínculo que precisa ser revisado pela equipe.'}
    if not pasta.exists() or not (pasta/_ARQUIVO_ESTILO).exists() or not perfil.exists():
        return {'estado': 'AUSENTE', 'mensagem': 'A estrutura do cofre ainda não está preparada.'}
    _, estilo = _ler(pasta/_ARQUIVO_ESTILO)
    if not estilo:
        return {'estado': 'REVISAO', 'mensagem': 'O estilo está vazio ou não pôde ser lido. Revise a nota sem substituir suas edições.'}
    return {'estado': 'PRONTO', 'mensagem': 'Estilo legível e cofre disponível.', 'padroes': len(_padroes_aprovados(pasta))}


def registrar_funcionamento(dados: dict) -> None:
    """Nota derivada do aplicativo. Não aceita textos livres nem ordens da IA."""
    pasta = diretorio()
    if not pasta.is_dir() or pasta.is_symlink() or (hasattr(pasta, 'is_junction') and pasta.is_junction()):
        return
    destino = pasta/_ARQUIVO_FUNCIONAMENTO
    if destino.is_symlink() or (hasattr(destino, 'is_junction') and destino.is_junction()):
        return
    anterior = ''
    if destino.exists():
        if destino.stat().st_size > _MAX_LEITURA_NOTA:
            return
        anterior = destino.read_text(encoding='utf-8')
        if _MARCA_FUNCIONAMENTO not in anterior:
            return
    estados_ol = {'NAO_SELECIONADO':'Não selecionado', 'PREPARANDO':'Em preparação', 'DESLIGADO':'Não respondeu', 'SEM_MODELO':'Modelo ausente', 'FALHA':'Falha de preparação ou inferência', 'FALHA_RECENTE':'Falha recente de inferência', 'DISPONIVEL':'Serviço e modelo disponíveis'}
    estados_cofre = {'PRONTO':'Leitura disponível', 'AUSENTE':'Estrutura ausente', 'REVISAO':'Nota de estilo precisa de revisão', 'ERRO':'Acesso ao cofre precisa de revisão'}
    estado_ol = estados_ol.get(dados.get('ollama',{}).get('estado'), 'Ainda não verificado')
    estado_cofre = estados_cofre.get(dados.get('cofre',{}).get('estado'), 'Ainda não verificado')
    automatico = 'Ativada' if dados.get('automatico') is True else 'Desativada'
    supervisao = 'Em execução no Desktop' if dados.get('disponivel') is True else 'Encerrada ou indisponível'
    tentativas = dados.get('tentativas', 0)
    tentativas = tentativas if type(tentativas) is int and 0 <= tentativas <= 3 else 0
    conteudo = ('---\ntipo: estado-operacional\natendimento: false\n---\n' + _MARCA_FUNCIONAMENTO
                + '\n# Estado do funcionamento\n\nOllama: ' + estado_ol + '.\n\nCofre Obsidian: ' + estado_cofre
                + '.\n\nVerificação: ' + supervisao + '.\n\nRecuperação automática: ' + automatico + f'. Tentativas consecutivas: {tentativas} de 3.\n\n'
                + 'Resumo técnico atualizado pelo aplicativo. Não avalia a qualidade das respostas e não executa comandos. '
                + 'Use [[Verificação e recuperação do atendimento]] e acompanhe a verificação atual em WhatsApp e IA.\n')
    if conteudo == anterior:
        return
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=pasta, suffix='.tmp', delete=False) as arquivo:
        temporario = Path(arquivo.name)
        arquivo.write(conteudo)
    try:
        os.replace(temporario, destino)
    finally:
        temporario.unlink(missing_ok=True)


def visualizacao() -> dict:
    """Mostra notas editoriais ao administrador; nunca documentos de estoque."""
    pasta = _preparar()
    caminhos = [pasta/n for n in (*_NOTAS_INICIAIS, 'Pedidos pelo WhatsApp.md', 'Pedidos manuais e caixa.md', 'Computadores dos funcionários.md', 'Segurança dos funcionários.md', 'Continuidade do atendimento humano.md', 'Proteção das conversas com IA.md', 'Conexão e página de pedidos.md', 'Verificação e recuperação do atendimento.md', _ARQUIVO_FUNCIONAMENTO, _ARQUIVO_MAPA)]
    # Mostra os padrões antes do conhecimento extra para não ocultá-los no limite.
    padroes = _padroes_aprovados(pasta)
    caminhos.extend([pasta / 'Atendimentos/Como personalizar.md', *padroes, *_notas_aprovadas(pasta)])
    notas, vistos = [], set()
    for caminho in caminhos:
        nome = caminho.relative_to(pasta).as_posix()
        if nome in vistos:
            continue
        vistos.add(nome)
        metadados, corpo = _ler(caminho)
        if caminho in padroes and not _aprovada(metadados):
            continue
        if corpo:
            notas.append({'nome':nome,'conteudo':corpo,'uso': 'Estilo' if caminho.name==_ARQUIVO_ESTILO else 'Contexto aprovado' if _aprovada(metadados) else 'Guia; não enviado ao modelo'})
        if len(notas)>=32:
            break
    return {'pasta':str(pasta),'notas':notas}


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
    for caminho in candidatas:
        if caminho.is_symlink() or not caminho.is_file():
            continue
        # _ler valida raiz, componentes e destino antes de abrir o arquivo.
        # Repetir resolve aqui acrescentava acesso ao disco sem outra proteção.
        metadados, corpo = _ler(caminho)
        if corpo and _aprovada(metadados):
            aprovadas.append(caminho)
    return aprovadas


def _padroes_aprovados(pasta: Path, etapa: str | None = None) -> list[Path]:
    """Somente arquivos conhecidos do perfil ativo, com identificação e revisão válidas."""
    categoria = padroes_atendimento.categoria()
    base = pasta / 'Atendimentos' / padroes_atendimento.PERFIS[categoria][0]
    esperados = {'Perfil.md': 'perfil', **{dados[0]: slug for slug, dados in padroes_atendimento.ETAPAS.items()}}
    aprovados = []
    for nome, esperado in esperados.items():
        if etapa is not None and esperado not in {'perfil', etapa}:
            continue
        caminho = base / nome
        metadados, corpo = _ler(caminho)
        if (corpo and _aprovada(metadados)
                and _metadado(metadados, 'categoria_atendimento') == categoria
                and _metadado(metadados, 'etapa_atendimento') == esperado):
            aprovados.append(caminho)
    return aprovados


def instrucoes_estilo() -> str:
    """Mantém uma API simples para leitores que precisam somente da voz."""
    _, conteudo = _ler(arquivo_estilo())
    return conteudo


def instrucoes_contexto(pergunta: str = '') -> str:
    """Seleciona conhecimento aprovado pelo assunto; nunca grava a pergunta no cofre."""
    # O Graph é uma visão derivada, atualizada ao abrir o cofre/leitor/estado.
    # As notas continuam sendo relidas e revalidadas em cada resposta.
    pasta = _preparar(sincronizar_mapa=False)
    secoes = []
    _, estilo = _ler(pasta / _ARQUIVO_ESTILO)
    if estilo:
        secoes.append(("Estilo de atendimento", estilo))
    selecionada = padroes_atendimento.etapa(pergunta)
    for caminho in _padroes_aprovados(pasta, selecionada):
        # Revalida após a seleção: uma edição/revogação pode ocorrer entre leituras.
        metadados, corpo = _ler(caminho)
        categoria = padroes_atendimento.categoria()
        esperado = 'perfil' if caminho.name == 'Perfil.md' else selecionada
        if (corpo and _aprovada(metadados)
                and _metadado(metadados, 'categoria_atendimento') == categoria
                and _metadado(metadados, 'etapa_atendimento') == esperado):
            secoes.append((caminho.relative_to(pasta).as_posix(), corpo))
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
