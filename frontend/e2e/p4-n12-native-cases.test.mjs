import { existsSync, readFileSync } from 'node:fs';
import { copyFile, mkdir, mkdtemp, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { isN12Peer, matchesN12LifecycleRequest } from './p4-n12-native-cases.mjs';

const api = 'http://127.0.0.1:8000/api';
const id = 'a'.repeat(32);
const url = `${api}/projects/${id}/lifecycle`;
const permit = { id, action: 'archive', revision: 0 };
const request = (body, target = url, method = 'PUT') => ({
  method: () => method, url: () => target, postDataJSON: () => body,
});

test('only the exact revisioned peer mutation is eligible for the native route', () => {
  const body = { action: 'archive', expected_revision: 0 };
  assert.equal(matchesN12LifecycleRequest(request(body), api, permit), true);
  for (const candidate of [
    request({ ...body, name: 'unexpected' }), request({ ...body, expected_revision: '0' }),
    request({ ...body, action: 'restore' }), request(null), request(body, url + '?bypass=1'),
    request(body, url.replace(id, 'b'.repeat(32))), request(body, url, 'POST'),
  ]) {
    assert.equal(matchesN12LifecycleRequest(candidate, api, permit), false);
  }
  assert.equal(matchesN12LifecycleRequest(request(body), api, null), false);
});

test('only the exact same-origin peer URL is excluded from primary discovery', () => {
  const peer = 'http://127.0.0.1:5173/p4_n12_lifecycle_peer.html';
  const stage = readFileSync(new URL('../../qa/p4_research/n12_app_build.py', import.meta.url), 'utf8');
  assert.ok(stage.includes(JSON.stringify(peer)));
  assert.equal(isN12Peer({ url: () => peer }), true);
  for (const other of [
    peer.replace('127.0.0.1', 'localhost'), peer.replace('5173', '5178'),
    peer + '?other=1', 'http://127.0.0.1:5173/',
  ]) {
    assert.equal(isN12Peer({ url: () => other }), false);
  }
});

test('the Vite config runner loads the QA configuration without a temporary bundle', async () => {
  const { resolveConfig } = await import('vite');
  const vite = fileURLToPath(new URL('../node_modules/vite', import.meta.url));
  const configuration = new URL('../vite.config.ts', import.meta.url);
  const scratch = await mkdtemp(join(tmpdir(), 'pilotodin-n12-vite-'));
  try {
    for (const configLoader of ['bundle', 'runner']) {
      const root = join(scratch, configLoader);
      const dependencies = join(root, 'node_modules');
      const configFile = join(root, 'vite.config.ts');
      await mkdir(dependencies, { recursive: true });
      await symlink(vite, join(dependencies, 'vite'), 'junction');
      await writeFile(join(root, 'package.json'), JSON.stringify({ type: 'module' }));
      await copyFile(configuration, configFile);

      const config = await resolveConfig({ root, configLoader }, 'serve');

      assert.equal(await realpath(config.configFile), await realpath(configFile));
      assert.deepEqual(config.server.watch.ignored, ['**/src-tauri/target', '**/src-tauri/target/**']);
      assert.equal(existsSync(join(dependencies, '.vite-temp')), configLoader === 'bundle');
    }
  } finally {
    await rm(scratch, { recursive: true, force: true });
  }
});
