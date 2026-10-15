'use strict';
function clearRemoteInvite(){$('#remote-invite-link').value='';$('#remote-invite-link').type='password';$('#remote-invite-reveal').textContent='Mostrar link';$('#remote-invite-result').hidden=true;}
async function remoteAdminLoad(){
  clearRemoteInvite();
  try{const [s,contas]=await Promise.all([api('remoto'),api('operadores')]);
    $('#remote-admin-status').textContent=s.url?'HTTPS disponível: '+s.url:'Inicie a página HTTPS antes de gerar um convite.';
    $('#remote-account').innerHTML='<option value="">Selecione uma conta</option>'+contas.filter(c=>c.ativo&&['ADMIN','ATENDENTE'].includes(c.perfil)).map(c=>`<option value="${Number(c.id)}">${escapeHTML(c.nome)} · ${escapeHTML(c.login)}</option>`).join('');
    const now=Date.now()/1000;
    $('#remote-access-list').innerHTML=s.acessos.map(a=>{const active=a.ativo&&a.expira_em>now;const expired=!!a.usado&&a.ultimo+900<=now;const status=!active?'Encerrado':expired?'Sessão expirada':a.usado?'Sessão iniciada':'Aguardando entrada';return `<article class="card"><h3>${escapeHTML(a.nome)} <span class="badge">${status}</span></h3><p>${a.permissao==='PEDIDOS'?'Consulta e avanço de pedidos':'Somente consulta'} · até ${escapeHTML(new Date(a.expira_em*1000).toLocaleString('pt-BR'))}</p>${active?`<button type="button" data-revoke-remote="${Number(a.id)}">Revogar acesso</button>`:''}</article>`;}).join('')||'<p>Nenhum convite criado. O acesso remoto permanece fechado.</p>';
  }catch(e){$('#remote-admin-status').textContent=e.message;throw e;}
}
$('#remote-admin-refresh').addEventListener('click',e=>run(e.currentTarget,remoteAdminLoad));
$('#remote-invite-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{clearRemoteInvite();const d=Object.fromEntries(new FormData(e.target));const r=await api('remoto','POST',{operador_id:Number(d.operador_id),minutos:Number(d.minutos),permissao:d.permissao});await remoteAdminLoad();$('#remote-invite-link').value=r.link;$('#remote-invite-result').hidden=false;toast('Convite criado. Compartilhe com a pessoa autorizada.');});});
$('#remote-invite-reveal').addEventListener('click',e=>{const input=$('#remote-invite-link');input.type=input.type==='password'?'text':'password';e.currentTarget.textContent=input.type==='password'?'Mostrar link':'Ocultar link';});
$('#remote-invite-copy').addEventListener('click',e=>run(e.currentTarget,async()=>{try{await navigator.clipboard.writeText($('#remote-invite-link').value);toast('Convite copiado.');}catch{throw new Error('Mostre o link e copie manualmente neste computador.');}}));
$('#remote-invite-hide').addEventListener('click',clearRemoteInvite);
$('#remote-access-list').addEventListener('click',e=>{const b=e.target.closest('[data-revoke-remote]');if(!b||!confirm('Encerrar este acesso remoto agora?'))return;run(b,async()=>{await api('remoto/'+b.dataset.revokeRemote,'DELETE',{confirmar:true});await remoteAdminLoad();toast('Acesso revogado.');});});
$('#remote-revoke-all').addEventListener('click',e=>{if(!confirm('Encerrar todos os convites e sessões remotas agora?'))return;run(e.currentTarget,async()=>{await api('remoto','DELETE',{confirmar:true});await remoteAdminLoad();toast('Todos os acessos remotos foram encerrados.');});});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden')clearRemoteInvite();});
