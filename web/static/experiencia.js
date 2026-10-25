/* Regras de interface locais, sem persistir dados de formulários ou clientes. */
(function(root, factory) {
  const helpers = factory();
  if (typeof module === 'object' && module.exports) module.exports = helpers;
  else root.DeliveryUX = helpers;
})(typeof globalThis === 'object' ? globalThis : this, function() {
  'use strict';
  function texto(value) {
    return String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();
  }
  function pedidos(items, filtro, busca) {
    const termos = texto(busca).split(/\s+/).filter(Boolean);
    return items.filter(p => {
      const final = ['CANCELADO', 'RETIRADO', 'ENTREGUE'].includes(p.status);
      const status = filtro === 'todos' || filtro === 'abertos' && !final ||
        filtro === 'concluidos' && ['RETIRADO', 'ENTREGUE'].includes(p.status) ||
        filtro === 'cancelados' && p.status === 'CANCELADO';
      const conteudo = texto([p.numero_pedido, p.cliente_nome, p.cliente_telefone,
        ...(p.itens || []).map(i => i.produto_nome)].join(' '));
      return status && termos.every(t => conteudo.includes(t));
    });
  }
  function proximoPasso(s) {
    const pendente = (s.tutorial || []).find(e => !e.opcional && !e.concluida);
    if (pendente) return {titulo:pendente.titulo, pagina:pendente.pagina, pronto:false};
    const op = s.operacao || {};
    if (!op.fila_ok) return {titulo:'Verificar o atendimento', pagina:'conexoes', pronto:false};
    if (!op.whatsapp_ok) return {titulo:'Conectar o WhatsApp', pagina:'conexoes', pronto:false};
    if (!op.https_ok) return {titulo:'Verificar a página de pedidos', pagina:'publicacao', pronto:false};
    return {titulo:'Acompanhar seus pedidos', pagina:'pedidos', pronto:true};
  }
  function conexao(s) {
    const op = s.operacao || {};
    if (op.whatsapp_estado === 'TESTE') return {texto:'Modo de teste', ok:false};
    if (!op.whatsapp_ok) return {texto:'WhatsApp precisa de atenção', ok:false};
    if (!op.https_ok) return {texto:'Página de pedidos precisa de atenção', ok:false};
    if (!op.fila_ok) return {texto:'Atendimento precisa de atenção', ok:false};
    return {texto:s.whatsapp === 'META' ? 'Meta configurada · confira o webhook' : 'WhatsApp conectado · HTTPS disponível', ok:true};
  }
  function fila(dados={}) {
    const quantidade = valor => Number.isSafeInteger(valor) && valor >= 0 ? valor : 0;
    const pendentes = quantidade(dados.pendentes);
    const https = Math.min(pendentes, quantidade(dados.aguardando_https));
    return `${pendentes} ${pendentes === 1 ? 'mensagem' : 'mensagens'} em processamento ou aguardando` +
      (https ? `. ${https} aguardando a página HTTPS; a retomada é automática dentro do prazo da fila.` : '');
  }
  async function solicitar(fetcher, url, options, {timeout=30000, agendar=setTimeout, cancelar=clearTimeout}={}) {
    const escrita = !['GET', 'HEAD'].includes(options.method || 'GET');
    const controller = new AbortController();
    let expirou = false;
    const timer = agendar(() => {expirou=true; controller.abort();}, timeout);
    try {
      const response = await fetcher(url, {...options, signal:controller.signal});
      let result;
      try {result = await response.json();}
      catch {throw new Error(response.status === 401 ? 'Sua sessão terminou. Entre novamente no aplicativo.' :
        escrita ? 'Não foi possível confirmar o resultado. Atualize os dados antes de repetir a operação.' :
          'O aplicativo retornou uma resposta incompleta. Tente atualizar os dados.');}
      if (!response.ok) throw new Error(response.status === 401 ? 'Sua sessão terminou. Entre novamente no aplicativo.' :
        response.status === 403 ? (/sess[aã]o|csrf/i.test(result?.erro || '') ? 'Sua sessão terminou. Entre novamente no aplicativo.' :
          'Sua conta não permite esta operação. Solicite ajuda ao administrador.') :
          result?.erro || 'Não foi possível concluir a operação. Confira os dados e tente novamente.');
      return result;
    } catch(error) {
      if (expirou || error.name === 'AbortError' || error instanceof TypeError) {
        throw new Error((expirou ? 'O aplicativo demorou para responder.' : 'A conexão com o aplicativo foi interrompida.') +
          (escrita ? ' A operação pode ter sido concluída. Atualize os dados antes de repetir.' : ' Seus dados foram mantidos. Tente atualizar novamente.'));
      }
      throw error;
    } finally {cancelar(timer);}
  }
  async function ocupado(button, action) {
    if (button?.disabled) return false;
    const rotulo = button?.tagName === 'BUTTON';
    const aria = button?.getAttribute('aria-busy');
    const label = button?.getAttribute('aria-label');
    if (button) {button.disabled=true;button.setAttribute('aria-busy','true');button.classList.add('busy');if(rotulo)button.setAttribute('aria-label','Aguarde…');}
    try {await action();return true;}
    finally {
      if (button) {button.disabled=false;button.classList.remove('busy');
        if(rotulo){if(label===null)button.removeAttribute('aria-label');else button.setAttribute('aria-label',label);}
        if (aria === null) button.removeAttribute('aria-busy');else button.setAttribute('aria-busy',aria);}
    }
  }
  return {texto, pedidos, proximoPasso, conexao, fila, solicitar, ocupado};
});
