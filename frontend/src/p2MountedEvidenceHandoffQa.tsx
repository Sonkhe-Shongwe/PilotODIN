import {useCallback,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ReportWorkspace} from './ReportWorkspace';

/** CI-only source-true React mount; no stub API, user dataset or production route. */
if(import.meta.env.VITE_P2_MOUNTED_HANDOFF_QA!=='1'||!import.meta.env.DEV||
   location.hostname!=='127.0.0.1'||location.port!=='5178') {
 throw new Error('Mounted P2 handoff QA is restricted to the isolated CI Vite server.');
}
const params=new URLSearchParams(location.search);
const projectId=params.get('project')??'';
const first=params.get('first')??'';
const second=params.get('second')??'';
const unknown=params.get('unknown')??'';
if(![projectId,first,second,unknown].every(id=>/^[a-f0-9]{32}$/.test(id))||
   new Set([first,second,unknown]).size!==3){
 throw new Error('Invalid synthetic P2 mounted handoff fixture identifiers.');
}
const mount=document.getElementById('root');
if(!mount)throw new Error('Missing CI test mount point.');

function MountedHandoff(){
 const [incoming,setIncoming]=useState<string|null>(null);
 const [renderNumber,setRenderNumber]=useState(0);
 const [dirty,setDirty]=useState(false);
 const onUnsavedChange=useCallback((value:boolean)=>setDirty(value),[]);
 return <main>
  <section aria-label="Synthetic handoff controls">
   <button type="button" onClick={()=>setIncoming(first)}>Request synthetic A</button>
   <button type="button" onClick={()=>setIncoming(second)}>Request synthetic B</button>
   <button type="button" onClick={()=>setIncoming(unknown)}>Request nonexistent evidence</button>
   <button type="button" onClick={()=>setRenderNumber(n=>n+1)}>Rerender unchanged request</button>
   <output aria-label="Parent render count">{renderNumber}</output>
   <output aria-label="Deliver draft state">{dirty?'dirty':'clean'}</output>
  </section>
  <ReportWorkspace projectId={projectId} preselectEvidenceId={incoming}
   onUnsavedChange={onUnsavedChange}/>
 </main>;
}
createRoot(mount).render(<MountedHandoff/>);
