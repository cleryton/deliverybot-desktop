'use strict';
(() => {
// Contas e auditoria.
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

// Manutenção e atualização do aplicativo.
let atualizacaoAlterando=false;
const consultaAtualizacoes=DeliveryUX.consultaAtual(()=>api('atualizacoes'),r=>{
  $('#update-current').textContent=r.atual;
  $('#update-auto').checked=!!r.automatica;
  $('#update-status').textContent=r.tarefa?.mensagem||r.release.mensagem||'Consulte as versões publicadas no GitHub.';
  $('#update-latest').textContent=r.release.versao||'—';
  DeliveryUX.disponivel($('#update-download'), r.release.nova&&r.tarefa?.estado!=='EXECUTANDO');
  DeliveryUX.disponivel($('#update-install'), r.download.assinatura_confiavel&&r.tarefa?.estado!=='EXECUTANDO');
  $('#update-files').textContent=r.download.caminho?'Instalador: '+r.download.caminho+'\nBackup verificado: '+r.download.backup+'\nAssinatura confiável: '+(r.download.assinatura_confiavel?'Sim':'Não — instalação automática bloqueada.') : '';
  if(r.release.nova)$('#update-notice').textContent='Versão '+r.release.versao+' disponível. Abra Atualizações para conferir.';
});
async function atualizacoesStatus(){
  if(atualizacaoAlterando)return false;
  return consultaAtualizacoes.consultar();
}
async function alterarAtualizacao(acao){
  if(atualizacaoAlterando)throw new Error('Aguarde a alteração da atualização terminar.');
  atualizacaoAlterando=true;consultaAtualizacoes.invalidar();
  let falhou=false;
  try{return await acao();}catch(erro){falhou=true;throw erro;}
  finally{atualizacaoAlterando=false;try{await atualizacoesStatus();}catch(erro){if(!falhou)throw erro;}}
}
$('#update-check').addEventListener('click',e=>run(e.target,()=>alterarAtualizacao(()=>api('atualizacoes','POST',{acao:'consultar'}))));
$('#update-auto').addEventListener('change',e=>run(e.target,async()=>{const automatica=e.target.checked;await alterarAtualizacao(()=>api('atualizacoes','PUT',{automatica}));toast('Preferência salva. A consulta automática ocorre uma vez por dia com o aplicativo aberto.');}));
$('#update-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const campo=e.target.elements.senha,senha=campo.value;await alterarAtualizacao(async()=>{await api('atualizacoes','POST',{acao:'baixar',senha});if(campo.value===senha)campo.value='';});});});
$('#update-install').addEventListener('click',e=>run(e.target,async()=>{if(!window.pywebview?.api)throw new Error('Abra o aplicativo Desktop para instalar.');if(confirm('Encerrar o aplicativo e abrir o instalador verificado? O backup anterior está guardado.'))await window.pywebview.api.instalar_atualizacao();}));
if(isAdmin){atualizacoesStatus().catch(e=>toast(e.message,true));setInterval(()=>{if(document.visibilityState==='visible'&&state.page==='atualizacoes')run(null,atualizacoesStatus);},3000);}
})();
