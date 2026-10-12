'use strict';
async function operadoresStatus(){
  const [contas,acoes]=await Promise.all([api('operadores'),api('operadores/auditoria')]);
  $('#operator-list').innerHTML=contas.map(c=>`<p><b>${escapeHTML(c.nome)}</b> · ${escapeHTML(c.login)} · ${c.perfil==='ADMIN'?'Administrador':c.perfil==='CAIXA'?'Caixa':'Atendente'} · ${c.ativo?'Ativo':'Desativado'} <button data-operador="${c.id}" data-perfil="${c.perfil}" data-ativo="${c.ativo}">Alterar conta</button></p>`).join('')||'Nenhuma conta criada. O responsável local tem acesso administrativo.';
  $('#operator-audit').innerHTML=acoes.map(a=>`<p>${date(a.criado_em)} · ${escapeHTML(a.operador)} · ${escapeHTML(a.acao)} ${escapeHTML(a.objeto||'')}</p>`).join('')||'Sem registros.';
}
$('#operator-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{await api('operadores','POST',Object.fromEntries(new FormData(e.target)));e.target.reset();await operadoresStatus();toast('Conta criada. Guarde a senha em local seguro.');});});
$('#operator-list').addEventListener('click',e=>{const b=e.target.closest('[data-operador]');if(!b)return;run(b,async()=>{
  const f=$('#operator-edit-form');f.reset();f.elements.id.value=b.dataset.operador;f.elements.perfil.value=b.dataset.perfil;f.elements.ativo.checked=b.dataset.ativo==='1';$('#operator-edit').showModal();
});});
$('#operator-edit-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const f=e.target;await api('operadores/'+f.elements.id.value,'PUT',{perfil:f.elements.perfil.value,ativo:f.elements.ativo.checked,senha:f.elements.senha.value});f.reset();location.reload();});});
$('#operator-logout').addEventListener('click',e=>run(e.target,async()=>{const r=await fetch('/gestao/sair',{method:'POST',headers:{'X-CSRF-Token':$('meta[name="csrf-token"]').content}});if(!r.ok)throw new Error('Não foi possível sair.');location.assign('/gestao');}));
if(isAdmin)operadoresStatus().catch(e=>toast(e.message,true));
