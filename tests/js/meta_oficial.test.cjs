const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

function ambiente(relatorio){
  const elementos=new Map();
  const get=k=>{if(!elementos.has(k))elementos.set(k,{value:k==='#meta-month'?'2026-10':'TODOS',textContent:'',innerHTML:'',dataset:{},eventos:{},addEventListener(nome,fn){this.eventos[nome]=fn;}});return elementos.get(k);};
  const contexto=vm.createContext({Intl,Date,URLSearchParams,FormData:function(f){return f.entradas;},isAdmin:true,state:{page:'meta'},document:{visibilityState:'visible'},setInterval(){},$:get,run:async(b,fn)=>fn(),toast(){},
    api:async()=>relatorio,escapeHTML:v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../../web/static/meta_oficial.js'),'utf8'),contexto);
  return {contexto,elementos};
}

test('valores subcentavo permanecem visíveis e custo ausente não vira zero',()=>{
  const {contexto:c}=ambiente();
  assert.equal(c.metaMoney(null),'Pendente');
  assert.match(c.metaMoney(0),/0,00/);
  assert.match(c.metaMoney(1000),/0,001/);
  assert.match(c.metaMoney(123456),/0,123456/);
});

test('salvar tarifas usa o contrato PUT da API comum e manda os valores sem expor credenciais',async()=>{
  const {contexto:c,elementos:e}=ambiente();
  const chamadas=[];
  c.api=async(...args)=>{chamadas.push(args);return {};};
  c.metaLoad=async()=>{};
  const form=e.get('#meta-rates-form');
  form.entradas=[['marketing','0.25'],['utility',''],['limite','2.00'],['alerta_percentual','80']];
  await form.eventos.submit({preventDefault(){},submitter:{},target:form});
  assert.equal(chamadas.length,1);
  assert.equal(chamadas[0][0],'meta/custos');
  assert.equal(chamadas[0][1],'PUT');
  assert.deepEqual(JSON.parse(JSON.stringify(chamadas[0][2])),{tarifas:{marketing:'0.25'},limite:'2.00',alerta_percentual:80});
});

test('painel escapa os dados de categoria e mostra pendência e orçamento incompleto',async()=>{
  const r={totais:{enviadas:1,entregues:1,cobraveis:1,estimativa_micros:0,gratuitas:0,sem_estimativa:1,falhas:0},aviso:'Estimativa',
    orcamento:{nivel:'ATENCAO',gasto_micros:800000,limite_micros:1000000,incompleto:true},
    mensagens:[{referencia:'<img>',ambiente:'PRODUCAO',entregue_em:null,estado:'sent',categoria:'<script>alert(1)</script>',mercado:'BR',cobravel:1,estimativa_micros:null}]};
  const {contexto:c,elementos:e}=ambiente(r);
  await c.metaReport();
  const html=e.get('#meta-cost-rows').innerHTML;
  assert.ok(!html.includes('<script>')&&!html.includes('<img>'));
  assert.match(html,/&lt;script&gt;/);
  assert.match(html,/Pendente/);
  assert.match(html,/Enviada/);
  assert.match(e.get('#meta-budget-note').textContent,/custos de produção ainda não estimados/);
});

test('troca exige confirmação e usa POST com o número anterior, limpando os campos de credenciais',async()=>{
  const {contexto:c,elementos:e}=ambiente();
  const chamadas=[];
  c.api=async(...args)=>{chamadas.push(args);return {aviso:'Conexão fictícia trocada.'};};
  c.metaLoad=async()=>{};
  const form=e.get('#meta-migration-form');
  form.entradas=[['WHATSAPP_PHONE_NUMBER_ID','123456789111'],['WHATSAPP_BUSINESS_ACCOUNT_ID','987654321000'],['WHATSAPP_TOKEN','token-ficticio']];
  form.elements={WHATSAPP_TOKEN:{value:'token-ficticio'},WHATSAPP_APP_SECRET:{value:'segredo-ficticio'},WHATSAPP_VERIFY_TOKEN:{value:'verificacao-ficticia'}};
  vm.runInContext("metaValidated=true;metaCurrent={numero_id:'123456789000'};",c);
  const botao=e.get('#meta-migrate');
  c.confirm=()=>false;
  await botao.eventos.click({currentTarget:botao});
  assert.equal(chamadas.length,0);
  c.confirm=()=>true;
  await botao.eventos.click({currentTarget:botao});
  assert.equal(chamadas.length,1);
  assert.equal(chamadas[0][0],'meta/migrar');
  assert.equal(chamadas[0][1],'POST');
  assert.equal(chamadas[0][2].numero_anterior,'123456789000');
  assert.equal(chamadas[0][2].confirmar_migracao,true);
  assert.equal(form.elements.WHATSAPP_TOKEN.value,'');
  assert.equal(form.elements.WHATSAPP_APP_SECRET.value,'');
  assert.equal(form.elements.WHATSAPP_VERIFY_TOKEN.value,'');
  assert.equal(botao.disabled,true);
});
