'use strict';
let paginaCarregada=false;
let tokenConfigurado=false;
let estadoPublicacao=null;
let publicacaoAlterando=false, publicacaoEdicoes=0;
$('#public-form').addEventListener('input',()=>publicacaoEdicoes++);
$('#public-form').addEventListener('change',()=>publicacaoEdicoes++);
function camposPublicacao(){
  $('#public-fixed').hidden=$('#public-mode').value!=='FIXO';
  atualizarAssistenteDominio();
}
function atualizarAssistenteDominio(s=estadoPublicacao){
  if(!s||!$('#fixed-config-state'))return;
  const dominio=Boolean($('#public-domain').value.trim());
  const token=Boolean($('#public-token').value.trim())||tokenConfigurado;
  const online=s.estado==='ONLINE';
  const etapas=[['Domínio HTTPS informado',dominio],['Token do conector salvo',token],['Túnel conectado',online]];
  $('#fixed-config-state').innerHTML=etapas.map(([nome,ok])=>`<p>${escapeHTML(nome)} <span class="badge ${ok?'':'warning'}">${ok?'Pronto':'Pendente'}</span></p>`).join('');
  const concluidos=etapas.filter(([,ok])=>ok).length;
  $('#fixed-setup-status').textContent=concluidos===3?'Configuração pronta. Gere o link de teste e confirme o acesso pelo celular.':`${concluidos} de 3 etapas concluídas. O token nunca é exibido novamente.`;
}
const consultaPublicacao=DeliveryUX.consultaAtual(()=>api('pagina-publica'),(s,atualizarFormulario,revisao)=>{
  estadoPublicacao=s;
  $('#public-state').textContent=({ONLINE:'Página HTTPS pronta',DESLIGADO:'Desligada',INICIANDO:'Iniciando…',RECONECTANDO:'Reconectando…',ERRO:'Confira a conexão'})[s.estado]||s.estado;
  $('#public-status').textContent=s.mensagem;
  $('#public-url').value=s.url;
  DeliveryUX.disponivel($('#public-copy'), !!s.url);
  DeliveryUX.disponivel($('#public-test'), !!s.url);
  DeliveryUX.disponivel($('#public-start'), s.disponivel&&!(s.ativo&&s.estado!=='ERRO'));
  DeliveryUX.disponivel($('#public-stop'), s.disponivel&&s.ativo);
  $('#public-settings').disabled=s.ativo||!s.disponivel;
  $('#public-origin').textContent='http://127.0.0.1:'+s.porta;
  $('#public-token').placeholder=s.token_configurado?'Token já salvo. Vazio preserva o atual.':'Cole somente o token do conector';
  tokenConfigurado=s.token_configurado;
  if((atualizarFormulario&&revisao===publicacaoEdicoes)||(!paginaCarregada&&publicacaoEdicoes===0)){
    $('#public-mode').value=s.modo_configurado;
    $('#public-auto').checked=s.automatico;
    $('#public-domain').value=s.dominio;
    $('#public-port').value=s.porta_configurada;
    camposPublicacao();
  }
  paginaCarregada=true;
  atualizarAssistenteDominio(s);
});
async function paginaPublica(atualizarFormulario=false,revisao=publicacaoEdicoes){
  if(publicacaoAlterando)return false;
  return consultaPublicacao.consultar(atualizarFormulario,revisao);
}
async function alterarPublicacao(acao,atualizarFormulario=false,revisao=publicacaoEdicoes){
  if(publicacaoAlterando)throw new Error('Aguarde a alteração da página de pedidos terminar.');
  publicacaoAlterando=true;consultaPublicacao.invalidar();
  let falhou=false;
  try{return await acao();}catch(erro){falhou=true;throw erro;}
  finally{publicacaoAlterando=false;try{await paginaPublica(atualizarFormulario&&!falhou,revisao);}catch(erro){if(!falhou)throw erro;}}
}
function configuracaoPublicacao(){
  return {TUNEL_MODO:$('#public-mode').value,TUNEL_AUTOMATICO:$('#public-auto').checked?'SIM':'NAO',TUNEL_URL:$('#public-domain').value,TUNEL_TOKEN:$('#public-token').value,TUNEL_PORTA:Number($('#public-port').value)};
}
async function salvarPublicacao(dados){
  await api('pagina-publica','PUT',dados);
  if($('#public-token').value===dados.TUNEL_TOKEN)$('#public-token').value='';
}
$('#public-mode').addEventListener('change',camposPublicacao);
$('#public-port').addEventListener('input',e=>$('#public-origin').textContent='http://127.0.0.1:'+e.target.value);
$('#public-domain').addEventListener('input',()=>atualizarAssistenteDominio());
$('#public-token').addEventListener('input',()=>atualizarAssistenteDominio());
$('#public-copy-origin').addEventListener('click',e=>run(e.target,async()=>{const destino=$('#public-origin').textContent;try{await navigator.clipboard.writeText(destino);toast('Destino copiado. Cole-o como serviço HTTP na Cloudflare.');}catch{$('#public-origin').focus();toast('Destino: '+destino);}}));
$('#public-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{
  const dados=configuracaoPublicacao(),revisao=publicacaoEdicoes;
  await alterarPublicacao(()=>salvarPublicacao(dados),true,revisao);toast('Configuração salva. Clique em Iniciar página de pedidos.');
});});
$('#public-start').addEventListener('click',e=>run(e.target,async()=>{
  const dados=configuracaoPublicacao();
  await alterarPublicacao(async()=>{
    const s=await api('pagina-publica');
    if(s.ativo&&s.estado==='ERRO')await api('pagina-publica','POST',{acao:'parar'});
    if(!s.ativo||s.estado==='ERRO')await salvarPublicacao(dados);
    await api('pagina-publica','POST',{acao:'iniciar'});
  });toast('Página iniciando em segundo plano…');
}));
$('#public-stop').addEventListener('click',e=>run(e.target,async()=>{if(!confirm('Desligar a página pública? Os clientes não conseguirão abrir seus links até você iniciar novamente.'))return;await alterarPublicacao(()=>api('pagina-publica','POST',{acao:'parar'}));}));
$('#public-copy').addEventListener('click',e=>run(e.target,async()=>{try{await navigator.clipboard.writeText($('#public-url').value);toast('Endereço copiado. Os links de compra individuais são enviados pelo bot.');}catch{$('#public-url').focus();$('#public-url').select();toast('Endereço selecionado. Pressione Ctrl+C para copiar.');}}));
$('#public-test').addEventListener('click',e=>run(e.target,async()=>{const r=await api('preparacao/testar','POST',{});$('#public-test-link').value=r.url;$('#public-test-link').hidden=false;toast('Copie o link de teste e abra no celular usando dados móveis.');}));
$('#public-url').addEventListener('click',e=>e.target.select());
$('#public-test-link').addEventListener('click',e=>e.target.select());
document.addEventListener('click',e=>{if(e.target.closest('[data-page=publicacao]'))run(null,paginaPublica);});
if(isAdmin)paginaPublica().catch(e=>toast(e.message,true));
setInterval(()=>{if(isAdmin&&document.visibilityState==='visible'&&state.page==='publicacao')run(null,paginaPublica);},3000);
