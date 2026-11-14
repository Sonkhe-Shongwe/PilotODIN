import test from 'node:test';
import assert from 'node:assert/strict';
import {diagnoseDevPage,discoverUniqueDevPage,hasTauriNativeBridge} from './p4-73-cdp-target-discovery.mjs';
const page = u=>({url:()=>u,evaluate:async()=>true});
const wanted=page('http://127.0.0.1:5173/#/studio/prepare');
const empty=page('about:blank');
const unrelated=page('https://example.org/secret?token=private-data');

test('delayed genuine target is selected only when it appears',async()=>{
  let polls=0,waits=0;
  const res=await discoverUniqueDevPage(()=>++polls<3?[empty]:[empty,wanted],()=>{waits++});
  assert.equal(res.status,'FOUND');assert.equal(res.page,wanted);
  assert.equal(res.attempts,3);assert.equal(waits,2);
});
test('missing target exhausts strictly bounded attempts with redacted classifications',async()=>{
  let polls=0,waits=0;
  const res=await discoverUniqueDevPage(()=>{polls++;return [unrelated,empty]},()=>{waits++},4);
  assert.equal(res.status,'BLOCKED_NO_TARGET');assert.equal(polls,4);assert.equal(waits,3);
  assert.deepEqual(res.classes,['blank','other-web-origin']);
  assert.ok(!JSON.stringify(res).includes('private-data'));
});
test('ambiguous target refuses without waiting or selecting one',async()=>{
  let waits=0;
  const res=await discoverUniqueDevPage(()=>[wanted,page('http://127.0.0.1:5173/index.html')],()=>{waits++});
  assert.equal(res.status,'BLOCKED_AMBIGUOUS');assert.equal(waits,0);assert.equal(res.page,undefined);
});
test('spoofed near matching host is never accepted',async()=>{
  const res=await discoverUniqueDevPage(()=>[page('http://127.0.0.1:5173.evil.example/')],async()=>{},1);
  assert.equal(res.status,'BLOCKED_NO_TARGET');
});
test('invalid source and invalid attempt count are blocked',async()=>{
  const res=await discoverUniqueDevPage(()=>null,()=>{},1);
  assert.equal(res.status,'BLOCKED_INVALID_SNAPSHOT');
  await assert.rejects(discoverUniqueDevPage(()=>[],()=>{},21),/invalid bounded/);
});
test('an expected page is retried until its native bridge is callable',async()=>{
  let checks=0,waits=0;
  const late={...wanted,evaluate:async()=>++checks===3};
  const res=await discoverUniqueDevPage(()=>[late],()=>{waits++},4);
  assert.equal(res.status,'FOUND');
  assert.equal(res.page,late);
  assert.equal(res.attempts,3);
  assert.equal(waits,2);
});
test('a browser page at the expected URL stays blocked without a bridge',async()=>{
  const noBridge={...wanted,evaluate:async()=>false};
  const res=await discoverUniqueDevPage(()=>[noBridge],()=>{},2);
  assert.equal(res.status,'BLOCKED_BRIDGE_UNVERIFIED');
  assert.equal(res.page,undefined);
  assert.equal(res.attempts,2);
});
test('ambiguity is refused even after a prior single page without a bridge',async()=>{
  const noBridge={...wanted,evaluate:async()=>false};
  let polls=0;
  const res=await discoverUniqueDevPage(()=>++polls===1?[noBridge]:[noBridge,wanted],()=>{},3);
  assert.equal(res.status,'BLOCKED_AMBIGUOUS');
  assert.equal(res.page,undefined);
});
test('a page that leaves the approved development origin cannot be returned',async()=>{
  let url=wanted.url();
  const moved={url:()=>url,evaluate:async()=>{url=unrelated.url();return true;}};
  const res=await discoverUniqueDevPage(()=>[moved],()=>{},2);
  assert.equal(res.status,'BLOCKED_BRIDGE_UNVERIFIED');
  assert.equal(res.page,undefined);
});
test('native bridge must exist and supply actual callable invoke',async()=>{
  const original=globalThis.window;
  try {
    globalThis.window={};
    assert.equal(await hasTauriNativeBridge({evaluate:async fn=>fn()}),false);
    globalThis.window={__TAURI_INTERNALS__:{invoke:'not-callable'}};
    assert.equal(await hasTauriNativeBridge({evaluate:async fn=>fn()}),false);
    globalThis.window={__TAURI_INTERNALS__:{invoke:()=>{}}};
    assert.equal(await hasTauriNativeBridge({evaluate:async fn=>fn()}),true);
    assert.equal(await hasTauriNativeBridge({evaluate:async()=>{throw Error('page not ready')}}),false);
  } finally {
    if(original===undefined)delete globalThis.window;
    else globalThis.window=original;
  }
});

test('blocked discovery compares the dev server with debugger page categories', async () => {
  const called = [];
  const result = await diagnoseDevPage(async (url, options) => {
    called.push(url);
    assert.equal(options.redirect, 'error');
    assert.ok(options.signal instanceof AbortSignal);
    if (url.endsWith(':5173/')) return new Response('private response body');
    return Response.json([
      {type: 'page', url: 'http://127.0.0.1:5173/#/studio/prepare', title: 'private title'},
      {type: 'page', url: 'https://example.org/private-path?token=private-query'},
      {type: 'service_worker', url: 'https://example.org/private-worker'},
    ]);
  });
  assert.deepEqual(called, ['http://127.0.0.1:5173/', 'http://127.0.0.1:9331/json/list']);
  assert.deepEqual(result, {
    devServer: {httpStatus: 200},
    debuggerList: {
      httpStatus: 200,
      pageCount: 2,
      otherTargetCount: 1,
      pageClasses: ['expected-5173-root', 'other-web-origin'],
    },
  });
  assert.doesNotMatch(JSON.stringify(result), /private/);
});

test('failed loopback requests report statuses without exposing request errors', async () => {
  const result = await diagnoseDevPage(async (url) => {
    if (url.endsWith(':5173/')) throw new DOMException('private error', 'TimeoutError');
    return new Response('private debugger error', {status: 503});
  });
  assert.deepEqual(result, {devServer: {status: 'timeout'}, debuggerList: {httpStatus: 503}});
});

test('empty and unreadable debugger results are distinct from a server failure', async () => {
  for (const [response, expected] of [
    [Response.json([]), {pageCount: 0, otherTargetCount: 0, pageClasses: []}],
    [Response.json({}), {status: 'invalid'}],
    [new Response('invalid JSON'), {status: 'unreadable'}],
  ]) {
    const result = await diagnoseDevPage(async (url) => {
      if (url.endsWith(':5173/')) throw new TypeError('private error');
      return response;
    });
    assert.deepEqual(result, {
      devServer: {status: 'unavailable'},
      debuggerList: {httpStatus: 200, ...expected},
    });
  }
});
