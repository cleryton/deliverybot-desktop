'use strict';
async function humanos(){const lista=await api('humano');$('#human-list').innerHTML=lista.map(a=>`<p><b>${escapeHTML(a.nome)}</b> · ${escapeHTML(a.telefone)} · ${escapeHTML(a.estado)} <button data-human="${escapeHTML(a.telefone)}">Abrir conversa</button></p>`).join('')||'Nenhuma solicitação de atendimento humano.';}
document.addEventListener('click',e=>{const b=e.target.closest('[data-human]');if(b)run(b,async()=>{$('#human-form').elements.telefone.value=b.dataset.human;await abrirConversa();});});
async function abrirConversa(){const t=$('#human-form').elements.telefone.value;const r=await api('humano?telefone='+encodeURIComponent(t));$('#human-chat').textContent=r.map(m=>(m.direcao==='ENTRADA'?'Cliente: ':'Loja: ')+m.conteudo).join('\n\n')||'Sem mensagens registradas.';}
$('#human-form').addEventListener('submit',e=>{e.preventDefault();run(e.submitter,async()=>{const d=Object.fromEntries(new FormData(e.target));d.acao=e.submitter.value;if(d.acao==='abrir'){await abrirConversa();return;}if(d.acao==='responder'){d.confirmar_envio=confirm('Enviar esta mensagem pelo WhatsApp ao cliente informado?');if(!d.confirmar_envio)return;}await api('humano','POST',d);if(d.acao==='responder')e.target.elements.mensagem.value='';await humanos();await abrirConversa();toast(d.acao==='responder'?'Resposta registrada para envio.':'Atendimento atualizado.');});});
$('#human-refresh').addEventListener('click',e=>run(e.target,humanos));
humanoInit();
function humanoInit(){humanos().catch(e=>toast(e.message,true));}
