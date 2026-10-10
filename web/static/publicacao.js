'use strict';
let paginaCarregada=false;
function camposPublicacao(){
  $('#public-fixed').hidden=$('#public-mode').value!=='FIXO';
}
async function paginaPublica(atualizarFormulario=false){
  const s=await api('pagina-publica');
  $('#public-state').textContent=({ONLINE:'Conector ligado',DESLIGADO:'Desligada',INICIANDO:'Iniciando…',RECONECTANDO:'Reconectando…',ERRO:'Confira a conexão'})[s.estado]||s.estado;
  $('#public-status').textContent=s.mensagem;
  $('#public-url').value=s.url;
  $('#public-copy').disabled=!s.url;
  $('#public-test').disabled=!s.url;
  $('#public-start').disabled=!s.disponivel||s.ativo&&s.estado!=='ERRO';
  $('#public-stop').disabled=!s.disponivel||!s.ativo;
  $('#public-settings').disabled=s.ativo||!s.disponivel;
  $('#public-origin').textContent='http://127.0.0.1:'+s.porta;
  $('#public-token').placeholder=s.token_configurado?'Token já salvo. Vazio preserva o atual.':'Cole somente o token do conector';
  if(atualizarFormulario||!paginaCarregada){
    $('#public-mode').value=s.modo_configurado;
    $('#public-auto').checked=s.automatico;
    $('#public-domain').value=s.dominio;
    $('#public-port').value=s.porta_configurada;
    camposPublicacao();paginaCarregada=true;
  }
}
$('#public-mode').addEventListener('change',camposPublicacao);
$('#public-port').addEventListener('input',e=>$('#public-origin').textContent='http://127.0.0.1:'+e.target.value);
$('#public-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{
  await api('pagina-publica','PUT',{TUNEL_MODO:$('#public-mode').value,TUNEL_AUTOMATICO:$('#public-auto').checked?'SIM':'NAO',TUNEL_URL:$('#public-domain').value,TUNEL_TOKEN:$('#public-token').value,TUNEL_PORTA:Number($('#public-port').value)});
  $('#public-token').value='';await paginaPublica(true);toast('Configuração salva. Clique em Iniciar página de pedidos.');
});});
$('#public-start').addEventListener('click',e=>run(e.target,async()=>{
  const s=await api('pagina-publica');
  if(s.ativo&&s.estado==='ERRO')await api('pagina-publica','POST',{acao:'parar'});
  if(!s.ativo||s.estado==='ERRO'){
    await api('pagina-publica','PUT',{TUNEL_MODO:$('#public-mode').value,TUNEL_AUTOMATICO:$('#public-auto').checked?'SIM':'NAO',TUNEL_URL:$('#public-domain').value,TUNEL_TOKEN:$('#public-token').value,TUNEL_PORTA:Number($('#public-port').value)});
    $('#public-token').value='';
  }
  await api('pagina-publica','POST',{acao:'iniciar'});await paginaPublica();toast('Página iniciando em segundo plano…');
}));
$('#public-stop').addEventListener('click',e=>run(e.target,async()=>{if(!confirm('Desligar a página pública? Os clientes não conseguirão abrir seus links até você iniciar novamente.'))return;await api('pagina-publica','POST',{acao:'parar'});await paginaPublica();}));
$('#public-copy').addEventListener('click',e=>run(e.target,async()=>{try{await navigator.clipboard.writeText($('#public-url').value);toast('Endereço copiado. Os links de compra individuais são enviados pelo bot.');}catch{$('#public-url').focus();$('#public-url').select();toast('Endereço selecionado. Pressione Ctrl+C para copiar.');}}));
$('#public-test').addEventListener('click',e=>run(e.target,async()=>{const r=await api('preparacao/testar','POST',{});$('#public-test-link').value=r.url;$('#public-test-link').hidden=false;toast('Copie o link de teste e abra no celular usando dados móveis.');}));
$('#public-url').addEventListener('click',e=>e.target.select());
$('#public-test-link').addEventListener('click',e=>e.target.select());
document.addEventListener('click',e=>{if(e.target.closest('[data-page=publicacao]'))run(null,paginaPublica);});
if(isAdmin)paginaPublica().catch(e=>toast(e.message,true));
setInterval(()=>{if(isAdmin&&document.visibilityState==='visible'&&state.page==='publicacao')run(null,paginaPublica);},3000);
