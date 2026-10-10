import {createServer} from 'node:http';
import {timingSafeEqual} from 'node:crypto';
import {createInterface} from 'node:readline';
import {WhatsAppBridge} from './bridge.mjs';

export function serverFor(bridge,key,{testMode=false}={}){
  return createServer(async(req,res)=>{
    const respond=(status,body)=>{res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});res.end(JSON.stringify(body));};
    const received=Buffer.from(req.headers['x-api-key']||'');const expected=Buffer.from(key);
    if(received.length!==expected.length||!timingSafeEqual(received,expected))return respond(401,{erro:'Acesso não autorizado.'});
    // Não oferece CORS nem acesso por um Host externo ao processo local.
    if(!/^127\.0\.0\.1:\d+$/.test(req.headers.host||''))return respond(403,{erro:'Endereço local obrigatório.'});
    try{
      let raw='';for await(const chunk of req){raw+=chunk.toString();if(Buffer.byteLength(raw)>65536)return respond(413,{erro:'Requisição muito grande.'});}
      const data=raw?JSON.parse(raw):{};const path=new URL(req.url,'http://localhost').pathname;
      const sessionPath='/api/sessions/'+encodeURIComponent(bridge.session);
      if(req.method==='GET'&&path==='/health')return respond(200,{engine:'DELIVERYBOT_NATIVE',ready:true});
      if(req.method==='GET'&&path===sessionPath)return respond(200,bridge.info());
      if(req.method==='GET'&&path===`/api/${encodeURIComponent(bridge.session)}/auth/qr`){
        if(!bridge.qr)return respond(409,{erro:'O QR Code ainda não está disponível.'});
        return respond(200,{mimetype:'image/png',data:bridge.qr.toString('base64')});
      }
      if(req.method==='PUT'&&path===sessionPath){await bridge.configure(data.config);return respond(200,bridge.info());}
      if(req.method==='POST'&&path===sessionPath+'/start'){await bridge.start();return respond(200,bridge.info());}
      if(req.method==='POST'&&path===sessionPath+'/stop'){await bridge.stop();return respond(200,bridge.info());}
      if(req.method==='POST'&&path===sessionPath+'/restart'){await bridge.restart();return respond(200,bridge.info());}
      if(req.method==='POST'&&path==='/api/sendText')return respond(200,await bridge.send(data));
      if(testMode&&req.method==='POST'&&path==='/test/connect'){await bridge.connection(bridge.socket,{connection:'open'});return respond(200,bridge.info());}
      return respond(404,{erro:'Operação inexistente.'});
    }catch(e){respond(400,{erro:e.message||'Não foi possível concluir a operação.'});}
  });
}

export async function main(){
  const key=process.env.DELIVERYBOT_NATIVE_KEY;
  const directory=process.env.DELIVERYBOT_NATIVE_DATA;
  const callback=process.env.DELIVERYBOT_NATIVE_CALLBACK;
  if(!key||key.length<32||!directory||!callback)throw new Error('Abra este componente pelo DeliveryBot.');
  const testMode=process.argv.includes('--self-test')&&process.env.DELIVERYBOT_NATIVE_TEST==='1';
  let injected={};
  if(testMode){const {fakeDependencies}=await import('./self-test.mjs');injected=fakeDependencies();}
  const bridge=new WhatsAppBridge({directory,session:process.env.DELIVERYBOT_NATIVE_SESSION||'default',callback,...injected});
  await bridge.initialize();
  const server=serverFor(bridge,key,{testMode});
  const close=async()=>{server.close();await bridge.close();process.exit(0);};
  const lines=createInterface({input:process.stdin});
  lines.on('line',line=>{if(line==='shutdown')close();});lines.on('close',close);
  process.on('SIGTERM',close);process.on('SIGINT',close);
  server.listen(Number(process.env.DELIVERYBOT_NATIVE_PORT||0),'127.0.0.1');
  server.on('error',err=>{console.error('Falha ao iniciar componente local:',err.code);close();});
}
if(process.argv[1]?.replaceAll('\\','/').endsWith('/server.mjs'))main().catch(err=>{console.error(err.message);process.exitCode=1;});
