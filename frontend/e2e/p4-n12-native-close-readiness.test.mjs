import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readBrowserProcessId, waitForNativeCloseRegistration } from './p4-n12-native-close-readiness.mjs';

test('close readiness requires the mounted shell and registration acknowledgement', async () => {
  let release;
  let completed = false;
  const page = {
    locator(selector) {
      assert.equal(selector, '.po-unified-shell[data-native-close-ready="true"]');
      return {
        waitFor(options) {
          assert.deepEqual(options, { state: 'visible', timeout: 30_000 });
          return new Promise(resolve => { release = resolve; });
        },
      };
    },
  };
  const ready = waitForNativeCloseRegistration(page).then(() => { completed = true; });
  assert.equal(completed, false);
  release();
  await ready;
  assert.equal(completed, true);
});

test('registration timeout propagates and cannot start the close sequence', async () => {
  const page = { locator: () => ({ waitFor: async () => { throw Error('registration missing'); } }) };
  await assert.rejects(waitForNativeCloseRegistration(page), /registration missing/);
});

test('browser identity requires exactly one positive browser PID from the browser session', async () => {
  const browserFor = processInfo => ({
    newBrowserCDPSession: async () => ({
      send: async method => {
        assert.equal(method, 'SystemInfo.getProcessInfo');
        return { processInfo };
      },
    }),
  });
  const browser = { type: 'browser', id: 12 };
  assert.equal(await readBrowserProcessId(browserFor([{ type: 'renderer', id: 13 }, browser])), 12);
  assert.equal(await readBrowserProcessId(browserFor([browser, { ...browser, id: 14 }])), null);
  assert.equal(await readBrowserProcessId(browserFor([{ ...browser, id: '12' }])), null);
  assert.equal(await readBrowserProcessId(browserFor(null)), null);
});

test('unavailable browser identity does not block the close probe', async () => {
  const rejected = { newBrowserCDPSession: async () => { throw Error('unsupported'); } };
  assert.equal(await readBrowserProcessId(rejected), null);
  const stalled = { newBrowserCDPSession: () => new Promise(() => {}) };
  assert.equal(await readBrowserProcessId(stalled, 5), null);
});

test('the QA acknowledgement follows successful native listener registration', () => {
  const shell = readFileSync(new URL('../src/UnifiedShell.tsx', import.meta.url), 'utf8');
  assert.match(shell, /listen<NativeCloseRequest>\(NATIVE_CLOSE_EVENT,[\s\S]+?\.then\(stop=>\{\s*if\(disposed\)stop\(\);\s*else\s*\{\s*unlisten=stop;\s*if\(isNativeA4SmokeMode\(\)\)setNativeCloseRegistered\(true\);/);
  assert.ok(shell.includes('data-native-close-ready={isNativeA4SmokeMode()&&nativeCloseRegistered?'));
});
