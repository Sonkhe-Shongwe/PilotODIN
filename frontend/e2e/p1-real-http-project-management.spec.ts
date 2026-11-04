import {expect,test} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const names={D:'pilotodin_p1_manage_D.csv',E:'pilotodin_p1_manage_E.csv'};
const csv=(prefix:'D'|'E')=>[
 'RecordID,Amount,Status',
 ...Array.from({length:20},(_,i)=>prefix+String(i+1).padStart(4,'0')+','+(i+1)*19+','+(i%2?'ready':'hold')),
].join('\n')+'\n';
type Permission={id:string;action:'rename'|'archive'|'restore';expected_revision:number;name?:string};
const equivalent=(a:unknown,b:Permission)=>{
 if(!a||typeof a!=='object'||Array.isArray(a))return false;
 const obj=a as Record<string,unknown>;
 return Object.keys(obj).sort().join('|')===Object.keys(b).sort().join('|')
  &&Object.keys(b).every(k=>obj[k]===b[k as keyof Permission]);
};
async function guardBrowser(context:BrowserContext,did:string,eid:string){
 let permit:Permission|null=null;
 const audit:{writes:Permission[];blocked:string[];unexpectedReads:string[];remote:string[]}
  ={writes:[],blocked:[],unexpectedReads:[],remote:[]};
 await context.route('**/*',async(route:Route)=>{
  const request=route.request(),url=new URL(request.url()),method=request.method();
  if(url.origin===UI){
   if(method==='GET'||method==='HEAD'){await route.continue();return}
   audit.blocked.push('UI '+method+' '+url.pathname);
   await route.fulfill({status:403,json:{detail:'Unapproved UI request'}});return;
  }
  if(url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'&&method==='GET'){
   await route.fulfill({status:200,contentType:'text/css',body:'/* fixture, no external network */'});return;
  }
  if(url.origin!==API||!url.pathname.startsWith('/api/')){
   audit.remote.push(method+' '+url.origin+url.pathname);
   await route.abort('blockedbyclient');return;
  }
  const path=url.pathname.slice(4);
  const read=path==='/projects'||path==='/projects/manage'||path==='/ai/settings'
   ||[did,eid].some(id=>new RegExp('^/projects/'+id+'(?:/(?:live-profile|quality|quality/history|quality/preview|preparation|features|target-opportunities))?$').test(path));
  if(method==='GET'&&read){await route.continue();return}
  if(method==='PUT'&&url.search===''&&permit&&path==='/projects/'+permit.id+'/lifecycle'){
   let parsed:unknown;
   try{parsed=JSON.parse(request.postData()??'null')}catch{parsed=null}
   const exactBody={
    action:permit.action,expected_revision:permit.expected_revision,
    ...(permit.name===undefined?{}:{name:permit.name}),
   };
   if(equivalent(parsed,exactBody)){
    audit.writes.push(permit);permit=null;
    await route.continue();return;
   }
  }
  if(method==='GET'){
   audit.unexpectedReads.push(path);
   await route.fulfill({status:404,json:{detail:'Unreviewed synthetic read'}});return;
  }
  audit.blocked.push(method+' '+path);
  await route.fulfill({status:403,json:{detail:'Unreviewed synthetic write'}});
 });
 return {
  audit,
  authorize:(grant:Permission)=>{
   if(permit)throw Error('Prior scoped capability was unused');
   if(grant.id!==did)throw Error('Only the inactive disposable D is mutable');
   permit=grant;
  },
  outstanding:()=>permit,
 };
}
let owned:DisposableBackend|null=null;
test.beforeEach(async()=>{owned=await startDisposableBackend()});
test.afterEach(async()=>{if(owned){const old=owned;owned=null;await stopDisposableBackend(old)}});

test('real HTTP reversible project management preserves originals and active Studio selection',async({page,context,request})=>{
 if(process.env.CI!=='true'||process.env.P1_REAL_HTTP_E2E!=='1')throw Error('Refuse non-CI lifecycle acceptance');
 const ids:Partial<Record<'D'|'E',string>>={};
 for(const prefix of ['D','E'] as const){
  const response=await request.post(API+'/api/projects',{multipart:{
   file:{name:names[prefix],mimeType:'text/csv',buffer:Buffer.from(csv(prefix))}
  }});
  expect(response.status()).toBe(201);
  ids[prefix]=(await response.json()).id as string;
  expect(ids[prefix]).toMatch(/^[a-f0-9]{32}$/);
 }
 const did=ids.D!,eid=ids.E!;
 const historyBefore=await (await request.get(API+'/api/projects/'+did+'/quality/history')).json();
 expect(historyBefore.current_version).toBe(0);
 const gate=await guardBrowser(context,did,eid);
 await page.addInitScript((id:string)=>{
  localStorage.setItem('pilotodin-current',id);
  localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview']));
  localStorage.setItem('pilotodin-workspace-active-v1-'+id,'overview');
 },eid);
 await page.goto('/#/studio/overview');
 const selector=page.getByRole('combobox',{name:'Switch project'});
 await expect(selector).toHaveValue(eid);
 const opener=page.getByRole('button',{name:'Manage projects'});
 await opener.click();
 const modal=page.getByRole('dialog',{name:'Manage projects'});
 await expect(modal).toBeVisible();
 await expect(modal.getByRole('button',{name:'Close project management'})).toBeFocused();
 await modal.getByRole('button',{name:'Close project management'}).press('Shift+Tab');
 await expect(modal.getByRole('button',{name:'Done'})).toBeFocused();
 await modal.press('Escape');
 await expect(modal).toHaveCount(0);
 await expect(opener).toBeFocused();
 await opener.click();
 await expect(modal.getByRole('button',{name:'Archive '+names.E.replace('.csv','')})).toBeDisabled();

 // Rename only D; active E remains mounted and selected throughout.
 const dName=names.D.replace('.csv','');
 const replacement='Synthetic D review';
 const dRow=modal.locator('.po-pm-item').filter({hasText:dName});
 await dRow.getByRole('button',{name:'Rename '+dName}).click();
 await modal.getByRole('textbox',{name:'Project name'}).fill(replacement);
 gate.authorize({id:did,action:'rename',expected_revision:0,name:replacement});
 const renameResponse=page.waitForResponse(r=>r.request().method()==='PUT'&&
   r.url()===API+'/api/projects/'+did+'/lifecycle');
 await modal.getByRole('button',{name:'Save'}).click();
 const renameReply=await renameResponse;
 expect(renameReply.status(),await renameReply.text()).toBe(200);
 await expect(modal.getByText('Project renamed.')).toBeVisible();
 await expect(modal.getByRole('button',{name:'Archive '+replacement})).toBeVisible();
 const dRenamed=await request.get(API+'/api/projects/'+did);
 expect(dRenamed.status()).toBe(200);
 expect((await dRenamed.json()).name).toBe(replacement);
 await expect(selector).toHaveValue(eid);

 // Archive D with the actual user confirmation, not a direct unreviewed PUT.
 page.on('dialog',async d=>{expect(d.message()).toContain('Archive');await d.accept()});
 gate.authorize({id:did,action:'archive',expected_revision:1});
 await modal.getByRole('button',{name:'Archive '+replacement}).click();
 const archived=modal.getByRole('region',{name:'Archived projects'});
 await expect(archived.getByRole('button',{name:'Restore '+replacement})).toBeVisible();
 await expect(selector.locator('option[value="'+did+'"]')).toHaveCount(0);
 expect((await request.get(API+'/api/projects/'+did)).status()).toBe(404);
 await expect(selector).toHaveValue(eid);

 // Restore the same immutable project identity, without reimporting.
 gate.authorize({id:did,action:'restore',expected_revision:2});
 await archived.getByRole('button',{name:'Restore '+replacement}).click();
 const active=modal.getByRole('region',{name:'Active projects'});
 await expect(active.getByRole('button',{name:'Archive '+replacement})).toBeVisible();
 await expect(selector.locator('option[value="'+did+'"]')).toHaveCount(1);
 expect((await request.get(API+'/api/projects/'+did)).status()).toBe(200);
 expect(await (await request.get(API+'/api/projects/'+did+'/quality/history')).json()).toEqual(historyBefore);
 await expect(selector).toHaveValue(eid);
 expect(gate.audit.writes.map(x=>x.action)).toEqual(['rename','archive','restore']);
 expect(gate.outstanding()).toBeNull();
 expect(gate.audit.blocked).toEqual([]);
 expect(gate.audit.unexpectedReads).toEqual([]);
 expect(gate.audit.remote).toEqual([]);

 await modal.getByRole('button',{name:'Done'}).click();
 // Restart only this disposable child: metadata remains after a new backend process.
 if(!owned)throw Error('No owned backend');
 const old=owned;await stopDisposableBackend(old);owned=null;
 owned=await startDisposableBackend();
 expect(owned.pid).not.toBe(old.pid);
 const after=await request.get(API+'/api/projects/manage');
 expect(after.status()).toBe(200);
 const row=(await after.json() as {id:string;name:string;revision:number;archived_at:string|null}[])
  .find(x=>x.id===did);
 expect(row).toMatchObject({id:did,name:replacement,revision:3,archived_at:null});
 expect(await (await request.get(API+'/api/projects/'+did+'/quality/history')).json()).toEqual(historyBefore);
});
