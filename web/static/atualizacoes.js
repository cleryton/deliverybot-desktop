'use strict';
async function atualizacoesStatus(){
  const r=await api('atualizacoes');$('#update-current').textContent=r.atual;
  $('#update-auto').checked=!!r.automatica;
  $('#update-status').textContent=r.tarefa?.mensagem||r.release.mensagem||'Consulte as versões publicadas no GitHub.';
  $('#update-latest').textContent=r.release.versao||'—';
  $('#update-download').disabled=!r.release.nova||r.tarefa?.estado==='EXECUTANDO';
  $('#update-install').disabled=!r.download.assinatura_confiavel||r.tarefa?.estado==='EXECUTANDO';
  $('#update-files').textContent=r.download.caminho?'Instalador: '+r.download.caminho+'\nBackup verificado: '+r.download.backup+'\nAssinatura confiável: '+(r.download.assinatura_confiavel?'Sim':'Não — instalação automática bloqueada.') : '';
  if(r.release.nova)$('#update-notice').textContent='Versão '+r.release.versao+' disponível. Abra Atualizações para conferir.';
}
$('#update-check').addEventListener('click',e=>run(e.target,async()=>{await api('atualizacoes','POST',{acao:'consultar'});await atualizacoesStatus();}));
$('#update-auto').addEventListener('change',e=>run(null,async()=>{await api('atualizacoes','PUT',{automatica:e.target.checked});toast('Preferência salva. A consulta automática ocorre uma vez por dia com o aplicativo aberto.');}));
$('#update-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{await api('atualizacoes','POST',{acao:'baixar',senha:e.target.elements.senha.value});e.target.elements.senha.value='';await atualizacoesStatus();});});
$('#update-install').addEventListener('click',e=>run(e.target,async()=>{if(!window.pywebview?.api)throw new Error('Abra o aplicativo Desktop para instalar.');if(confirm('Encerrar o aplicativo e abrir o instalador verificado? O backup anterior está guardado.'))await window.pywebview.api.instalar_atualizacao();}));
if(isAdmin){atualizacoesStatus().catch(e=>toast(e.message,true));setInterval(()=>{if(document.visibilityState==='visible'&&state.page==='atualizacoes')run(null,atualizacoesStatus);},3000);}
