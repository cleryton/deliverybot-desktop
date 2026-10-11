'use strict';
let documentReview=null;
let documentApplied=false;
function documentReset(){documentReview=null;documentApplied=false;$('#document-review').hidden=true;$('#document-apply').disabled=true;$('#document-confirmed').checked=false;$('#document-save-note').hidden=true;$('#document-status').textContent='';}
['#document-file','#document-type','#document-model'].forEach(s=>$(s).addEventListener('change',documentReset));
$('#document-read').addEventListener('click',e=>run(e.target,async()=>{
  const file=$('#document-file').files[0];
  if(!file||file.size>10*1024*1024)throw new Error('Escolha um PDF, XLSX, CSV ou Markdown de até 10 MB.');
  documentReset();$('#document-status').textContent='Lendo os produtos… A leitura com IA pode levar até dois minutos.';
  const d=new FormData();d.append('arquivo',file);d.append('tipo',$('#document-type').value);d.append('modelo',$('#document-model').value.trim());
  const controls=['#document-file','#document-type','#document-model'].map(s=>$(s));controls.forEach(c=>c.disabled=true);try{documentReview=await api('documentos/ler','POST',d);}catch(error){$('#document-status').textContent='Nenhum produto foi lançado. Confira o arquivo e tente novamente.';throw error;}finally{controls.forEach(c=>c.disabled=false);}
  $('#document-warning').textContent=documentReview.aviso;
  $('#document-status').textContent=`${documentReview.quantidade} produtos encontrados. Confira a revisão abaixo.`;
  $('#document-rows').replaceChildren();
  documentReview.produtos.forEach((p,index)=>{
    const item=document.createElement('details');item.className='document-product';item.dataset.index=index;item.open=index===0;
    const summary=document.createElement('summary');summary.textContent=`${index+1}. ${p.nome||'Nome a conferir'}${p.sku?' · '+p.sku:''}`;item.append(summary);
    if(p.nome_existente){const aviso=document.createElement('p');aviso.textContent=`SKU já cadastrado: ${p.nome_existente}. Saldo na leitura: ${p.saldo_conferido??'sem controle'}.`;item.append(aviso);}
    const grid=document.createElement('div');grid.className='form-grid';
    [['nome','Nome do produto'],['sku','Código / SKU'],['categoria','Categoria (novo produto)'],['unidade','Unidade'],['estoque','Quantidade do documento'],['preco','Preço de venda (novo produto)'],['custo','Custo de compra (opcional)']].forEach(([key,title])=>{const label=document.createElement('label');label.textContent=title;const input=document.createElement('input');input.dataset.field=key;input.value=p[key]??'';input.type='text';input.maxLength=key==='nome'||key==='categoria'?160:key==='sku'?80:key==='unidade'?20:30;if(['estoque','preco','custo'].includes(key))input.inputMode='decimal';label.append(input);grid.append(label);});
    const escolha=document.createElement('label');escolha.textContent='Como lançar';const select=document.createElement('select');select.dataset.field='acao';[['novo','Cadastrar novo produto'],['entrada','Entrada: somar ao estoque'],['contagem','Contagem: definir o saldo'],['ignorar','Ignorar esta linha']].forEach(([value,label])=>select.add(new Option(label,value,false,p.acao===value)));escolha.append(select);grid.append(escolha);
    const fracao=document.createElement('label');fracao.className='check wide';const check=document.createElement('input');check.type='checkbox';check.dataset.field='fracionado';check.checked=!!p.fracionado;fracao.append(check,document.createTextNode(' Produto novo vendido em quantidades fracionadas'));grid.append(fracao);
    item.append(grid);$('#document-rows').append(item);
  });$('#document-review').hidden=false;
}));
$('#document-confirmed').addEventListener('change',()=>{$('#document-apply').disabled=!$('#document-confirmed').checked||documentApplied;});
$('#document-rows').addEventListener('input',()=>{if(!documentApplied){$('#document-confirmed').checked=false;$('#document-apply').disabled=true;}});
$('#document-apply').addEventListener('click',e=>run(e.target,async()=>{
  if(!documentReview||documentApplied||!$('#document-confirmed').checked)return;
  const produtos=[...$('#document-rows').children].map(row=>{const p={};row.querySelectorAll('[data-field]').forEach(input=>{p[input.dataset.field]=input.type==='checkbox'?input.checked:input.value;});return p;});
  const controls=[...$('#document-rows').querySelectorAll('input,select'),...['#document-file','#document-type','#document-model','#document-obsidian','#document-confirmed'].map(s=>$(s))];controls.forEach(c=>c.disabled=true);let r;try{r=await api('documentos/lancar','POST',{token:documentReview.token,produtos,obsidian:$('#document-obsidian').checked});}catch(error){controls.forEach(c=>c.disabled=false);throw error;}controls.filter(c=>!c.closest('#document-rows')).forEach(c=>c.disabled=false);
  documentApplied=true;$('#document-status').textContent=r.aviso||'Este documento já foi lançado.';
  $('#document-save-note').hidden=!$('#document-obsidian').checked||r.nota_salva;
  $('#document-rows').querySelectorAll('input,select').forEach(input=>input.disabled=true);
  await products();toast(r.aviso||'Estoque lançado.');
  setTimeout(()=>$('#document-apply').disabled=true,0);
}));
$('#document-save-note').addEventListener('click',e=>run(e.target,async()=>{await api('documentos/nota','POST',{token:documentReview.token});e.target.hidden=true;$('#document-status').textContent='Estoque lançado e registro salvo no Obsidian.';}));
$('#catalog-pdf-quantities').addEventListener('change',()=>{$('#catalog-pdf-download').href='/gestao/api/catalogo.pdf'+($('#catalog-pdf-quantities').checked?'?quantidades=sim':'');});
