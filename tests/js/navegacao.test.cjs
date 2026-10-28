const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const nav = require('../../web/static/navegacao.js');

function elemento(dados={}) {
  const classes=new Set(), atributos=new Map();
  const e={dataset:{},hidden:false,value:'',textContent:'',innerHTML:'',eventos:{},focos:0,cliques:0,
    ...dados,
    classList:{toggle(nome,valor){valor?classes.add(nome):classes.delete(nome);},contains(nome){return classes.has(nome);},add(nome){classes.add(nome);},remove(nome){classes.delete(nome);}},
    setAttribute(nome,valor){atributos.set(nome,valor);},getAttribute(nome){return atributos.get(nome)??null;},removeAttribute(nome){atributos.delete(nome);},
    addEventListener(nome,fn){(this.eventos[nome] ||= []).push(fn);},
    emitir(nome,extras={}){const evento={target:this,currentTarget:this,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.propagacaoInterrompida=true;},...extras};for(const fn of this.eventos[nome]||[])fn(evento);return evento;},
    closest(seletor){return seletor==='[data-admin-only]'?(this.admin?this:null):seletor==='[data-page]'?(this.dataset.page?this:null):seletor==='button'?this:null;},
    focus(){this.focos++;},click(){this.cliques++;},querySelector(){return this.busy?{}:null;},querySelectorAll(){return [];},
    reset(){},showModal(){},close(){},scrollIntoView(){},replaceChildren(){},insertAdjacentHTML(){},remove(){},
  };
  e.elements=new Proxy({}, {get(obj,nome){return obj[nome] ||= elemento();}});
  return Object.assign(e,dados);
}
function menu(administrador=true) {
  const botoes=[elemento({textContent:'Pedidos',dataset:{page:'pedidos'}}),
    elemento({textContent:'Cardápio e encomendas',dataset:{page:'produtos',searchTerms:'produtos estoque catálogo'}}),
    elemento({textContent:'Configurações',dataset:{page:'configuracoes',searchTerms:'horário pagamento'},admin:true}),
    elemento({textContent:'Movimentações',dataset:{page:'movimentos'},hidden:true,admin:true})];
  const grupos=[{classList:elemento().classList,contains:b=>botoes.slice(0,2).includes(b)},
    {classList:elemento().classList,contains:b=>botoes.slice(2).includes(b)}];
  const pagina=elemento({querySelectorAll:seletor=>seletor==='[data-page]'?botoes:grupos});
  const busca=elemento(),limpar=elemento(),resultado=elemento();
  const controle=nav.criar({nav:pagina,busca,limpar,resultado,administrador});
  const filtrar=valor=>{busca.value=valor;busca.emitir('input');};
  return {botoes,grupos,pagina,busca,limpar,resultado,controle,filtrar};
}

test('busca ignora acentos e aceita todos os termos e aliases conhecidos',()=>{
  assert.ok(nav.corresponde('Configurações','horário pagamento','  CONFIGURACOES  horario '));
  assert.ok(!nav.corresponde('Pedidos','vendas','pedido estoque'));
});
test('filtrar e limpar não reexibe ações ocultas nem revela telas administrativas',()=>{
  const a=menu(false);a.filtrar('config');
  assert.match(a.resultado.textContent,/Nenhuma tela/);
  assert.ok(a.botoes[2].classList.contains('nav-filtered'));
  a.limpar.emitir('click');
  assert.equal(a.busca.value,'');assert.equal(a.busca.focos,1);assert.ok(a.resultado.hidden);
  assert.ok(a.botoes[2].classList.contains('nav-filtered'));
  assert.ok(a.botoes[3].hidden);
});
test('teclado percorre apenas resultados autorizados e Enter único abre a tela',()=>{
  const a=menu();a.filtrar('catalogo');
  a.busca.emitir('keydown',{key:'ArrowDown'});assert.equal(a.botoes[1].focos,1);
  a.busca.emitir('keydown',{key:'Enter'});assert.equal(a.botoes[1].cliques,1);
  a.controle.limparBusca(false);
  a.pagina.emitir('keydown',{key:'ArrowUp',target:a.botoes[0]});assert.equal(a.botoes[2].focos,1);
  a.pagina.emitir('keydown',{key:'Home',target:a.botoes[2]});assert.equal(a.botoes[0].focos,1);
  a.pagina.emitir('keydown',{key:'End',target:a.botoes[0]});assert.equal(a.botoes[2].focos,2);
});
test('Enter com vários resultados não escolhe uma tela sem o usuário decidir',()=>{
  const a=menu();a.busca.emitir('keydown',{key:'Enter'});
  assert.equal(a.botoes[0].focos,1);assert.ok(a.botoes.every(b=>b.cliques===0));
  a.filtrar('inexistente');a.busca.emitir('keydown',{key:'Enter'});assert.ok(a.botoes.every(b=>b.cliques===0));
});
test('primeiro Escape limpa a busca e o seguinte pode fechar o menu móvel',()=>{
  const a=menu();a.filtrar('pedido');
  const primeiro=a.busca.emitir('keydown',{key:'Escape'});
  assert.ok(primeiro.defaultPrevented&&primeiro.propagacaoInterrompida);assert.equal(a.busca.value,'');
  assert.equal(a.busca.emitir('keydown',{key:'Escape'}).defaultPrevented,undefined);
});
test('atualização de perfil respeita nome novo e disponibilidade do item de navegação',()=>{
  const a=menu();a.botoes[1].textContent='Serviços e agenda';a.botoes[1].dataset.searchTerms='';
  a.filtrar('agenda');assert.match(a.resultado.textContent,/1 tela encontrada/);
  a.botoes[1].hidden=true;a.controle.atualizar();assert.match(a.resultado.textContent,/Nenhuma tela/);
});
test('cancelar descarte mantém edição pendente e limpar invalida consultas antigas',()=>{
  const estado=nav.alteracoes();assert.ok(estado.confirmar('comercio',()=>{throw Error('Não há edição');}));
  estado.registrar('comercio');const antes=estado.revisao('comercio');
  assert.equal(estado.confirmar('comercio',()=>false),false);assert.ok(estado.tem('comercio'));
  assert.ok(estado.confirmar('comercio',()=>true));assert.ok(estado.tem('comercio'));
  estado.limpar('comercio');assert.ok(!estado.tem());assert.notEqual(estado.revisao('comercio'),antes);
});

function painel() {
  const elementos=new Map(),acoes=[],avisos=[],confirmacoes=[],documentoEventos={},janelaEventos={};
  const $=seletor=>{if(!elementos.has(seletor))elementos.set(seletor,elemento());return elementos.get(seletor);};
  const botoes=['inicio','pedidos','produtos','humano','configuracoes','comercio'].map(page=>elemento({dataset:{page},textContent:page}));
  $('#navigation-pages').querySelectorAll=seletor=>seletor==='[data-page]'?botoes:[];
  const contexto=vm.createContext({console,DeliveryNav:nav,
    DeliveryUX:{solicitar:async()=>({}),texto:String,pedidos:items=>items,ocupado:(_,fn)=>{const p=fn();p.catch(()=>{});acoes.push(p);return p;}},
    document:{body:{dataset:{admin:'true',whatsappProvider:'TESTE',perfilPendente:'false'},classList:elemento().classList},querySelector:$,
      querySelectorAll:seletor=>seletor==='#app-menu nav [data-page]'?botoes:[],addEventListener(nome,fn){(documentoEventos[nome]||=[]).push(fn);},visibilityState:'visible'},
    window:{addEventListener(nome,fn){janelaEventos[nome]=fn;},scrollTo(){}},
    matchMedia:()=>({matches:false,addEventListener(){}}),
    setInterval(){},setTimeout(){},clearTimeout(){},
    confirm:mensagem=>{confirmacoes.push(mensagem);return contexto.aprovar;},aprovar:false,
    fetch:async()=>{throw Error('Sem transporte real');},FormData:class{constructor(form){return form.entradas||[];}},
    Option:class{},FileReader:class{},
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/static/gestao.js'),'utf8'),contexto);
  contexto.toast=(mensagem)=>avisos.push(mensagem);
  contexto.summary=async()=>{};
  contexto.api=async()=>({segredos_configurados:{},nome:'Loja fictícia',segmento:'Lanchonete',descricao:'Exemplo',modelo:'PRODUCAO',controlar_estoque:false});
  const exec=codigo=>vm.runInContext(codigo,contexto);
  const editar=pagina=>$(pagina==='configuracoes'?'#settings-form':'#commerce-form').emitir('input');
  return {$,contexto,acoes,avisos,confirmacoes,janelaEventos,exec,editar};
}
const aguardar=()=>new Promise(resolve=>setImmediate(resolve));

test('cancelar Atualizar dados mantém formulário e não inicia consulta',async()=>{
  const a=painel();a.exec("state.page='configuracoes'");a.editar('configuracoes');
  a.$('#settings-fields').innerHTML='campos preenchidos';let consultas=0;a.contexto.summary=async()=>{consultas++;};
  assert.equal(await a.exec('reload()'),false);assert.equal(consultas,0);
  assert.equal(a.$('#settings-fields').innerHTML,'campos preenchidos');assert.equal(a.confirmacoes.length,1);
});
test('edição iniciada enquanto resumo carrega não é sobrescrita pela atualização',async()=>{
  const a=painel();a.exec("state.page='configuracoes'");a.$('#settings-fields').innerHTML='nova edição';
  let liberar;a.contexto.summary=()=>new Promise(resolve=>{liberar=resolve;});
  const operacao=a.exec('reload()');a.editar('configuracoes');liberar();await operacao;
  assert.equal(a.$('#settings-fields').innerHTML,'nova edição');assert.ok(a.exec("edicoes.tem('configuracoes')"));
});
test('consulta atrasada do comércio preserva novas edições feitas durante a leitura',async()=>{
  const a=painel();a.exec("state.page='comercio'");const f=a.$('#commerce-form');f.elements.nome.value='Novo nome';
  let liberar;a.contexto.api=()=>new Promise(resolve=>{liberar=resolve;});
  const operacao=a.exec('commerce()');a.editar('comercio');liberar({nome:'Nome anterior'});await operacao;
  assert.equal(f.elements.nome.value,'Novo nome');assert.ok(a.exec("edicoes.tem('comercio')"));
});
for(const pagina of ['configuracoes','comercio'])test(`salvamento pendente não apaga novas edições de ${pagina}`,async()=>{
  const a=painel();a.exec(`state.page='${pagina}'`);a.editar(pagina);
  const f=a.$(pagina==='configuracoes'?'#settings-form':'#commerce-form');f.entradas=[['nome','Versão enviada']];
  let liberar;a.contexto.api=()=>new Promise(resolve=>{liberar=resolve;});
  f.emitir('submit',{submitter:elemento()});await aguardar();
  a.editar(pagina);f.elements.nome.value='Edição nova';liberar({});await Promise.all(a.acoes);await aguardar();
  assert.equal(f.elements.nome.value,'Edição nova');assert.ok(a.exec(`edicoes.tem('${pagina}')`));
  assert.match(a.avisos.at(-1),/novas alterações/);assert.equal(a.exec('state.page'),pagina);
});
test('falha ao salvar mantém o aviso de edição e não marca os dados como salvos',async()=>{
  const a=painel();a.exec("state.page='configuracoes'");a.editar('configuracoes');
  a.contexto.api=async()=>{throw Error('Falha simulada');};
  a.$('#settings-form').emitir('submit',{submitter:elemento()});await Promise.allSettled(a.acoes);await aguardar();
  assert.ok(a.exec("edicoes.tem('configuracoes')"));assert.match(a.$('#settings-save-status').textContent,/não salvas/);
});
test('salvar sem novas edições renova dados oficiais e encerra o aviso de pendência',async()=>{
  const a=painel();a.exec("state.page='configuracoes'");a.editar('configuracoes');
  const chamadas=[];a.contexto.api=async(rota,metodo)=>{chamadas.push([rota,metodo]);return {NOME_RESTAURANTE:'Nome confirmado',segredos_configurados:{}};};
  a.$('#settings-form').emitir('submit',{submitter:elemento()});await Promise.all(a.acoes);await aguardar();
  assert.ok(!a.exec("edicoes.tem('configuracoes')"));assert.match(a.$('#settings-fields').innerHTML,/Nome confirmado/);
  assert.deepEqual(chamadas,[['configuracoes','PUT'],['configuracoes',undefined]]);
});
test('limpa segredo já enviado sem apagar um segredo novo digitado durante o salvamento',async()=>{
  const a=painel();a.exec("state.page='configuracoes'");a.editar('configuracoes');
  const f=a.$('#settings-form'),anterior=elemento({name:'CHAVE_A',value:'credencial-ficticia-antiga'}),nova=elemento({name:'CHAVE_B',value:'credencial-ficticia-enviada'});
  f.entradas=[['CHAVE_A',anterior.value],['CHAVE_B',nova.value]];f.querySelectorAll=()=>[anterior,nova];
  let liberar;a.contexto.api=()=>new Promise(resolve=>{liberar=resolve;});
  f.emitir('submit',{submitter:elemento()});await aguardar();nova.value='edicao-ficticia-nova';a.editar('configuracoes');liberar({});await Promise.all(a.acoes);await aguardar();
  assert.equal(anterior.value,'');assert.equal(nova.value,'edicao-ficticia-nova');assert.ok(a.exec("edicoes.tem('configuracoes')"));
});
test('cancelar navegação mantém o menu móvel aberto e a página atual',async()=>{
  const a=painel();a.exec("state.page='configuracoes';telaCompacta.matches=true;document.body.classList.add('menu-open')");a.editar('configuracoes');
  assert.equal(await a.exec("navigate('pedidos')"),false);
  assert.equal(a.exec('state.page'),'configuracoes');assert.ok(a.exec("document.body.classList.contains('menu-open')"));
});
test('salvamento em andamento impede descarte e formulário pendente avisa antes de fechar',async()=>{
  const a=painel();a.exec("state.page='comercio'");a.editar('comercio');a.$('#commerce-form').busy=true;a.contexto.aprovar=true;
  assert.equal(await a.exec("navigate('pedidos')"),false);assert.equal(a.confirmacoes.length,0);assert.match(a.avisos.at(-1),/Aguarde/);
  const evento={preventDefault(){this.impedido=true;}};a.janelaEventos.beforeunload(evento);assert.ok(evento.impedido);
});
