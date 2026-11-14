import React, {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {UnifiedShell} from './UnifiedShell';
import {isDesktop, startDesktopBackend} from './desktopBootstrap';
import './studio-fonts.css';
import './styles.css';
import './studio.css';
import './design-tokens.css';
import './finish-polish.css';

const root = createRoot(document.getElementById('root')!);

function showStarting(message: string, failed = false) {
  root.render(
    <div style={{minHeight:'100vh',display:'grid',placeItems:'center',padding:24,background:'#f7f9fd',color:'#202b40',fontFamily:'Inter,system-ui,sans-serif'}}>
      <section role="status" style={{maxWidth:540,width:'100%',padding:36,background:'white',border:'1px solid #e6e8f4',borderRadius:20,boxShadow:'0 12px 40px #1e28500c'}}>
        <div style={{fontSize:13,fontWeight:700,letterSpacing:2,color:'#7466ef',marginBottom:14}}>PILOTODIN STUDIO</div>
        <h1 style={{fontSize:26,margin:'0 0 10px'}}>{failed?'We could not start the engine':'Preparing your workspace'}</h1>
        <p style={{lineHeight:1.6,color:'#637089'}}>{message}</p>
        {failed && <button type="button" onClick={()=>void initialise()} style={{background:'#7466ef',color:'white',border:0,borderRadius:10,padding:'11px 20px',cursor:'pointer'}}>Try again</button>}
      </section>
    </div>);
}

async function initialise() {
  if (isDesktop()) {
    showStarting('Starting the secure, local data science engine. Your datasets remain on this computer.');
    try {await startDesktopBackend();}
    catch (error) {
      showStarting(error instanceof Error ? error.message : 'An unexpected error occurred starting the desktop engine.', true);
      return;
    }
  }
  root.render(<React.StrictMode><UnifiedShell/></React.StrictMode>);
}
void initialise();
