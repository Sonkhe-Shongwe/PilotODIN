// Renderer-local, nonpersistent settings-operation fence. It is not backend
// consent authority. All external dispatch still requires the saved server state.
type Snapshot=Readonly<{generation:number;pending:boolean}>;
type Ticket=Readonly<{generation:number}>;
let snapshot:Snapshot=Object.freeze({generation:0,pending:false});
let owner:Ticket|null=null;
const listeners=new Set<()=>void>();

export function cloudConsentSnapshot():Snapshot{return snapshot}
export function subscribeCloudConsent(listener:()=>void){
  listeners.add(listener);
  return ()=>{listeners.delete(listener)}
}
function advance(pending:boolean){
  snapshot=Object.freeze({generation:snapshot.generation+1,pending});
  for(const listener of [...listeners])listener();
}
export function beginCloudSettingsOperation(expectedGeneration:number):Ticket|null{
  if(owner||snapshot.pending||snapshot.generation!==expectedGeneration)return null;
  const ticket=Object.freeze({generation:snapshot.generation+1});
  owner=ticket;
  advance(true);
  return ticket;
}
export function finishCloudSettingsOperation(ticket:Ticket):Snapshot|null{
  if(owner!==ticket)return null;
  owner=null;
  advance(false);
  return snapshot;
}
export function cloudConsentIsCurrent(generation:number):boolean{
  return !snapshot.pending&&snapshot.generation===generation;
}

export type SavedCloudPermission={
  cloud_enabled?:unknown;share_aggregates?:unknown;intelligence_mode?:unknown;
  credential_warning?:unknown;settings_warning?:unknown;
  providers?:readonly {id?:unknown;connected?:unknown;verified?:unknown}[];
};
function permissionEnabled(saved:SavedCloudPermission|null|undefined){
  return saved?.cloud_enabled===true&&saved.share_aggregates===true&&
    (saved.intelligence_mode==='hybrid'||saved.intelligence_mode==='cloud')&&
    !saved.credential_warning&&!saved.settings_warning;
}
export function canTestCloud(saved:SavedCloudPermission|null|undefined,provider:string):boolean{
  return Boolean(permissionEnabled(saved)&&['gemini','groq','openrouter'].includes(provider)&&
    Array.isArray(saved?.providers)&&saved.providers.some(p=>p.id===provider&&p.connected===true));
}
export function savedCloudStatus(saved:SavedCloudPermission):'local'|'unverified'|'connected'{
  if(!permissionEnabled(saved))return 'local';
  return Array.isArray(saved.providers)&&saved.providers.some(p=>
    typeof p.id==='string'&&canTestCloud(saved,p.id)&&p.verified===true)?'connected':'unverified';
}


// Saved cloud preferences are not user intent. Preserve only local routes.
export type LocalPanelProvider='auto'|'local'|'ollama';
export function isLocalPanelProvider(value:unknown):value is LocalPanelProvider{
  return value==='auto'||value==='local'||value==='ollama';
}
export function localPanelProvider(value:unknown):LocalPanelProvider{
  return isLocalPanelProvider(value)?value:'auto';
}
export function projectCloudProviderName(value:unknown):string|null{
  switch(value){
    case 'gemini':return 'Google Gemini';
    case 'groq':return 'GroqCloud';
    case 'openrouter':return 'OpenRouter';
    default:return null;
  }
}
// Intermediate C4 batch: the project-data path remains closed pending
// server-generation binding and cross-renderer result invalidation.
export function projectCloudHold(value:unknown):string{
  return value==='openrouter'?'OpenRouter project-data sharing is disabled because downstream destinations are not established.':
    'Project-data cloud requests are not available until consent and response safeguards are verified.';
}
export const projectCloudDisclosure='A cloud request may include bounded column names, row counts, supported aggregate statistics, quality issue categories, aggregate model metrics and your question. Summaries are not guaranteed anonymous. Do not include private information in the question. Uploaded rows, local paths, individual prediction inputs and previous answers are excluded. Only the selected provider is intended; no automatic fallback to another provider. Already sent data cannot be recalled.';
export function localPanelRequest(value:unknown):{selected_provider:LocalPanelProvider;cloud_intent:false}|null{
  return isLocalPanelProvider(value)?{selected_provider:value,cloud_intent:false}:null;
}
export function localPanelMayContinue(source:unknown):boolean{return source==='local_llm'}
