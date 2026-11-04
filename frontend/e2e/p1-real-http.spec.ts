import {expect,test} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {Buffer} from 'node:buffer';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

const UI='http://127.0.0.1:5178';
const API='http://127.0.0.1:8000';
const A_FILENAME='pilotodin_p1_http_A.csv';
const B_FILENAME='pilotodin_p1_http_B.csv';
const csv=(prefix:string)=>[
  'OrderID,Outcome,Amount',
  ...Array.from({length:18},(_,i)=>
    `${prefix}${String(i+1).padStart(4,'0')},${i%3===0?'Pending':'Approved'},${(i+1)*13}`),
].join('\n')+'\n';

type Audit={imports:number;blockedWrites:string[];unexpectedReads:string[];blockedOrigins:string[];backendReads:string[]};

// The browser can send exact synthetic data to a real local backend, but no
// other API mutation, cloud request or unknown GET may leave this context.
async function allowOnlyDisposableHTTP(context:BrowserContext,expectedB:string):Promise<Audit>{
  const audit:Audit={imports:0,blockedWrites:[],unexpectedReads:[],blockedOrigins:[],backendReads:[]};
  await context.route('**/*',async(route:Route)=>{
    const req=route.request(),url=new URL(req.url()),method=req.method();
    if(url.origin===UI){
      if(method==='GET'||method==='HEAD'){await route.continue();return;}
      audit.blockedWrites.push(method+' '+url.pathname+' [UI]');
      await route.fulfill({status:403,json:{detail:'Unapproved frontend write'}});return;
    }
    const families=url.searchParams.getAll('family');
    if(method==='GET'&&url.origin==='https://fonts.googleapis.com'
      &&url.pathname==='/css2'&&families.length===2
      &&families[0]==='Inter:wght@400;450;500;550;600;650;700;750;800'
      &&families[1]==='Manrope:wght@500;600;650;700;750;800'
      &&url.searchParams.get('display')==='swap'
      &&[...url.searchParams.keys()].length===3){
      await route.fulfill({status:200,contentType:'text/css',
        body:'/* CI: local system fonts only; no external network */'});return;
    }
    if(url.origin!==API||!url.pathname.startsWith('/api/')){
      audit.blockedOrigins.push(method+' '+url.origin+url.pathname);
      await route.abort('blockedbyclient');return;
    }
    const p=url.pathname.slice(4);
    const allowedRead=p==='/projects'||p==='/ai/settings'
      ||/^\/projects\/[a-f0-9]{32}(?:\/(?:live-profile|quality|quality\/history|quality\/preview|preparation|features|target-opportunities))?$/.test(p);
    if(method==='GET'&&allowedRead){
      audit.backendReads.push(p);
      await route.continue();return;
    }
    // Accept a single exact browser multipart upload of fixture B only.
    if(method==='POST'&&p==='/projects'&&url.search===''&&audit.imports===0){
      const ct=req.headers()['content-type']??'';
      const boundary=ct.match(/^multipart\/form-data; boundary=([A-Za-z0-9_-]{8,100})$/)?.[1];
      const expected=boundary?
        '--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="'+B_FILENAME+
        '"\r\nContent-Type: text/csv\r\n\r\n'+expectedB+'\r\n--'+boundary+'--\r\n':'';
      if(expected&&req.postData()===expected){
        audit.imports++;
        await route.continue();return;
      }
    }
    if(method==='GET'){
      audit.unexpectedReads.push(p);
      await route.fulfill({status:404,json:{detail:'Blocked unreviewed read'}});return;
    }
    audit.blockedWrites.push(method+' '+p);
    await route.fulfill({status:403,json:{detail:'Blocked unreviewed write'}});return;
  });
  return audit;
}

function fixtureGuard(action:'hide'|'restore'|'audit',id:string):string{
  const output=execFileSync('python', ['../tools/p1_real_http_fixture_guard.py',
    action,'--project-id',id],{encoding:'utf8',timeout:10_000});
  return output.trim();
}

let ownedBackend:DisposableBackend|null=null;
test.beforeEach(async()=>{
  ownedBackend=await startDisposableBackend();
});
test.afterEach(async()=>{
  if(ownedBackend){
    const old=ownedBackend;
    ownedBackend=null;
    await stopDisposableBackend(old);
  }
});

test('real HTTP import, Quality, rejected switch and restored source retain primary Prepare draft',async({page,context,request})=>{
  if(process.env.P1_REAL_HTTP_E2E!=='1'||process.env.CI!=='true')
    throw new Error('Refuse non-isolated real HTTP run');
  const sourceA=csv('A'),sourceB=csv('B');
  const initial=await request.get(API+'/api/projects');
  expect(initial.status()).toBe(200);
  expect(await initial.json()).toEqual([]);
  // Exact synthetic seed A through actual Uvicorn HTTP, not a browser mock.
  const seed=await request.post(API+'/api/projects',{
    multipart:{file:{name:A_FILENAME,mimeType:'text/csv',buffer:Buffer.from(sourceA)}},
  });
  expect(seed.status()).toBe(201);
  const aid=(await seed.json()).id as string;
  expect(aid).toMatch(/^[a-f0-9]{32}$/);
  const audit=await allowOnlyDisposableHTTP(context,sourceB);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','quality']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'overview');
  },aid);
  await page.goto('/#/studio/overview');
  const switcher=page.getByRole('combobox',{name:'Switch project'});
  await expect(switcher).toHaveValue(aid);
  await page.getByRole('button',{name:'New project: import dataset'}).click();
  await page.locator('.po-primary-pane input[type="file"]').setInputFiles({
    name:B_FILENAME,mimeType:'text/csv',buffer:Buffer.from(sourceB),
  });
  await page.getByRole('button',{name:'Analyse dataset'}).click();
  const catalogue=await request.get(API+'/api/projects');
  expect(catalogue.status()).toBe(200);
  const entries=await catalogue.json() as {id:string;filename:string}[];
  expect(entries).toHaveLength(2);
  const bid=entries.find(x=>x.filename===B_FILENAME)?.id;
  expect(bid).toMatch(/^[a-f0-9]{32}$/);
  await expect(switcher).toHaveValue(bid!);
  const primary=page.locator('.po-primary-pane');
  const nav=page.getByRole('navigation',{name:'Workspace navigation'});
  await nav.getByRole('button',{name:'Quality'}).click();
  await expect(primary.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
  await expect(primary.getByText('WORKING VERSION 0')).toBeVisible();
  await nav.getByRole('button',{name:'Prepare'}).click();
  const target=primary.getByRole('combobox',{name:/target variable/i});
  await expect(target).toBeVisible();
  await target.selectOption('Outcome');
  await expect(target).toHaveValue('Outcome');
  const before=fixtureGuard('audit',aid);
  expect(JSON.parse(before).original_sha256_matches).toBe(true);

  const failedStatuses:number[]=[];
  page.on('response',response=>{
    if(response.url()===API+'/api/projects/'+aid+'/live-profile')
      failedStatuses.push(response.status());
  });
  const approvals:string[]=[];
  page.on('dialog',async dialog=>{
    approvals.push(dialog.message());
    await dialog.accept();
  });
  let hidden=false;
  try{
    expect(fixtureGuard('hide',aid)).toBe('P1_SYNTHETIC_SOURCE_HIDDEN');
    hidden=true;
    // Both calls are REAL backend HTTP. B remains mounted after A profile 409.
    await switcher.selectOption(aid);
    await expect(page.getByText(/selected project could not be opened|Could not open project/i).first()).toBeVisible();
    await expect(switcher).toHaveValue(bid!);
    await expect(target).toHaveValue('Outcome');
    expect(failedStatuses).toContain(409);
    expect(approvals).toHaveLength(1);
    expect(approvals[0]).toMatch(/primary workspace.*discard/i);
    await nav.getByRole('button',{name:'Quality'}).click();
    await expect(primary.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
    await expect(primary.getByText('WORKING VERSION 0')).toBeVisible();
    const bLive=await request.get(API+'/api/projects/'+bid+'/live-profile');
    expect(bLive.status()).toBe(200);
    expect((await bLive.json()).version).toBe(0);
  }finally{
    if(hidden)expect(fixtureGuard('restore',aid)).toBe('P1_SYNTHETIC_SOURCE_RESTORED');
  }
  expect(fixtureGuard('audit',aid)).toBe(before);
  const aRecovered=await request.get(API+'/api/projects/'+aid+'/live-profile');
  expect(aRecovered.status()).toBe(200);
  expect((await aRecovered.json()).version).toBe(0);
  expect(audit.imports).toBe(1);
  expect(audit.blockedWrites).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
  expect(audit.backendReads).toContain('/projects/'+aid+'/live-profile');

  await test.step('a second real browser tab commits A; B draft survives the cross-tab A profile failure',async()=>{
    // After the same-tab failure above, B remains the selected, usable project.
    // Explicitly edit another Prepare value to ensure a dirty primary form.
    await nav.getByRole('button',{name:'Prepare'}).click();
    await expect(target).toHaveValue('Outcome');
    await target.selectOption('Amount');
    await expect(target).toHaveValue('Amount');
    await expect(switcher).toHaveValue(bid!);

    // Both pages are in the SAME browser context. The other tab uses the real
    // project selector; it does not directly spoof a storage event or API body.
    const other=await context.newPage();
    await other.goto('/#/studio/prepare');
    const otherSwitcher=other.getByRole('combobox',{name:'Switch project'});
    await expect(otherSwitcher).toHaveValue(bid!);
    await expect(other.locator('.po-primary-pane')
      .getByRole('combobox',{name:/target variable/i})).toBeVisible();

    // The other tab can read A successfully first. Only when this edited B
    // tab attempts to read A do we hide the test-owned original source.
    // All ensuing status codes are from the REAL Uvicorn backend.
    let hiddenCrossTab=false;
    let crossTabProfileReads=0;
    await page.route('**/api/projects/'+aid+'/live-profile',async route=>{
      expect(route.request().method()).toBe('GET');
      crossTabProfileReads++;
      if(!hiddenCrossTab){
        expect(fixtureGuard('hide',aid)).toBe('P1_SYNTHETIC_SOURCE_HIDDEN');
        hiddenCrossTab=true;
      }
      await route.continue();
    });
    const attemptedRead=page.waitForResponse(response=>
      response.url()===API+'/api/projects/'+aid+'/live-profile'
        &&response.status()===409);
    const originalPromptCount=approvals.length;
    try{
      await otherSwitcher.selectOption(aid);
      await expect(otherSwitcher).toHaveValue(aid);
      await attemptedRead;
      await expect(page.getByText(/The other tab selected a project that could not be opened here/))
        .toBeVisible();
      await expect(switcher).toHaveValue(bid!);
      await expect(target).toHaveValue('Amount');
      await expect(page).toHaveURL(UI+'/#/studio/prepare');
      expect(crossTabProfileReads).toBe(1);
      expect(approvals.length).toBe(originalPromptCount+1);
      expect(approvals.at(-1)).toMatch(/primary workspace.*discard/i);
      // The other tab owns shared selection A, but it must not steal B's
      // mounted unsaved form when A is temporarily unreadable in this tab.
      expect(await other.evaluate(()=>localStorage.getItem('pilotodin-current'))).toBe(aid);
      expect(await page.evaluate(()=>localStorage.getItem('pilotodin-current'))).toBe(aid);
      await nav.getByRole('button',{name:'Quality'}).click();
      await expect(primary.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
      await expect(primary.getByText('WORKING VERSION 0')).toBeVisible();
    }finally{
      if(hiddenCrossTab)
        expect(fixtureGuard('restore',aid)).toBe('P1_SYNTHETIC_SOURCE_RESTORED');
    }
    expect(fixtureGuard('audit',aid)).toBe(before);
    const afterRecovery=await request.get(API+'/api/projects/'+aid+'/live-profile');
    expect(afterRecovery.status()).toBe(200);
    expect((await afterRecovery.json()).version).toBe(0);
    expect(audit.imports).toBe(1);
    expect(audit.blockedWrites).toEqual([]);
    expect(audit.unexpectedReads).toEqual([]);
    expect(audit.blockedOrigins).toEqual([]);
  });

  await test.step('stop and restart the owned Uvicorn process without losing B Quality or the edited Prepare target',async()=>{
    if(!ownedBackend)throw new Error('Missing owned disposable backend');
    // B remains mounted in this tab. The other tab's A selection is shared
    // storage, but it never became a successful B-to-A load in this tab.
    await nav.getByRole('button',{name:'Prepare'}).click();
    await expect(switcher).toHaveValue(bid!);
    await expect(target).toHaveValue('Amount');
    await target.selectOption('Outcome');
    await expect(target).toHaveValue('Outcome');
    const historyBefore=await request.get(API+'/api/projects/'+bid+'/quality/history');
    expect(historyBefore.status()).toBe(200);
    const originalBHistory=await historyBefore.json();
    expect(originalBHistory.current_version).toBe(0);
    expect(originalBHistory.actions).toEqual([]);
    expect(originalBHistory.decisions).toEqual([]);
    const pidBefore=ownedBackend.pid;
    const oldProcess=ownedBackend;
    await stopDisposableBackend(oldProcess);
    ownedBackend=null; // afterEach must never kill the already stopped process.

    // The actual backend is offline; no mock response may mask this outage.
    // The mounted primary project and edited values must remain on screen.
    await expect(switcher).toHaveValue(bid!);
    await expect(target).toHaveValue('Outcome');
    await nav.getByRole('button',{name:'Quality'}).click();
    await expect(primary.locator('.quality-page .alert-error').first())
      .toContainText('Could not connect to PilotODIN');
    await expect(switcher).toHaveValue(bid!);
    await nav.getByRole('button',{name:'Prepare'}).click();
    await expect(target).toHaveValue('Outcome');
    // Keep the failed Quality component mounted during the backend restart.
    await nav.getByRole('button',{name:'Quality'}).click();
    const qualityRetry=primary.getByRole('button',{name:'Retry loading Quality'});
    await expect(primary.locator('.quality-page .alert-error').first())
      .toContainText('Could not connect to PilotODIN');
    await expect(qualityRetry).toBeVisible();

    ownedBackend=await startDisposableBackend();
    expect(ownedBackend.pid).not.toBe(pidBefore);
    const health=await request.get(API+'/api/health');
    expect(health.status()).toBe(200);
    expect((await health.json()).status).toBe('ok');
    const aProfile=await request.get(API+'/api/projects/'+aid+'/live-profile');
    const bProfile=await request.get(API+'/api/projects/'+bid+'/live-profile');
    expect(aProfile.status()).toBe(200);
    expect(bProfile.status()).toBe(200);
    expect((await aProfile.json()).version).toBe(0);
    expect((await bProfile.json()).version).toBe(0);
    const bHistoryAfter=await request.get(API+'/api/projects/'+bid+'/quality/history');
    expect(bHistoryAfter.status()).toBe(200);
    expect(await bHistoryAfter.json()).toEqual(originalBHistory);
    expect(fixtureGuard('audit',aid)).toBe(before);
    // Retry on the SAME mounted Quality component; no route remount or POST.
    await expect(qualityRetry).toBeVisible();
    await qualityRetry.click();
    await expect(primary.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
    await expect(primary.getByText('WORKING VERSION 0')).toBeVisible();
    await expect(primary.locator('.quality-page .alert-error')).toHaveCount(0);
    await nav.getByRole('button',{name:'Prepare'}).click();
    await expect(target).toHaveValue('Outcome');
    await expect(switcher).toHaveValue(bid!);
    expect(audit.imports).toBe(1);
    expect(audit.blockedWrites).toEqual([]);
    expect(audit.unexpectedReads).toEqual([]);
    expect(audit.blockedOrigins).toEqual([]);
  });
});
