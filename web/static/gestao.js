'use strict';
const $ = (s) => document.querySelector(s);
const escapeHTML = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = (v) => Number(v).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const date = (v) => v ? new Date(v.replace(' ','T')+'Z').toLocaleString('pt-BR') : '—';
const state = {page:'inicio',products:[],orders:[],settings:null,summary:null};
let toastTimer;
function toast(message,error=false){$('#toast').textContent=message;$('#toast').classList.toggle('error',error);$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,error?9000:5500);}
async function api(path,method='GET',data){
  const response=await fetch('/gestao/api/'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':$('meta[name="csrf-token"]').content},body:data===undefined?undefined:JSON.stringify(data)});
  let result;try{result=await response.json();}catch{throw new Error('Não foi possível ler a resposta. Reabra o aplicativo.');}
  if(!response.ok)throw new Error(result.erro||'Não foi possível concluir a operação.');
  return result;
}
async function run(button,action){if(button?.disabled)return;if(button)button.disabled=true;try{await action();}catch(e){toast(e.message,true);}finally{if(button)button.disabled=false;}}
async function summary(){
  const s=state.summary=await api('resumo');$('#loja-nome').textContent=s.nome;$('#connection').textContent=s.modo_teste?'Modo de teste':`WhatsApp · ${s.whatsapp} configurado`;
  const values=[['Produtos cadastrados',s.produtos,`${s.ativos} ativos no catálogo`],['Pedidos em andamento',s.pendentes,'Aguardando conclusão'],['Estoque baixo',s.baixos,'Produtos para repor'],['Vendas acumuladas',money(s.vendas),`${s.pedidos} pedidos não cancelados`]];
  $('#metrics').innerHTML=values.map(([title,value,help])=>`<article class="metric"><span>${title}</span><strong>${value}</strong><small>${help}</small></article>`).join('');
  $('#daily-note').textContent=s.modo_teste?'Você está em modo de teste. Os dados são salvos normalmente, mas mensagens não são enviadas ao WhatsApp. Configure a conexão quando estiver pronto.':'Atendimento configurado. Mantenha este aplicativo aberto e o computador ligado. A conexão real depende do seu serviço de WhatsApp e do endereço público.';
  $('#waha-hook').value=s.webhook_waha;
  if(!s.privacidade_configurada)$('#daily-note').textContent+=' Configure a empresa responsável e o contato em Privacidade e LGPD antes de atender clientes.';
}
async function products(){state.products=await api('produtos');renderProducts();renderLow();$('#categories').innerHTML=[...new Set(state.products.map(p=>p.categoria))].map(c=>`<option value="${escapeHTML(c)}">`).join('');}
function renderLow(){const low=state.products.filter(p=>p.ativo&&p.estoque!==null&&p.estoque<=p.estoque_minimo);$('#low-stock').innerHTML=low.length?low.slice(0,6).map(p=>`<div class="stock-alert"><span class="product-avatar">▦</span><div><b>${escapeHTML(p.nome)}</b><small>${escapeHTML(p.categoria)} · Mínimo ${p.estoque_minimo}</small></div><span class="badge ${p.estoque===0?'red':'warning'}">${p.estoque} ${escapeHTML(p.unidade)}</span></div>`).join(''):`<div class="empty"><div class="empty-icon">✓</div><h2>${state.products.length?'Estoque em dia':'Nenhum produto ainda'}</h2><p>${state.products.length?'Os produtos ativos estão acima do alerta de reposição.':'Seu primeiro produto aparecerá aqui depois do cadastro.'}</p></div>`;}
function renderProducts(){const term=$('#search').value.toLocaleLowerCase('pt-BR'),filter=$('#filter').value;const items=state.products.filter(p=>`${p.nome} ${p.categoria} ${p.sku}`.toLocaleLowerCase('pt-BR').includes(term)&&(filter==='todos'||filter==='ativo'&&p.ativo||filter==='inativo'&&!p.ativo||filter==='baixo'&&p.ativo&&p.estoque!==null&&p.estoque<=p.estoque_minimo));$('#product-count').textContent=`${items.length} produtos`;$('#products-empty').hidden=items.length>0;
  $('#product-list').innerHTML=items.map(p=>`<tr><td><div class="product-name"><span class="product-avatar">▦</span><div><b>${escapeHTML(p.nome)}</b><small>${escapeHTML(p.sku||'Sem código')}</small></div></div></td><td>${escapeHTML(p.categoria)}</td><td>${money(p.preco)}</td><td>${p.estoque===null?'<span class="muted">Sem controle</span>':`<b>${p.estoque}</b> ${escapeHTML(p.unidade)}`}</td><td><span class="badge ${!p.ativo?'gray':p.estoque===0?'red':p.estoque!==null&&p.estoque<=p.estoque_minimo?'warning':''}">${!p.ativo?'Inativo':p.estoque===0?'Esgotado':p.estoque!==null&&p.estoque<=p.estoque_minimo?'Estoque baixo':'Ativo'}</span></td><td><div class="row-actions"><button data-edit="${p.id}">Editar</button>${p.estoque===null?'':`<button data-stock="${p.id}">Movimentar</button>`}</div></td></tr>`).join('');
}
const statusLabels={RECEBIDO:'Recebido',CONFIRMADO:'Confirmado',EM_PREPARO:'Em separação',PRONTO:'Pronto',RETIRADO:'Retirado',ENTREGUE:'Entregue',CANCELADO:'Cancelado'};
async function orders(){state.orders=await api('pedidos');renderOrders();}
function renderOrders(){const filter=$('#order-filter').value,final=['CANCELADO','RETIRADO','ENTREGUE'];const items=state.orders.filter(p=>filter==='todos'||filter==='abertos'&&!final.includes(p.status)||filter==='concluidos'&&['RETIRADO','ENTREGUE'].includes(p.status)||filter==='cancelados'&&p.status==='CANCELADO');$('#order-list').innerHTML=items.length?items.map(p=>`<article class="card order"><div class="order-heading"><b>${escapeHTML(p.numero_pedido)}</b><span class="badge ${p.status==='CANCELADO'?'red':''}">${statusLabels[p.status]||escapeHTML(p.status)}</span></div><strong>${escapeHTML(p.cliente_nome)}</strong><p>${escapeHTML(p.cliente_telefone)} · ${date(p.criado_em)}</p><p>${p.forma_entrega==='ENTREGA'?'Entrega':'Retirada'} · ${escapeHTML(p.forma_pagamento)}</p>${p.cliente_endereco&&p.forma_entrega==='ENTREGA'?`<p>${escapeHTML(p.cliente_endereco)}</p>`:''}<ul>${p.itens.map(i=>`<li><b>${i.quantidade}×</b> ${escapeHTML(i.produto_nome)}</li>`).join('')}</ul><div class="order-total"><span>Total do pedido</span><b>${money(p.total_pedido)}</b></div>${!final.includes(p.status)?`<div class="button-row"><button class="primary" data-advance="${p.id}">${['RECEBIDO','CONFIRMADO'].includes(p.status)?'Iniciar separação':p.status==='EM_PREPARO'?'Marcar como pronto':p.forma_entrega==='ENTREGA'?'Concluir entrega':'Concluir retirada'}</button><button class="danger" data-cancel="${p.id}">Cancelar</button></div>`:''}</article>`).join(''):'<div class="card empty"><div class="empty-icon">▤</div><h2>Nenhum pedido nesta seleção</h2><p>As compras pelo link do bot aparecerão aqui.</p></div>';}
async function movements(){const items=await api('movimentos');$('#movement-list').innerHTML=items.length?items.map(m=>`<tr><td>${date(m.criado_em)}</td><td>${escapeHTML(m.produto_nome)}</td><td><span class="badge ${m.quantidade<0?'warning':''}">${escapeHTML(m.tipo)}</span></td><td>${m.quantidade>0?'+':''}${m.quantidade} ${escapeHTML(m.unidade)}</td><td>${m.saldo??'Sem controle'}</td><td>${escapeHTML(m.motivo)}</td></tr>`).join(''):'<tr><td colspan="6" class="empty">Nenhuma movimentação registrada.</td></tr>';}
const groups=[
  ['Informações da loja','Esses dados aparecem no atendimento e nos pedidos.',[
    ['NOME_RESTAURANTE','Nome da loja'],['TELEFONE_RESTAURANTE','Telefone'],['ENDERECO_RESTAURANTE','Endereço'],['HORARIO_FUNCIONAMENTO','Horário de funcionamento'],['FORMAS_PAGAMENTO','Formas de pagamento (separadas por vírgula)'],['TAXA_ENTREGA','Taxa de entrega (R$)','number'],['TEMPO_PREPARO_MIN','Tempo estimado de separação (min)','number'],['CEP_RESTAURANTE','CEP da loja']]],
  ['WhatsApp e acesso dos clientes','Use WhatsApp e IA para conectar pelo QR Code. Estes campos permitem configurar servidores externos.',[
    ['WHATSAPP_PROVIDER','Conexão do WhatsApp',['TESTE','LOCAL','WAHA','META']],['BASE_URL','Endereço público da loja'],['WAHA_URL','Endereço WAHA externo (opcional)'],['WAHA_SESSION','Nome da sessão'],['WAHA_WEBHOOK_BASE_URL','Endereço visto pelo WAHA externo (vazio = automático)'],['WAHA_API_KEY','Chave WAHA externo','password'],['WEBHOOK_SECRET','Chave privada do recebimento','password'],['WHATSAPP_PHONE_NUMBER_ID','ID do número (Meta)'],['WHATSAPP_TOKEN','Token de acesso (Meta)','password'],['WHATSAPP_VERIFY_TOKEN','Token de verificação (Meta)','password'],['WHATSAPP_APP_SECRET','Segredo do aplicativo (App Secret da Meta)','password']]],
  ['Inteligência artificial (opcional)','Sem IA, o bot atende pelo menu. Ollama requer instalação à parte; Anthropic usa uma API paga.',[
    ['IA_PROVIDER','Tipo de atendimento',['','OLLAMA','ANTHROPIC']],['OLLAMA_URL','Endereço Ollama'],['OLLAMA_MODEL','Modelo Ollama'],['ANTHROPIC_API_KEY','Chave Anthropic','password'],['ANTHROPIC_MODEL','Modelo Anthropic']]]
];
async function settings(){const cfg=state.settings=await api('configuracoes');$('#settings-fields').innerHTML=groups.map(([title,help,fields])=>`<article class="card"><h2>${title}</h2><p>${help}</p><div class="settings-grid">${fields.map(([key,label,type])=>`<label>${label}${Array.isArray(type)?`<select name="${key}">${type.map(v=>`<option value="${v}" ${cfg[key]===v?'selected':''}>${v||'Menu sem IA'}</option>`).join('')}</select>`:`<input name="${key}" type="${type||'text'}" value="${type==='password'?'':escapeHTML(cfg[key])}" ${type==='number'?`min="${key==='TEMPO_PREPARO_MIN'?1:0}" step="${key==='TAXA_ENTREGA'?'0.01':'1'}" required`:''} ${type==='password'?`autocomplete="new-password" placeholder="${cfg.segredos_configurados[key]?'Configurado · vazio mantém a chave':'Não configurado'}"`:''}>`}</label>`).join('')}</div></article>`).join('');}
async function navigate(page){state.page=page;document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!=='page-'+page);document.querySelectorAll('nav [data-page]').forEach(el=>el.classList.toggle('selected',el.dataset.page===page));$('#breadcrumb').textContent=({inicio:'Sua operação, em um só lugar',produtos:'Catálogo / Produtos e estoque',pedidos:'Vendas / Pedidos',movimentos:'Estoque / Histórico',bot:'Atendimento / Simulação',conexoes:'Atendimento / WhatsApp e inteligência artificial',privacidade:'Sua loja / Privacidade e LGPD',configuracoes:'Sua loja / Configurações'})[page];await reload();}
async function reload(){await summary();if(['inicio','produtos'].includes(state.page))await products();if(state.page==='pedidos')await orders();if(state.page==='movimentos')await movements();if(state.page==='configuracoes')await settings();if(state.page==='conexoes')await refreshConnections();if(state.page==='privacidade')await privacy();}
function openProduct(id){const form=$('#product-form');form.reset();const p=state.products.find(p=>p.id===id);form.elements.id.value=p?.id||'';$('#product-title').textContent=p?'Editar produto':'Cadastrar produto';if(p){for(const key of ['nome','sku','categoria','preco','unidade','descricao','estoque_minimo']){form.elements[key].value=p[key]??'';}if(![...form.elements.unidade.options].some(o=>o.value===p.unidade))form.elements.unidade.add(new Option(p.unidade,p.unidade,true,true));form.elements.estoque.value=p.estoque??0;form.elements.ativo.checked=!!p.ativo;form.elements.controlar_estoque.checked=p.estoque!==null;}stockInputs();$('#product-dialog').showModal();}
function stockInputs(){const f=$('#product-form'),p=state.products.find(p=>String(p.id)===f.elements.id.value),control=f.elements.controlar_estoque.checked;f.elements.estoque.disabled=!control||p?.estoque!==null&&!!p;f.elements.estoque_minimo.disabled=!control;$('#stock-help').textContent=p?.estoque!==null&&p?'Use Movimentar para registrar entradas e saídas. A edição do produto preserva o saldo atual.':'As quantidades são inteiras. Crie um produto por variação (cor, tamanho ou embalagem).';}
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b||(!Object.keys(b.dataset).length&&b.id!=='refresh'))return;run(b,async()=>{
  if(b.dataset.connectionAction)await connectionAction(b.dataset.connectionAction);
  if(b.dataset.action==='conexoes-atualizar')await refreshConnections();
  if(b.dataset.action==='qr-atualizar')await refreshQR();
  if(b.dataset.messageAction&&confirm(b.dataset.messageAction==='reenviar'?'Confira no celular se a resposta já chegou. Reenviar esta resposta?':'Marcar esta mensagem como resolvida e liberar o atendimento deste cliente?')){await api(`conexoes/mensagens/${b.dataset.messageId}/${b.dataset.messageAction}`,'POST',{});await refreshConnections();}
  if(b.dataset.page)await navigate(b.dataset.page);
  if(b.dataset.close)$('#'+b.dataset.close).close();
  if(b.dataset.edit)openProduct(Number(b.dataset.edit));
  if(b.dataset.stock){const p=state.products.find(p=>p.id===Number(b.dataset.stock));$('#stock-form').reset();$('#stock-form').elements.id.value=p.id;$('#stock-product').textContent=`${p.nome} · Disponível: ${p.estoque} ${p.unidade}`;$('#stock-dialog').showModal();}
  if(b.dataset.advance){const result=await api(`pedidos/${b.dataset.advance}/avancar`,'POST',{});toast(result.aviso||'Pedido atualizado.');await reload();}
  if(b.dataset.cancel&&confirm('Cancelar este pedido e devolver os produtos ao estoque?')){const result=await api(`pedidos/${b.dataset.cancel}/cancelar`,'POST',{});toast(result.aviso||'Pedido cancelado. Estoque devolvido.');await reload();}
  if(b.dataset.action==='novo')openProduct();
  if(b.dataset.action==='backup')openBackup('criar');
  if(b.dataset.action==='pasta'){if(window.pywebview?.api)await window.pywebview.api.abrir_pasta();else toast('Pasta dos dados: '+state.summary.pasta);}
  if(b.dataset.action==='restaurar'){if(!window.pywebview?.api)throw new Error('Abra o aplicativo Desktop para restaurar um backup.');openBackup('restaurar');}
  if(b.dataset.action==='privacy-clean'&&confirm('Remover conversas concluídas fora do prazo configurado e links expirados do banco atual? Atendimentos pendentes serão preservados.')){const r=await api('privacidade/limpar','POST',{confirmar_limpeza:true});toast(`${r.mensagens} mensagens e ${r.links_expirados} links removidos; ${r.atendimentos} atendimentos tiveram os dados limpos.`);await privacy();}
  if(b.id==='refresh')await reload();
});});
$('#search').addEventListener('input',renderProducts);$('#filter').addEventListener('change',renderProducts);$('#order-filter').addEventListener('change',renderOrders);$('#product-form').elements.controlar_estoque.addEventListener('change',stockInputs);
$('#product-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const f=e.target,d=Object.fromEntries(new FormData(f)),id=d.id;d.ativo=f.elements.ativo.checked;d.controlar_estoque=f.elements.controlar_estoque.checked;d.estoque=f.elements.estoque.value;d.estoque_minimo=f.elements.estoque_minimo.value;delete d.id;await api('produtos'+(id?'/'+id:''),id?'PUT':'POST',d);$('#product-dialog').close();toast('Produto salvo no catálogo.');await reload();});});
$('#stock-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const d=Object.fromEntries(new FormData(e.target));await api(`produtos/${d.id}/estoque`,'POST',{quantidade:Number(d.quantidade)*Number(d.tipo),motivo:d.motivo});$('#stock-dialog').close();toast('Movimentação registrada.');await reload();});});
$('#settings-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{await api('configuracoes','PUT',Object.fromEntries(new FormData(e.target)));toast('Configurações salvas.');await reload();});});
$('#bot-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const d=Object.fromEntries(new FormData(e.target));$('#chat').insertAdjacentHTML('beforeend',`<div class="bubble customer">${escapeHTML(d.texto)}</div>`);const result=await api('simular','POST',d);$('#chat').insertAdjacentHTML('beforeend',`<div class="bubble assistant">${escapeHTML(result.resposta)}${result.caminho?`<br><a href="${escapeHTML(result.caminho)}" target="_blank" rel="noopener">Abrir pedido de teste →</a>`:''}</div>`);e.target.elements.texto.value='';$('#chat').scrollTop=$('#chat').scrollHeight;});});
function openBackup(acao){$('#backup-form').reset();$('#backup-form').dataset.acao=acao;$('#backup-title').textContent=acao==='criar'?'Criar backup criptografado':'Restaurar backup';$('#backup-dialog').showModal();}
$('#backup-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const f=e.target,senha=f.elements.senha.value;if(senha!==f.elements.confirmacao.value)throw new Error('As senhas devem ser iguais.');if(f.dataset.acao==='criar'){const r=await api('backup','POST',{senha});$('#backup-result').textContent=r.caminho;toast('Backup criptografado criado. Guarde a senha em local separado.');}else{if(!confirm('Substituir os dados atuais pelo backup? Uma cópia protegida será criada antes. O aplicativo fechará; abra-o novamente para concluir.'))return;const r=await window.pywebview.api.restaurar_backup(senha);if(r?.erro)throw new Error(r.erro);}f.reset();$('#backup-dialog').close();});});
async function privacy(){const [cfg,s]=await Promise.all([api('configuracoes'),api('privacidade')]);for(const field of $('#privacy-settings').elements){if(field.name&&cfg[field.name]!==undefined)field.value=cfg[field.name];}$('#privacy-note').textContent=`${s.clientes} cadastros com identificação. `+(!cfg.LGPD_CONTATO||!cfg.LGPD_RESPONSAVEL?'Informe a empresa e o contato antes de iniciar o atendimento.':'Responsável e contato configurados. Confira se a retenção dos pedidos corresponde à política da loja.');$('#privacy-audit').innerHTML=s.auditoria.map(a=>`<li>${date(a.criado_em)} · ${escapeHTML(({EXPORTAR:'Exportação de dados',CORRIGIR:'Correção de cadastro',REMOVER_IDENTIFICACAO:'Remoção de identificação',LIMPAR_HISTORICO:'Limpeza do histórico'})[a.acao]||a.acao)}</li>`).join('');}
$('#privacy-settings').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{await api('configuracoes','PUT',Object.fromEntries(new FormData(e.target)));toast('Opções de privacidade salvas.');await privacy();});});
$('#privacy-client').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const acao=e.submitter.value,d=Object.fromEntries(new FormData(e.target));d.identidade_confirmada=e.target.elements.identidade_confirmada.checked;$('#privacy-export').value='';$('#privacy-export').hidden=true;if(acao==='remover'){if(!confirm('Remover nome, telefone, endereço e conversas do banco atual? Os dados de venda serão preservados. Revise cópias antigas e provedores separadamente.'))return;d.confirmar_remocao=true;}const r=await api('privacidade/'+acao,'POST',d);if(acao==='exportar'){if(window.pywebview?.api){await window.pywebview.api.salvar_exportacao(r);}else{$('#privacy-export').value=JSON.stringify(r,null,2);$('#privacy-export').hidden=false;}toast('Dados preparados. Entregue apenas ao titular verificado.');}else{toast(r.aviso||'Cadastro corrigido.');}await privacy();});});
run(null,reload);
setInterval(()=>{if(document.visibilityState==='visible'&&!document.querySelector('dialog[open]')&&['inicio','pedidos'].includes(state.page))run(null,reload);},15000);

let connectionsBusy=false,qrBusy=false,lastQR=0;
function connectionJob(selector,job){const el=$(selector);el.hidden=!job;if(job){el.textContent=job.mensagem;el.classList.toggle('error',job.estado==='ERRO');}}
function renderConnections(c){
  const w=c.whatsapp,o=c.ollama,waBusy=c.tarefas.whatsapp?.estado==='EXECUTANDO',olBusy=c.tarefas.ollama?.estado==='EXECUTANDO';
  $('#wa-status').textContent=w.mensagem+(w.numero?' · '+w.numero:'');
  $('#wa-badge').textContent=w.conectado?'Conectado':w.estado==='SCAN_QR_CODE'?'Aguardando QR':w.servico?'Disponível':'Desligado';
  $('#wa-badge').className='badge '+(w.conectado?'':w.servico?'warning':'gray');
  $('#wa-connect').textContent=w.conectado?'Verificar e configurar conexão':'Conectar WhatsApp';
  $('#wa-connect').disabled=waBusy;
  $('#wa-pause').disabled=waBusy||!w.servico||['STOPPED','SEM_SESSAO'].includes(w.estado);
  $('#wa-qr-area').hidden=w.estado!=='SCAN_QR_CODE';
  $('#wa-hook-status').textContent=c.provedor==='META'?'O atendimento está usando a Meta. Use a conexão integrada para conectar pelo QR Code.':c.provedor==='TESTE'?'Modo de teste. Clique em Conectar para ativar o atendimento real.':w.webhook_configurado?'Recebimento automático configurado. Envie uma mensagem de outro número para conferir.':'Recebimento automático pendente. Clique em Conectar para configurar.';
  $('#wa-integrated').hidden=c.whatsapp_local;$('#wa-integrated').disabled=waBusy||!c.pode_iniciar_local;
  connectionJob('#wa-job',c.tarefas.whatsapp);connectionJob('#ol-job',c.tarefas.ollama);
  $('#ol-badge').textContent=o.online&&o.modelo_instalado&&o.ativo?'Ativo no bot':o.online?'Disponível':'Desligado';
  $('#ol-badge').className='badge '+(o.online&&o.modelo_instalado&&o.ativo?'':o.online?'warning':'gray');
  $('#ol-status').textContent=o.mensagem+(o.ativo&&o.online?' · IA selecionada no atendimento':'');
  if(!$('#ollama-model').value)$('#ollama-model').value=o.modelo;
  $('#ollama-models').innerHTML=o.modelos.map(m=>`<option value="${escapeHTML(m)}">`).join('');
  $('#ol-start').disabled=olBusy||!c.pode_iniciar_local;$('#ol-download').disabled=olBusy||!o.online;
  $('#ollama-model').disabled=olBusy;
  const progress=c.tarefas.ollama?.percentual;$('#ol-progress').hidden=!olBusy||progress===null||progress===undefined;if(progress!=null)$('#ol-progress').value=progress;
  $('#public-url-note').textContent=c.links_publicos?'Links de compra usam '+c.endereco_publico+'. Confira se esse endereço abre no celular do cliente.':'Para clientes abrirem os links de compra, configure um endereço público da loja em Configurações. O WhatsApp pode conectar localmente antes dessa etapa.';
  $('#inbox-count').textContent=c.fila.pendentes+' mensagens em processamento ou aguardando';
  $('#inbox-last').textContent='Última mensagem recebida: '+date(c.fila.ultima_mensagem);
  $('#inbox-errors').innerHTML=c.fila.falhas.map(f=>`<div class="inbox-error"><b>${escapeHTML(f.telefone)}</b><p>${escapeHTML(f.erro)}</p><div class="button-row"><button data-message-action="reenviar" data-message-id="${f.id}">Tentar novamente</button><button data-message-action="ignorar" data-message-id="${f.id}">Marcar como resolvida</button></div></div>`).join('');
  $('#connection').textContent=['LOCAL','WAHA'].includes(c.provedor)?(w.conectado?'WhatsApp conectado':'WhatsApp · '+w.mensagem):c.provedor==='TESTE'?'Modo de teste':'WhatsApp · Meta configurada';
}
async function refreshQR(){
  if(qrBusy)return;qrBusy=true;lastQR=Date.now();
  try{const q=await api('conexoes/qr');$('#wa-qr').src=q.imagem;$('#qr-status').textContent='QR atualizado às '+new Date().toLocaleTimeString('pt-BR')+'.';}
  catch(e){$('#qr-status').textContent=e.message;}
  finally{qrBusy=false;}
}
async function refreshConnections(){
  if(connectionsBusy)return;connectionsBusy=true;
  try{const c=state.connections=await api('conexoes');renderConnections(c);if(c.whatsapp.estado==='SCAN_QR_CODE'&&Date.now()-lastQR>15000)await refreshQR();}
  finally{connectionsBusy=false;}
}
async function connectionAction(action){
  const c=state.connections;if(!c)throw new Error('Aguarde a verificação da conexão.');
  if(action==='whatsapp-conectar'){
    if(c.provedor==='META'){if(!confirm('Mudar o atendimento da Meta para a conexão integrada pelo QR Code?'))return;action='whatsapp-iniciar';}
    if(!c.whatsapp.servico&&c.whatsapp_local&&c.pode_iniciar_local)action='whatsapp-iniciar';
  }
  if(action==='whatsapp-integrado'){if(!confirm('Usar o WhatsApp integrado ao aplicativo? Será necessário escanear o QR Code para conectar esta sessão.'))return;action='whatsapp-iniciar';}
  if(action==='whatsapp-pausar'&&!confirm('Pausar a conexão WhatsApp? As mensagens na fila aguardarão a retomada.'))return;
  if(action.startsWith('ollama-')){
    const model=$('#ollama-model').value.trim();if(!model)throw new Error('Informe o nome do modelo Ollama.');
    if(action==='ollama-baixar'&&!confirm('Baixar '+model+'? O download pode ocupar alguns GB. Mantenha o aplicativo aberto até terminar.'))return;
    await api('configuracoes','PUT',{OLLAMA_MODEL:model});
  }
  const job=await api('conexoes/'+action,'POST',{});
  if(action!=='whatsapp-pausar')c.tarefas[action.startsWith('ollama')?'ollama':'whatsapp']=job;
  renderConnections(c);toast(action==='whatsapp-pausar'?'Conexão pausada.':'Preparação iniciada. Acompanhe o estado neste painel.');
  // O servidor verifica o serviço na próxima atualização, sem prender o botão ao download.
  setTimeout(()=>run(null,refreshConnections),500);
}
setInterval(()=>{if(document.visibilityState==='visible'&&state.page==='conexoes')run(null,refreshConnections);},4000);
