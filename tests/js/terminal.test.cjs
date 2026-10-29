const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const script=fs.readFileSync(require.resolve('../../web/funcionario/terminal.js'),'utf8');

// O script e os eventos são reais; DOM e ponte desktop ficam em memória.
function terminal(fracionado=false){
  const ids=new Map(),todos=[],chamadas=[];
  class Element{
    constructor(tag='div'){this.tagName=tag;this.children=[];this.events={};this.attrs={};this.disabled=false;this.hidden=false;this.textContent='';this.value='';this.classList={toggle(){}};todos.push(this);}
    append(...filhos){this.children.push(...filhos);}
    replaceChildren(...filhos){this.children=[...filhos];}
    setAttribute(k,v){this.attrs[k]=String(v);}
    addEventListener(k,fn){(this.events[k]||=[]).push(fn);}
    get validity(){const v=Number(this.value),passo=Number(this.step||1),min=Number(this.min||0);
      return {valid:(!this.required||this.value!=='')&&Number.isFinite(v)&&v>=min&&v<=Number(this.max||Infinity)&&Math.abs((v-min)/passo-Math.round((v-min)/passo))<1e-7};}
    reportValidity(){return todos.filter(e=>e.attrs.form==='pedido-form').every(e=>e.validity.valid);}
    reset(){}
    async fire(k,event={}){await Promise.all((this.events[k]||[]).map(fn=>fn({target:this,currentTarget:this,preventDefault(){},...event})));await new Promise(resolve=>setImmediate(resolve));}
  }
  const get=id=>{if(!ids.has(id))ids.set(id,new Element());return ids.get(id);};
  const formulario=get('pedido-form');
  for(const [nome,valor] of Object.entries({nome:'Pessoa fictícia',entrega:'RETIRADA BALCAO',endereco:'',forma:'DINHEIRO',recebido:'20'})){
    formulario[nome]=new Element('input');formulario[nome].value=valor;
  }
  formulario.pago=new Element('input');formulario.pago.checked=true;
  const contexto=vm.createContext({document:{querySelector:s=>get(s.slice(1)),querySelectorAll:s=>s==='button'?todos.filter(e=>e.tagName==='button'):[],createElement:t=>new Element(t),hidden:false},
    window:{addEventListener(){},pywebview:{api:{cotar:async(itens,entrega)=>{chamadas.push({tipo:'cotar',itens,entrega});return {total_pedido:20};},
      executar:async(acao,dados)=>{chamadas.push({tipo:acao,dados});return {numero_pedido:'#FICTICIO',pago:true};},
      sessao:async()=>({autenticado:true})}}},setInterval(){},confirm:()=>true,Intl,Map,Number,String,Math});
  const exec=code=>vm.runInContext(code,contexto);
  vm.runInContext(script,contexto);
  contexto.precoFracionado=fracionado;
  exec("catalogo=[{id:1,nome:'Produto fictício',fracionado:precoFracionado}];itens.set(1,2);renderCarrinho();refresh=async()=>{}");
  const quantidade=()=>get('carrinho').children[0].children[0].children[0];
  return {get,exec,contexto,chamadas,quantidade,
    cotado(){exec('cotacao={total_pedido:20}');get('registrar').disabled=false;}};
}

for(const valor of ['', '0', '-1', '1.5', '1000000','NaN']){
  test(`quantidade inválida ${JSON.stringify(valor)} descarta cotação e não registra quantidade anterior`,async()=>{
    const f=terminal();f.cotado();const input=f.quantidade();input.value=valor;await input.fire('input');
    assert.equal(input.attrs.form,'pedido-form');assert.equal(input.required,true);
    assert.equal(input.attrs['aria-invalid'],'true');assert.equal(f.get('registrar').disabled,true);
    await f.get('revisar').fire('click');await f.get('pedido-form').fire('submit');
    assert.equal(f.chamadas.length,0);
  });
}
test('edição válida precisa de nova conferência e envia a quantidade exibida',async()=>{
  const f=terminal();f.cotado();f.quantidade().value='3';await f.quantidade().fire('input');
  assert.equal(f.get('registrar').disabled,true);await f.get('revisar').fire('click');
  assert.equal(f.get('registrar').disabled,false);await f.get('pedido-form').fire('submit');
  const venda=f.chamadas.find(c=>c.tipo==='vender');assert.ok(venda);
  assert.equal(venda.dados.itens[0].quantidade,3);
});
test('quantidade fracionada mantém três casas e rejeita fração abaixo do passo',async()=>{
  const f=terminal(true);f.quantidade().value='0.125';await f.quantidade().fire('change');await f.get('revisar').fire('click');
  assert.equal(f.chamadas[0].itens[0].quantidade,.125);
  f.quantidade().value='0.0005';await f.quantidade().fire('input');await f.get('revisar').fire('click');
  assert.equal(f.chamadas.length,1);assert.equal(f.get('registrar').disabled,true);
});
test('cotação antiga não volta a autorizar depois de quantidade mudar durante a consulta',async()=>{
  const f=terminal();let concluir;
  f.contexto.window.pywebview.api.cotar=()=>new Promise(resolve=>{concluir=resolve;});
  const consulta=f.get('revisar').fire('click');await new Promise(resolve=>setImmediate(resolve));assert.ok(concluir);
  f.quantidade().value='4';await f.quantidade().fire('input');
  concluir({total_pedido:20});await consulta;
  assert.equal(f.exec('cotacao'),null);assert.equal(f.get('registrar').disabled,true);
  await f.get('pedido-form').fire('submit');assert.equal(f.chamadas.length,0);
});
test('validação do formulário também protege envio disparado sem evento de edição',async()=>{
  const f=terminal();f.cotado();f.quantidade().value='0';await f.get('pedido-form').fire('submit');
  assert.equal(f.chamadas.length,0);assert.equal(f.get('registrar').disabled,true);
});
