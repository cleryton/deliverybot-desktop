const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function ambiente(){
  const els=new Map(),calls=[];
  const $=s=>{if(!els.has(s))els.set(s,{value:'',hidden:false,type:'password',innerHTML:'',textContent:'',eventos:{},addEventListener(n,f){this.eventos[n]=f;}});return els.get(s);};
  const c=vm.createContext({$: $,Date,confirm:()=>true,navigator:{clipboard:{writeText:async()=>{}}},document:{visibilityState:'visible',addEventListener(){}},FormData:class{constructor(f){return f.entradas;}},escapeHTML:v=>String(v).replaceAll('<','&lt;').replaceAll('>','&gt;'),toast(){},run:async(b,fn)=>fn(),api:async(p,m,d)=>{calls.push([p,m,d]);if(p==='operadores')return [{id:1,nome:'<admin>',login:'patrao',ativo:1,perfil:'ADMIN'},{id:2,nome:'caixa',login:'caixa',ativo:1,perfil:'CAIXA'}];return {url:'https://loja.example',acessos:[],link:'https://loja.example/remoto#codigo'};}});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/static/acesso_remoto_admin.js'),'utf8'),c);
  return {c,$,calls};
}
test('lista só oferece contas autorizáveis e escapa nomes',async()=>{
  const {c,$}=ambiente();await c.remoteAdminLoad();
  assert.match($('#remote-account').innerHTML,/&lt;admin&gt;/);
  assert.ok(!$('#remote-account').innerHTML.includes('caixa'));
});
test('gerar convite envia tipos corretos e apresenta segredo apenas no resultado',async()=>{
  const {c,$,calls}=ambiente();const f=$('#remote-invite-form');
  f.entradas=[['operador_id','1'],['minutos','60'],['permissao','CONSULTA']];
  await f.eventos.submit({preventDefault(){},submitter:{},target:f});
  await new Promise(r=>setImmediate(r));
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0])),['remoto','POST',{operador_id:1,minutos:60,permissao:'CONSULTA'}]);
  assert.equal($('#remote-invite-result').hidden,false);
  assert.equal($('#remote-invite-link').type,'password');
  c.clearRemoteInvite();assert.equal($('#remote-invite-link').value,'');
});
test('encerrar todos exige confirmação explícita',async()=>{
  const {c,$,calls}=ambiente();c.confirm=()=>false;
  await $('#remote-revoke-all').eventos.click({currentTarget:{}});assert.equal(calls.length,0);
  c.confirm=()=>true;await $('#remote-revoke-all').eventos.click({currentTarget:{}});
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0])),['remoto','DELETE',{confirmar:true}]);
});
