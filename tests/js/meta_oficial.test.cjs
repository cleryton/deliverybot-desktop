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

test('conta individual lista números escapados e invalida seleção ao editar credenciais',async()=>{
  const {contexto:c,elementos:e}=ambiente();
  const form=e.get('#meta-own-form');form.entradas=[['WHATSAPP_TOKEN','token-proprio']];
  const chamadas=[];
  c.api=async(...args)=>{chamadas.push(args);return {numeros:[{id:'12345',telefone:'<img>',nome:'<script>'}],expira_em:0,acesso_dados_expira_em:1};};
  await form.eventos.submit({preventDefault(){},submitter:{},target:form});
  assert.equal(chamadas[0][0],'meta/numeros');assert.equal(chamadas[0][1],'POST');
  assert.ok(!e.get('#meta-own-number').innerHTML.includes('<img>'));
  assert.match(e.get('#meta-own-number').innerHTML,/&lt;script&gt;/);
  assert.match(e.get('#meta-own-validity').textContent,/Acesso aos dados/);
  assert.equal(e.get('#meta-own-connect').disabled,false);
  form.eventos.input({target:{name:'WHATSAPP_TOKEN'}});
  assert.equal(e.get('#meta-own-connect').disabled,true);
});

test('resposta atrasada da consulta não valida credenciais editadas enquanto aguardava',async()=>{
  const {contexto:c,elementos:e}=ambiente();
  const form=e.get('#meta-own-form');form.entradas=[];
  let resolver;c.api=()=>new Promise(r=>resolver=r);
  const promessa=form.eventos.submit({preventDefault(){},submitter:{},target:form});
  form.eventos.input({target:{name:'WHATSAPP_APP_SECRET'}});
  resolver({numeros:[{id:'12345',telefone:'antigo',nome:'antigo'}],expira_em:0});
  await promessa;
  assert.equal(e.get('#meta-own-connect').disabled,true);
  assert.ok(!e.get('#meta-own-number').innerHTML.includes('antigo'));
});

test('conexão própria exige confirmação, bloqueia formulário e remove credenciais após salvar',async()=>{
  const {contexto:c,elementos:e}=ambiente();
  const form=e.get('#meta-own-form');form.entradas=[['WHATSAPP_TOKEN','token-proprio'],['WHATSAPP_APP_SECRET','segredo-proprio'],['WHATSAPP_PHONE_NUMBER_ID','12345']];
  form.elements={WHATSAPP_TOKEN:{value:'token-proprio'},WHATSAPP_APP_SECRET:{value:'segredo-proprio'},configurar_webhook:{checked:true}};
  vm.runInContext("metaCurrent={numero_id:''};metaOwnValidated=true;",c);
  c.confirm=()=>true;c.metaLoad=async()=>{};
  let dados;c.api=async(path,method,d)=>{assert.equal(path,'meta/conectar');assert.equal(method,'POST');assert.equal(e.get('#meta-own-fields').disabled,true);dados=d;return {salvo:true,webhook_configurado:false,aviso:'Conta salva, webhook pendente'};};
  await e.get('#meta-own-connect').eventos.click({currentTarget:e.get('#meta-own-connect')});
  assert.equal(dados.confirmar,true);assert.equal(dados.configurar_webhook,true);assert.equal(dados.numero_anterior,'');
  assert.equal(form.elements.WHATSAPP_TOKEN.value,'');assert.equal(form.elements.WHATSAPP_APP_SECRET.value,'');
  assert.equal(e.get('#meta-own-fields').disabled,false);assert.equal(e.get('#meta-own-connect').disabled,true);
  assert.equal(e.get('#meta-setup-steps').dataset.stage,'webhook');
});
