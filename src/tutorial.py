"""Guias locais: explicam a configuração sem executar ações pelo usuário."""


def etapas(s):
    producao = s['modelo'] == 'PRODUCAO'
    servicos = s['modelo'] == 'SERVICOS'
    exemplo = ('Cadastre uma refeição com preço e categoria. Deixe a contagem desmarcada para prepará-la sob pedido.' if producao else
               'Cadastre um serviço com preço definido e unidade Serviço ou Hora. Orçamentos e agendamentos devem ser combinados com a equipe.' if servicos else
               'Cadastre um item com nome, categoria e preço. Adicione uma foto para o cliente reconhecer o produto.')
    itens = [
        ('comercio', 'Guia do negócio', 'Conte como seu comércio funciona', s['perfil'], False, 'comercio', [
            'Informe o nome, o segmento e uma descrição do que você oferece.',
            'Escolha revenda, produção sob pedido, serviços ou operação mista. Produção e serviços começam sem estoque obrigatório.',
            'Salve o perfil. Você pode controlar quantidades individualmente; os cadastros anteriores serão preservados.']),
        ('operacao', 'Guia do negócio', 'Defina as informações do atendimento', s['loja'], False, 'configuracoes', [
            'Informe o telefone, os horários e o endereço comercial.',
            'Confira formas de pagamento, entrega e tempo de preparo conforme sua operação.',
            'Salve as configurações. Use apenas informações que seu comércio consegue cumprir.']),
        ('catalogo', 'Guia do catálogo', 'Monte seu catálogo', s['produtos'], False, 'produtos', [
            exemplo,
            'Ative a contagem somente nos itens que precisam dela, como bebidas prontas ou peças. Um item controlado com saldo zero fica indisponível.',
            'Salve e mantenha o item ativo. PDFs e planilhas podem ser importados após conferir a prévia.']),
        ('privacidade', 'Guia de privacidade', 'Identifique o responsável pelos dados', s['privacidade'], False, 'privacidade', [
            'Informe a empresa responsável e um contato para solicitações sobre dados pessoais.',
            'Revise os prazos das conversas e pedidos de acordo com a política da sua loja.',
            'Salve e confira o aviso aos clientes. Estes campos não substituem a revisão das suas práticas de privacidade.']),
        ('whatsapp', 'Guia de conexão', 'Conecte seu WhatsApp', s['operacao']['whatsapp_ok'], False, 'conexoes', [
            'No aplicativo Desktop, abra WhatsApp e IA e use Conectar WhatsApp. Acompanhe a preparação dos serviços.',
            'No celular, abra WhatsApp → Aparelhos conectados → Conectar um aparelho e leia o QR Code quando aparecer.',
            'Aguarde o estado conectado. O modo de teste não envia mensagens; mantenha o aplicativo aberto e o computador ligado.']),
        ('ia', 'Guia de atendimento', 'Personalize as respostas', None, True, 'conexoes', [
            'Você pode começar com o menu sem inteligência artificial.',
            'Para usar Ollama, acompanhe a preparação em WhatsApp e IA e confira se o modelo está pronto. A primeira preparação pode demorar.',
            'Para ajustar o estilo, use o cofre do Obsidian em WhatsApp e IA e consulte Início.md. Teste as respostas em Testar atendimento antes de usar com clientes.']),
        ('pagina', 'Guia dos pedidos', 'Prepare o endereço dos clientes', s['endereco_publico'], False, 'publicacao', [
            'Abra Página de pedidos e acompanhe o estado do endereço HTTPS.',
            'Para começar, use o endereço temporário. Ele muda ao reiniciar o túnel; para uso diário, siga o assistente de domínio fixo.',
            'Um endereço configurado ainda precisa ser testado de fora do computador. Compartilhe apenas o link público HTTPS.']),
        ('teste', 'Guia dos pedidos', 'Confira pelo celular', s['abertura_recebida'], False, 'inicio', [
            'Na Visão geral, clique em Gerar teste para abrir no celular. Esse teste de acesso não cria um pedido nem envia WhatsApp.',
            'Desligue o Wi-Fi do celular e abra o link usando dados móveis. Depois clique em Atualizar status.',
            'A abertura recebida confirma um acesso ao endereço atual. Confira também o catálogo e simule o atendimento; pedidos de teste reais devem ser cancelados depois.']),
    ]
    return [dict(id=id_, agente=agente, titulo=titulo, concluida=ok, opcional=opcional,
                 pagina=pagina, instrucoes=instrucoes) for id_, agente, titulo, ok, opcional, pagina, instrucoes in itens]
