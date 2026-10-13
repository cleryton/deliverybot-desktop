# Marca DeliveryBot

A opção 3 foi escolhida pelo usuário: uma caixa combinada com um balão de conversa, representando pedidos e atendimento de comércios de diferentes categorias.

`web/static/marca.svg` é a fonte vetorial final. Mantém faces em verde esmeralda, verde intermediário e menta, com espaços transparentes. O nome DeliveryBot permanece como texto da interface, para acompanhar escala, acessibilidade e tema. A marca aparece no painel, no login e no terminal do funcionário; uma base clara preserva o contraste também no tema escuro.

Execute `python packaging/criar_icone.py` depois de editar a fonte. O comando sincroniza a cópia incluída no terminal e gera `packaging/DeliveryBot.ico` nas resoluções 16, 24, 32, 48, 64, 128 e 256 pixels. O aplicativo e os instaladores usam o mesmo ícone. Os testes conferem os recursos distribuídos e a transparência das faces em todas as resoluções.

## Exploração visual

`opcao-3.png` guarda a proposta aprovada. Foi gerada pelo recurso de imagens integrado, com este pedido: “DeliveryBot: símbolo de uma caixa que se combina com um balão de conversa, verde esmeralda e menta, nome DeliveryBot abaixo, apresentação clara e simples, sem restringir a marca a alimentos”. A fonte vetorial é a adaptação final para distribuição; a proposta não é carregada pelo aplicativo.

Prompt original da proposta aprovada:

> Use case: logo-brand. Design a polished original logo proposal for Brazilian app DeliveryBot, a professional general-commerce desktop app for customer service, product catalogues and orders. Standalone square pale ivory presentation. Concept THREE: a minimal compact isometric parcel/order box cleverly merging with the outline of a speech bubble, constructed from three broad solid geometric planes with strong negative space, not a detailed illustration. Avoid suggesting only food delivery. Elegant, memorable, balanced, readable when reduced to small Windows application icon. Emerald green #187D64 with mint green second plane, charcoal text. Large emblem centered upper-middle, exact wordmark "DeliveryBot" beneath in confident contemporary sans-serif. Flat vector-like shapes, no photorealism, no shadow, no glow, no gradient, no 3D rendering, no other brand marks, no watermark, no slogan. Generous whitespace and small numeral "3" top-left. Make the emblem distinct from a generic cardboard box clipart.
