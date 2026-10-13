'use strict';
let metaCurrent=null,metaValidated=false;
const metaCategories={marketing:'Marketing',utility:'Utilidade',authentication:'Autenticação',authentication_international:'Autenticação internacional',service:'Serviço'};
const metaStatuses={sent:'Enviada',delivered:'Entregue',read:'Lida',failed:'Falha'};
function metaMoney(value){return value===null||value===undefined?'Pendente':new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL',minimumFractionDigits:2,maximumFractionDigits:6}).format(value/1000000);}
function metaDate(value){return value?new Date(value.replace(' ','T')+'Z').toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'}):'Aguardando';}
async function metaReport(){
  const r=await api('meta/custos?'+new URLSearchParams({mes:$('#meta-month').value,ambiente:$('#meta-report-environment').value}));
  const t=r.totais;
  $('#meta-cost-metrics').innerHTML=[['Mensagens registradas',t.enviadas],['Entregues',t.entregues],['Cobráveis pela Meta',t.cobraveis],['Estimativa conhecida',metaMoney(t.estimativa_micros)]].map(([label,value])=>`<article class="metric"><span>${label}</span><strong>${escapeHTML(value)}</strong></article>`).join('');
  $('#meta-cost-note').textContent=`${r.aviso} ${t.gratuitas} gratuitas confirmadas; ${t.sem_estimativa} entregues sem estimativa; ${t.falhas} falhas de entrega.`;
  const b=r.orcamento;
  $('#meta-budget-note').dataset.level=b.nivel;
  $('#meta-budget-note').textContent=b.nivel==='DESATIVADO'?'Orçamento mensal de produção desativado.':`${b.nivel==='EXCEDIDO'?'Orçamento de produção atingido.':b.nivel==='ATENCAO'?'Atenção ao orçamento de produção.':'Orçamento de produção em acompanhamento.'} Estimativa conhecida: ${metaMoney(b.gasto_micros)} de ${metaMoney(b.limite_micros)}.${b.incompleto?' Existem custos de produção ainda não estimados.':''}`;
  $('#meta-cost-rows').innerHTML=r.mensagens.length?r.mensagens.map(m=>`<tr><td>${escapeHTML(m.referencia)}</td><td>${m.ambiente==='PRODUCAO'?'Produção':'Teste'}</td><td>${escapeHTML(metaDate(m.entregue_em))}<small>${escapeHTML(metaStatuses[m.estado]||'Pendente')}</small></td><td>${escapeHTML(metaCategories[m.categoria]||m.categoria||'Pendente')}<small>${escapeHTML(m.mercado==='BR'?'Brasil':'Outro mercado')}</small></td><td>${m.cobravel===null?'Não informada':m.cobravel?'Cobrável':'Gratuita'}</td><td>${escapeHTML(metaMoney(m.estimativa_micros))}</td></tr>`).join(''):'<tr><td colspan="6" class="empty">Ainda não há registros neste período. O acompanhamento começa com os envios e eventos recebidos por esta versão.</td></tr>';
}
async function metaLoad(){
  if(!$('#meta-month').value)$('#meta-month').value=new Intl.DateTimeFormat('sv-SE',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit'}).format(new Date());
  metaCurrent=await api('meta/situacao');
  $('#meta-environment').textContent=metaCurrent.ambiente==='PRODUCAO'?'Produção':'Teste Meta';
  $('#meta-current').textContent=`Provedor: ${metaCurrent.provedor}. ID do número: ${metaCurrent.numero_id||'Não configurado'}. Conta: ${metaCurrent.waba_id||'Não configurada'}. Mensagens pendentes: ${metaCurrent.pendentes}.`;
  $('#meta-callback').value=metaCurrent.callback;
  $('#meta-domain-note').textContent=metaCurrent.dominio_fixo?'Túnel fixo selecionado. Confira o endereço e a assinatura messages no painel Meta.':'Para produção, use um endereço HTTPS fixo. Um túnel rápido muda de endereço ao reiniciar e exige atualizar o webhook na Meta.';
  $('#meta-last-delivery').textContent=`Última entrega confirmada para este número: ${metaDate(metaCurrent.ultima_entrega_confirmada)}. Credenciais configuradas, sozinhas, não comprovam recebimento e resposta.`;
  const f=$('#meta-migration-form');
  if(!f.elements.WHATSAPP_BUSINESS_ACCOUNT_ID.value)f.elements.WHATSAPP_BUSINESS_ACCOUNT_ID.value=metaCurrent.waba_id;
  const rates=await api('meta/tarifas'),rf=$('#meta-rates-form');
  for(const [category,rate] of Object.entries(rates.tarifas))rf.elements[category].value=rate?.valor??'';
  rf.elements.limite.value=rates.orcamento.limite;rf.elements.alerta_percentual.value=rates.orcamento.alerta_percentual;
  await metaReport();
}
$('#meta-refresh').addEventListener('click',e=>run(e.currentTarget,metaLoad));
$('#meta-report-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,metaReport);});
$('#meta-migration-form').addEventListener('input',()=>{metaValidated=false;$('#meta-migrate').disabled=true;$('#meta-migration-result').textContent='Os dados mudaram. Valide novamente antes de confirmar.';});
$('#meta-migration-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{
  const r=await api('meta/verificar','POST',Object.fromEntries(new FormData(e.target)));
  metaValidated=true;$('#meta-migrate').disabled=false;$('#meta-migration-result').textContent=`Número validado: ${r.telefone} · ${r.nome}. ${r.aviso}`;
});});
$('#meta-migrate').addEventListener('click',e=>run(e.currentTarget,async()=>{
  if(!metaValidated||!metaCurrent)return;
  if(!confirm('Trocar a conexão local para este número próprio da Meta? Confira a preparação no painel Meta e o HTTPS fixo. Produtos, pedidos e custos anteriores serão preservados.'))return;
  const d=Object.fromEntries(new FormData($('#meta-migration-form')));
  d.confirmar_migracao=true;d.numero_anterior=metaCurrent.numero_id;
  const r=await api('meta/migrar','POST',d);
  for(const k of ['WHATSAPP_TOKEN','WHATSAPP_APP_SECRET','WHATSAPP_VERIFY_TOKEN'])$('#meta-migration-form').elements[k].value='';
  metaValidated=false;$('#meta-migrate').disabled=true;$('#meta-migration-result').textContent=r.aviso;
  await metaLoad();
}));
$('#meta-rates-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{
  const d=Object.fromEntries(new FormData(e.target)),tarifas={};
  for(const k of Object.keys(metaCategories))if(d[k]!=='')tarifas[k]=d[k];
  await api('meta/custos','PUT',{tarifas,limite:d.limite,alerta_percentual:Number(d.alerta_percentual)});
  toast('Tarifas e orçamento salvos. Os valores continuam sendo estimativas.');await metaLoad();
});});
let metaPolling=false;
setInterval(async()=>{if(!isAdmin||state.page!=='meta'||document.visibilityState!=='visible'||metaPolling)return;metaPolling=true;try{await metaReport();}catch(e){$('#meta-cost-note').textContent=e.message;}finally{metaPolling=false;}},15000);
