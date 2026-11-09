import {test,expect} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
const csv=[
 'row_id,churn,fraud_reported,outcome,failure_flag,future_cost,feature',
 ...Array.from({length:80},(_,i)=>[
  'P4-'+String(i).padStart(3,'0'),
  i%2?'Y':'N',
  i%3?'Y':'N',
  i%2?'done':'pending',
  i%4?'no':'yes',
  110+i, i%7,
 ].join(','))
].join('\n')+'\n';

let backend:DisposableBackend|null=null;
test.beforeEach(async()=>{backend=await startDisposableBackend()});
test.afterEach(async()=>{
 if(backend){const owned=backend;backend=null;await stopDisposableBackend(owned)}
});

async function readOnlyBrowserGuard(context:BrowserContext,projectId:string){
 const blocked:string[]=[];
 await context.route('**/*',async(route:Route)=>{
  const request=route.request(),url=new URL(request.url()),method=request.method();
  if(url.origin===UI&&(method==='GET'||method==='HEAD')){
   await route.continue();return;
  }
  if(url.origin==='https://fonts.googleapis.com'&&method==='GET'&&url.pathname==='/css2'){
   await route.fulfill({status:200,contentType:'text/css',body:'/* CI-only */'});
   return;
  }
  if(url.origin===API&&method==='GET'&&url.pathname.startsWith('/api/')){
   const p=url.pathname.slice('/api'.length);
   const expected=p===`/projects/${projectId}`||
    p.startsWith(`/projects/${projectId}/`)||p==='/projects'||p==='/ai/settings';
   if(expected){await route.continue();return}
  }
  blocked.push(method+' '+url.origin+url.pathname);
  await route.abort('blockedbyclient');
 });
 return blocked;
}

test('P4-05 real HTTP: review ordering, other targets and explicit selection only',
 async({page,context,request})=>{
  if(process.env.CI!=='true'||process.env.GITHUB_ACTIONS!=='true'||
     process.env.P1_REAL_HTTP_E2E!=='1'||!process.env.PILOTODIN_HOME)
   throw Error('Only trusted disposable GitHub browser tests may execute');

  // This pre-test fixture upload happens through Playwright's isolated API
  // client before the page's strict read-only request allowlist starts.
  const res=await request.post(API+'/api/projects',{multipart:{
   file:{name:'p4_05_disposable.csv',mimeType:'text/csv',buffer:Buffer.from(csv)},
  }});
  expect(res.status(),await res.text()).toBe(201);
  const projectId=(await res.json()).id as string;
  const status=await request.get(
   `${API}/api/projects/${projectId}/target-opportunities?expected_version=0`);
  expect(status.status(),await status.text()).toBe(200);
  const data=await status.json();
  expect(data.eligible_count).toBeGreaterThan(3);
  expect(data.ranking_contract.business_value_verified).toBe(false);
  expect(data.other_reviewable.length).toBeGreaterThan(0);

  const blocked=await readOnlyBrowserGuard(context,projectId);
  await page.addInitScript((id:string)=>{
   localStorage.setItem('pilotodin-current',id);
   localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['prepare']));
   localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },projectId);
  await page.goto('/#/studio/prepare');
  const section=page.getByRole('region',{name:'Potential prediction opportunities'});
  await expect(section).toBeVisible();
  await expect(section.getByText('Review order, not an estimated business-value ranking.',{
   exact:false,
  })).toBeVisible();
  await expect(section.getByText('Evidence needed before selecting this target')).toHaveCount(3);
  const other=section.locator('details[aria-label="Additional reviewable target alternatives"]');
  await expect(other.locator('summary')).toContainText('More structurally reviewable targets');
  await other.locator('summary').click();
  const alternative=other.getByRole('button',{name:'Review this alternative target'}).first();
  await expect(alternative).toBeVisible();
  await expect(alternative).toHaveAttribute('aria-pressed','false');
  await alternative.click(); // Only sets the local user's Prepare target draft.
  const pressed=other.locator('button[aria-pressed="true"]');
  await expect(pressed).toHaveCount(1);
  await expect(pressed).toHaveText('Chosen for preparation review');

  // No target automatically fit, no server-side train or mutation from this UI.
  expect(blocked).toEqual([]);
  const project=await request.get(`${API}/api/projects/${projectId}`);
  expect(project.status()).toBe(200);
  expect((await project.json()).experiments).toEqual([]);
 });
