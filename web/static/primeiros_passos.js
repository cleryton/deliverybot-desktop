'use strict';
async function preparacao(){
  const s=await api('preparacao');
  const op=s.operacao;
  const etapas=[['Personalize a loja',s.loja,'configuracoes'],['Cadastre seus produtos',s.produtos,'produtos'],['Defina responsável e contato',s.privacidade,'privacidade'],['Conecte o WhatsApp · '+s.whatsapp,op.whatsapp_ok,'conexoes'],['Prepare a IA (opcional) · '+s.ia,true,'conexoes'],['Inicie a página pública',s.endereco_publico,'publicacao'],['Abra uma compra de teste',s.abertura_recebida,'publicacao']];
  $('#preparation-steps').innerHTML=etapas.map(([titulo,ok,pagina],i)=>`<p><button data-page="${pagina}">${i+1}. ${escapeHTML(titulo)}</button> <span class="badge ${ok?'':'warning'}">${ok?'Configurado':'Confira esta etapa'}</span></p>`).join('');
  const servicos=[
    ['WhatsApp',op.whatsapp_estado,op.whatsapp_ok,'conexoes'],
    ['HTTPS da página de pedidos',op.https_estado,op.https_ok,'publicacao'],
    ['Fila de atendimento',op.fila_ok?'EM EXECUÇÃO':'PARADA',op.fila_ok,'conexoes']
  ];
  $('#preparation-live').innerHTML=servicos.map(([nome,estado,ok,pagina])=>`<p><button data-page="${pagina}">${escapeHTML(nome)}</button> <span class="badge ${ok?'':'warning'}">${escapeHTML(estado)}</span></p>`).join('');
  $('#preparation-status').textContent=!op.fila_ok?'A fila de atendimento não está ativa. Reabra o aplicativo para iniciá-la.':op.whatsapp_estado==='TESTE'?'O aplicativo está seguro em modo de teste. Quando a loja estiver pronta, abra WhatsApp e IA e conecte seu número.':!op.whatsapp_ok?'O WhatsApp ainda precisa de autenticação ou está reconectando. Abra WhatsApp e IA para ver o QR Code ou tentar novamente.':!op.https_ok?'O WhatsApp está conectado, mas os clientes ainda precisam de um endereço HTTPS. Abra Página de pedidos para configurar o túnel.':s.abertura_recebida?'A abertura do endereço de teste foi recebida. Confirme que usou os dados móveis.':s.endereco_publico?'Gere o link de teste e abra no celular usando os dados móveis.':'O link de compra precisa de um endereço HTTPS público. Abra Página de pedidos para gerar o endereço dentro do aplicativo.';
}
$('#preparation-check').addEventListener('click',e=>run(e.target,preparacao));
$('#preparation-test').addEventListener('click',e=>run(e.target,async()=>{const r=await api('preparacao/testar','POST',{});$('#preparation-link').value=r.url;$('#preparation-link').hidden=false;}));
$('#preparation-link').addEventListener('click',e=>e.target.select());
if(isAdmin)preparacao().catch(e=>toast(e.message,true));
$('#app-exit').addEventListener('click',e=>run(e.target,async()=>{if(!window.pywebview?.api?.sair_aplicativo)throw new Error('Use o aplicativo Desktop para encerrar.');if(confirm('Encerrar o aplicativo e interromper o atendimento?'))await window.pywebview.api.sair_aplicativo();}));
async function rotinasStatus(){const r=await api('rotinas'),f=$('#routines-form');for(const k of ['horas','quantidade','pasta'])f.elements[k].value=r[k];for(const k of ['backup_ativo','limpar'])f.elements[k].checked=!!r[k];$('#routines-status').textContent=r.erro||(r.executando?'Rotinas em execução.':r.backup_ativo?(r.atrasado?'Atenção: backup automático ainda ausente ou atrasado. ':'' )+'Último backup verificado: '+date(r.ultima_copia?.split('.')[0]):'Backup automático desativado. Configure uma cópia fora deste computador.');}
$('#routines-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const d=Object.fromEntries(new FormData(e.target));for(const k of ['backup_ativo','limpar'])d[k]=e.target.elements[k].checked;await api('rotinas','PUT',d);e.target.elements.senha.value='';await rotinasStatus();toast('Rotinas salvas.');});});
$('#routines-run').addEventListener('click',e=>run(e.target,async()=>{await api('rotinas','POST',{});toast('Rotinas iniciadas. Verifique o resultado em instantes.');setTimeout(()=>rotinasStatus().catch(e=>toast(e.message,true)),3000);}));
if(isAdmin)rotinasStatus().catch(e=>toast(e.message,true));
