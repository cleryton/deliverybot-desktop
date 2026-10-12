'use strict';
async function preparacao(){
  const s=await api('preparacao');
  const op=s.operacao;
  const etapas=s.tutorial;
  const proximo=DeliveryUX.proximoPasso(s),conexao=DeliveryUX.conexao(s);
  $('#next-step-title').textContent=proximo.titulo;$('#next-step-label').textContent=proximo.pronto?'VERIFICAÇÕES ATENDIDAS':'PRÓXIMO PASSO';
  $('#next-step-help').textContent=proximo.pronto?'As verificações atuais estão atendidas. Mantenha o computador ligado e acompanhe o atendimento.':'Continue pela etapa abaixo. Seus cadastros e configurações anteriores são preservados.';
  $('#next-step-action').dataset.page=proximo.pagina;$('#next-step-action').textContent=proximo.pronto?'Ver pedidos':'Continuar configuração';
  $('#connection').textContent=conexao.texto;$('#connection').classList.toggle('warning',!conexao.ok);
  $('#preparation-steps').innerHTML=etapas.map((s,i)=>`<p><button data-page="${s.pagina}">${i+1}. ${escapeHTML(s.titulo)}</button> <span class="badge ${s.concluida||s.opcional?'':'warning'}">${s.opcional?'Opcional':s.concluida?'Verificação atendida':'Confira esta etapa'}</span></p>`).join('');
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
// A visão geral atualiza a preparação no próprio carregamento, sem consultas duplicadas.
$('#app-exit').addEventListener('click',e=>run(e.target,async()=>{if(!window.pywebview?.api?.sair_aplicativo)throw new Error('Use o aplicativo Desktop para encerrar.');if(confirm('Encerrar o aplicativo e interromper o atendimento?'))await window.pywebview.api.sair_aplicativo();}));
async function rotinasStatus(){const r=await api('rotinas'),f=$('#routines-form');for(const k of ['horas','quantidade','pasta'])f.elements[k].value=r[k];for(const k of ['backup_ativo','limpar'])f.elements[k].checked=!!r[k];const aviso=$('#backup-warning');$('#routines-status').textContent=r.erro||(r.executando?'Rotinas em execução.':r.backup_ativo?(r.atrasado?'Atenção: backup automático ainda ausente ou atrasado. ':'')+'Último backup verificado: '+date(r.ultima_copia?.split('.')[0]):'Backup automático desativado. Configure uma cópia fora deste computador.');if(r.erro||r.atrasado||!r.backup_ativo){aviso.hidden=false;aviso.classList.add('warning');aviso.innerHTML=`${r.erro?'O último backup automático falhou. Confira as configurações e tente novamente.':r.atrasado?'O backup automático está atrasado. Confira se o disco de destino está disponível.':'Os backups automáticos estão desativados.'} <button type="button" id="backup-warning-action">Revisar proteção</button>`;}else aviso.hidden=true;}
$('#backup-warning').addEventListener('click',e=>{if(e.target.id==='backup-warning-action')$('#routines-form').scrollIntoView({behavior:'smooth',block:'center'});});
$('#routines-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const d=Object.fromEntries(new FormData(e.target));for(const k of ['backup_ativo','limpar'])d[k]=e.target.elements[k].checked;await api('rotinas','PUT',d);e.target.elements.senha.value='';await rotinasStatus();toast('Rotinas salvas.');});});
$('#routines-run').addEventListener('click',e=>run(e.target,async()=>{await api('rotinas','POST',{});toast('Rotinas iniciadas. Verifique o resultado em instantes.');setTimeout(()=>rotinasStatus().catch(e=>toast(e.message,true)),3000);}));
if(isAdmin)rotinasStatus().catch(e=>toast(e.message,true));
