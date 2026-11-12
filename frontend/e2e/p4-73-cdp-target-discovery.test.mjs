import test from 'node:test';
import assert from 'node:assert/strict';
import {discoverUniqueDevPage,hasTauriNativeBridge} from './p4-73-cdp-target-discovery.mjs';
const page = u=>({url:()=>u});
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
