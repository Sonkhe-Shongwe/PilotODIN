import { readFileSync } from 'node:fs';
import { test } from 'node:test';
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
