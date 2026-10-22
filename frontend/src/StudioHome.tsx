import {useMemo} from 'react';
import {ArrowRight, BarChart3, BrainCircuit, CheckCircle2, CircleAlert, Database, FileSpreadsheet, FlaskConical, FolderOpen, Lightbulb, Plus, ShieldCheck, Sparkles, WandSparkles, Target, Activity, Clock3} from 'lucide-react';
import type {Project} from './api';

type Destination='overview'|'understand'|'quality'|'explore'|'prepare'|'model'|'evaluate'|'predict'|'assistant'|'ai_settings';
type Props={project:Project;projects:{id:string;name:string;filename:string}[];onGo:(dest:Destination)=>void;onNew:()=>void;onOpenProject:(id:string)=>void;onResume:(id:string)=>Promise<void>;onAI:()=>void};
const shortcuts=[
  {id:'explore' as Destination,label:'Explore your data',detail:'Find patterns and shape compelling charts',icon:BarChart3,tone:'purple'},
  {id:'quality' as Destination,label:'Clean and improve',detail:'Review issues and approve smart corrections',icon:ShieldCheck,tone:'mint'},
  {id:'prepare' as Destination,label:'Build a prediction',detail:'Prepare, train and compare reliable models',icon:FlaskConical,tone:'blue'},
];
export function StudioHome({project,projects,onGo,onNew,onOpenProject,onResume,onAI}:Props){
 const profile=project.profile;
 const latest=project.experiments[0];
 const issues=useMemo(()=>[
  ...(profile.missing_cells>0?[{label:`${profile.missing_cells.toLocaleString()} missing values`,detail:'Review their potential effect before analysis',icon:CircleAlert}]:[]),
  ...profile.warnings.slice(0,2).map((w)=>({label:w.split(':')[0]||'Review dataset warning',detail:w,icon:Lightbulb})),
  ...(profile.target_candidates.length?[{label:'Prediction opportunity',detail:`Consider ${profile.target_candidates.slice(0,2).join(' or ')} as a possible target`,icon:Target}]:[]),
 ],[profile]);
 return <div className="studio-home">
  <section className="studio-welcome">
    <div className="welcome-left"><div className="welcome-kicker"><span className="tiny-orb"/> YOUR INTELLIGENCE WORKSPACE <span className="welcome-spark">✦</span></div><h1>Your next great insight<br/><span>starts right here.</span></h1><p>Explore, understand and shape your data with an intelligent companion by your side.</p><div className="welcome-actions"><button className="studio-primary" onClick={onNew}><Plus size={17}/> New analysis <ArrowRight size={17}/></button><button className="studio-outline" onClick={()=>onGo('explore')}><BarChart3 size={17}/> Explore current data</button></div></div>
    <div className="welcome-art" aria-hidden="true"><div className="welcome-bloom bloom-a"/><div className="welcome-bloom bloom-b"/><div className="welcome-bloom bloom-c"/><div className="welcome-bloom bloom-d"/><div className="welcome-orbit orbit-one"/><div className="welcome-orbit orbit-two"/><div className="welcome-art-mark"><BrainCircuit size={29}/><span>ODIN<span className="ready-dot"/></span><small>Intelligence, ready when you are</small></div></div>
  </section>
  <div className="studio-section-title"><div><span className="studio-mini-label">YOUR WORKSPACE</span><h2>Pick up where you left off</h2></div><button className="studio-link" onClick={onNew}>New dataset <ArrowRight size={16}/></button></div>
  <div className="studio-home-grid">
   <div className="studio-home-primary">
    <section className="studio-feature-project"><div className="project-card-head"><span className="studio-project-icon"><FileSpreadsheet size={22}/></span><span className="studio-live"><span/> ACTIVE PROJECT</span></div><h3>{project.name.replaceAll('_',' ')}</h3><p>{profile.rows.toLocaleString()} records · {profile.columns_count} fields · {project.filename}</p><div className="studio-data-readiness"><span><ShieldCheck size={16}/> Data completeness</span><b>{(100-(profile.missing_cells/Math.max(1,profile.rows*profile.columns_count))*100).toFixed(1)}%</b><div className="readiness-track"><div style={{width:`${Math.max(0,100-(profile.missing_cells/Math.max(1,profile.rows*profile.columns_count))*100)}%`}}/></div><small>Calculated from populated cells. Not a guarantee of data quality.</small></div><div className="project-card-bottom"><span><CheckCircle2 size={15}/> Ready to explore</span><button onClick={()=>onGo('explore')}>Open project <ArrowRight size={16}/></button></div></section>
    <div className="studio-stat-strip">
      <div><Database size={18}/><strong>{profile.rows.toLocaleString()}</strong><span>Records</span></div>
      <div><Activity size={18}/><strong>{profile.columns_count}</strong><span>Columns</span></div>
      <div><CircleAlert size={18}/><strong>{profile.missing_cells.toLocaleString()}</strong><span>Missing cells</span></div>
      <div><FlaskConical size={18}/><strong>{project.experiments.length}</strong><span>Experiments</span></div>
    </div>
    <section className="studio-surface studio-quick-section"><div className="studio-card-title"><h3>What would you like to do?</h3><span className="studio-soft-sub">Choose a starting point</span></div><div className="studio-quick-grid">{shortcuts.map(shortcut=>{const Icon=shortcut.icon;return <button key={shortcut.id} className={'studio-quick quick-'+shortcut.tone} onClick={()=>onGo(shortcut.id)}><span className="studio-quick-icon"><Icon size={23}/></span><b>{shortcut.label}</b><small>{shortcut.detail}</small><ArrowRight size={16} className="quick-arrow"/></button>})}</div></section>
   </div>
   <div className="studio-home-aside">
     <section className="studio-surface studio-assistant-card"><div className="studio-card-title"><span className="studio-odin-glyph"><BrainCircuit size={20}/></span><span className="assistant-heading"><b>ODIN is by your side</b><small>Context-aware intelligence</small></span><span className="studio-ready-pip"/></div><p>I've got your current dataset in view. Want to explore what's worth looking at first?</p><button className="studio-ask-action" onClick={onAI}>Investigate with ODIN <Sparkles size={16}/></button><button className="studio-secondary-link" onClick={()=>onGo('assistant')}>Open full conversation <ArrowRight size={15}/></button></section>
     <section className="studio-surface studio-findings-card"><div className="studio-card-title"><h3>Worth a closer look</h3><span className="studio-count-chip">{issues.length}</span></div>{issues.length?issues.slice(0,3).map((item,i)=>{const Icon=item.icon;return <button className="studio-finding" key={i} onClick={()=>onGo(i===0&&profile.missing_cells?'quality':'understand')}><span className={'finding-marker finding-'+i}><Icon size={16}/></span><span><b>{item.label}</b><small>{item.detail}</small></span><ArrowRight size={15}/></button>}):<div className="studio-no-issues"><CheckCircle2 size={19}/> No immediate structural flags. Explore patterns to learn more.</div>}<button className="studio-secondary-link" onClick={()=>onGo('quality')}>See data quality <ArrowRight size={15}/></button></section>
     <section className="studio-surface studio-history"><div className="studio-card-title"><h3>Recent work</h3><Clock3 size={17}/></div>{latest?<button className="studio-recent" onClick={()=>void onResume(latest.id)}><span><FlaskConical size={17}/></span><div><b>Model experiment</b><small>{latest.status} · {new Date(latest.created_at).toLocaleDateString()}</small></div><ArrowRight size={17}/></button>:<p className="studio-empty-history">Your experiments will appear here once you've trained a model.</p>}{projects.filter(p=>p.id!==project.id).slice(0,2).map(p=><button className="studio-recent" key={p.id} onClick={()=>onOpenProject(p.id)}><span><FolderOpen size={17}/></span><div><b>{p.name.replaceAll('_',' ')}</b><small>{p.filename}</small></div><ArrowRight size={17}/></button>)}</section>
   </div>
  </div>
 </div>;
}
