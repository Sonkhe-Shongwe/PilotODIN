import {BrainCircuit, ChevronRight, MessageSquareText, Sparkles, X} from 'lucide-react';
import type {ReactNode} from 'react';
export function StudioAssistant({open,onClose,onChat,scope,children}:{open:boolean;onClose:()=>void;onChat:()=>void;scope:string;children:ReactNode}){
 return <><div className={'studio-assistant-veil'+(open?' visible':'')} onClick={onClose} aria-hidden="true"/>
  <aside className={'studio-assistant-drawer'+(open?' visible':'')} aria-label="ODIN intelligence panel" aria-hidden={!open}>
   <header className="studio-drawer-header"><span className="studio-drawer-avatar"><BrainCircuit size={23}/></span><div><strong>ODIN intelligence</strong><small><span className="tiny-orb"/> Ready to investigate · {scope}</small></div><button className="studio-drawer-close" onClick={onClose} aria-label="Close ODIN panel"><X size={19}/></button></header>
   <div className="studio-drawer-content">{children}</div>
   <footer className="studio-drawer-footer"><button onClick={onChat}><MessageSquareText size={17}/> Continue in Ask ODIN <ChevronRight size={16}/></button><span><Sparkles size={13}/> Verified analysis · user-approved actions</span></footer>
  </aside></>;
}
