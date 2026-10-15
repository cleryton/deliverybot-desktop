'use strict';
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money=v=>Number(v).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
const steps={AGUARDANDO:'Iniciar preparo',EM_PREPARO:'Marcar como pronto',PRONTO:'Concluir entrega ou retirada'};
const labels={AGUARDANDO:'Recebido',EM_PREPARO:'Em preparo',PRONTO:'Pronto'};
const number=v=>'#'+String(v??'').replace(/^#+/,'');
let csrf=$('meta[name="csrf-token"]').content, current=null, expiryTimer;
function takeInvite(){const code=location.hash.slice(1);history.replaceState(null,'','/remoto');if(/^[\w-]{43}$/.test(code))$('#remote-code').value=code;}
takeInvite();
addEventListener('hashchange',takeInvite);
function message(text,error=false){$('#remote-message').textContent=text;$('#remote-message').classList.toggle('error',error);}
function locked(){clearTimeout(expiryTimer);current=null;$('#remote-panel').hidden=true;$('#remote-login').hidden=false;$('#remote-orders').innerHTML='';$('#remote-products').innerHTML='';}
async function api(path,method='GET',data){
  const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),30000);
  try{const r=await fetch('/remoto/api/'+path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:data===undefined?undefined:JSON.stringify(data),signal:abort.signal,redirect:'error'});let d;try{d=await r.json();}catch{throw new Error('A página HTTPS está indisponível. Confira a conexão com a loja e reabra seu acesso.');}if(!r.ok){if(r.status===401)locked();throw new Error(d.erro||'Não foi possível concluir.');}return d;}
  catch(e){if(e.name==='AbortError'||e instanceof TypeError)throw new Error(method==='GET'?'A conexão demorou ou foi interrompida. Tente atualizar novamente.':path==='entrar'?'Não foi possível confirmar a entrada. Reabra a página; se o convite já foi usado, peça outro ao responsável.':'Não foi possível confirmar o resultado. Atualize os pedidos antes de tentar novamente.');throw e;}finally{clearTimeout(timer);}
}
async function busy(b,fn){if(b?.disabled)return;if(b)b.disabled=true;try{await fn();}catch(e){message(e.message,true);}finally{if(b)b.disabled=false;}}
function render(d){current=d;$('#remote-login').hidden=true;$('#remote-panel').hidden=false;$('#remote-person').textContent=d.nome;$('#remote-permission').textContent=d.permissao==='PEDIDOS'?'Consulta e avanço de pedidos':'Acesso somente para consulta';$('#remote-expiry').textContent='Válido até '+new Date(d.expira_em*1000).toLocaleString('pt-BR')+' · encerra após 15 min sem atividade';$('#remote-count').textContent=d.pedidos.length;$('#remote-total').textContent=money(d.pedidos.reduce((s,p)=>s+p.total_pedido,0));
  clearTimeout(expiryTimer);expiryTimer=setTimeout(()=>{locked();message('Sessão expirada. Solicite um novo convite.',true);},Math.max(0,Math.min(900000,d.expira_em*1000-Date.now())));
  $('#remote-orders').innerHTML=d.pedidos.map(p=>`<article class="card"><span class="badge">${esc(labels[p.status]||p.status)}</span><h2>${esc(number(p.numero_pedido))}</h2><p>${esc(p.cliente_nome)} · ${esc(p.forma_entrega==='RETIRADA BALCAO'?'Retirada na loja':p.forma_entrega==='ENTREGA'?'Entrega':p.forma_entrega)}</p><ul>${p.itens.map(i=>`<li>${esc(i.quantidade)} × ${esc(i.produto_nome)}${i.observacao?'<br><small>'+esc(i.observacao)+'</small>':''}</li>`).join('')}</ul><p class="order-total">${money(p.total_pedido)}</p>${d.permissao==='PEDIDOS'&&steps[p.status]?`<button class="primary" data-next="${Number(p.pedido_id)}">${steps[p.status]}</button>`:''}</article>`).join('')||'<article class="card">Nenhum pedido em andamento.</article>';
  $('#remote-products').innerHTML=d.produtos.map(p=>`<p><b>${esc(p.nome)}</b> · ${money(p.preco)}<br><small>${esc(p.categoria)} · ${p.estoque===null?'Sob pedido':esc(p.estoque)+' '+esc(p.unidade)}</small></p>`).join('')||'<p>Nenhum produto ativo.</p>';
}
async function refresh(){render(await api('estado'));}
$('#remote-login-form').addEventListener('submit',e=>{e.preventDefault();busy(e.submitter,async()=>{const d=Object.fromEntries(new FormData(e.target));const r=await api('entrar','POST',d);csrf=r.csrf;e.target.reset();message('Acesso autorizado.');await refresh();});});
$('#remote-refresh').addEventListener('click',e=>busy(e.currentTarget,async()=>{await refresh();message('Dados atualizados agora.');}));
$('#remote-logout').addEventListener('click',e=>busy(e.currentTarget,async()=>{await api('sair','POST',{});locked();message('Acesso encerrado. Para entrar novamente, solicite um novo convite.');}));
$('#remote-orders').addEventListener('click',e=>{const b=e.target.closest('[data-next]');if(!b||b.disabled)return;const p=current?.pedidos.find(p=>String(p.pedido_id)===b.dataset.next);if(!p||!confirm('Avançar o pedido '+number(p.numero_pedido)+'? O cliente poderá receber uma notificação.'))return;busy(b,async()=>{const r=await api('pedidos/'+p.pedido_id+'/avancar','POST',{status:p.status,confirmar:true});await refresh();message(r.aviso||'Etapa do pedido atualizada.');});});
// Sem atualização automática: uma página abandonada não prolonga a autorização.
api('estado').then(render).catch(()=>{});
