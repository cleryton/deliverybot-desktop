// Somente o diagnóstico do executável usa estas dependências, sem acesso a contas.
import {EventEmitter} from 'node:events';
export function fakeDependencies(){
  return {authFactory:async()=>({state:{creds:{registered:false},keys:{get:async()=>({}),set:async()=>{}}},saveCreds:async()=>{}}),
    socketFactory:()=>{const ev=new EventEmitter();setTimeout(()=>ev.emit('connection.update',{qr:'DeliveryBot:TESTE-SEM-CONEXAO-REAL'}),40);
      return {ev,user:{id:'5547999990000@s.whatsapp.net'},end:()=>{},sendMessage:async()=>({key:{id:'TESTE'},message:{conversation:'teste'}})};}};
}
