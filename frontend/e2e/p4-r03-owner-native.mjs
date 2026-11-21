import {chromium, expect} from '@playwright/test';
import {discoverUniqueDevPage, hasTauriNativeBridge} from './p4-73-cdp-target-discovery.mjs';

const site = 'http://127.0.0.1:5173';
const api = 'http://127.0.0.1:8000';
const questions = [
  ['Which outcomes have the most missing premiums?', 'Missing premium by outcome'],
  ['What percentage of labelled outcomes are Yes?', '2 of 3 labelled rows in outcome match Yes (66.6667%)'],
  ['What percentage of all rows have a Yes outcome?', '2 of all 4 rows in outcome match Yes (50%)'],
  ['What is the median premium for Yes outcomes?', 'Median premium where outcome = Yes is 30'],
  ['What about No?', 'Median premium where outcome = No is unavailable. 0 usable values from 1 matching rows.'],
];

async function verify() {
  const project = process.env.PILOTODIN_R03_FIXTURE_ID;
  if (process.platform !== 'win32' || process.env.PILOTODIN_R03_NATIVE_RUN !== 'approved-owner-session'
      || !/^[a-f0-9]{32}$/.test(project ?? '')) {
    throw Error('Run this driver through the approved Windows desktop check.');
  }
  const browser = await chromium.connectOverCDP('http://127.0.0.1:9331', {timeout:15000});
  try {
    const found = await discoverUniqueDevPage(
      () => browser.contexts().flatMap(context => context.pages()),
      () => new Promise(resolve => setTimeout(resolve, 750)), 16,
    );
    if (found.status !== 'FOUND') throw Error('Native Tauri bridge unavailable: '+found.status);
    const page = found.page;
    const insight = '/api/projects/'+project+'/ai/insight';
    const blocked = [];
    await page.context().route('**/*', async route => {
      const request = route.request();
      const url = new URL(request.url());
      const method = request.method();
      if (url.origin === site && ['GET','HEAD'].includes(method)) return route.continue();
      if (url.origin === api && method === 'GET' && (
        ['/api/projects','/api/health','/api/ai/settings','/api/resource/status'].includes(url.pathname)
        || url.pathname === '/api/projects/'+project || url.pathname.startsWith('/api/projects/'+project+'/')
      )) return route.continue();
      if (url.origin === api && url.pathname === insight && method === 'POST'
          && request.postDataJSON()?.selected_provider === 'local') return route.continue();
      blocked.push({method, scope:url.origin === site || url.origin === api ? 'loopback' : 'external'});
      return route.abort();
    });
    await page.evaluate(id => {
      localStorage.setItem('pilotodin-current', id);
      localStorage.setItem('pilotodin-workspace-tabs-v1-'+id, JSON.stringify(['assistant']));
      localStorage.setItem('pilotodin-workspace-active-v1-'+id, 'assistant');
      localStorage.setItem('pilotodin-ai-provider-assistant','local');
    }, project);
    await page.goto(site+'/?r03=native#/studio/assistant', {waitUntil:'domcontentloaded',timeout:15000});
    expect(await hasTauriNativeBridge(page)).toBe(true);
    await expect(page.getByLabel('Switch project')).toHaveValue(project);
    await expect(page.getByLabel('Choose intelligence')).toHaveValue('local');

    const checks = [];
    for (const [index,[question,expected]] of questions.entries()) {
      await page.getByRole('textbox',{name:'Dataset question'}).fill(question);
      const started = performance.now();
      const [reply] = await Promise.all([
        page.waitForResponse(response => response.url() === api+insight && response.request().method()==='POST',
          {timeout:10000}),
        page.getByRole('button',{name:'Ask',exact:true}).click(),
      ]);
      expect(reply.ok()).toBe(true);
      const result = await reply.json();
      expect(result.dataset_version).toBe(0);
      expect(result.source).toBe('local_computed_rules');
      expect(result.local_status).toBe('not_requested');
      const followUp = reply.request().postDataJSON().local_follow_up;
      if (index === questions.length - 1) {
        expect(followUp).toEqual({project_id:project,dataset_version:0,question:questions[3][0]});
      } else {
        expect(followUp).toBeUndefined();
      }
      const message = page.locator('.chat-message.assistant').last();
      await expect(message).toContainText(expected);
      if (index === 0) {
        await expect(message.getByRole('listitem')).toHaveText([
          'No · 1 of 1 missing (100%)','Yes · 0 of 2 missing (0%)','Blank group · 0 of 1 missing (0%)',
        ]);
      }
      checks.push({case:index+1,click_to_verified_ui_ms:Math.round(performance.now()-started)});
      // Leave time for the process sampler to observe the native workspace.
      await new Promise(resolve => setTimeout(resolve, 1200));
    }
    // The app may request remote assets. Report blocked traffic without URLs.
    expect(blocked.filter(item => item.scope === 'loopback')).toEqual([]);
    console.log(JSON.stringify({checks,external_page_requests_blocked:blocked.filter(item=>item.scope==='external').length}));
  } finally {
    await browser.close();
  }
}

await verify();
