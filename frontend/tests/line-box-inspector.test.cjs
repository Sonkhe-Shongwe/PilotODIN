const{test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=(name)=>fs.readFileSync(path.join(__dirname,'../src',name),'utf8');
const source=read('ExploreWorkspace.tsx');
const css=read('explore-enhancements.css');

test('line charts let the user inspect a visible group by mouse and keyboard',()=>{
 assert.match(source,/kind:'line_category';label:string/);
 assert.match(source,/role="button" tabIndex=\{0\}/);
 assert.match(source,/onSelect\(\{kind:'line_category',label:d\.label\?\?''\}\)/);
 assert.match(source,/onKeyDown=\{event=>\{if\(event\.key==='Enter'\|\|event\.key===' '\)/);
 assert.match(source,/Select a point to inspect its finite-measure records/);
 assert.match(css,/\.po-inspect-line-point:hover,\.po-inspect-line-point:focus-visible/);
});
test('Tukey outlier markers expose a bounded individual-value inspection and full inlier/outlier actions',()=>{
 assert.match(source,/kind:'box_inliers'\|'box_outliers'/);
 assert.match(source,/kind:'box_outlier';value:number/);
 assert.match(source,/className="po-box-outlier"/);
 assert.match(source,/onSelect\(\{kind:'box_outlier',value:v\}\)/);
 assert.match(source,/onSelect\(\{kind:'box_inliers'\}\)/);
 assert.match(source,/onSelect\(\{kind:'box_outliers'\}\)/);
 assert.match(source,/disabled=\{!d\.outliers_total\}/);
 assert.match(css,/\.po-box-outlier:hover,\.po-box-outlier:focus-visible/);
});
test('row drill-down is pinned to an approved version and is reset after the chart changes',()=>{
 assert.match(source,/expected_version:overview\.version,filters,x,y/);
 assert.match(source,/selection,offset:inspectOffset,limit:12/);
 assert.match(source,/if\(value\.version!==overview\.version\)/);
 assert.match(source,/setSelection\(null\);setInspection\(null\);setInspectOffset\(0\)/);
});
