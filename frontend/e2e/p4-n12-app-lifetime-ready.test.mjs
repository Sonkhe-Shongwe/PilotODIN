import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const script = fileURLToPath(new URL('./p4-n12-app-lifetime-ready.mjs', import.meta.url));
const hosted = {
  CI: 'true',
  GITHUB_ACTIONS: 'true',
  RUNNER_OS: 'Windows',
  RUNNER_ENVIRONMENT: 'github-hosted',
  GITHUB_RUN_ATTEMPT: '1',
};
const lifetimeConsent = {
  PILOTODIN_N12_APP_LIFETIME_CONSENT: 'I_APPROVE_ONE_N12_APP_LIFETIME',
};
const storageConsent = {
  PILOTODIN_N12_WEBVIEW_STORAGE_CONSENT: 'I_APPROVE_ONE_N12_WEBVIEW_STORAGE',
};

function checkConsent(scope, consent, environment = hosted) {
  const env = { SYSTEMROOT: process.env.SYSTEMROOT ?? '', ...environment, ...consent };
  const result = spawnSync(process.execPath, [script, scope, '--check-consent'], {
    encoding: 'utf8',
    env,
    timeout: 10_000,
  });
  assert.ifError(result.error);
  return result;
}

test('both native readiness scopes accept their own consent without contacting CDP', () => {
  for (const [scope, consent] of [['lifetime', lifetimeConsent], ['webview-storage', storageConsent]]) {
    const result = checkConsent(scope, consent);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), 'N12 native readiness consent preflight passed');
  }
});

test('each native readiness scope rejects missing and cross-scope consent', () => {
  for (const [scope, wrongConsent] of [['lifetime', storageConsent], ['webview-storage', lifetimeConsent]]) {
    for (const consent of [{}, wrongConsent]) {
      const result = checkConsent(scope, consent);
      assert.equal(result.status, 1);
      assert.match(result.stderr, /requires the approved hosted fixture/);
    }
  }
});

test('native readiness rejects a rerun even with matching consent', () => {
  const result = checkConsent('webview-storage', storageConsent, { ...hosted, GITHUB_RUN_ATTEMPT: '2' });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /requires the approved hosted fixture/);
});

test('native readiness rejects an unknown scope', () => {
  const result = checkConsent('other', { ...lifetimeConsent, ...storageConsent });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Invalid native readiness probe arguments/);
});
