'use strict';
const $=s=>document.querySelector(s),money=c=>(c/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
let catalogo=[],itens=new Map(),cotacao=null,busy=false,caixa=null,revisaoCotacao=0;
function aviso(t,erro=false){$('#aviso').textContent=t;$('#aviso').classList.toggle('erro',erro);}
async function tratarSessao(){
  if($('#painel').hidden)return;
  const s=await window.pywebview.api.sessao();
  if(!s.autenticado){itens.clear();catalogo=[];limparCotacao();renderCarrinho();$('#catalogo').replaceChildren();$('#pedidos').replaceChildren();$('#historico').replaceChildren();$('#pedido-form').reset();$('#painel').hidden=true;$('#login').hidden=false;$('#sair').hidden=true;$('#identidade').textContent='Entre novamente com sua conta vinculada';}
}
async function run(fn){if(busy)return;busy=true;const botoes=[...document.querySelectorAll('button')],estados=botoes.map(b=>b.disabled);botoes.forEach(b=>b.disabled=true);try{await fn();}catch(e){try{await tratarSessao();}catch(_){}aviso(e.message||String(e),true);if(!$('#painel').hidden)$('#pendencia').hidden=false;}finally{busy=false;botoes.forEach((b,i)=>b.disabled=estados[i]);$('#registrar').disabled=!cotacao;}}
function el(tag,texto,classe){const e=document.createElement(tag);if(texto!==undefined)e.textContent=texto;if(classe)e.className=classe;return e;}
function limparCotacao(){revisaoCotacao++;cotacao=null;$('#cotacao').textContent='Revise os valores antes de confirmar.';$('#registrar').disabled=true;}
function renderCatalogo(){const q=$('#busca').value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();$('#catalogo').replaceChildren();for(const p of catalogo){if(![p.nome,p.variacao,p.categoria].join(' ').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().includes(q))continue;const a=el('article',undefined,'card produto');a.append(el('strong',p.nome+(p.variacao?' · '+p.variacao:'')),el('small',p.categoria+' · '+(p.estoque===null?'Sob demanda':p.estoque+' '+p.unidade)),el('p',money(Math.round(p.preco*100)),'preco'));const b=el('button','Adicionar');b.disabled=p.estoque===0;b.addEventListener('click',()=>{const atual=itens.get(p.id)||0,passo=p.fracionado?.1:1;itens.set(p.id,Math.round((atual+passo)*1000)/1000);limparCotacao();renderCarrinho();});a.append(b);$('#catalogo').append(a);}if(!$('#catalogo').children.length)$('#catalogo').append(el('p','Nenhum produto nesta busca.'))}
function renderCarrinho(){
  $('#carrinho').replaceChildren();
  for(const [id,q] of itens){
    const p=catalogo.find(p=>p.id===id);if(!p)continue;
    const a=el('div',undefined,'item'),label=el('label',p.nome),n=el('input');
    n.type='number';n.required=true;n.min=p.fracionado?'0.001':'1';n.max='999999';n.step=p.fracionado?'0.001':'1';n.value=q;
    n.setAttribute('form','pedido-form');n.setAttribute('aria-label','Quantidade de '+p.nome);
    const editar=()=>{
      limparCotacao();
      n.setAttribute('aria-invalid',String(!n.validity.valid));
      if(n.validity.valid)itens.set(id,Number(n.value));
    };
    n.addEventListener('input',editar);n.addEventListener('change',editar);label.append(n);
    const b=el('button','Remover');b.type='button';
    b.addEventListener('click',()=>{itens.delete(id);limparCotacao();renderCarrinho();});
    a.append(label,b);$('#carrinho').append(a);
  }
  if(!itens.size)$('#carrinho').append(el('p','Seu pedido ainda está vazio.','muted'));
}
function itensPedido(){return [...itens].map(([produto_id,quantidade])=>({produto_id,quantidade}));}
async function refresh(){const r=await window.pywebview.api.consultar('estado');caixa=r.caixas.find(c=>!c.fechado_em);$('#movimento').hidden=!r.permissoes?.movimentar;$('#abertura').hidden=!!caixa;$('#operacao').hidden=!caixa;$('#esperado').textContent=caixa?money(caixa.esperado_centavos):'Caixa fechado';$('#vendas-total').textContent=caixa?money(caixa.vendas_centavos):'—';$('#pix').textContent=caixa?money(caixa.recebimentos.PIX):'—';$('#cartao').textContent=caixa?money(caixa.recebimentos.CARTAO):'—';$('#pedidos').replaceChildren();for(const p of r.vendas){const linha=el('div',undefined,'item');linha.append(el('span',p.numero_pedido+' · '+p.nome+' · '+money(Math.round(p.total_pedido*100))+' · '+(p.total_pago>=p.total_pedido?'Recebido':'Pendente')+' · '+p.status));if(caixa&&p.total_pago<p.total_pedido&&p.status!=='CANCELADO'){const b=el('button','Registrar recebimento');b.addEventListener('click',()=>run(async()=>{const forma=prompt('Forma: DINHEIRO, PIX ou CARTAO','DINHEIRO');if(!forma)return;const recebido=forma==='DINHEIRO'?prompt('Dinheiro recebido em R$',String(p.total_pedido)):undefined;if(forma==='DINHEIRO'&&recebido===null)return;await window.pywebview.api.executar('receber/'+p.id,{forma,recebido});aviso('Recebimento registrado.');await refresh();}));linha.append(b);}$('#pedidos').append(linha);}$('#historico').replaceChildren();for(const c of r.caixas.filter(c=>c.fechado_em))$('#historico').append(el('p','Caixa #'+c.id+' · '+c.fechado_em+' UTC · esperado '+money(c.esperado_centavos)+' · contado '+money(c.contado_centavos)+' · diferença '+money(c.diferenca_centavos)));const pend=await window.pywebview.api.conferir();$('#pendencia').hidden=!pend.pendente;}
$('#importar').addEventListener('click',()=>run(async()=>{const r=await window.pywebview.api.importar();if(!r.cancelado)aviso('Computador autorizado. Entre com sua conta.');}));
$('#login-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{const f=e.target,r=await window.pywebview.api.entrar(f.login.value,f.senha.value);f.senha.value='';$('#identidade').textContent=r.loja+' · '+r.usuario.nome;$('#login').hidden=true;$('#painel').hidden=false;$('#sair').hidden=false;catalogo=await window.pywebview.api.consultar('catalogo');renderCatalogo();renderCarrinho();await refresh();aviso('Você entrou no seu caixa.');});});
$('#sair').addEventListener('click',()=>run(async()=>{await window.pywebview.api.sair();itens.clear();catalogo=[];limparCotacao();renderCarrinho();$('#catalogo').replaceChildren();$('#pedidos').replaceChildren();$('#historico').replaceChildren();$('#pedido-form').reset();$('#painel').hidden=true;$('#login').hidden=false;$('#sair').hidden=true;$('#identidade').textContent='Seu balcão, organizado';aviso('Conta encerrada.');}));
$('#abertura').addEventListener('submit',e=>{e.preventDefault();run(async()=>{await window.pywebview.api.executar('abrir',{abertura:e.target.abertura.value});await refresh();aviso('Caixa aberto.');});});
$('#busca').addEventListener('input',renderCatalogo);
$('#atualizar').addEventListener('click',()=>run(async()=>{catalogo=await window.pywebview.api.consultar('catalogo');limparCotacao();renderCatalogo();await refresh();}));
$('#revisar').addEventListener('click',()=>run(async()=>{
  const f=$('#pedido-form');if(!f.reportValidity()){limparCotacao();return;}
  const revisao=revisaoCotacao;
  const conferida=await window.pywebview.api.cotar(itensPedido(),f.entrega.value);
  if(revisao!==revisaoCotacao)return;
  cotacao=conferida;$('#cotacao').textContent='Total conferido: '+money(Math.round(cotacao.total_pedido*100));
}));
$('#pedido-form').addEventListener('input',e=>{if(e.target.name==='entrega'){limparCotacao();const entrega=e.currentTarget.entrega.value==='ENTREGA';$('#endereco-label').hidden=!entrega;e.currentTarget.endereco.required=entrega;}if(e.target.name==='pago'||e.target.name==='forma')$('#recebido-label').hidden=!e.currentTarget.pago.checked||e.currentTarget.forma.value!=='DINHEIRO';});
$('#pedido-form').addEventListener('submit',e=>{e.preventDefault();run(async()=>{if(!cotacao)return;const f=e.target;if(!f.reportValidity()){limparCotacao();return;}if(!confirm('Registrar este pedido de '+money(Math.round(cotacao.total_pedido*100))+'?'))return;const r=await window.pywebview.api.executar('vender',{nome:f.nome.value.trim()||'Cliente do balcão',itens:itensPedido(),cotacao,entrega:f.entrega.value,endereco:f.endereco.value,pago:f.pago.checked,forma:f.forma.value,recebido:f.recebido.value});itens.clear();limparCotacao();renderCarrinho();f.reset();$('#recebido-label').hidden=false;$('#endereco-label').hidden=true;f.endereco.required=false;await refresh();aviso('Pedido '+r.numero_pedido+' registrado.'+(r.pago?' Troco: '+money(r.troco_centavos||0):' Pagamento pendente.'));});});
$('#movimento').addEventListener('submit',e=>{e.preventDefault();run(async()=>{const f=e.target;await window.pywebview.api.executar('movimentar',{tipo:f.tipo.value,valor:f.valor.value,motivo:f.motivo.value});f.reset();await refresh();aviso('Movimentação registrada.');});});
$('#fechamento').addEventListener('submit',e=>{e.preventDefault();run(async()=>{if(!confirm('Conferir e encerrar este caixa?'))return;const r=await window.pywebview.api.executar('fechar',{contado:e.target.contado.value});e.target.reset();await refresh();aviso('Caixa fechado. Diferença: '+money(r.diferenca_centavos));});});
for(const [id,repetir] of [['conferir',false],['repetir',true]])$('#'+id).addEventListener('click',()=>run(async()=>{const r=await window.pywebview.api.conferir(repetir);$('#pendencia').hidden=!r.pendente;await refresh();aviso(r.pendente?'A loja ainda não confirmou. Você pode repetir a mesma operação.':'Operação conferida. Confira seus pedidos e os valores do caixa.');}));
$('#conferir-bloqueada').addEventListener('click',()=>run(async()=>{const r=await window.pywebview.api.conferir(false);aviso(r.pendente?'Entre com a conta vinculada para conferir.':'Pendência conferida. O responsável pode revisar o registro no caixa central.');}));
window.addEventListener('pywebviewready',()=>aviso('Importe o acesso da loja ou entre com sua conta.'));
setInterval(()=>{if(!busy&&!$('#painel').hidden&&!document.hidden)refresh().catch(async e=>{try{await tratarSessao();}catch(_){}aviso(e.message||'Sem atualização da loja. Confira a conexão antes de continuar.',true);});},15000);
