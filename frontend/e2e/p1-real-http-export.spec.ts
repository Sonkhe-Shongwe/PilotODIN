import {test,expect} from '@playwright/test';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {request as httpRequest} from 'node:http';
import {resolve} from 'node:path';
import {startDisposableBackend,stopDisposableBackend} from './p1-real-http-backend';
import type {DisposableBackend} from './p1-real-http-backend';

const API='http://127.0.0.1:8000';
const UI='http://127.0.0.1:5178';
type Receipt={format:string,state:string,size:number,sha256:string,reason:string|null,scratch_exists:boolean};
function audit(pid:string):{receipts:Receipt[],original_matches:boolean,version:number,original_history:boolean}{
  return JSON.parse(execFileSync('python',[resolve('..','tools','p1_real_http_export_audit.py'),pid],
    {encoding:'utf8',timeout:10000}));
}
let owned:DisposableBackend|null=null;
test.beforeEach(async()=>{owned=await startDisposableBackend()});
test.afterEach(async()=>{if(owned){const old=owned;owned=null;await stopDisposableBackend(old)}});

test('real HTTP B5 export browser click produces exact CSV and XLSX receipts',async({page,context,request})=>{
  const source=Buffer.from('OrderID,Note,Amount\nA001,=SUM(1),12\nA002,Normal,3\n');
  const imported=await request.post(API+'/api/projects',{multipart:{
    file:{name:'pilotodin_b5_browser.csv',mimeType:'text/csv',buffer:source}
  }});
  expect(imported.status()).toBe(201);
  const pid=(await imported.json()).id as string;
  expect(pid).toMatch(/^[a-f0-9]{32}$/);
  const exportPath='/api/projects/'+pid+'/quality/export';
  const historyPath='/api/projects/'+pid+'/quality/history';
  const before=await (await request.get(API+historyPath)).json();
  let permitted:string|null=null;
  const writes:string[]=[];
  const blocked:string[]=[];
  await context.route('**/*',async route=>{
    const req=route.request(),url=new URL(req.url()),method=req.method();
    if(url.origin===UI&&(method==='GET'||method==='HEAD')){await route.continue();return;}
    if(url.origin==='https://fonts.googleapis.com'&&url.pathname==='/css2'&&method==='GET'){
      await route.fulfill({status:200,contentType:'text/css',body:'/* isolated fonts */'});return;
    }
    if(url.origin===API){
      if(method==='OPTIONS'&&url.pathname===exportPath){await route.continue();return;}
      if(method==='GET'&&(url.pathname==='/api/projects'||url.pathname==='/api/ai/settings'
        ||new RegExp('^/api/projects/'+pid+'(?:/(?:live-profile|quality|quality/history|quality/preview|preparation|features|target-opportunities))?$').test(url.pathname))){
        await route.continue();return;
      }
      if(method==='POST'&&url.pathname===exportPath&&permitted){
        const body=req.postDataJSON();
        if(body.version===0&&body.format===permitted&&body.columns===null&&Array.isArray(body.filters)&&body.filters.length===0){
          writes.push(permitted);permitted=null;await route.continue();return;
        }
      }
    }
    if(method!=='GET'&&method!=='HEAD')blocked.push(method+' '+url.pathname);
    await route.abort('blockedbyclient');
  });
  await page.addInitScript((id:string)=>{
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['overview','quality']));
  },pid);
  await page.goto('/#/studio/overview');
  await expect(page.getByRole('combobox',{name:'Switch project'})).toHaveValue(pid);
  await page.getByRole('navigation',{name:'Workspace navigation'}).getByRole('button',{name:'Quality'}).click();
  const section=page.getByRole('region',{name:'Export cleaned data'});
  await expect(section.getByRole('button',{name:'Export dataset'})).toBeEnabled();
  expect(audit(pid).receipts).toEqual([]);
  // Implicit wrapping labels can include the select's option text.
  // Identify the unique format control by its exact two offered choices.
  const format=section.getByRole('combobox').filter({has:page.locator('option[value="xlsx"]')});
  await expect(format).toHaveCount(1);
  await expect(format.locator('option')).toHaveText(['CSV','Excel XLSX']);
  for(const fmt of ['csv','xlsx']){
    await format.selectOption(fmt);
    await expect(format).toHaveValue(fmt);
    permitted=fmt;
    const metadata=page.waitForResponse(r=>r.url()===API+exportPath&&r.request().method()==='POST');
    const waiting=page.waitForEvent('download');
    await section.getByRole('button',{name:'Export dataset'}).click();
    const download=await waiting;
    expect(await download.failure()).toBeNull();
    expect(download.suggestedFilename()).toBe('pilotodin_b5_browser_cleaned_v0.'+fmt);
    const bytes=readFileSync(await download.path());
    const headers=(await metadata).headers();
    expect(headers['x-pilotodin-export-sha256']).toBe(createHash('sha256').update(bytes).digest('hex'));
    expect(headers['content-length']).toBe(String(bytes.length));
    expect(headers['x-pilotodin-dataset-version']).toBe('0');
    expect(headers['x-pilotodin-exported-rows']).toBe('2');
    if(fmt==='csv'){
      expect(bytes.subarray(0,3).toString('hex')).toBe('efbbbf');
      expect(bytes.toString('utf8')).toContain("A001,'=SUM(1),12");
    }else{
      expect(bytes.subarray(0,4).toString('hex')).toBe('504b0304');
    }
    await expect.poll(()=>audit(pid).receipts.find(r=>r.format===fmt)?.state).toBe('released');
    const receipt=audit(pid).receipts.find(r=>r.format===fmt)!;
    expect(receipt).toMatchObject({size:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex'),scratch_exists:false});
  }
  expect(writes).toEqual(['csv','xlsx']);
  expect(blocked).toEqual([]);
  expect(audit(pid)).toMatchObject({original_matches:true,version:0,original_history:true});
  expect(await (await request.get(API+historyPath)).json()).toEqual(before);
});

test('real HTTP B5 export disconnect interrupts a backpressured response',async({request})=>{
  // Generated ~16 MiB CSV, comfortably under the existing source admission cap.
  const rows=['RecordID,Note',...Array.from({length:16000},(_,i)=>'R'+String(i).padStart(5,'0')+','+'x'.repeat(1000))];
  const imported=await request.post(API+'/api/projects',{multipart:{
    file:{name:'pilotodin_b5_disconnect.csv',mimeType:'text/csv',buffer:Buffer.from(rows.join('\n')+'\n')}
  }});
  expect(imported.status()).toBe(201);
  const pid=(await imported.json()).id as string;
  expect(pid).toMatch(/^[a-f0-9]{32}$/);
  const body=JSON.stringify({version:0,format:'csv'});
  await new Promise<void>((done,fail)=>{
    const req=httpRequest(API+'/api/projects/'+pid+'/quality/export',{
      method:'POST',headers:{'Content-Type':'application/json','Content-Length':Buffer.byteLength(body)}
    },res=>{
      if(res.statusCode!==200){res.resume();fail(Error('Unexpected export status '+res.statusCode));return;}
      res.once('data',(chunk:Buffer)=>{
        expect(chunk.length).toBeGreaterThan(0);
        expect(Number(res.headers['content-length'])).toBeGreaterThan(15*1024*1024);
        // Abort after first bytes, without reading the rest of the large body.
        res.destroy();req.destroy();done();
      });
      res.on('error',()=>{});
    });
    req.setTimeout(30000,()=>{req.destroy();fail(Error('Export timed out'))});
    req.on('error',fail);
    req.end(body);
  });
  await expect.poll(()=>audit(pid).receipts[0]?.state,{timeout:15000}).toBe('interrupted');
  expect(audit(pid)).toMatchObject({original_matches:true,version:0,original_history:true,
    receipts:[{format:'csv',state:'interrupted',reason:'cancelled',scratch_exists:false}]});
});
