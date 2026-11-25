// Disposable metadata-only C5 tests. No npm, build, or executable launch.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const root = path.resolve(__dirname,"..");
const load = () => import("../scripts/verify-npm-lock.mjs");

function fixture(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(),"pilotodin-c5-npm-"));
  t.after(() => fs.rmSync(dir,{recursive:true,force:true}));
  for (const name of ["package.json","package-lock.json"]) fs.copyFileSync(path.join(root,name),path.join(dir,name));
  const lockPath = path.join(dir,"package-lock.json");
  const lock = JSON.parse(fs.readFileSync(lockPath,"utf8"));
  const save = () => fs.writeFileSync(lockPath,JSON.stringify(lock));
  return {dir,lock,save,lockPath};
}
test("current checked-in lock passes without mutation", async () => {
  const {verifyLock}=await load();
  const p=path.join(root,"package-lock.json");
  const before=fs.readFileSync(p);
  assert.ok(Object.keys(verifyLock(root)).length>1);
  assert.deepEqual(fs.readFileSync(p),before);
});
for (const [label,mutate] of [
  ["missing lock", f=>fs.unlinkSync(f.lockPath)],
  ["malformed lock", f=>fs.writeFileSync(f.lockPath,"{")],
  ["duplicate key", f=>fs.writeFileSync(f.lockPath,'{"lockfileVersion":3,"lockfileVersion":3}')],
  ["manifest drift", f=>{f.lock.packages[""].dependencies.react="^18";f.save()}],
  ["missing integrity", f=>{delete f.lock.packages["node_modules/react"].integrity;f.save()}],
  ["unreviewed registry", f=>{f.lock.packages["node_modules/react"].resolved="https://example.invalid/react.tgz";f.save()}],
  ["unsafe path", f=>{f.lock.packages["node_modules/../react"]=f.lock.packages["node_modules/react"];f.save()}],
  ["missing dependency", f=>{delete f.lock.packages["node_modules/react"];f.save()}],
  ["missing Windows optional package", f=>{delete f.lock.packages["node_modules/@esbuild/win32-x64"];f.save()}],
  ["wrong Windows optional selector", f=>{f.lock.packages["node_modules/@rollup/rollup-win32-x64-msvc"].cpu=["arm64"];f.save()}],
  ["invalid digest", f=>{f.lock.packages["node_modules/react"].integrity="sha512-AAAA";f.save()}],
]) {
  test("refuses "+label+" without repair",async t=>{
    const f=fixture(t);mutate(f);
    const before=fs.existsSync(f.lockPath)?fs.readFileSync(f.lockPath):null;
    const {verifyLock}=await load();
    assert.throws(()=>verifyLock(f.dir));
    assert.deepEqual(fs.existsSync(f.lockPath)?fs.readFileSync(f.lockPath):null,before);
  });
}
function stageMetadata(f) {
  const platformNative=new Set(["node_modules/@esbuild/win32-x64","node_modules/@rollup/rollup-win32-x64-msvc","node_modules/@tauri-apps/cli-win32-x64-msvc"]);
  for(const [key,p] of Object.entries(f.lock.packages)) {
    if(!key || (p.optional && !platformNative.has(key)))continue;
    const dir=path.join(f.dir,...key.split("/"));fs.mkdirSync(dir,{recursive:true});
    fs.writeFileSync(path.join(dir,"package.json"),JSON.stringify({name:key.slice("node_modules/".length),version:p.version}));
  }
  fs.mkdirSync(path.join(f.dir,"node_modules",".bin"),{recursive:true});
  fs.writeFileSync(path.join(f.dir,"node_modules",".bin","vite.cmd"),"synthetic metadata fixture");
}
test("Windows x64 existing metadata and mandatory platform inputs",async t=>{
  const f=fixture(t);stageMetadata(f);
  const {verifyInstalled}=await load();
  assert.ok(verifyInstalled(f.dir,"win32","x64"));
  assert.throws(()=>verifyInstalled(f.dir,"win32","arm64"),/UNSUPPORTED_DEV_PLATFORM/);
  fs.writeFileSync(path.join(f.dir,"node_modules","react","package.json"),JSON.stringify({name:"react",version:"0.0.0"}));
  assert.throws(()=>verifyInstalled(f.dir,"win32","x64"),/INSTALLED_PACKAGE_VERSION_MISMATCH/);
});
test("refuses absent required installed Windows package",async t=>{
  const f=fixture(t);stageMetadata(f);
  fs.rmSync(path.join(f.dir,"node_modules","@esbuild","win32-x64"),{recursive:true});
  const {verifyInstalled}=await load();
  assert.throws(()=>verifyInstalled(f.dir,"win32","x64"));
});
