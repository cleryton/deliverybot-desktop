'use strict';
let tutorialSteps=[],tutorialIndex=0,tutorialLoaded=false;
function tutorialRender(){
  if(!tutorialSteps.length)return;
  const step=tutorialSteps[tutorialIndex],required=tutorialSteps.filter(s=>!s.opcional),done=required.filter(s=>s.concluida).length;
  $('#tutorial-progress').textContent=`${done} de ${required.length} verificações básicas atendidas. A IA é opcional. Confira cada etapa antes de atender clientes.`;
  $('#tutorial-steps').innerHTML=tutorialSteps.map((s,i)=>`<button type="button" data-tutorial-index="${i}" aria-current="${i===tutorialIndex?'step':'false'}"><b>${i+1}</b><span>${escapeHTML(s.titulo)}<small>${s.opcional?'Opcional':s.concluida?'Verificação atendida':'Confira esta etapa'}</small></span></button>`).join('');
  $('#tutorial-agent').textContent=step.agente;
  $('#tutorial-title').textContent=step.titulo;
  $('#tutorial-state').textContent=step.opcional?'Você pode pular esta etapa e usar o menu sem IA.':step.concluida?'A verificação desta etapa está atendida. Confira as orientações para sua operação.':'Ainda falta verificar esta etapa. Siga as orientações abaixo.';
  $('#tutorial-instructions').replaceChildren(...step.instrucoes.map(text=>{const item=document.createElement('li');item.textContent=text;return item;}));
  $('#tutorial-back').disabled=tutorialIndex===0;
  $('#tutorial-next').disabled=tutorialIndex===tutorialSteps.length-1;
}
async function tutorialLoad(){
  const s=await api('preparacao');tutorialSteps=s.tutorial;
  if(!tutorialLoaded){const first=tutorialSteps.findIndex(s=>!s.opcional&&!s.concluida);tutorialIndex=first<0?0:first;tutorialLoaded=true;}
  tutorialRender();
}
$('#tutorial-steps').addEventListener('click',e=>{const b=e.target.closest('[data-tutorial-index]');if(b){tutorialIndex=Number(b.dataset.tutorialIndex);tutorialRender();}});
$('#tutorial-refresh').addEventListener('click',e=>run(e.target,tutorialLoad));
$('#tutorial-open').addEventListener('click',e=>run(e.target,()=>navigate(tutorialSteps[tutorialIndex].pagina)));
$('#tutorial-back').addEventListener('click',()=>{if(tutorialIndex>0){tutorialIndex--;tutorialRender();}});
$('#tutorial-next').addEventListener('click',()=>{if(tutorialIndex<tutorialSteps.length-1){tutorialIndex++;tutorialRender();}});
