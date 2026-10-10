import {mkdir, readFile, writeFile, rename, readdir, unlink} from 'node:fs/promises';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import QRCode from 'qrcode';
import makeWASocket, {useMultiFileAuthState, makeCacheableSignalKeyStore, normalizeMessageContent, DisconnectReason, Browsers} from '@whiskeysockets/baileys';
import pino from 'pino';

const logger=pino({level:'warn'});
export async function atomicJSON(path,value){
  const temporary=path+'.tmp';
  await writeFile(temporary,JSON.stringify(value),{mode:0o600});
  await rename(temporary,path);
}
export function privateJid(jid){return typeof jid==='string'&&/^\d+(?::\d+)?@(s\.whatsapp\.net|lid|c\.us)$/.test(jid);}
export function destination(jid){
  if(!privateJid(jid))throw new Error('Conversa inválida.');
  return jid.replace(/@c\.us$/,'@s.whatsapp.net');
}

export class WhatsAppBridge{
  constructor({directory,session='default',callback,socketFactory=makeWASocket,authFactory=useMultiFileAuthState,fetcher=fetch}){
    this.directory=directory;this.session=session;this.callback=callback;
    this.socketFactory=socketFactory;this.authFactory=authFactory;this.fetcher=fetcher;
    this.status='STOPPED';this.config={webhooks:[]};this.enabled=false;this.needsPairing=false;
    this.socket=null;this.qr=null;this.error=null;this.retry=0;this.closed=false;
    this.writes=Promise.resolve();this.pending=new Set();this.messages=new Map();this.number=null;
    this.incoming=Promise.resolve();this.sequence=0;
    this.epoch=0;this.connecting=false;
  }
  async initialize(){
    await mkdir(join(this.directory,'inbox'),{recursive:true});
    try{const saved=JSON.parse(await readFile(join(this.directory,'session.json'),'utf8'));this.config=saved.config||this.config;this.enabled=!!saved.enabled;this.needsPairing=!!saved.needsPairing;}
    catch(e){if(e.code!=='ENOENT')throw new Error('A sessão local não pôde ser lida. Confira whatsapp.log na pasta de dados.');}
    this.pump=setInterval(()=>this.deliver().catch(()=>{}),2000);
    if(this.enabled)this.start().catch(()=>this.fail('Não foi possível iniciar a conexão. Clique em Conectar WhatsApp.'));
  }
  persist(){
    const value={config:this.config,enabled:this.enabled,needsPairing:this.needsPairing};
    this.writes=this.writes.catch(()=>{}).then(()=>atomicJSON(join(this.directory,'session.json'),value));
    return this.writes;
  }
  info(){return {name:this.session,status:this.status,config:this.config,engine:'DELIVERYBOT_NATIVE',me:this.number?{id:this.number}:null,error:this.error};}
  async configure(config){
    if(!config||typeof config!=='object'||Array.isArray(config))throw new Error('Configuração inválida.');
    // Só o servidor do aplicativo recebe as mensagens deste componente local.
    if((config.webhooks||[]).some(w=>w.url!==this.callback))throw new Error('O recebimento integrado usa o endereço local do aplicativo.');
    this.config=structuredClone(config);await this.persist();
  }
  fail(message){this.status='FAILED';this.error=message;this.qr=null;}
  track(work){const p=Promise.resolve(work);this.pending.add(p);p.catch(()=>{logger.warn('Não foi possível salvar uma mensagem local.');}).finally(()=>this.pending.delete(p));return p;}
  async start(){
    if(this.closed)throw new Error('O componente está encerrando.');
    if(this.socket&&['WORKING','STARTING','SCAN_QR_CODE'].includes(this.status))return;
    clearTimeout(this.reconnect);this.epoch++;
    this.enabled=true;this.error=null;this.status='STARTING';this.retry=0;await this.persist();
    await this.connect();
  }
  async connect(){
    if(this.closed||!this.enabled||this.connecting)return;
    this.connecting=true;const epoch=this.epoch;
    try{await this.openSocket(epoch);}finally{
      this.connecting=false;
      if(!this.closed&&this.enabled&&epoch!==this.epoch){clearTimeout(this.reconnect);this.reconnect=setTimeout(()=>this.connect().catch(()=>this.fail('Clique em Conectar WhatsApp para retomar.')),0);}
    }
  }
  async openSocket(epoch){
    if(this.needsPairing){
      // Preserva a autenticação expirada, em vez de apagar dados do usuário.
      try{await rename(join(this.directory,'auth'),join(this.directory,'auth-expirada-'+Date.now()));}catch(e){if(e.code!=='ENOENT')throw e;}
      this.needsPairing=false;await this.persist();
    }
    const {state,saveCreds}=await this.authFactory(join(this.directory,'auth'));
    if(this.closed||!this.enabled||epoch!==this.epoch)return;
    const sock=this.socketFactory({auth:{creds:state.creds,keys:makeCacheableSignalKeyStore(state.keys,logger)},
      logger,browser:Browsers.windows('DeliveryBot'),syncFullHistory:false,shouldSyncHistoryMessage:()=>false,
      markOnlineOnConnect:false,connectTimeoutMs:30000,keepAliveIntervalMs:20000,
      shouldIgnoreJid:jid=>!privateJid(jid),getMessage:async key=>this.messages.get(key.id)});
    this.socket=sock;
    let credentials=Promise.resolve();
    sock.ev.on('creds.update',()=>{credentials=credentials.catch(()=>{}).then(saveCreds);this.track(credentials);});
    sock.ev.on('connection.update',update=>this.track(this.connection(sock,update)));
    sock.ev.on('messages.upsert',upsert=>{this.incoming=this.incoming.catch(()=>{}).then(()=>this.receive(upsert));this.track(this.incoming);});
  }
  async connection(sock,{connection,qr,lastDisconnect}){
    if(this.socket!==sock||this.closed)return;
    if(qr){const image=await QRCode.toBuffer(qr,{type:'png',width:300,margin:2});if(this.socket===sock&&!this.closed){this.qr=image;this.status='SCAN_QR_CODE';}}
    if(connection==='open'){this.status='WORKING';this.qr=null;this.error=null;this.retry=0;this.number=sock.user?.id?.replace(/:\d+@/,'@')||null;}
    if(connection==='close'){
      this.socket=null;this.qr=null;this.number=null;
      if(!this.enabled){this.status='STOPPED';return;}
      const code=lastDisconnect?.error?.output?.statusCode;
      if(code===DisconnectReason.loggedOut||code===DisconnectReason.badSession){
        this.needsPairing=true;this.enabled=false;await this.persist();this.fail('A sessão expirou. Clique em Conectar WhatsApp para gerar outro QR Code.');return;
      }
      if(code===DisconnectReason.connectionReplaced){this.enabled=false;await this.persist();this.fail('A conexão foi aberta em outra sessão. Clique em Conectar para retomar aqui.');return;}
      this.status='STARTING';this.retry++;
      if(this.retry>8){this.fail('A conexão não respondeu. Confira a internet e clique em Conectar WhatsApp.');return;}
      clearTimeout(this.reconnect);
      this.reconnect=setTimeout(()=>this.connect().catch(()=>this.fail('Falha ao retomar a conexão. Clique em Conectar WhatsApp.')),code===DisconnectReason.restartRequired?500:Math.min(30000,1000*2**this.retry));
    }
  }
  async stop(){
    this.enabled=false;this.epoch++;clearTimeout(this.reconnect);this.qr=null;this.number=null;
    const sock=this.socket;this.socket=null;sock?.end(undefined);this.status='STOPPED';await this.persist();
  }
  async restart(){await this.stop();await this.start();}
  async receive({type,messages}){
    if(type!=='notify'||this.closed)return;
    for(const msg of messages||[]){
      const jid=msg.key?.remoteJid;
      if(msg.key?.fromMe||!privateJid(jid)||!msg.key.id)continue;
      const content=normalizeMessageContent(msg.message);
      const text=content?.conversation||content?.extendedTextMessage?.text||content?.imageMessage?.caption||content?.videoMessage?.caption;
      if(typeof text!=='string'||!text.trim())continue;
      const alternative=msg.key.remoteJidAlt;
      const phone=(alternative?.endsWith('@s.whatsapp.net')?alternative:jid).split('@')[0].split(':')[0];
      const key=jid+':'+msg.key.id;
      const file=join(this.directory,'inbox',createHash('sha256').update(key).digest('hex')+'.json');
      const event={event:'message',session:this.session,recebido:Date.now()*1000+this.sequence++%1000,payload:{id:key,from:jid,telefone:phone,body:text.slice(0,8000),fromMe:false,notifyName:msg.pushName||'Cliente'}};
      try{await readFile(file);}catch(e){if(e.code!=='ENOENT')throw e;await atomicJSON(file,event);}
      this.messages.set(msg.key.id,content);if(this.messages.size>300)this.messages.delete(this.messages.keys().next().value);
    }
    await this.deliver();
  }
  async deliver(){
    if(this.delivering||this.closed)return;this.delivering=true;
    try{
      const files=(await readdir(join(this.directory,'inbox'))).filter(f=>/^[a-f0-9]{64}\.json$/.test(f));
      // O timestamp do evento é preservado para garantir a ordem de recebimento.
      const entries=await Promise.all(files.map(async file=>({file,event:JSON.parse(await readFile(join(this.directory,'inbox',file),'utf8'))})));
      entries.sort((a,b)=>(a.event.recebido||0)-(b.event.recebido||0));
      for(const {file,event} of entries){
        if(this.closed)break;
        const response=await this.fetcher(this.callback,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(event),signal:AbortSignal.timeout(5000),redirect:'error'});
        if(!response.ok)break;
        const result=await response.json();
        if(result.status!=='recebido')break;
        await unlink(join(this.directory,'inbox',file));
      }
    }finally{this.delivering=false;}
  }
  async send({chatId,text}){
    if(this.status!=='WORKING'||!this.socket)throw new Error('WhatsApp desconectado.');
    if(typeof text!=='string'||!text.trim()||text.length>16000)throw new Error('Mensagem inválida.');
    const sent=await this.socket.sendMessage(destination(chatId),{text});
    if(sent?.message&&sent.key?.id){this.messages.set(sent.key.id,sent.message);if(this.messages.size>300)this.messages.delete(this.messages.keys().next().value);}
    return {id:sent?.key?.id};
  }
  async close(){
    this.closed=true;clearTimeout(this.reconnect);clearInterval(this.pump);
    const sock=this.socket;this.socket=null;sock?.end(undefined);
    await Promise.allSettled([...this.pending,this.writes]);
  }
}
