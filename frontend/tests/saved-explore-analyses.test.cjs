const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const load=(file)=>fs.readFileSync(path.join(__dirname,'../src',file),'utf8');
const explore=load('ExploreWorkspace.tsx');
const views=load('SavedExploreAnalyses.tsx');
const css=load('saved-explore-analyses.css');

test('Explore includes project/version-scoped saved analysis with the live chart configuration',()=>{
 assert.match(explore,/import \{SavedExploreAnalyses\}/);
 assert.match(explore,/<SavedExploreAnalyses projectId=\{projectId\} version=\{overview\?\.version\?\?null\}/);
 assert.match(explore,/configuration=\{\{x,y:y\|\|null,kind,aggregation,bins,correlation_method:corrMethod,filters,color_by:/);
 assert.match(explore,/onRestore=\{restoreSaved\}/);
 assert.match(explore,/function restoreSaved\(config:ExploreState\)/);
 assert.match(explore,/setFilters\(config\.filters as FilterClause\[\]\)/);
});

test('save persists title/version/config, then reopens a server-scoped frozen snapshot',()=>{
 assert.match(views,/\/projects\/\$\{projectId\}\/explore\/saved/);
 assert.match(views,/expected_version:version,\.\.\.configuration/);
 assert.match(views,/Saved analyses and evidence/);
 assert.match(views,/SHA-256/);
 assert.match(views,/result\.sha256|selected\.sha256/);
 assert.match(views,/Saved investigation library/);
 assert.match(views,/const refreshed=await get<SavedSummary\[\]>/);
 assert.match(views,/setList\(refreshed\)/);
});

test('historical snapshots are preview only, not silently applied to current working data',()=>{
 assert.match(views,/if\(saved\.configuration_verified&&!saved\.stale&&saved\.dataset_version===version\)/);
 assert.match(views,/onRestore\(saved\.configuration\)/);
 assert.match(views,/Historical snapshot opened read-only/);
 assert.match(views,/Live filters and charts have not changed/);
 assert.match(views,/HISTORICAL SNAPSHOT/);
 assert.match(views,/LEGACY · UNVERIFIED SETTINGS/);
 assert.match(views,/disabled=\{busy!==''\|\|!selected\.configuration_verified\}/);
 assert.match(views,/cannot be restored or attached as verified report evidence/);
 assert.match(views,/not recalculated on the current data/);
});

test('save is disabled during incomplete or invalid live calculations and UI remains responsive',()=>{
 assert.match(views,/disabled=\{!ready\|\|version===null\|\|title\.trim\(\)\.length<4\|\|busy!==''\}/);
 assert.match(explore,/ready=\{!!filteredOverview&&!loading&&!error&&!!filterCatalog&&filterCatalog\.version===overview\?\.version\}/);
 assert.match(css,/@media\(max-width:710px\)/);
});

test('saved library shows integrity status before an item is opened',()=>{
 assert.match(views,/item\.results_valid===false\?'Integrity error · unavailable'/);
 assert.match(views,/item\.configuration_verified===false\?'Legacy · settings unverified'/);
 assert.match(views,/disabled=\{busy!==''\|\|item\.results_valid===false\}/);
 assert.match(views,/Current verified version/);
 assert.match(views,/Historical verified version/);
});


test('delayed saved analysis HTTP replies cannot cross a project or dataset-version transition',()=>{
 const reset=views.slice(views.indexOf('useEffect(()=>{'),views.indexOf('// Navigation belongs'));
 assert.match(reset,/const request=\+\+generation\.current/);
 assert.match(reset,/return\(\)=>\{generation\.current\+\+\}/);
 assert.match(reset,/if\(generation\.current===request\)setList\(result\)/);
 const save=views.slice(views.indexOf('async function saveCurrent('),views.indexOf('async function openSaved('));
 const open=views.slice(views.indexOf('async function openSaved('),views.indexOf('\n return <section'));
 for(const block of [save,open]){
  assert.match(block,/const request=generation\.current/);
  assert.match(block,/if\(generation\.current!==request\)return/);
  assert.match(block,/catch\(e\)\{if\(generation\.current===request\)setError/);
  assert.match(block,/finally\{if\(generation\.current===request\)setBusy\(''\)\}/);
 }
 assert.match(save,/result\.project_id!==projectId\|\|result\.dataset_version!==version/);
 assert.match(save,/const refreshed=await get<SavedSummary\[\]>/);
 assert.match(save,/if\(generation\.current!==request\)return;\s*setList\(refreshed\)/);
 assert.match(open,/if\(saved\.project_id!==projectId\)throw new Error/);
 assert.match(open,/if\(generation\.current!==request\)return;\s*if\(saved\.project_id!==projectId\)/);
 assert.match(open,/if\(saved\.configuration_verified&&!saved\.stale&&saved\.dataset_version===version\)/);
 assert.match(open,/onRestore\(saved\.configuration\)/);
});
