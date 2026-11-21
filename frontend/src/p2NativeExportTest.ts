import {invoke} from '@tauri-apps/api/core';
import {saveReportNative} from './api';
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
async function fixture(format:Format):Promise<Blob>{
 const path=format==='pdf'?'/p2-native-fixtures/report.pdf':'/p2-native-fixtures/report.html';
 const response=await fetch(path,{cache:'no-store'});
 if(!response.ok)throw new Error('Synthetic fixture unavailable: '+path+' HTTP '+response.status);
 const data=await response.blob();
 if(data.size<50)throw new Error('Synthetic fixture unexpectedly empty');
 return data;
}
function invalidSave(bytes:ArrayBuffer,filename:string){
 return invoke('save_report_as',bytes,{
  headers:{'x-pilotodin-report-format':'pdf','x-pilotodin-report-filename':encodeURIComponent(filename)},
 });
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
 const result=await saveReportNative(bytes,'PilotODIN_P2_Synthetic.pdf','pdf');
 status('pdf',result.status==='saved'&&result.filename==='PilotODIN_P2_Synthetic.pdf',
   'Native PDF Save As '+result.status+'; '+(result.filename??'no filename'));
});
wire('html',async()=>{
 const bytes=await fixture('html');
 const result=await saveReportNative(bytes,'PilotODIN_P2_Synthetic.html','html');
 status('html',result.status==='saved'&&result.filename==='PilotODIN_P2_Synthetic.html',
   'Native HTML Save As '+result.status+'; '+(result.filename??'no filename'));
});
wire('cancel',async()=>{
 const bytes=await fixture('pdf');
 const result=await saveReportNative(bytes,'PilotODIN_P2_Cancel.pdf','pdf');
 status('cancel',result.status==='cancelled',
   result.status==='cancelled'?'Cancellation confirmed by Rust command':'Expected Cancel, got '+result.status);
});
wire('badcontent',async()=>{
 let rejected=false;
 try{
  await invalidSave(new TextEncoder().encode('not a PDF document').buffer,'P2_Invalid_Content.pdf');
 }catch(error){
  rejected=String(error).includes('Report file content does not match its declared format');
 }
 status('badcontent',rejected,rejected?'Malformed payload correctly rejected by Rust':'Unexpected result or non-validation error');
});
wire('badextension',async()=>{
 const bytes=await fixture('pdf');
 let rejected=false;
 try{await invalidSave(await bytes.arrayBuffer(),'P2_Invalid_Extension.html')}
 catch(error){rejected=String(error).includes('Invalid report filename or extension')}
 status('badextension',rejected,rejected?'Mismatched extension rejected by Rust':'Unexpected result or non-validation error');
});
log('Ready. Test-only native command surface; no real data, backend or model loads.');
