# DeliveryBot Web — laboratório QA gratuito

Este serviço publica somente o catálogo e as páginas de pedidos, imagens, PDF, privacidade e minijogo. Ele reutiliza as funções do aplicativo, com banco separado e oito produtos fictícios com imagens de demonstração. A gestão, cozinha, WhatsApp, webhooks, IA, contas reais e terminal dos funcionários não são publicados.

## Render

- Repositório: https://github.com/cleryton/deliverybot-desktop
- Ambiente: Python 3.12.10; plano **Free**.
- Build: `pip install -r requirements-web.txt`.
- Iniciar: `gunicorn wsgi_qa:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 90`.
- Variável obrigatória: `QA_WEB_HABILITADO=SIM`.
- Verificação de saúde: `/healthz`.
- A origem HTTPS vem de `RENDER_EXTERNAL_URL`, definida pelo Render. Para outro provedor, defina `QA_BASE_URL`.
- Use apenas um processo Gunicorn. A chave de sessão é aleatória a cada início; `QA_SESSION_SECRET` opcional permite defini-la por variável secreta, nunca no Git.
- `render.yaml` registra a configuração gratuita, com publicação automática desligada. Ao configurar pela interface, selecione a branch validada e deixe a publicação manual.

A entrada não carrega `.env` e não usa a pasta de dados do desktop. O banco descartável fica em uma pasta temporária identificada como QA; uma pasta existente sem marcador é recusada. O modo WhatsApp é forçado para TESTE e as credenciais de envio são esvaziadas. O HTTP aceita somente o domínio HTTPS configurado. Apenas o protocolo encaminhado pelo proxy do Render é reconhecido; cabeçalhos de IP e de host encaminhado não concedem privilégios.

## Roteiro do grupo

1. Abra a URL pública e escolha **Iniciar pedido de teste**.
2. Teste busca, categorias, fotos, quantidades, cálculos e download do PDF.
3. Preencha nome e endereço fictícios. Para entrega, o CEP é consultado no ViaCEP, como no aplicativo; não utilize endereço pessoal.
4. Confirme o pedido e confira o recibo e o minijogo. A tela informa que nenhum WhatsApp foi enviado.
5. Volte ao início para outro pedido. O link anterior não confirma outro pedido.
6. Anote dispositivo, navegador, passos, resultado esperado/obtido e captura de tela de cada falha.

Após confirmar, **Imprimir ou salvar comprovante** abre a impressão do próprio navegador: escolha uma impressora ou Salvar como PDF. O comprovante identifica a loja, os itens, o total e a forma de recebimento; não tem valor fiscal nem comprova pagamento. O botão não envia dados a serviços externos e não reenvia o pedido. O jogo e os controles são ocultados na impressão.

A confirmação redireciona para o comprovante. Atualizar essa página não repete pedidos ou mensagens. Ele pode ser consultado por até oito horas no mesmo navegador; a sessão guarda até cinco autorizações. Abrir o endereço em outro navegador não libera a consulta. O link original de compra continua sendo de uso único. Reiniciar a hospedagem pode encerrar o acesso antes desse prazo; salve o PDF se precisar guardar o resultado.

Sessão expirada, link usado, página inexistente, excesso de tentativas e falha do serviço apresentam uma orientação com retorno ao início. Os códigos HTTP e os bloqueios continuam ativos; erros internos não exibem detalhes técnicos. Um link usado não deve ser reenviado para tentar repetir a mesma compra.

A página é pública, contém aviso de dados fictícios e solicita não indexação aos buscadores; não use dados pessoais nem senhas reais. Os dados de cada pedido não são expostos em listas ou painéis públicos. A confirmação HTTP usa CSRF. A geração de links e os pedidos têm limite global de 60 gravações por minuto, mil links e 500 pedidos por ciclo da instância, para conter consumo do laboratório. O estoque fictício começa com mil unidades por produto e não é redefinido a cada acesso.

## Limites do plano gratuito

Segundo a [documentação do Render](https://render.com/docs/free), a instância hiberna após 15 minutos sem tráfego, pode levar cerca de um minuto para reabrir e perde arquivos locais ao reiniciar, republicar ou hibernar. Portanto, pedidos QA e alterações de estoque são descartáveis. O catálogo e as imagens são recriados no próximo início. Não é um ambiente de produção e não depende do computador da loja ligado.

O plano inclui cotas de horas, tráfego e construção. Mantenha o serviço no plano Free e não habilite complementos pagos. Caso a plataforma solicite um cartão ou uma contratação, interrompa e reveja a configuração. Não há banco pago, disco persistente, SMS nem consumo de API Meta nesta publicação.

Os testes automatizados cobrem isolamento de rotas, dados e pasta; configuração sem credenciais de WhatsApp; catálogo e fotos; CSRF e origem; pedido/recibo; link de uso único; PDF; cabeçalhos, host e proxy HTTPS.
