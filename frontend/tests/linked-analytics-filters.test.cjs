const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const read=name=>fs.readFileSync(path.join(__dirname,'../src',name),'utf8');
const explore=read('ExploreWorkspace.tsx');

test('Explore computes chart, metrics and correlation through one version-pinned request',()=>{
 assert.match(explore,/post<Workbench>\(`\/projects\/\$\{projectId\}\/explore\/workbench`/);
 assert.match(explore,/expected_version:overview\.version,filters/);
 assert.match(explore,/setPlot\(value\.chart\)/);
 assert.match(explore,/setCorrelation\(value\.correlation\)/);
 assert.match(explore,/setFilteredOverview\(value\.overview\)/);
 assert.match(explore,/setFilteredRows\(value\.filtered_rows\)/);
 assert.doesNotMatch(explore,/get<Plot>\(/);
});

test('Filters are bounded, reset on dataset changes, and do not alter project data',()=>{
 assert.match(explore,/setFilterCatalog\(null\);setFilters\(\[\]\)/);
 assert.match(explore,/filters\.length>=4/);
 assert.match(explore,/\[projectId,versionToken\]/);
 assert.match(explore,/Add filter/);
 assert.match(explore,/Clear filters/);
 assert.match(explore,/No corrections are applied/);
});

test('UI distinguishes filtered metrics from full-data suggestions and empty charts',()=>{
 assert.match(explore,/FILTERED RECORDS/);
 assert.match(explore,/No rows match these filters|chartMessage/);
 assert.match(explore,/Recommendations and proactive insights below describe the full working dataset/);
 assert.match(explore,/setPlot\(null\);setCorrelation\(null\);setFilteredOverview\(null\)/);
});
