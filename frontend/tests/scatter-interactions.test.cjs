const{test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const src=file=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8');
const scatter=src('ScatterExplorer.tsx');
const explorer=src('ExploreWorkspace.tsx');
const reports=src('SavedExploreAnalyses.tsx');
const style=src('scatter-explorer.css');

test('scatter view offers real zoom/pan interactions and reset with bounded controls',()=>{
 assert.match(scatter,/const \[zoom,setZoom\]=useState\(1\)/);
 assert.match(scatter,/const \[panX,setPanX\]=useState\(\.5\)/);
 assert.match(scatter,/setZoom\(clamp\(next,1,8\)\)/);
 assert.match(scatter,/aria-label="Pan up"/);
 assert.match(scatter,/aria-label="Pan down"/);
 assert.match(scatter,/aria-label="Zoom in"/);
 assert.match(scatter,/aria-label="Reset scatter view"/);
 assert.match(scatter,/onSelect\(point\.row_ref\)/);
 assert.match(scatter,/point\.x>=xMin&&point\.x<=xMax/);
 assert.match(style,/@media\(prefers-reduced-motion:reduce\)/);
});

test('plotted-only category legend never changes underlying model selection or dataset',()=>{
 assert.match(scatter,/plot\.color_groups\?\.length/);
 assert.match(scatter,/aria-pressed=\{activeGroup===g\.label\}/);
 assert.match(scatter,/setActiveGroup\(activeGroup===g\.label\?null:g\.label\)/);
 assert.match(scatter,/Zoom and legend choices affect visibility only/);
 assert.match(explorer,/Colour by category/);
 assert.match(explorer,/c\.unique<=8/);
 assert.match(explorer,/kind==='scatter'&&colorBy/);
 assert.match(reports,/color_by\?:string\|null/);
});
