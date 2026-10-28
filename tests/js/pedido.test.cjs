const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(require.resolve('../../web/static/pedido.js'), 'utf8');

// DOM mínimo em memória: executa o mesmo script e os eventos do navegador,
// sem bibliotecas, armazenamento, formulário real ou chamadas de rede.
function fixture() {
  let document;
  class Element {
    constructor(tag='div', id='') {
      this.tagName=tag.toUpperCase();this.id=id;this.dataset={};this.children=[];
      this.attributes={};this.events={};this.hidden=false;this.disabled=false;
      this.value='';this.textContent='';this.labels=[];this.className='';
      this.classList={toggle:(name,on)=>{const s=new Set(this.className.split(' ').filter(Boolean));
        if(on)s.add(name);else s.delete(name);this.className=[...s].join(' ');},
        add:name=>this.classList.toggle(name,true)};
    }
    append(...nodes) {for(const node of nodes){if(node.tagName==='FRAGMENT')this.append(...node.children);else{this.children.push(node);node.parentElement=this;}}}
    appendChild(node){this.append(node);return node;}
    replaceChildren(...nodes) {this.children.forEach(n=>n.parentElement=null);this.children=[];this.append(...nodes);}
    setAttribute(name,value){this.attributes[name]=String(value);}
    getAttribute(name){return this.attributes[name]??null;}
    removeAttribute(name){delete this.attributes[name];}
    addEventListener(type,handler,options){(this.events[type]??=[]).push({handler,options});}
    fire(type,event={}) {const e={target:this,preventDefault(){this.prevented=true;},...event};for(const h of this.events[type]||[])h.handler.call(this,e);return e;}
    click(){if(!this.disabled)return this.fire('click');}
    focus(options){document.activeElement=this;this.focusOptions=options;}
    scrollIntoView(options){this.scrollOptions=options;}
    matches(selector){if(selector==='input')return this.tagName==='INPUT';if(selector==='input[type=number]')return this.type==='number';
      return selector[0]==='.'&&this.className.split(' ').includes(selector.slice(1));}
    querySelectorAll(selector){const result=[];const visit=node=>{for(const child of node.children){if(child.matches(selector))result.push(child);visit(child);}};visit(this);return result;}
    querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
    closest(selector){let e=this;while(e){if(e.matches(selector))return e;e=e.parentElement;}return null;}
    get validity(){return {valid:this.disabled||(!this.required||!!this.value)&&
      (this.type!=='number'||Number.isFinite(Number(this.value))&&Number(this.value)>=0&&Number(this.value)<=Number(this.max))};}
    get validationMessage(){return this.validity.valid?'':this.type==='number'?'Confira o limite disponível.':'Preencha este campo.';}
  }
  const form=new Element('form','form-pedido');form.dataset.taxaEntrega='5';
  const byId={};
  const ids=['forma_entrega','campo-endereco','botao-confirmar','botao-revisar','lista-carrinho','feedback-pedido',
    'busca-produtos','limpar-busca','validacao-pedido','subtotal-produtos','label-taxa','subtotal-entrega','total-checkout',
    'resumo-total','resumo-itens','carrinho-vazio','dica-carrinho','busca-vazia','resultado-busca','resetar-filtros',
    'cep','numero','nome','titulo-checkout','checkout','carrinho','valores-pedido','barra-pedido'];
  for(const id of ids){byId[id]=new Element(id==='nome'||id==='cep'||id==='numero'?'input':'div',id);form.append(byId[id]);}
  byId.forma_entrega.value='RETIRADA BALCAO';byId.nome.required=true;byId.nome.labels=[{textContent:'Seu nome'}];
  byId.cep.labels=[{textContent:'CEP'}];byId['campo-endereco'].append(byId.cep,byId.numero);
  // Retira as duas referências antigas ao mover os campos de endereço.
  form.children=form.children.filter(n=>n!==byId.cep&&n!==byId.numero);
  const tools=new Element();tools.className='ferramentas-catalogo';form.append(tools);
  const filters=['','1'].map(categoria=>{const b=new Element('button');b.className='categoria-filtro';b.dataset.categoria=categoria;tools.append(b);return b;});
  const products=[];
  const section=new Element();section.className='categoria';section.dataset.categoria='1';form.append(section);
  for(const [id,name,price,max,step,unit] of [['1','Lanche fictício',10.01,2,1,'un'],['2','Porção fracionada',6,.25,.001,'kg']]) {
    const product=new Element('article');product.className='produto';
    product.dataset={produtoId:id,nome:name,preco:String(price),unidade:unit,busca:name};
    const input=new Element('input','qtd-'+id);input.type='number';input.name='qtd_'+id;input.value='0';input.max=String(max);input.step=String(step);input.labels=[{textContent:'Quantidade de '+name}];
    const stepper=new Element();stepper.className='stepper';stepper.dataset.passo=step===1?'1':'.1';
    const less=new Element('button');less.className='menos';const more=new Element('button');more.className='mais';
    stepper.append(less,input,more);product.append(stepper);section.append(product);products.push({product,input,more,less});
  }
  const body=new Element('body');body.append(form);
  document={body,activeElement:null,createElement:tag=>new Element(tag),createDocumentFragment:()=>new Element('fragment'),
    getElementById:id=>{let found=null;const visit=e=>{if(e.id===id)found=e;for(const child of e.children)visit(child);};visit(body);return found;}};
  const window={events:{},matchMedia:()=>({matches:true}),addEventListener(type,handler){this.events[type]=handler;}};
  vm.runInNewContext(code,{document,window,Intl,Number,String,Math,Array,Set,setTimeout:fn=>{fn();return 1;},clearTimeout:()=>{}});
  return {document,window,form,byId,products,filters,section,get:id=>document.getElementById(id)};
}

test('editar o resumo altera o campo enviado, respeita estoque e mantém foco no controle disponível',()=>{
  const f=fixture(),p=f.products[0];p.more.click();
  const more=f.get('carrinho-1-mais');assert.ok(more);more.click();
  assert.equal(p.input.value,'2');assert.equal(f.byId['total-checkout'].textContent,'R$\u00a020,02');
  assert.equal(f.get('carrinho-1-mais').disabled,true);
  assert.equal(f.document.activeElement,f.get('carrinho-1-menos'));
  assert.equal(f.document.activeElement.focusOptions.preventScroll,true);
  assert.equal(f.byId['lista-carrinho'].querySelectorAll('input').length,0);
});
test('diminuir o último item limpa o resumo e retorna foco sem saltar a página',()=>{
  const f=fixture();f.products[0].more.click();f.get('carrinho-1-menos').click();
  assert.equal(f.products[0].input.value,'0');assert.equal(f.byId['botao-confirmar'].disabled,true);
  assert.equal(f.byId['carrinho-vazio'].hidden,false);assert.equal(f.byId['dica-carrinho'].hidden,true);
  assert.equal(f.document.activeElement,f.byId['titulo-checkout']);assert.equal(f.document.activeElement.focusOptions.preventScroll,true);
});
test('ajuste fracionado chega ao limite sem arredondar além do estoque e recalcula a taxa',()=>{
  const f=fixture(),p=f.products[1];p.more.click();f.get('carrinho-2-mais').click();f.get('carrinho-2-mais').click();
  assert.equal(p.input.value,'0.25');assert.equal(f.byId['subtotal-produtos'].textContent,'R$\u00a01,50');
  f.byId.forma_entrega.value='ENTREGA';f.byId.forma_entrega.fire('change');
  assert.equal(f.byId['total-checkout'].textContent,'R$\u00a06,50');assert.equal(f.byId.cep.required,true);
});
test('envio desabilita controles do resumo e não cria um segundo envio; retorno do navegador recupera edição',()=>{
  const f=fixture();f.products[0].more.click();assert.equal(f.form.fire('submit').prevented,undefined);
  assert.equal(f.form.getAttribute('aria-busy'),'true');assert.equal(f.get('carrinho-1-mais').disabled,true);
  assert.equal(f.form.fire('submit').prevented,true);f.window.events.pageshow({persisted:true});
  assert.equal(f.form.getAttribute('aria-busy'),null);assert.equal(f.get('carrinho-1-mais').disabled,false);
  assert.equal(f.products[0].input.value,'1');
});
test('quantidade inválida escondida pela busca reaparece antes do foco nativo e conserva os outros itens',()=>{
  const f=fixture();f.products[1].more.click();f.byId['busca-produtos'].value='inexistente';f.byId['busca-produtos'].fire('input');
  assert.equal(f.products[0].product.hidden,true);f.products[0].input.value='99';
  const invalid=f.form.fire('invalid',{target:f.products[0].input});
  assert.equal(invalid.prevented,undefined);assert.equal(f.products[0].product.hidden,false);assert.equal(f.byId['busca-produtos'].value,'');
  assert.equal(f.products[1].input.value,'0.1');assert.equal(f.products[0].input.getAttribute('aria-invalid'),'true');
  assert.match(f.byId['validacao-pedido'].textContent,/Quantidade de Lanche fictício.*limite disponível/);
  f.products[0].input.value='1';f.form.fire('input',{target:f.products[0].input});
  assert.equal(f.byId['validacao-pedido'].hidden,true);assert.equal(f.products[0].input.getAttribute('aria-invalid'),null);
  assert.equal(f.form.events.invalid[0].options,true);
});
test('corrigir quantidade pelos botões limpa o alerta sem depender de um evento input',()=>{
  const f=fixture();f.products[0].more.click();f.products[0].input.value='99';
  f.form.fire('invalid',{target:f.products[0].input});assert.equal(f.byId['validacao-pedido'].hidden,false);
  f.products[0].less.click();
  assert.equal(f.products[0].input.value,'2');assert.equal(f.byId['validacao-pedido'].hidden,true);
  assert.equal(f.products[0].input.getAttribute('aria-invalid'),null);
});
test('validação preserva os valores e deixa de exigir CEP quando a pessoa muda para retirada',()=>{
  const f=fixture();f.byId.forma_entrega.value='ENTREGA';f.byId.forma_entrega.fire('change');
  f.form.fire('invalid',{target:f.byId.nome});f.form.fire('invalid',{target:f.byId.cep});
  assert.match(f.byId['validacao-pedido'].textContent,/Seu nome.*outros campos/);
  f.byId.nome.value='Pessoa fictícia';f.form.fire('input',{target:f.byId.nome});
  assert.match(f.byId['validacao-pedido'].textContent,/^CEP:/);
  f.byId.forma_entrega.value='RETIRADA BALCAO';f.byId.forma_entrega.fire('change');
  assert.equal(f.byId['validacao-pedido'].hidden,true);assert.equal(f.byId.nome.value,'Pessoa fictícia');
});
