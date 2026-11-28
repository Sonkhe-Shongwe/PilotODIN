const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/SavedExploreAnalyses.tsx'),'utf8');
const motion=fs.readFileSync(path.join(__dirname,'../src/revealRecordInspector.ts'),'utf8');
const css=fs.readFileSync(path.join(__dirname,'../src/saved-explore-analyses.css'),'utf8');

test('Open reveals the saved history panel only after its detail is mounted',()=>{
 assert.match(source,/import \{useEffect,useLayoutEffect,useRef,useState\} from 'react'/);
 assert.match(source,/const frozenRef=useRef<HTMLDivElement\|null>\(null\)/);
 assert.match(source,/const \[openRevealSequence,setOpenRevealSequence\]=useState\(0\)/);
 assert.match(source,/setSelected\(saved\);\s*setOpenRevealSequence\(n=>n\+1\)/);
 assert.match(source,/useLayoutEffect\(\(\)=>\{\s*if\(!openRevealSequence\|\|!selected\)return/);
 assert.match(source,/window\.requestAnimationFrame\(\(\)=>\{\s*if\(frozenRef\.current\)cancel=revealWorkspaceSection\(frozenRef\.current\)/);
 assert.match(source,/window\.cancelAnimationFrame\(frame\);cancel\(\)/);
 assert.match(source,/\},\[openRevealSequence,selected\?\.id\]\)/);
});

test('Repeated Open works and Save never automatically jumps',()=>{
 const open=source.slice(source.indexOf('async function openSaved('),source.indexOf('\n return <section'));
 const save=source.slice(source.indexOf('async function saveCurrent('),source.indexOf('async function openSaved('));
 assert.match(open,/setOpenRevealSequence\(n=>n\+1\)/);
 assert.doesNotMatch(save,/setOpenRevealSequence\(/);
 assert.match(source,/ref=\{frozenRef\} tabIndex=\{-1\} aria-label=\{\`Saved history:/);
 assert.match(source,/aria-label=\{\`Open \$\{item\.title\} and jump to saved history\`\}/);
 assert.match(css,/\.po-saved-frozen\{[^}]*scroll-margin-top:28px/);
});

test('Revealing history scrolls its containing pane and respects system motion settings',()=>{
 assert.match(motion,/export const revealWorkspaceSection = revealRecordInspector/);
 assert.match(motion,/prefers-reduced-motion: reduce/);
 assert.match(motion,/panel\.scrollIntoView\(\{behavior:'auto',block:'start',inline:'nearest'\}\)/);
 assert.match(motion,/scrollContainer\.scrollTop=start\+distance\*eased/);
 assert.match(motion,/scrollContainer\.addEventListener\('wheel',cleanup/);
 assert.match(motion,/scrollContainer\.addEventListener\('pointerdown',cleanup/);
});
