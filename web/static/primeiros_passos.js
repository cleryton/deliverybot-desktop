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
async function rotinasStatus(){const r=await api('rotinas'),f=$('#routines-form');for(const k of ['horas','quantidade','pasta'])f.elements[k].value=r[k];for(const k of ['backup_ativo','limpar'])f.elements[k].checked=!!r[k];$('#routines-status').textContent=r.erro||(r.executando?'Rotinas em execução.':r.backup_ativo?(r.atrasado?'Atenção: backup automático ainda ausente ou atrasado. ':'' )+'Último backup verificado: '+date(r.ultima_copia?.split('.')[0]):'Backup automático desativado. Configure uma cópia fora deste computador.');}
$('#routines-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const d=Object.fromEntries(new FormData(e.target));for(const k of ['backup_ativo','limpar'])d[k]=e.target.elements[k].checked;await api('rotinas','PUT',d);e.target.elements.senha.value='';await rotinasStatus();toast('Rotinas salvas.');});});
$('#routines-run').addEventListener('click',e=>run(e.target,async()=>{await api('rotinas','POST',{});toast('Rotinas iniciadas. Verifique o resultado em instantes.');setTimeout(()=>rotinasStatus().catch(e=>toast(e.message,true)),3000);}));
rotinasStatus().catch(e=>toast(e.message,true));
