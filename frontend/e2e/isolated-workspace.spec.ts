import {expect,test} from '@playwright/test';
import type {BrowserContext,Route} from '@playwright/test';

const UI_ORIGIN='http://127.0.0.1:5187';
const API_ORIGIN='http://127.0.0.1:8000';
const TEST_PROJECT='playwright-synthetic-project';
const TEST_PROJECT_B='playwright-synthetic-second-project';

// All data in this test are invented. No CSV file or real PilotODIN project
// is read. The browser is given an empty, temporary storage context.
const profile={
  filename:'synthetic_browser_fixture.csv',
  rows:2,
  columns_count:2,
  missing_cells:0,
  duplicate_rows:0,
  columns:[
    {name:'fraud_reported',kind:'categorical',missing:0,missing_pct:0,unique:2,
     identifier_risk:false,leakage_risk:false,sample_values:['N','Y']},
    {name:'amount',kind:'numeric',missing:0,missing_pct:0,unique:2,
     identifier_risk:false,leakage_risk:false,sample_values:[10,20]},
  ],
  preview:[{fraud_reported:'N',amount:10},{fraud_reported:'Y',amount:20}],
  target_candidates:['fraud_reported'],
  warnings:[],
  summary:'Synthetic browser regression fixture. No real dataset was loaded.',
  summary_source:'test fixture',
  guidance:[],
};
const syntheticProject={
  id:TEST_PROJECT,
  name:'synthetic_browser_fixture',
  filename:profile.filename,
  profile,
  experiments:[],
};
const secondProfile={...profile,filename:'synthetic_second_fixture.csv'};
const syntheticSecondProject={
  id:TEST_PROJECT_B,
  name:'synthetic_second_fixture',
  filename:secondProfile.filename,
  profile:secondProfile,
  experiments:[],
};

type NetworkAudit={writes:string[]; unexpectedReads:string[]; blockedOrigins:string[]; stubbedFontStylesheets:string[]; readOnlyCalculations:string[]};

/** Fail closed: only the dedicated Vite origin is allowed onto the network.
 * Every API response comes from this handler, never the actual :8000 backend.
 * Unrecognised requests return a synthetic 404 and are recorded.
 */
async function installIsolatedAPI(context:BrowserContext,withProject:boolean,withSecondProject=false):Promise<NetworkAudit>{
  const audit:NetworkAudit={writes:[],unexpectedReads:[],blockedOrigins:[],stubbedFontStylesheets:[],readOnlyCalculations:[]};
  await context.route('**/*',async(route:Route)=>{
    const req=route.request();
    const url=new URL(req.url());
    if(url.origin===UI_ORIGIN){
      // Vite only serves assets: refuse and audit accidental UI-origin writes.
      if(req.method()!=='GET'&&req.method()!=='HEAD'){
        audit.writes.push(req.method()+' '+url.pathname+' [frontend-origin]');
        await route.fulfill({status:403,json:{detail:'E2E fixture blocks frontend-origin writes'}});
        return;
      }
      await route.continue();
      return;
    }
    // The production stylesheet currently imports Inter/Manrope from Google.
    // Offline E2E never contacts that host: serve an empty, test-owned CSS
    // response only for the exact known font request. Browser falls back to
    // installed system fonts; other external requests remain blocked/audited.
    const families=url.searchParams.getAll('family');
    if(req.method()==='GET'
      &&url.origin==='https://fonts.googleapis.com'
      &&url.pathname==='/css2'
      &&families.length===2
      &&families[0]==='Inter:wght@400;450;500;550;600;650;700;750;800'
      &&families[1]==='Manrope:wght@500;600;650;700;750;800'
      &&url.searchParams.get('display')==='swap'
      &&[...url.searchParams.keys()].length===3){
      audit.stubbedFontStylesheets.push('GET '+url.origin+url.pathname);
      await route.fulfill({status:200,contentType:'text/css; charset=utf-8',
        body:'/* Isolated PilotODIN E2E: use system font fallback; no external request. */'});
      return;
    }
    if(url.origin!==API_ORIGIN||!url.pathname.startsWith('/api/')){
      // Block AND record unexpected origins/paths, including cloud requests.
      audit.blockedOrigins.push(req.method()+' '+url.origin+url.pathname);
      await route.abort('blockedbyclient');
      return;
    }
    const pathname=url.pathname.slice('/api'.length);
    // A cross-origin JSON POST can cause a browser CORS preflight.
    // Approve ONLY the synthetic read-only workbench's content-type preflight.
    // Never forward OPTIONS (or the subsequent POST) to a real backend.
    if(req.method()==='OPTIONS'&&withProject
      &&pathname===`/projects/${TEST_PROJECT}/explore/workbench`
      &&url.search===''){
      const headers=req.headers();
      const asked=(headers['access-control-request-headers']??'').toLowerCase()
        .split(',').map(value=>value.trim()).filter(Boolean);
      if(headers.origin===UI_ORIGIN
        &&headers['access-control-request-method']==='POST'
        &&asked.length===1&&asked[0]==='content-type'){
        await route.fulfill({status:204,headers:{
          'access-control-allow-origin':UI_ORIGIN,
          'access-control-allow-methods':'POST',
          'access-control-allow-headers':'content-type',
        }});
        return;
      }
    }
    // Explore's workbench is a POST transport for read-only calculations.
    // Whitelist one exact, synthetic, schema-validated request only. Nothing
    // reaches the backend: even permitted calculations are locally fulfilled.
    if(req.method()==='POST'&&withProject
      &&pathname===`/projects/${TEST_PROJECT}/explore/workbench`
      &&url.search===''){
      let input:unknown=null;
      try{input=req.postDataJSON()}catch{/* reject malformed JSON below */}
      const body=input&&typeof input==='object'&&!Array.isArray(input)
        ?input as Record<string,unknown>:null;
      const keys=['expected_version','filters','x','y','kind',
        'aggregation','bins','correlation_method','color_by'];
      const valid=!!body&&Object.keys(body).length===keys.length
        &&keys.every(key=>Object.hasOwn(body,key))
        &&body.expected_version===0
        &&Array.isArray(body.filters)&&body.filters.length===0
        &&(body.x==='fraud_reported'||body.x==='amount')
        &&(body.y===null||body.y==='amount')
        &&body.kind==='auto'&&body.aggregation==='mean'
        &&body.bins===16&&body.correlation_method==='pearson'
        &&body.color_by===null;
      if(valid){
        audit.readOnlyCalculations.push('POST '+pathname);
        await route.fulfill({status:200,headers:{'access-control-allow-origin':UI_ORIGIN},
          json:{version:0,total_rows:2,filtered_rows:2,filter_count:0,
            overview:{version:0,rows:2,missing_cells:0,exact_duplicates:0,
              columns:[{name:'fraud_reported',kind:'categorical',unique:2,missing:0,missing_pct:0},
                {name:'amount',kind:'numeric',unique:2,missing:0,missing_pct:0,min:10,max:20,mean:15,median:15}]},
            chart:{version:0,type:'bar',x:body!.x,y:body!.y,aggregation:'mean',
              data:[{label:'N',value:10},{label:'Y',value:20}],
              sampled:false,note:'Synthetic chart: no real data analysed.'},
            chart_message:'',
            correlation:{version:0,method:'pearson',columns:[],cells:[],
              note:'Synthetic dataset has fewer than three records.'},
            note:'Synthetic read-only workbench response; no real backend contacted.'}});
        return;
      }
    }
    if(req.method()!=='GET'){
      audit.writes.push(req.method()+' '+pathname);
      await route.fulfill({status:403,json:{detail:'E2E fixture blocks all unapproved writes'}});
      return;
    }
    let result:unknown;
    if(pathname==='/projects'){
      result=withProject?[{id:TEST_PROJECT,name:syntheticProject.name,filename:syntheticProject.filename},
        ...(withSecondProject?[{id:TEST_PROJECT_B,name:syntheticSecondProject.name,filename:syntheticSecondProject.filename}]:[])]:[];
    }else if(pathname==='/ai/settings'){
      result={cloud_enabled:false,share_aggregates:false,auto_insights:false,providers:[]};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}`){
      result=syntheticProject;
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/live-profile`){
      result={version:0,profile};
    // The second fixture exists only when the new P1 project-switch test
    // explicitly opts into it. It is never a real owner dataset.
    }else if(withProject&&withSecondProject&&pathname===`/projects/${TEST_PROJECT_B}`){
      result=syntheticSecondProject;
    }else if(withProject&&withSecondProject&&pathname===`/projects/${TEST_PROJECT_B}/live-profile`){
      result={version:0,profile:secondProfile};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/quality`){
      result={project_id:TEST_PROJECT,version:0,rows:2,columns:2,
        summary:{issues:0,automatic_available:0,review_required:0,information:0,applied_actions:0},
        issues:[]};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/quality/history`){
      result={current_version:0,
        versions:[{version:0,event:'initial',created_at:'2026-10-28T00:00:00',details:{}}],
        actions:[]};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/quality/preview`){
      result={version:0,total_matching_rows:2,offset:0,limit:12,rows:[]};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/target-opportunities`){
      result={version:0,ranking_basis:'Synthetic test, no real target ranking',
        suggestions:[],blocked_examples:[],eligible_count:0,blocked_count:0,
        abstained:true,abstention_reason:'No business objective verified for test-only data',
        business_context_state:'unverified',note:'Synthetic browser fixture',privacy:'No user data'};
    // Prepare mounts TargetOpportunities as soon as verified B is displayed.
    // Only this exact second-project read at the expected dataset version is
    // part of the approved A-to-B switch. All other B routes stay fail-closed.
    }else if(withProject&&withSecondProject
      &&pathname===`/projects/${TEST_PROJECT_B}/target-opportunities`
      &&url.search==='?expected_version=0'){
      result={version:0,ranking_basis:'Synthetic second-project label screening, not target approval',
        suggestions:[],blocked_examples:[],eligible_count:0,blocked_count:0,
        abstained:true,abstention_reason:'No business objective verified for synthetic B',
        business_context_state:'unverified',note:'Synthetic second-project fixture only',privacy:'No user data'};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/features`){
      result={features:[]};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/preparation`){
      result={task:'classification',target:'fraud_reported',available_features:['amount'],
        recommend_exclude:[],feature_audit:[],high_risk_features:[],
        missing_targets:0,transformations:[],warnings:[]};
    // The Explore UI mounts multiple read-only panels, even for history-only
    // navigation. Match the local backend's response shapes and data version.
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/explore/overview`){
      result={version:0,rows:2,missing_cells:0,exact_duplicates:0,source:'synthetic_test_fixture',
        columns:[{name:'fraud_reported',kind:'categorical',unique:2,missing:0,missing_pct:0},
          {name:'amount',kind:'numeric',unique:2,missing:0,missing_pct:0,
            min:10,max:20,mean:15,median:15}]};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/explore/insights`){
      result={version:0,findings:[],method:'deterministic_descriptive_rules'};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/explore/recommended`){
      result={version:0,recommendations:[]};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/explore/filter-options`){
      result={version:0,max_filters:4,
        columns:[{name:'fraud_reported',kind:'categorical',options:['N','Y'],missing:0},
          {name:'amount',kind:'numeric',min:10,max:20,missing:0}],
        note:'Test-owned filter catalogue; no data changes.'};
    }else if(withProject&&pathname===`/projects/${TEST_PROJECT}/explore/saved`){
      result=[];
    }else{
      // Preserve the query string in diagnostics: a wrong version/target is
      // not the same request as the explicitly accepted read-only endpoint.
      audit.unexpectedReads.push(pathname+url.search);
      await route.fulfill({status:404,headers:{'access-control-allow-origin':UI_ORIGIN},
        json:{detail:'Unmocked read in isolated E2E fixture'}});
      return;
    }
    await route.fulfill({
      status:200,
      headers:{'access-control-allow-origin':UI_ORIGIN},
      json:result,
    });
  });
  return audit;
}

test('empty project catalogue displays safe onboarding and disables import without a file',async({page,context})=>{
  const audit=await installIsolatedAPI(context,false);
  await page.goto('/#/studio/overview');

  await expect(page.getByRole('heading',{name:/Turn raw data into/i})).toBeVisible();
  await expect(page.getByRole('button',{name:'Analyse dataset'})).toBeDisabled();
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue('');
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});

test('edited Prepare dock rejects a new import before any backend POST',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['quality','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'quality');
    localStorage.setItem('pilotodin-dock-layout-v2-'+id,
      JSON.stringify({schema:2,secondary:'prepare',side:'right',fraction:0.39}));
  },TEST_PROJECT);
  await page.goto('/#/studio/quality');

  await expect(page.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(TEST_PROJECT);
  const target=page.locator('.po-secondary-pane').getByRole('combobox',{name:/target variable/i});
  await expect(target).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');

  await page.getByRole('button',{name:'New project: import dataset'}).click();
  await expect(page.getByRole('tab',{name:'Home'})).toHaveAttribute('aria-selected','true');

  // In-memory file; never writes a CSV to disk or calls the real Python API.
  await page.locator('.po-primary-pane input[type="file"]').setInputFiles({
    name:'synthetic_upload.csv',mimeType:'text/csv',
    buffer:Buffer.from('amount,fraud_reported\n10,N\n20,Y\n'),
  });
  await expect(page.getByText('synthetic_upload.csv',{exact:true})).toBeVisible();

  const dialogs:string[]=[];
  page.once('dialog',async dialog=>{
    dialogs.push(dialog.message());
    await dialog.dismiss(); // Cancel; never approve an import.
  });
  await page.getByRole('button',{name:'Analyse dataset'}).click();

  expect(dialogs).toHaveLength(1);
  expect(dialogs[0]).toContain('You changed fields in the docked workspace');
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(TEST_PROJECT);
  await expect(target).toHaveValue('fraud_reported');
  await expect(page.getByText('synthetic_upload.csv',{exact:true})).toBeVisible();
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});

test('edited Prepare dock pauses when narrow and restores its unsaved target on widening',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true);
  // Identical synthetic, project-scoped layout used by the accepted Cancel test.
  // No owner profile, CSV or backend is accessed.
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['quality','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'quality');
    localStorage.setItem('pilotodin-dock-layout-v2-'+id,
      JSON.stringify({schema:2,secondary:'prepare',side:'right',fraction:0.39}));
  },TEST_PROJECT);
  await page.goto('/#/studio/quality');

  const dock=page.locator('.po-secondary-pane');
  const target=dock.getByRole('combobox',{name:/target variable/i});
  await expect(page.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
  await expect(dock).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');

  // At this width the split cannot fit two 300px analytical panes.
  // Hidden is intentional: it must keep the edited React form mounted,
  // exclude its inputs from focus, and not erase any draft content.
  await page.setViewportSize({width:680,height:900});
  await expect(page.getByText(/Edited docked fields are kept in memory while this view is narrow/)).toBeVisible();
  await expect(dock).toHaveCount(1);
  await expect(dock).toBeHidden();
  await expect(page.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();

  await page.setViewportSize({width:1440,height:900});
  await expect(dock).toBeVisible();
  await expect(dock.getByRole('combobox',{name:/target variable/i})).toHaveValue('fraud_reported');
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(TEST_PROJECT);
  await expect(page.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});

test('browser Back and Forward preserve an edited dock across unrelated routes',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true);
  // All project and preference data are synthetic and scoped to the :5187 context.
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['quality','explore','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'quality');
    localStorage.setItem('pilotodin-dock-layout-v2-'+id,
      JSON.stringify({schema:2,secondary:'prepare',side:'right',fraction:0.39}));
  },TEST_PROJECT);
  await page.goto('/#/studio/quality');

  const primary=page.locator('.po-primary-pane');
  const dock=page.locator('.po-secondary-pane');
  const target=dock.getByRole('combobox',{name:/target variable/i});
  await expect(primary.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
  await expect(dock).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');

  // An unrelated route must not promote/destroy the edited secondary pane.
  // This uses real browser hash history, not synthetic popstate dispatches.
  await page.evaluate(()=>{window.location.hash='#/studio/explore';});
  await expect(page).toHaveURL(/#\/studio\/explore$/);
  await expect(primary.getByRole('heading',{name:'Explore',exact:true})).toBeVisible();
  // Prove the Explore workbench finished its synthetic read-only calculation
  // before changing the hash again. A heading alone can render before data.
  await expect(primary.getByText('2 of 2 records',{exact:true})).toBeVisible();
  await expect(target).toHaveValue('fraud_reported');

  await page.goBack();
  await expect(page).toHaveURL(/#\/studio\/quality$/);
  await expect(primary.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
  await expect(target).toHaveValue('fraud_reported');

  await page.goForward();
  await expect(page).toHaveURL(/#\/studio\/explore$/);
  await expect(primary.getByRole('heading',{name:'Explore',exact:true})).toBeVisible();
  await expect(target).toHaveValue('fraud_reported');
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(TEST_PROJECT);
  // Explore calculated from the same synthetic version via an explicit
  // read-only endpoint. All other attempted POSTs remain blocked and audited.
  expect(audit.readOnlyCalculations.length).toBeGreaterThan(0);
  expect(audit.readOnlyCalculations.every(path=>path===
    `POST /projects/${TEST_PROJECT}/explore/workbench`)).toBe(true);
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});

test('cancelled dock promotion leaves no duplicate browser Back Forward history',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true);
  // Synthetic project and split only; this test never reads a user dataset.
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,
      JSON.stringify(['quality','explore','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'quality');
    localStorage.setItem('pilotodin-dock-layout-v2-'+id,
      JSON.stringify({schema:2,secondary:'prepare',side:'right',fraction:0.39}));
  },TEST_PROJECT);
  await page.goto('/#/studio/quality');

  const primary=page.locator('.po-primary-pane');
  const dock=page.locator('.po-secondary-pane');
  const target=dock.getByRole('combobox',{name:/target variable/i});
  await expect(primary.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
  await expect(target).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');

  // Establish one earlier accepted history entry that Back must reach.
  await page.evaluate(()=>{window.location.hash='#/studio/explore';});
  await expect(page).toHaveURL(/#\/studio\/explore$/);
  await expect(primary.getByRole('heading',{name:'Explore',exact:true})).toBeVisible();
  await expect(primary.getByText('2 of 2 records',{exact:true})).toBeVisible();

  const prompts:string[]=[];
  page.on('dialog',async dialog=>{
    prompts.push(dialog.message());
    await dialog.dismiss(); // Always Cancel: never permit destructive promotion.
  });
  // Direct URL changes, including browser history actions, must consult the
  // same memory-only edited-dock guard used by Studio and navigation tabs.
  await page.evaluate(()=>{window.location.hash='#/studio/prepare';});
  await expect.poll(()=>prompts.length).toBe(1);
  expect(prompts[0]).toContain('You changed fields in the docked workspace');
  await expect(page).toHaveURL(/#\/studio\/explore$/);
  await expect(primary.getByRole('heading',{name:'Explore',exact:true})).toBeVisible();
  await expect(dock).toBeVisible();
  await expect(target).toHaveValue('fraud_reported');

  // Cancel must not leave a phantom Prepare route OR an extra Explore history
  // entry requiring the user to press Back twice to reach prior Quality.
  await page.goBack();
  await expect(page,'Back after Cancel must reach the prior accepted Quality entry')
    .toHaveURL(/#\/studio\/quality$/);
  await expect(primary.getByRole('heading',{name:'Data Quality',exact:true})).toBeVisible();
  await expect(target).toHaveValue('fraud_reported');

  await page.goForward();
  await expect(page).toHaveURL(/#\/studio\/explore$/);
  await expect(primary.getByRole('heading',{name:'Explore',exact:true})).toBeVisible();
  await expect(target).toHaveValue('fraud_reported');
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(TEST_PROJECT);
  expect(prompts).toHaveLength(1);
  expect(audit.readOnlyCalculations.length).toBeGreaterThan(0);
  expect(audit.readOnlyCalculations.every(path=>path===
    `POST /projects/${TEST_PROJECT}/explore/workbench`)).toBe(true);
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});
test('primary Prepare unsaved target requires Cancel protection before project switching',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true,true);
  // Two invented projects, an empty browser storage context, and only mocked API.
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },TEST_PROJECT);
  await page.goto('/#/studio/prepare');

  const primary=page.locator('.po-primary-pane');
  const target=primary.getByRole('combobox',{name:/target variable/i});
  const switcher=page.getByRole('combobox',{name:'Switch project'});
  await expect(target).toBeVisible();
  await expect(switcher).toHaveValue(TEST_PROJECT);
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');

  const prompts:string[]=[];
  page.on('dialog',async dialog=>{
    prompts.push(dialog.message());
    await dialog.dismiss(); // Always Cancel: no permission to discard primary edits.
  });
  await switcher.selectOption(TEST_PROJECT_B);
  await expect.poll(()=>prompts.length,{
    message:'An edited primary Prepare target needs consent BEFORE switching projects',
  }).toBe(1);
  expect(prompts[0]).toMatch(/changed|unsaved|discard/i);
  await expect(switcher).toHaveValue(TEST_PROJECT);
  await expect(primary.getByRole('combobox',{name:/target variable/i}))
    .toHaveValue('fraud_reported');
  await expect(page).toHaveURL(/#\/studio\/prepare$/);
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});
test('cross-tab project selection Cancel preserves an edited primary Prepare draft',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true,true);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },TEST_PROJECT);
  await page.goto('/#/studio/prepare');
  const target=page.locator('.po-primary-pane').getByRole('combobox',{name:/target variable/i});
  const switcher=page.getByRole('combobox',{name:'Switch project'});
  await expect(target).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');
  await expect(switcher).toHaveValue(TEST_PROJECT);

  // Same isolated browser context and origin: only B writes the shared key.
  // A should reject the storage event without writing B's choice back to A.
  const other=await context.newPage();
  let reportRequestSeen:()=>void=()=>{};
  const requestStarted=new Promise<void>(resolve=>{reportRequestSeen=resolve;});
  let releaseOldProfile:()=>void=()=>{};
  const oldProfileGate=new Promise<void>(resolve=>{releaseOldProfile=resolve;});
  await other.route('**/api/projects/playwright-synthetic-project/live-profile',async route=>{
    if(route.request().method()!=='GET')throw new Error('Only the test-owned profile GET may be delayed');
    reportRequestSeen();
    await oldProfileGate;
    await route.fulfill({status:200,
      headers:{'access-control-allow-origin':UI_ORIGIN},
      json:{version:0,profile}});
  });
  await other.goto('/#/studio/quality');
  await requestStarted; // A's older project load is now deliberately in flight.
  const prompts:string[]=[];
  page.on('dialog',async dialog=>{
    prompts.push(dialog.message());
    await dialog.dismiss();
  });
  await other.evaluate((id:string)=>localStorage.setItem('pilotodin-current',id),TEST_PROJECT_B);
  await expect.poll(()=>prompts.length,{
    message:'Cross-tab selection must warn before losing an edited primary draft',
  }).toBe(1);
  expect(prompts[0]).toMatch(/primary workspace.*Switching projects may discard/i);
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(TEST_PROJECT);
  await expect(target).toHaveValue('fraud_reported');
  await expect(page).toHaveURL(/#\/studio\/prepare$/);
  await expect(page.getByText(/Another tab selected a different project/)).toBeVisible();
  // Complete B-tab's stale A profile read only after the cross-tab B selection.
  // Its delayed success must not steal the shared selection back from project B.
  const delayedResponse=other.waitForResponse(response=>
    response.url().endsWith(`/api/projects/${TEST_PROJECT}/live-profile`)
      &&response.status()===200);
  releaseOldProfile();
  await delayedResponse; // An actual stale GET response, not just a queued release.
  await expect.poll(async()=>other.evaluate(()=>localStorage.getItem('pilotodin-current')))
    .toBe(TEST_PROJECT_B);
  // Let the browser process the completed mock response and related state effects.
  await other.evaluate(()=>new Promise<void>(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  expect(await other.evaluate(()=>localStorage.getItem('pilotodin-current'))).toBe(TEST_PROJECT_B);
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});

test('approved cross-tab project read failure preserves primary Prepare without stealing storage',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true,true);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },TEST_PROJECT);
  await page.goto('/#/studio/prepare');
  const primary=page.locator('.po-primary-pane');
  const target=primary.getByRole('combobox',{name:/target variable/i});
  const switcher=page.getByRole('combobox',{name:'Switch project'});
  await expect(target).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');
  await expect(switcher).toHaveValue(TEST_PROJECT);

  // Only A's requested B profile read fails. The synthetic project catalogue
  // and B's other-tab reads still work. There is no real HTTP backend.
  await page.route('**/api/projects/playwright-synthetic-second-project/live-profile',async route=>{
    if(route.request().method()!=='GET')throw new Error('Only synthetic profile GET failure is allowed');
    await route.fulfill({status:503,
      headers:{'access-control-allow-origin':UI_ORIGIN},
      json:{detail:'Synthetic project profile temporarily unavailable'}});
  });
  const other=await context.newPage();
  // Both tabs share project A's persisted active Prepare stage. Matching the
  // restored stage avoids requiring an unrelated Quality navigation before
  // this test exercises the approved B read failure.
  await other.goto('/#/studio/prepare');
  await expect(other.getByRole('combobox',{name:'Switch project'}))
    .toHaveValue(TEST_PROJECT);
  await expect(other.locator('.po-primary-pane')
    .getByRole('combobox',{name:/target variable/i})).toBeVisible();

  const prompts:string[]=[];
  page.on('dialog',async dialog=>{
    prompts.push(dialog.message());
    await dialog.accept(); // Approved attempt, not an approval for any API write.
  });
  await other.evaluate((id:string)=>localStorage.setItem('pilotodin-current',id),TEST_PROJECT_B);
  await expect.poll(()=>prompts.length).toBe(1);
  expect(prompts[0]).toMatch(/primary workspace.*Switching projects may discard/i);
  // Approval authorises a read; failure must NOT unmount the edited A workspace.
  await expect(page.getByText(/The other tab selected a project that could not be opened here/))
    .toBeVisible();
  await expect(switcher).toHaveValue(TEST_PROJECT);
  await expect(target).toHaveValue('fraud_reported');
  await expect(page).toHaveURL(/#\/studio\/prepare$/);
  expect(await other.evaluate(()=>localStorage.getItem('pilotodin-current'))).toBe(TEST_PROJECT_B);
  expect(prompts).toHaveLength(1);
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});

test('approved cross-tab successful project load avoids duplicate failing profile request',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true,true);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },TEST_PROJECT);
  await page.goto('/#/studio/prepare');
  const primary=page.locator('.po-primary-pane');
  const target=primary.getByRole('combobox',{name:/target variable/i});
  const switcher=page.getByRole('combobox',{name:'Switch project'});
  await expect(target).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');
  await expect(switcher).toHaveValue(TEST_PROJECT);

  // The first B profile request succeeds using the isolated response contract.
  // Any subsequent B profile GET gets a synthetic 503. No actual API is reached.
  let profileReads=0;
  await page.route('**/api/projects/playwright-synthetic-second-project/live-profile',async route=>{
    if(route.request().method()!=='GET')
      throw new Error('Only synthetic second-project profile reads are permitted');
    profileReads++;
    if(profileReads===1){await route.fallback();return;}
    await route.fulfill({status:503,headers:{'access-control-allow-origin':UI_ORIGIN},
      json:{detail:'Synthetic duplicate profile GET refused'}});
  });
  const other=await context.newPage();
  // Both tabs share the saved active stage for synthetic project A. The first
  // tab persisted Prepare, so do not demand Quality before switching B.
  // Confirm B's selecting tab is actually mounted on the same fake A project.
  await other.goto('/#/studio/prepare');
  await expect(other.getByRole('combobox',{name:'Switch project'}))
    .toHaveValue(TEST_PROJECT);
  await expect(other.locator('.po-primary-pane')
    .getByRole('combobox',{name:/target variable/i})).toBeVisible();

  const prompts:string[]=[];
  page.on('dialog',async dialog=>{
    prompts.push(dialog.message());
    await dialog.accept(); // Approve only the read-only project selection.
  });
  const firstBProfile=page.waitForResponse(response=>
    response.url().endsWith(`/api/projects/${TEST_PROJECT_B}/live-profile`)
      &&response.status()===200);
  // A valid B Prepare mount also performs a scoped target-opportunities GET.
  // Confirm the B fixture actually serves it with 200, not an audited 404.
  const bOpportunities=page.waitForResponse(response=>{
    const url=new URL(response.url());
    return url.origin===API_ORIGIN
      &&url.pathname===`/api/projects/${TEST_PROJECT_B}/target-opportunities`
      &&url.search==='?expected_version=0';
  });
  await other.evaluate((id:string)=>localStorage.setItem('pilotodin-current',id),TEST_PROJECT_B);
  await firstBProfile;
  expect((await bOpportunities).status()).toBe(200);
  await expect.poll(()=>prompts.length).toBe(1);
  await expect(switcher).toHaveValue(TEST_PROJECT_B);
  // Allow App/shell state changes and mount effects to settle after first success.
  await page.evaluate(()=>new Promise<void>(resolve=>
    requestAnimationFrame(()=>requestAnimationFrame(()=>resolve()))));
  expect(profileReads).toBe(1);
  // UnifiedShell deliberately hides the legacy Studio sidebar and its
  // 'Choose project' control. Verify project B in the VISIBLE primary content,
  // rather than querying a hidden control excluded by accessibility roles.
  await expect(primary.locator('.heading .eyebrow'))
    .toHaveText('PROJECT / '+syntheticSecondProject.name.toUpperCase());
  await expect(primary.getByRole('combobox',{name:/target variable/i})).toHaveValue('');
  await expect(page).toHaveURL(/#\/studio\/prepare$/);
  expect(await other.evaluate(()=>localStorage.getItem('pilotodin-current'))).toBe(TEST_PROJECT_B);
  expect(prompts).toHaveLength(1);
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});

test('approved same-tab global project read failure preserves edited primary Prepare',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true,true);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },TEST_PROJECT);
  await page.goto('/#/studio/prepare');

  const primary=page.locator('.po-primary-pane');
  const target=primary.getByRole('combobox',{name:/target variable/i});
  const switcher=page.getByRole('combobox',{name:'Switch project'});
  await expect(target).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');
  await expect(switcher).toHaveValue(TEST_PROJECT);
  const prompts:string[]=[];
  page.on('dialog',async dialog=>{
    prompts.push(dialog.message());
    await dialog.accept(); // Explicitly approve the read attempt only.
  });
  // Never reach a real backend. Project B is in the synthetic catalogue, but
  // opening B cannot succeed because the synthetic profile GET returns 503.
  let failedBProfileReads=0;
  await page.route('**/api/projects/playwright-synthetic-second-project/live-profile',async route=>{
    if(route.request().method()!=='GET')throw new Error('Read-only B profile failure only');
    failedBProfileReads++;
    await route.fulfill({status:503,headers:{'access-control-allow-origin':UI_ORIGIN},
      json:{detail:'Synthetic direct chooser B profile read failed'}});
  });
  const failedB=page.waitForResponse(response=>
    response.url().endsWith(`/api/projects/${TEST_PROJECT_B}/live-profile`)
      &&response.status()===503);
  await switcher.selectOption(TEST_PROJECT_B);
  await failedB;
  await expect.poll(()=>prompts.length).toBe(1);
  // Permission to attempt loading B is not consent to discard A if B fails.
  // No provisional B identity may replace the still-edited A workspace.
  await expect(switcher).toHaveValue(TEST_PROJECT);
  await expect(primary.locator('.heading .eyebrow'))
    .toHaveText('PROJECT / '+syntheticProject.name.toUpperCase());
  await expect(target).toHaveValue('fraud_reported');
  await expect(page).toHaveURL(/#\/studio\/prepare$/);
  expect(await page.evaluate(()=>localStorage.getItem('pilotodin-current')))
    .toBe(TEST_PROJECT);
  expect(failedBProfileReads).toBe(1);
  expect(prompts).toHaveLength(1);
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});

test('approved same-tab global project load commits B only after verified GETs',async({page,context})=>{
  const audit=await installIsolatedAPI(context,true,true);
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','prepare']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'prepare');
  },TEST_PROJECT);
  await page.goto('/#/studio/prepare');
  const primary=page.locator('.po-primary-pane');
  const switcher=page.getByRole('combobox',{name:'Switch project'});
  const target=primary.getByRole('combobox',{name:/target variable/i});
  await expect(target).toBeVisible();
  await target.selectOption('fraud_reported');
  await expect(target).toHaveValue('fraud_reported');
  await expect(switcher).toHaveValue(TEST_PROJECT);

  let bProfileReads=0;
  await page.route('**/api/projects/playwright-synthetic-second-project/live-profile',async route=>{
    if(route.request().method()!=='GET')throw new Error('Read-only synthetic B profile only');
    bProfileReads++;
    if(bProfileReads===1){await route.fallback();return;}
    await route.fulfill({status:503,headers:{'access-control-allow-origin':UI_ORIGIN},
      json:{detail:'Synthetic unexpected second B profile GET'}});
  });
  const prompts:string[]=[];
  page.on('dialog',async dialog=>{
    prompts.push(dialog.message());
    await dialog.accept();
  });
  const bRead=page.waitForResponse(response=>
    response.url().endsWith(`/api/projects/${TEST_PROJECT_B}/live-profile`)
      &&response.status()===200);
  const bOpportunities=page.waitForResponse(response=>{
    const url=new URL(response.url());
    return url.origin===API_ORIGIN&&
      url.pathname===`/api/projects/${TEST_PROJECT_B}/target-opportunities`&&
      url.search==='?expected_version=0';
  });
  await switcher.selectOption(TEST_PROJECT_B);
  await bRead;
  expect((await bOpportunities).status()).toBe(200);
  await expect(switcher).toHaveValue(TEST_PROJECT_B);
  await expect(primary.locator('.heading .eyebrow'))
    .toHaveText('PROJECT / '+syntheticSecondProject.name.toUpperCase());
  await expect(target).toHaveValue('');
  await expect(page).toHaveURL(/#\/studio\/prepare$/);
  expect(await page.evaluate(()=>localStorage.getItem('pilotodin-current'))).toBe(TEST_PROJECT_B);
  expect(prompts).toHaveLength(1);
  expect(bProfileReads).toBe(1);
  expect(audit.writes).toEqual([]);
  expect(audit.unexpectedReads).toEqual([]);
  expect(audit.blockedOrigins).toEqual([]);
});
