import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile,readdir} from 'node:fs/promises';
import {join,resolve,dirname} from 'node:path';
import {tmpdir} from 'node:os';
import {once} from 'node:events';
import {get} from 'node:http';
import {WhatsAppBridge,destination} from '../bridge.mjs';
import {serverFor} from '../server.mjs';
import {fakeDependencies} from '../self-test.mjs';

async function fixture(t,extra={}){
  const directory=await mkdtemp(join(tmpdir(),'deliverybot-native-test-'));
  const bridge=new WhatsAppBridge({directory,callback:'http://127.0.0.1:5000/webhook/waha/secret',...fakeDependencies(),...extra});
  await bridge.initialize();
  t.after(async()=>{await bridge.close();
    const target=resolve(directory);
    if(dirname(target)!==resolve(tmpdir())||!target.split(/[\\/]/).at(-1).startsWith('deliverybot-native-test-'))throw new Error('Pasta de teste inválida.');
    await rm(target,{recursive:true,force:true});});
  return bridge;
}
const message=(id,text='Oi',jid='5547999990000@s.whatsapp.net')=>({key:{id,remoteJid:jid,fromMe:false},message:{conversation:text}});
const accepted=()=>({ok:true,json:async()=>({status:'recebido'})});

test('rejeita grupos, broadcasts e JIDs malformados no envio',()=>{
  assert.equal(destination('5511999990000@c.us'),'5511999990000@s.whatsapp.net');
  assert.equal(destination('123456789@lid'),'123456789@lid');
  for(const jid of ['grupo@g.us','status@broadcast','bad','@s.whatsapp.net'])assert.throws(()=>destination(jid));
});
test('API local exige chave e Host local, sem CORS',async t=>{
  const bridge=await fixture(t);const key='x'.repeat(40);const server=serverFor(bridge,key);
  server.listen(0,'127.0.0.1');await once(server,'listening');t.after(()=>new Promise(r=>server.close(r)));
  const url=`http://127.0.0.1:${server.address().port}`;
  assert.equal((await fetch(url+'/health')).status,401);
  const headers={'X-Api-Key':key};const good=await fetch(url+'/health',{headers});
  assert.equal(good.status,200);assert.equal(good.headers.get('access-control-allow-origin'),null);
  const wrongHost=await new Promise((done,reject)=>{get(url+'/health',{headers:{...headers,Host:'evil.example'}},res=>{res.resume();done(res.statusCode);}).on('error',reject);});
  assert.equal(wrongHost,403);
  assert.equal((await fetch(url+'/test/connect',{method:'POST',headers})).status,404);
  assert.equal((await fetch(url+'/api/sendText',{method:'POST',headers,body:JSON.stringify({chatId:'5511@c.us',text:'Oi'})})).status,400);
});
test('gera QR e preserva sessão pausada entre aberturas',async t=>{
  const bridge=await fixture(t);await bridge.start();await new Promise(r=>setTimeout(r,90));
  assert.equal(bridge.status,'SCAN_QR_CODE');assert.equal(bridge.qr.subarray(0,8).toString('hex'),'89504e470d0a1a0a');
  await bridge.stop();await bridge.close();
  const second=new WhatsAppBridge({directory:bridge.directory,callback:bridge.callback,...fakeDependencies()});
  await second.initialize();t.after(()=>second.close());assert.equal(second.status,'STOPPED');assert.equal(second.enabled,false);
});
test('entrada permanece no disco até o aplicativo confirmar e retoma após reiniciar',async t=>{
  let fail=true;const received=[];
  const fetcher=async(url,options)=>{if(fail)throw new Error('offline');received.push(JSON.parse(options.body));return accepted();};
  const bridge=await fixture(t,{fetcher});
  await assert.rejects(bridge.receive({type:'notify',messages:[message('1','primeira'),message('2','segunda')]}));
  assert.equal((await readdir(join(bridge.directory,'inbox'))).length,2);
  await bridge.close();
  fail=false;
  const second=new WhatsAppBridge({directory:bridge.directory,callback:bridge.callback,fetcher,...fakeDependencies()});
  await second.initialize();await second.deliver();await second.close();
  assert.deepEqual(received.map(e=>e.payload.body),['primeira','segunda']);
  assert.equal((await readdir(join(bridge.directory,'inbox'))).length,0);
});
test('ignora ecos, grupos e histórico; conserva PN e destino LID',async t=>{
  const received=[];const bridge=await fixture(t,{fetcher:async(u,o)=>{received.push(JSON.parse(o.body));return accepted();}});
  await bridge.receive({type:'append',messages:[message('history')]});
  const own=message('own');own.key.fromMe=true;
  const lid=message('lid','produto','123456789012345@lid');lid.key.remoteJidAlt='5547999990000@s.whatsapp.net';
  await bridge.receive({type:'notify',messages:[own,message('group','Oi','123@g.us'),message('status','Oi','status@broadcast'),lid]});
  assert.equal(received.length,1);assert.equal(received[0].payload.telefone,'5547999990000');assert.equal(received[0].payload.from,'123456789012345@lid');
});
test('repetição do mesmo evento não sobrescreve a entrada pendente',async t=>{
  const bridge=await fixture(t,{fetcher:async()=>({ok:false})});
  await bridge.receive({type:'notify',messages:[message('1')]});
  await bridge.receive({type:'notify',messages:[message('1')]});
  const files=await readdir(join(bridge.directory,'inbox'));assert.equal(files.length,1);
  assert.equal(JSON.parse(await readFile(join(bridge.directory,'inbox',files[0]))).payload.id,'5547999990000@s.whatsapp.net:1');
});
test('não entrega a entrada se o webhook responde com conteúdo inesperado',async t=>{
  const bridge=await fixture(t,{fetcher:async()=>({ok:true,json:async()=>({status:'ignorado'})})});
  await bridge.receive({type:'notify',messages:[message('1')]});
  assert.equal((await readdir(join(bridge.directory,'inbox'))).length,1);
});
test('configuração integrada recusa callback fora do aplicativo',async t=>{
  const bridge=await fixture(t);
  await assert.rejects(bridge.configure({webhooks:[{url:'https://other.example'}]}));
  await bridge.configure({webhooks:[{url:bridge.callback,events:['message']}]});
  assert.equal(bridge.info().config.webhooks[0].url,bridge.callback);
});

test('pausar cancela a reconexão pendente e preserva autenticação',async t=>{
  const bridge=await fixture(t);await bridge.start();
  await bridge.connection(bridge.socket,{connection:'close',lastDisconnect:{error:{output:{statusCode:515}}}});
  assert.equal(bridge.status,'STARTING');
  await bridge.stop();await new Promise(r=>setTimeout(r,550));
  assert.equal(bridge.socket,null);assert.equal(bridge.status,'STOPPED');assert.equal(bridge.enabled,false);
});
test('sessão expirada pede nova leitura do QR e não entra em loop',async t=>{
  const bridge=await fixture(t);await bridge.start();
  await bridge.connection(bridge.socket,{connection:'close',lastDisconnect:{error:{output:{statusCode:401}}}});
  assert.equal(bridge.status,'FAILED');assert.equal(bridge.enabled,false);assert.equal(bridge.needsPairing,true);
  const saved=JSON.parse(await readFile(join(bridge.directory,'session.json')));assert.equal(saved.needsPairing,true);
  await bridge.start();await new Promise(r=>setTimeout(r,90));assert.equal(bridge.status,'SCAN_QR_CODE');
});
