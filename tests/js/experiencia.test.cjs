const test = require('node:test');
const assert = require('node:assert/strict');
const ux = require('../../web/static/experiencia.js');

test('fila explica a espera por HTTPS sem prometer retomada após o prazo',()=>{
  const dados={pendentes:3,aguardando_https:2};
  assert.match(ux.fila(dados),/^3 mensagens.*2 aguardando a página HTTPS.*dentro do prazo/);
  assert.deepEqual(dados,{pendentes:3,aguardando_https:2});
});
test('fila vazia e respostas antigas não mostram problemas de HTTPS inexistentes',()=>{
  assert.equal(ux.fila(),'0 mensagens em processamento ou aguardando');
  assert.equal(ux.fila({pendentes:1}),'1 mensagem em processamento ou aguardando');
});
test('fila limita contagens inconsistentes e rejeita dados inválidos',()=>{
  assert.match(ux.fila({pendentes:1,aguardando_https:8}),/1 aguardando/);
  for(const valor of [-1,NaN,Infinity,'<script>',null,0.5]) {
    assert.equal(ux.fila({pendentes:valor,aguardando_https:valor}),'0 mensagens em processamento ou aguardando');
  }
});

const orders = [
  {numero_pedido:'#12',cliente_nome:'João Silva',cliente_telefone:'5542000012',status:'RECEBIDO',itens:[{produto_nome:'Café com pão'}]},
  {numero_pedido:'#13',cliente_nome:'Maria',cliente_telefone:'5542000013',status:'ENTREGUE',itens:[{produto_nome:'Peça de reposição'}]},
  {numero_pedido:'#14',cliente_nome:'Ana',status:'CANCELADO'},
  {numero_pedido:'#15',cliente_nome:'José',status:'RETIRADO'},
  {numero_pedido:'#16',cliente_nome:'Clara',status:'EM_PREPARO'},
];

test('busca ignora acentos, caixa e espaços externos',()=>{
  assert.equal(ux.texto('  CAFÉ e PÃO  '),'cafe e pao');
  assert.equal(ux.texto(null),'');
  assert.deepEqual(ux.pedidos(orders,'abertos','joao CAFE').map(p=>p.numero_pedido),['#12']);
  assert.deepEqual(ux.pedidos(orders,'todos','pao silva').map(p=>p.numero_pedido),['#12']);
});
test('busca encontra número, telefone e produto e respeita todos os termos',()=>{
  assert.equal(ux.pedidos(orders,'todos','#13')[0].cliente_nome,'Maria');
  assert.equal(ux.pedidos(orders,'todos','000012')[0].cliente_nome,'João Silva');
  assert.equal(ux.pedidos(orders,'todos','peca reposicao')[0].cliente_nome,'Maria');
  assert.deepEqual(ux.pedidos(orders,'todos','maria cafe'),[]);
});
test('filtros separam abertos, entregues, retirados e cancelados sem mudar a fonte',()=>{
  const before=JSON.stringify(orders);
  assert.equal(ux.pedidos(orders,'abertos','').length,2);
  assert.equal(ux.pedidos(orders,'concluidos','').length,2);
  assert.equal(ux.pedidos(orders,'cancelados','')[0].cliente_nome,'Ana');
  assert.equal(ux.pedidos(orders,'todos','').length,5);
  assert.equal(JSON.stringify(orders),before);
});
test('catálogo vazio e dados opcionais não quebram a busca',()=>{
  assert.deepEqual(ux.pedidos([],'todos',''),[]);
  assert.equal(ux.pedidos(orders,'cancelados','Ana').length,1);
  assert.deepEqual(ux.pedidos(orders,'desconhecido',''),[]);
});
test('próximo passo segue a primeira configuração obrigatória pendente, ignorando IA opcional',()=>{
  const data={tutorial:[{titulo:'IA',pagina:'conexoes',opcional:true},{titulo:'Catálogo',pagina:'produtos',concluida:false},{titulo:'Perfil',pagina:'comercio',concluida:true}]};
  const before=JSON.stringify(data);
  assert.deepEqual(ux.proximoPasso(data),{titulo:'Catálogo',pagina:'produtos',pronto:false});
  assert.equal(JSON.stringify(data),before);
});
for(const [field,page] of [['fila_ok','conexoes'],['whatsapp_ok','conexoes'],['https_ok','publicacao']]) {
  test('etapas concluídas ainda exigem '+field,()=>{
    const op={fila_ok:true,whatsapp_ok:true,https_ok:true,[field]:false};
    assert.equal(ux.proximoPasso({tutorial:[],operacao:op}).pronto,false);
    assert.equal(ux.proximoPasso({tutorial:[],operacao:op}).pagina,page);
  });
}
test('etapas e serviços atendidos direcionam aos pedidos',()=>{
  assert.deepEqual(ux.proximoPasso({tutorial:[{concluida:true}],operacao:{fila_ok:true,whatsapp_ok:true,https_ok:true}}),
    {titulo:'Acompanhar seus pedidos',pagina:'pedidos',pronto:true});
});
test('modo de teste e conexão pendente nunca aparecem como conectados',()=>{
  assert.deepEqual(ux.conexao({operacao:{whatsapp_estado:'TESTE'}}),{texto:'Modo de teste',ok:false});
  assert.equal(ux.conexao({operacao:{whatsapp_estado:'SCAN_QR_CODE'}}).ok,false);
});
test('WhatsApp conectado ainda exige página pública e fila',()=>{
  assert.match(ux.conexao({operacao:{whatsapp_ok:true,https_ok:false}}).texto,/Página/);
  assert.equal(ux.conexao({operacao:{whatsapp_ok:true,https_ok:true,fila_ok:false}}).ok,false);
  assert.equal(ux.conexao({operacao:{whatsapp_ok:true,https_ok:true,fila_ok:true}}).ok,true);
});
test('credenciais Meta não são apresentadas como prova de uma conexão real',()=>{
  assert.match(ux.conexao({whatsapp:'META',operacao:{whatsapp_ok:true,https_ok:true,fila_ok:true}}).texto,/confira o webhook/);
});

const response=(status,data)=>({status,ok:status>=200&&status<300,json:async()=>data});
test('consulta mantém método, CSRF e corpo e cancela o temporizador ao terminar',async()=>{
  let calls=0,cancelled=false;
  const opts={method:'POST',headers:{'X-CSRF-Token':'ficticio'},body:'{"nome":"Teste"}'};
  const result=await ux.solicitar(async(url,request)=>{
    calls++;assert.equal(url,'/local');assert.equal(request.headers,opts.headers);assert.equal(request.body,opts.body);
    assert.ok(request.signal instanceof AbortSignal);return response(201,{id:1});
  },'/local',opts,{agendar:()=>42,cancelar:id=>{assert.equal(id,42);cancelled=true;}});
  assert.deepEqual(result,{id:1});assert.equal(calls,1);assert.ok(cancelled);
});
for(const [status,message] of [[401,/sessão terminou/],[403,/administrador/],[400,/Preço inválido/]]) {
  test('erro HTTP orienta o usuário: '+status,async()=>{
    await assert.rejects(ux.solicitar(async()=>response(status,{erro:'Preço inválido'}),'/local',{method:'PUT'}),message);
  });
}
test('resposta incompleta em gravação orienta conferir o resultado sem repetir',async()=>{
  await assert.rejects(ux.solicitar(async()=>({status:200,ok:true,json:async()=>{throw new SyntaxError();}}),'/local',{method:'POST'}),/confirmar o resultado.*antes de repetir/);
});
test('HTML de login expirado orienta entrar novamente',async()=>{
  await assert.rejects(ux.solicitar(async()=>({status:401,ok:false,json:async()=>{throw new SyntaxError();}}),'/local',{method:'GET'}),/Entre novamente/);
});
test('CSRF expirado não é confundido com falta de permissão',async()=>{
  await assert.rejects(ux.solicitar(async()=>response(403,{erro:'Sessão expirada. Reabra o painel.'}),'/local',{method:'POST'}),/sessão terminou/);
});
test('falha de rede em gravação nunca repete automaticamente a solicitação',async()=>{
  let calls=0;
  await assert.rejects(ux.solicitar(async()=>{calls++;throw new TypeError('Network error');},'/local',{method:'POST'}),/pode ter sido concluída.*antes de repetir/);
  assert.equal(calls,1);
});
test('falha de rede em consulta preserva a orientação sem expor mensagem técnica',async()=>{
  await assert.rejects(ux.solicitar(async()=>{throw new TypeError('Network error');},'/local',{method:'GET'}),/Seus dados foram mantidos/);
});
test('tempo excedido cancela a chamada e avisa sobre resultado incerto da gravação',async()=>{
  let cancelled=0;
  await assert.rejects(ux.solicitar(async(url,{signal})=>{
    assert.ok(signal.aborted);throw Object.assign(new Error(),{name:'AbortError'});
  },'/local',{method:'PUT'},{agendar:callback=>{callback();return 1;},cancelar:()=>cancelled++}),/demorou.*pode ter sido concluída/);
  assert.equal(cancelled,1);
});

function button(tagName='BUTTON') {
  const attributes=new Map(),classes=new Set();
  return {tagName,innerHTML:'<span>Salvar</span>',textContent:'Salvar',disabled:false,
    getAttribute:k=>attributes.get(k)??null,setAttribute:(k,v)=>attributes.set(k,v),removeAttribute:k=>attributes.delete(k),
    classList:{add:k=>classes.add(k),remove:k=>classes.delete(k),contains:k=>classes.has(k)}};
}
test('botão ocupado impede envio duplicado e recupera rótulo e acessibilidade',async()=>{
  const b=button();let done,attempts=0;
  const pending=ux.ocupado(b,()=>new Promise(resolve=>{done=resolve;attempts++;}));
  assert.ok(b.disabled);assert.equal(b.getAttribute('aria-busy'),'true');assert.equal(b.getAttribute('aria-label'),'Aguarde…');assert.ok(b.classList.contains('busy'));
  assert.equal(await ux.ocupado(b,()=>attempts++),false);assert.equal(attempts,1);
  done();assert.equal(await pending,true);assert.ok(!b.disabled);assert.equal(b.innerHTML,'<span>Salvar</span>');
  assert.equal(b.getAttribute('aria-busy'),null);assert.equal(b.getAttribute('aria-label'),null);assert.ok(!b.classList.contains('busy'));
});
test('falha da ação libera botão e preserva o erro para o aviso',async()=>{
  const b=button();b.setAttribute('aria-busy','false');
  await assert.rejects(ux.ocupado(b,async()=>{throw new Error('Falha fictícia');}),/Falha fictícia/);
  assert.equal(b.disabled,false);assert.equal(b.getAttribute('aria-busy'),'false');
});
test('checkbox não perde conteúdo ou rótulo e estado alterado pela operação é preservado',async()=>{
  const c=button('INPUT');await ux.ocupado(c,async()=>assert.equal(c.textContent,'Salvar'));assert.equal(c.textContent,'Salvar');
  const b=button();await ux.ocupado(b,async()=>{b.textContent='Verificar novamente';});assert.equal(b.textContent,'Verificar novamente');
});
test('indicador ocupado preserva elementos internos e rótulos acessíveis do botão',async()=>{
  const b=button();b.setAttribute('aria-label','Abrir catálogo');
  Object.defineProperty(b,'innerHTML',{get:()=>'<b id="catalog-nav-label">Catálogo</b>',set:()=>assert.fail('Não substituir os elementos do botão')});
  Object.defineProperty(b,'textContent',{get:()=> 'Catálogo',set:()=>assert.fail('Não remover os elementos do botão')});
  await ux.ocupado(b,async()=>assert.match(b.innerHTML,/catalog-nav-label/));
  assert.equal(b.getAttribute('aria-label'),'Abrir catálogo');
});

for (const method of ['GET','POST']) {
  test('limite em resposta de texto informa a pausa sem repetir '+method,async()=>{
    let chamadas=0;
    const fetcher=async()=>{chamadas++;return {status:429,ok:false,headers:{get:()=> '120'},json:async()=>{throw new SyntaxError('HTML de limite');}};};
    await assert.rejects(ux.solicitar(fetcher,'/local',{method}),/Muitas tentativas.*2 minutos/);
    assert.equal(chamadas,1);
  });
}
for (const [header,expected] of [['1',/1 segundo/],['60',/1 minuto/],['<script>',/alguns minutos/],['999999',/alguns minutos/]]) {
  test('tempo de espera é legível e cabeçalho não vira conteúdo: '+header,async()=>{
    await assert.rejects(ux.solicitar(async()=>({status:429,ok:false,headers:{get:()=>header},json:async()=>({})}),'/local',{method:'GET'}),expected);
  });
}
test('arquivo grande recebe orientação útil mesmo em resposta HTML',async()=>{
  await assert.rejects(ux.solicitar(async()=>({status:413,ok:false,json:async()=>{throw new SyntaxError();}}),'/local',{method:'POST'}),/Reduza o tamanho/);
});
test('recusa não JSON não afirma que a conta perdeu permissão',async()=>{
  await assert.rejects(ux.solicitar(async()=>({status:403,ok:false,json:async()=>{throw new SyntaxError();}}),'/local',{method:'POST'}),/Reabra o aplicativo/);
});
test('falha de serviço mantém resultado incerto de gravação e não mostra detalhes internos',async()=>{
  let chamadas=0;
  await assert.rejects(ux.solicitar(async()=>{chamadas++;return response(503,{erro:'PRIVATE_SERVER_TRACE'});},'/local',{method:'POST'}),error=>
    /pode ter sido concluída.*antes de repetir/.test(error.message)&&!error.message.includes('PRIVATE_SERVER_TRACE'));
  assert.equal(chamadas,1);
});
test('ação em andamento não é duplicada se outra renderização reabilitar o botão',async()=>{
  const b=button();let concluir,chamadas=0;
  const primeira=ux.ocupado(b,()=>new Promise(resolve=>{chamadas++;concluir=resolve;}));
  b.disabled=false;
  assert.equal(await ux.ocupado(b,()=>chamadas++),false);
  concluir();await primeira;assert.equal(chamadas,1);
});
test('estado de negócio decidido durante a operação permanece após o fim da espera',async()=>{
  const b=button();ux.disponivel(b,true);
  await ux.ocupado(b,async()=>{ux.disponivel(b,false);});
  assert.equal(b.disabled,true);
  assert.equal(await ux.ocupado(b,()=>assert.fail('Estado de negócio bloqueia ação')),false);
  ux.disponivel(b,true);
  await ux.ocupado(b,async()=>{ux.disponivel(b,true);assert.equal(b.disabled,true);});
  assert.equal(b.disabled,false);
});
