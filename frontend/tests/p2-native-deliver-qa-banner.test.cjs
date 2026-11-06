const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const source=fs.readFileSync(path.resolve(__dirname,'../src/p2NativeDeliverConsentQa.tsx'),'utf8');
const badgeStart=source.indexOf("const banner=document.createElement('aside');");
const badgeEnd=source.indexOf('document.body.appendChild(banner);',badgeStart);
assert.ok(badgeStart>=0&&badgeEnd>badgeStart,'actual synthetic QA badge source');
const badge=source.slice(badgeStart,badgeEnd);

test('native Deliver QA badge does not obscure the upper-right New project header action',()=>{
 assert.match(badge,/banner\.style\.cssText='position:fixed;z-index:99999;left:12px;bottom:8px;/);
 assert.doesNotMatch(badge,/right:\d+px|top:\d+px/);
 assert.match(badge,/pointer-events:none/);
 assert.match(badge,/banner\.textContent='SYNTHETIC QA - NO WRITES'/);
 assert.doesNotMatch(badge,/Test Deliver Leave|via the main rail and New project/);
});

test('the scoped QA badge retains status semantics and disposable native-only gating',()=>{
 assert.match(badge,/banner\.setAttribute\('role','status'\)/);
 assert.match(badge,/banner\.setAttribute\('aria-label','Synthetic native consent QA scope'\)/);
 assert.match(source,/import\.meta\.env\.DEV&&/);
 assert.match(source,/VITE_P2_NATIVE_DELIVER_QA==='1'/);
 assert.match(source,/location\.origin==='http:\/\/127\.0\.0\.1:5177'/);
 assert.match(source,/isDesktop\(\)/);
 assert.match(source,/!\['GET','HEAD'\]\.includes\(method\)/);
 assert.match(source,/document\.body\.appendChild\(banner\)/);
});
