import test from 'node:test';
import assert from 'node:assert/strict';
import {isExpectedDevPage,safeTargetClass} from './p4-72-cdp-target-classifier.mjs';
test('accept only real loopback development root and index',()=>{
 for(const u of ['http://127.0.0.1:5173/','http://127.0.0.1:5173/index.html','http://127.0.0.1:5173/#/studio/prepare'])assert.equal(isExpectedDevPage(u),true);
});
test('refuse nonmatching protocol host port or path',()=>{
 for(const u of ['about:blank','http://localhost:5173/','http://127.0.0.1:8000/','http://127.0.0.1:5173/other','https://127.0.0.1:5173/','http://127.0.0.1:5173.evil.test/','not-a-url'])assert.equal(isExpectedDevPage(u),false,u);
});
test('classifies target types without exposing path or query',()=>{
 assert.equal(safeTargetClass('about:blank'),'blank');
 assert.equal(safeTargetClass('http://localhost:5173/private?token=secret'),'localhost-5173-alias');
 assert.equal(safeTargetClass('https://example.org/private?token=secret'),'other-web-origin');
 assert.equal(safeTargetClass('http://127.0.0.1:5173/another?token=secret'),'nonroot-5173-target');
 assert.equal(safeTargetClass('https://tauri.localhost/private'),'tauri-localhost');
 assert.equal(safeTargetClass('garbage'),'unknown-target');
});
