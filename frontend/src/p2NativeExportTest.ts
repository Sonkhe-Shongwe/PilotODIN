import {invoke} from '@tauri-apps/api/core';
type NativeResult={status:'saved'|'cancelled';filename:string|null};
type Format='pdf'|'html';

function status(id:string,pass:boolean,detail:string){
 const target=document.getElementById(id+'-state');
 if(!target)return;
 target.textContent=(pass?'PASS: ':'FAIL: ')+detail;
 target.className=pass?'pass':'fail';
}
function log(detail:string){
 const target=document.getElementById('native-note');
 if(target)target.textContent=detail;
}
async function fixture(format:Format):Promise<number[]>{
 const path=format==='pdf'?'/p2-native-fixtures/report.pdf':'/p2-native-fixtures/report.html';
 const response=await fetch(path,{cache:'no-store'});
 if(!response.ok)throw new Error('Synthetic fixture unavailable: '+path+' HTTP '+response.status);
 const data=Array.from(new Uint8Array(await response.arrayBuffer()));
 if(data.length<50)throw new Error('Synthetic fixture unexpectedly empty');
 return data;
}
function wire(id:string,task:()=>Promise<void>){
 const btn=document.getElementById(id) as HTMLButtonElement|null;
 if(!btn)throw new Error('Required test button missing: '+id);
 btn.addEventListener('click',()=>{
  btn.disabled=true;
  void task().catch(error=>{
   const detail=error instanceof Error?error.message:String(error);
   status(id,false,detail);
   log('Test failed. Close the native window and share the diagnostics. '+detail);
  }).finally(()=>{btn.disabled=false});
 });
}
wire('pdf',async()=>{
 const bytes=await fixture('pdf');
 const result=await invoke<NativeResult>('save_report_as',{
  format:'pdf',filename:'PilotODIN_P2_Synthetic.pdf',bytes
 });
 status('pdf',result.status==='saved'&&result.filename==='PilotODIN_P2_Synthetic.pdf',
   'Native PDF Save As '+result.status+'; '+(result.filename??'no filename'));
});
wire('html',async()=>{
 const bytes=await fixture('html');
 const result=await invoke<NativeResult>('save_report_as',{
  format:'html',filename:'PilotODIN_P2_Synthetic.html',bytes
 });
 status('html',result.status==='saved'&&result.filename==='PilotODIN_P2_Synthetic.html',
   'Native HTML Save As '+result.status+'; '+(result.filename??'no filename'));
});
wire('cancel',async()=>{
 const bytes=await fixture('pdf');
 const result=await invoke<NativeResult>('save_report_as',{
  format:'pdf',filename:'PilotODIN_P2_Cancel.pdf',bytes
 });
 status('cancel',result.status==='cancelled',
   result.status==='cancelled'?'Cancellation confirmed by Rust command':'Expected Cancel, got '+result.status);
});
wire('badcontent',async()=>{
 let rejected=false;
 try{
  await invoke('save_report_as',{format:'pdf',filename:'P2_Invalid_Content.pdf',
    bytes:Array.from(new TextEncoder().encode('not a PDF document'))});
 }catch{rejected=true}
 status('badcontent',rejected,'Malformed payload rejected before Save As');
});
wire('badextension',async()=>{
 const bytes=await fixture('pdf');
 let rejected=false;
 try{await invoke('save_report_as',{format:'pdf',filename:'P2_Invalid_Extension.html',bytes})}
 catch{rejected=true}
 status('badextension',rejected,'Mismatched extension rejected before Save As');
});
log('Ready. Test-only native command surface; no real data, backend or model loads.');
