const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function ambiente(){
  const els=new Map(),requests=[],timers=[];
  const $=s=>{if(!els.has(s))els.set(s,{value:'',content:'csrf-ficticio',hidden:false,innerHTML:'',textContent:'',disabled:false,eventos:{},classList:{toggle(){}},addEventListener(n,f){this.eventos[n]=f;},reset(){this.limpo=true;}});return els.get(s);};
  let resolve;
  const pending=new Promise(r=>resolve=r);
  const c=vm.createContext({document:{querySelector:$},location:{hash:'#'+'x'.repeat(43)},addEventListener(){},history:{replaceState(...a){requests.push(['history',...a]);}},setTimeout(f){timers.push(f);return timers.length;},clearTimeout(){},AbortController,Date,Intl,confirm:()=>true,FormData:class{constructor(f){return f.entradas;}},fetch:(...a)=>{requests.push(a);return pending;}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/static/remoto.js'),'utf8'),c);
  return {c,$,requests,timers,resolve};
}
function estado(permissao='CONSULTA'){return {nome:'Pessoa <img>',permissao,expira_em:Date.now()/1000+3600,pedidos:[{pedido_id:1,numero_pedido:'123',status:'AGUARDANDO',cliente_nome:'<script>cliente</script>',forma_entrega:'Retirada',total_pedido:10,itens:[{quantidade:1,produto_nome:'<img src=x>',observacao:'<script>nota</script>'}]}],produtos:[{nome:'<script>produto</script>',categoria:'<img>',preco:10,estoque:null}]};}
test('convite fica no fragmento, removido da barra, sem armazenamento persistente nem polling',()=>{
  const {c,$,requests}=ambiente();
  assert.equal($('#remote-code').value,'x'.repeat(43));
  assert.equal(requests[0].at(-1),'/remoto');
  assert.equal(requests[1][0],'/remoto/api/estado');
  assert.equal(vm.runInContext('typeof code',c),'undefined');
  assert.equal(requests.length,2);
});
test('consulta escapa conteúdo e não apresenta botões de alteração',()=>{
  const {c,$}=ambiente();c.render(estado());
  assert.ok(!$('#remote-orders').innerHTML.includes('<script>'));
  assert.ok(!$('#remote-orders').innerHTML.includes('<img'));
  assert.ok(!$('#remote-products').innerHTML.includes('<script>'));
  assert.ok(!$('#remote-orders').innerHTML.includes('data-next'));
  assert.equal($('#remote-count').textContent,1);
});
test('sessão expirada limpa os pedidos da tela',()=>{
  const {c,$,timers}=ambiente();c.render(estado('PEDIDOS'));
  assert.ok($('#remote-orders').innerHTML.includes('data-next="1"'));
  timers.at(-1)();
  assert.equal($('#remote-panel').hidden,true);
  assert.equal($('#remote-orders').innerHTML,'');
  assert.equal($('#remote-products').innerHTML,'');
});
test('login apaga formulário e usa novo CSRF nas próximas chamadas',async()=>{
  const {c,$}=ambiente();const requests=[];
  c.fetch=async(url,opt)=>{requests.push([url,opt]);return {ok:true,json:async()=>url.endsWith('/entrar')?{ok:true,csrf:'novo-csrf'}:estado()};};
  const f=$('#remote-login-form');f.entradas=[['convite','x'.repeat(43)],['login','pessoa'],['senha','senha-ficticia']];
  f.eventos.submit({preventDefault(){},submitter:{},target:f});
  await new Promise(r=>setImmediate(r));
  assert.equal(f.limpo,true);assert.equal(requests[1][1].headers['X-CSRF-Token'],'novo-csrf');
  assert.ok(!requests[0][0].includes('senha'));
});
test('avançar transmite o estado conhecido e exige confirmação sem repetição automática',async()=>{
  const {c,$}=ambiente();c.render(estado('PEDIDOS'));const requests=[];
  c.fetch=async(url,opt)=>{requests.push([url,opt]);return {ok:true,json:async()=>url.endsWith('/avancar')?{ok:true}:estado('PEDIDOS')};};
  const b={dataset:{next:'1'},disabled:false};
  $('#remote-orders').eventos.click({target:{closest:()=>b}});
  await new Promise(r=>setImmediate(r));
  assert.equal(requests[0][0],'/remoto/api/pedidos/1/avancar');
  assert.deepEqual(JSON.parse(requests[0][1].body),{status:'AGUARDANDO',confirmar:true});
  assert.equal(requests.length,2);
  c.confirm=()=>false;$('#remote-orders').eventos.click({target:{closest:()=>b}});
  assert.equal(requests.length,2);
});
test('resposta 401 encerra painel e não tenta alterar novamente',async()=>{
  const {c,$}=ambiente();c.render(estado('PEDIDOS'));
  c.fetch=async()=>({ok:false,status:401,json:async()=>({erro:'Revogado'})});
  await assert.rejects(c.api('estado'),/Revogado/);
  assert.equal($('#remote-panel').hidden,true);
});
