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
