const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/ExploreWorkspace.tsx'),'utf8');
const styles=fs.readFileSync(path.join(__dirname,'../src/explore-enhancements.css'),'utf8');

test('all three supported plot marks open a chart-specific local inspector',()=>{
 assert.match(source,/onSelect\(\{kind:'category',label:d\.label/);
 assert.match(source,/onSelect\(\{kind:'bin',bin_index:i\}\)/);
 assert.match(source,/onSelect\(\{kind:'point',row_ref:d\.row_ref\}\)/);
 assert.match(source,/aria-label="Selected chart records"/);
});

test('chart inspector never fetches records without a pinned selection and version',()=>{
 assert.match(source,/if\(!selection\|\|!overview\|\|!filterCatalog\|\|overview\.version!==filterCatalog\.version\)return/);
 assert.match(source,/post<InspectorResponse>\(`\/projects\/\$\{projectId\}\/explore\/inspect`/);
 assert.match(source,/expected_version:overview\.version,filters,x,y/);
 assert.match(source,/setSelection\(null\);setInspection\(null\);setInspectOffset\(0\)/);
 assert.match(source,/if\(!live\)return/);
});

test('inspector is read-only, paginated and keyboard accessible',()=>{
 assert.match(source,/READ-ONLY LOCAL PREVIEW/);
 assert.match(source,/limit:12/);
 assert.match(source,/Previous/);
 assert.match(source,/Next/);
 assert.match(source,/onKeyDown=\{e=>\{if\(d\.row_ref!==undefined/);
 assert.match(source,/role=\{d\.row_ref===undefined\?undefined:'button'\}/);
 assert.match(styles,/\.po-inspect-point:focus-visible/);
 assert.match(styles,/\.po-inspect-bar:focus-visible/);
});
