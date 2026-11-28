import {chromium, expect} from '@playwright/test';

const debugUrl = 'http://127.0.0.1:9331';
const question = 'In one sentence, explain why I should check for missing values before training a model on this dataset.';
const origin = /^https?:\/\/tauri\.localhost(?:\/|$)/;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const receipt = {stage: 'webview', insight_requests: 0};

async function connect() {
  await expect.poll(async () => {
    try {
      return (await fetch(debugUrl+'/json/version', {signal:AbortSignal.timeout(1000)})).ok;
    } catch {
      return false;
    }
  }, {timeout:50000}).toBe(true);
  return chromium.connectOverCDP(debugUrl, {timeout:10000});
}

async function run(browser) {
  const pages = () => browser.contexts().flatMap(context => context.pages()).filter(page => origin.test(page.url()));
  await expect.poll(() => pages().length, {timeout:30000}).toBe(1);
  const [page] = pages();
  await expect(page.getByLabel('Switch project')).toBeVisible({timeout:50000});
  receipt.stage = 'synthetic-fixture';
  const project = await page.evaluate(async () => {
    const connection = await window.__TAURI_INTERNALS__.invoke('launch_backend');
    if(!connection||!Number.isInteger(connection.port)||connection.port<1024||connection.port>65535||
       typeof connection.token!=='string'||!/^[0-9a-f]{64}$/.test(connection.token))
      throw Error('Invalid desktop connection');
    const base = 'http://127.0.0.1:'+connection.port+'/api';
    const auth = {'X-PilotODIN-Session':connection.token};
    const put = (path, body) => {
      if(path!=='/ai/settings'&&path!=='/resource/policy')throw Error('Unexpected desktop fixture destination');
      return fetch(base+path, {
      method:'PUT',headers:{...auth,'Content-Type':'application/json'},body:JSON.stringify(body),redirect:'error',
      signal:AbortSignal.timeout(10000),
      });
    };
    const projects = await fetch(base+'/projects', {headers:auth,signal:AbortSignal.timeout(10000),redirect:'error'});
    if (!projects.ok || (await projects.json()).length !== 0) throw Error('expected clean desktop project catalogue');
    const ai = await put('/ai/settings', {intelligence_mode:'local',cloud_enabled:false,local_timeout_seconds:120});
    if (!ai.ok || (await ai.json()).cloud_enabled !== false) throw Error('could not configure offline AI');
    const policy = await put('/resource/policy', {mode:'low_memory'});
    if (!policy.ok) throw Error('could not configure low-memory policy');
    const file = new FormData();
    file.append('file',new File(['premium,outcome\n10,Yes\n,No\n30,Yes\n40,No\n'],'r03_hosted_synthetic.csv',{type:'text/csv'}));
    const uploaded = await fetch(base+'/projects', {method:'POST',headers:auth,body:file,signal:AbortSignal.timeout(15000),redirect:'error'});
    if (uploaded.status !== 201) throw Error('synthetic CSV import failed');
    const {id} = await uploaded.json();
    localStorage.setItem('pilotodin-current',id);
    localStorage.setItem('pilotodin-workspace-tabs-v1-'+id,JSON.stringify(['assistant']));
    localStorage.setItem('pilotodin-workspace-active-v1-'+id,'assistant');
    return {id,port:connection.port};
  });
  expect(project.id).toMatch(/^[0-9a-f]{32}$/);
  receipt.stage = 'assistant-ready';
  const assistant = new URL('/?r03=hosted#/studio/assistant',page.url());
  await page.goto(assistant.href,{waitUntil:'domcontentloaded',timeout:25000});
  await expect(page.getByLabel('Switch project')).toHaveValue(project.id,{timeout:30000});
  await page.getByLabel('Choose intelligence').selectOption('ollama');
  await page.getByRole('textbox',{name:'Dataset question'}).fill(question);
  const api = 'http://127.0.0.1:'+project.port+'/api';
  const insight = api+'/projects/'+project.id+'/ai/insight';
  const isInsight = req => req.url() === insight && req.method() === 'POST';
  let reply;
  page.on('request', req => {if (isInsight(req)) receipt.insight_requests += 1;});
  page.on('response', response => {if (isInsight(response.request())) reply = response;});
  receipt.stage = 'ask-odin';
  const started = performance.now();
  const [preflight] = await Promise.all([
    page.waitForResponse(r => r.url().startsWith(api+'/resource/preflight?operation=local_inference'),{timeout:10000}),
    page.getByRole('button',{name:'Ask',exact:true}).click({timeout:10000}),
  ]);
  const preflightResult = await preflight.json();
  receipt.admission = ['allow','defer','skip'].includes(preflightResult.decision) ? preflightResult.decision : 'unknown';
  expect(receipt.admission).toBe('allow');

  await expect.poll(() => !!reply || page.isClosed(),{timeout:150000}).toBe(true);
  expect(reply).toBeDefined();
  receipt.http_status = reply.status();
  expect(reply.request().postDataJSON()?.selected_provider).toBe('ollama');
  expect(reply.ok()).toBe(true);
  const result = await reply.json();
  receipt.provider = ['bundled','local','ollama'].includes(result.provider) ? result.provider : 'other';
  receipt.local_status = typeof result.local_status === 'string' && /^[a-z_]{1,48}$/.test(result.local_status)
    ? result.local_status : 'unknown';
  if (result.fallback) {
    const fallback = page.locator('.chat-message.assistant').last();
    await expect(fallback).toContainText('VERIFIED RULES · NO LLM');
    const diagnostic = await fallback.innerText();
    receipt.startup_issue = diagnostic.match(/Desktop startup: ([a-z_]{1,48})\./)?.[1] ?? null;
  }
  expect(receipt.provider).toBe('bundled');
  expect(result.model).toBe('pilotodin-qwen3-1.7b');
  expect(result.source).toBe('local_llm');
  expect(result.fallback).toBe(false);
  const message = page.locator('.chat-message.assistant').last();
  await expect(message).toContainText('BUNDLED · pilotodin-qwen3-1.7b');
  await expect(message.locator('.chat-body')).toContainText(/missing/i);
  receipt.response_ms = Math.round(performance.now()-started);
  await pause(3000);
  await expect(page.getByRole('textbox',{name:'Dataset question'})).toBeEnabled();
  expect(receipt.insight_requests).toBe(1);
  receipt.stage = 'complete';
}

if (process.platform !== 'win32' || process.env.RUNNER_ENVIRONMENT !== 'github-hosted'
    || process.env.PILOTODIN_R03_HOSTED_DESKTOP !== 'approved') {
  throw Error('Run only in the approved hosted Windows job.');
}

let browser;
try {
  browser = await connect();
  await run(browser);
} catch (error) {
  receipt.outcome = 'fail';
  receipt.error_kind = error.name === 'TimeoutError' ? 'timeout' : 'assertion_or_runtime_error';
  process.exitCode = 1;
} finally {
  await browser?.close().catch(() => {});
  console.log('R03 desktop '+JSON.stringify({outcome:'pass',...receipt}));
}
