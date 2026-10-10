'use strict';
async function preparacao(){
  const s=await api('preparacao');
  const etapas=[['Personalize a loja',s.loja,'configuracoes'],['Cadastre seus produtos',s.produtos,'produtos'],['Defina responsável e contato',s.privacidade,'privacidade'],['Conecte o WhatsApp · '+s.whatsapp,s.whatsapp!=='TESTE','conexoes'],['Prepare a IA (opcional) · '+s.ia,true,'conexoes'],['Abra uma compra de teste',false,'bot']];
  $('#preparation-steps').innerHTML=etapas.map(([titulo,ok,pagina],i)=>`<p><button data-page="${pagina}">${i+1}. ${escapeHTML(titulo)}</button> <span class="badge ${ok?'':'warning'}">${ok?'Configurado':'Confira esta etapa'}</span></p>`).join('');
  $('#preparation-status').textContent=s.abertura_recebida?'A abertura do endereço de teste foi recebida. Confirme que você abriu pelo celular usando outra conexão de internet.':s.endereco_publico?'Gere o endereço de teste e abra no celular, usando os dados móveis. Depois clique em Verificar preparação.':'O link de compra precisa de um endereço HTTPS público. Um endereço localhost não abre no celular do cliente. Configure seu domínio ou túnel em Configurações.';
}
$('#preparation-check').addEventListener('click',e=>run(e.target,preparacao));
$('#preparation-test').addEventListener('click',e=>run(e.target,async()=>{const r=await api('preparacao/testar','POST',{});$('#preparation-link').value=r.url;$('#preparation-link').hidden=false;}));
$('#preparation-link').addEventListener('click',e=>e.target.select());
preparacao().catch(e=>toast(e.message,true));
$('#app-exit').addEventListener('click',e=>run(e.target,async()=>{if(!window.pywebview?.api?.sair_aplicativo)throw new Error('Use o aplicativo Desktop para encerrar.');if(confirm('Encerrar o aplicativo e interromper o atendimento?'))await window.pywebview.api.sair_aplicativo();}));
