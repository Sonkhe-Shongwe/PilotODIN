// Copied into frontend/ on the hosted fixture so it resolves the installed Playwright.
import assert from 'node:assert/strict';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
import {readdir, readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {setTimeout as wait} from 'node:timers/promises';
import {chromium} from '@playwright/test';

const {RUNNER_ENVIRONMENT, GITHUB_RUN_ATTEMPT, PILOTODIN_SAVE_QA_PID, PILOTODIN_SAVE_QA_OUTPUT, PILOTODIN_SAVE_QA_DIALOG} = process.env;
assert.equal(RUNNER_ENVIRONMENT, 'github-hosted');
assert.equal(GITHUB_RUN_ATTEMPT, '1');
assert.match(PILOTODIN_SAVE_QA_PID, /^[1-9][0-9]*$/);
assert.equal((await readdir(PILOTODIN_SAVE_QA_OUTPUT)).length, 0);

let browser;
for (let trial = 0; trial < 50; trial++) {
  try {
    browser = await chromium.connectOverCDP('http://127.0.0.1:9331', {timeout: 1000});
    break;
  } catch {
    await wait(250);
  }
}
assert.ok(browser, 'The isolated desktop never exposed its QA WebView.');
try {
  const context = browser.contexts()[0];
  const page = context.pages()[0] ?? (await context.waitForEvent('page', {timeout: 10000}));
  await page.waitForURL('**/p2_native_export_test.html', {timeout: 12000});
  await page.locator('#pdf').waitFor();
  await page.evaluate(() => {
    const realFetch = window.fetch.bind(window);
    window.reportQa = {calls: [], forceFallback: false};
    window.fetch = (input, init) => {
      if (/\/save_report_as$/.test(String(input))) {
        window.reportQa.calls.push({
          at: Date.now(),
          bytes: init.body.byteLength ?? null,
          contentType: new Headers(init.headers).get('content-type'),
        });
        if (window.reportQa.forceFallback) {
          window.reportQa.forceFallback = false;
          return Promise.reject(new Error('Force Tauri postMessage in the isolated fixture'));
        }
      }
      return realFetch(input, init);
    };
  });

  const validation = await page.evaluate(async () => {
    const payload = new Uint8Array(1024 * 1024).fill(255);
    const headers = {'x-pilotodin-report-format': 'pdf', 'x-pilotodin-report-filename': 'Timing.pdf'};
    const measurements = [];
    for (let index = 0; index < 4; index++) {
      const start = performance.now();
      try {
        await window.__TAURI_INTERNALS__.invoke('save_report_as', payload.buffer, {headers});
        throw new Error('Invalid timing fixture unexpectedly reached Save As');
      } catch (error) {
        if (!String(error).includes('Report file content does not match its declared format')) throw error;
      }
      if (index > 0) measurements.push(Number((performance.now() - start).toFixed(2)));
    }
    const start = performance.now();
    const serialized = JSON.stringify({format: 'pdf', filename: 'Timing.pdf', bytes: Array.from(payload)});
    return {
      raw_bytes: payload.byteLength,
      former_json_bytes: new TextEncoder().encode(serialized).byteLength,
      former_js_encoding_ms: Number((performance.now() - start).toFixed(2)),
      raw_round_trip_validation_ms: measurements,
      raw_requests: window.reportQa.calls,
    };
  });
  assert.equal(validation.raw_requests.length, 4);
  for (const request of validation.raw_requests) {
    assert.equal(request.contentType, 'application/octet-stream');
    assert.equal(request.bytes, validation.raw_bytes);
  }
  console.log(JSON.stringify({case: 'transfer_without_dialog', ...validation}));

  for (const format of ['pdf', 'html', 'cancel']) {
    const args = ['-NoProfile', '-NonInteractive', '-File', PILOTODIN_SAVE_QA_DIALOG, '-AppId', PILOTODIN_SAVE_QA_PID];
    const filename = 'PilotODIN_P2_Synthetic.' + format;
    const output = join(PILOTODIN_SAVE_QA_OUTPUT, filename);
    if (format === 'cancel') args.push('-Cancel');
    else args.push('-Destination', output);
    await page.locator('#' + format).click();
    const observed = JSON.parse(execFileSync('powershell.exe', args, {encoding: 'utf8', timeout: 28000}));
    await page.waitForFunction(id => !document.getElementById(id).disabled &&
      document.getElementById(id + '-state').textContent.startsWith('PASS:'), format, {timeout: 12000});
    const request = await page.evaluate(() => window.reportQa.calls.at(-1));
    assert.equal(request.contentType, 'application/octet-stream');
    assert.ok(observed.observed_at >= request.at);
    const result = {
      case: format, bytes: request.bytes,
      invoke_to_dialog_observed_ms: observed.observed_at - request.at,
      dialog_observed_to_action_ms: observed.action_at - observed.observed_at,
    };
    if (format !== 'cancel') {
      const digest = bytes => createHash('sha256').update(bytes).digest('hex');
      const expected = await readFile(join('public', 'p2-native-fixtures', 'report.' + format));
      const saved = await readFile(output);
      assert.equal(digest(saved), digest(expected));
      assert.equal(request.bytes, expected.length);
      result.sha256_matched = true;
    }
    console.log(JSON.stringify(result));
  }
  await page.locator('#badextension').click();
  await page.waitForFunction(() => document.getElementById('badextension-state').textContent.startsWith('PASS:'));
  const callsBeforeFallback = await page.evaluate(() => {
    window.reportQa.forceFallback = true;
    return window.reportQa.calls.length;
  });
  await page.locator('#badcontent').click();
  await page.waitForFunction(() => document.getElementById('badcontent-state').textContent.startsWith('PASS:'));
  assert.equal(await page.evaluate(() => window.reportQa.calls.length), callsBeforeFallback + 1);
  assert.deepEqual((await readdir(PILOTODIN_SAVE_QA_OUTPUT)).sort(), [
    'PilotODIN_P2_Synthetic.html', 'PilotODIN_P2_Synthetic.pdf',
  ]);
  console.log('PASS: raw transfer, Windows Save As hashes, no-write cancellation, extension validation and postMessage content rejection.');
} finally {
  await browser.close();
}
