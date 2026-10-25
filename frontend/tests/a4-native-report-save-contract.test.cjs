const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'..');
const source=n=>fs.readFileSync(path.join(root,'src',n),'utf8');
const native=n=>fs.readFileSync(path.join(root,'src-tauri',n),'utf8');

test('A4 Tauri Save As plugin stays Rust-side behind an explicit command',()=>{
 const cargo=native('Cargo.toml');
 const rust=native('src/lib.rs');
 const capabilities=JSON.parse(native('capabilities/default.json'));
 assert.match(cargo,/tauri-plugin-dialog\s*=\s*"2"/);
 assert.match(rust,/\.plugin\(tauri_plugin_dialog::init\(\)\)/);
 assert.match(rust,/fn save_report_as\(/);
 assert.match(rust,/tauri::generate_handler!\[launch_backend, launch_bundled_ai, save_report_as\]/);
 assert.deepEqual(capabilities.permissions,['core:default']);
});

test('Native save is type-restricted and returns cancel without a write',()=>{
 const rust=native('src/lib.rs');
 assert.match(rust,/MAX_REPORT_EXPORT_BYTES:\s*usize\s*=\s*12\s*\*\s*1024\s*\*\s*1024/);
 assert.match(rust,/check_report_payload\(&format, &filename, &bytes\)/);
 assert.match(rust,/bytes\.starts_with\(b"%PDF-"\)/);
 assert.match(rust,/b"<!doctype html>"/);
 assert.match(rust,/\.blocking_save_file\(\)/);
 assert.match(rust,/status:\s*"cancelled"/);
 const cancelPos=rust.indexOf('status: "cancelled"');
 const writePos=rust.indexOf('std::fs::write(&path, &bytes)');
 assert.ok(cancelPos > 0 && cancelPos < writePos,'Cancel must resolve before file writing');
 assert.match(rust,/Saved report size verification failed/);
 assert.match(rust,/Sha256::digest\(&bytes\)/);
 assert.match(rust,/saved_hash\[\.\.\] != expected_hash\[\.\.\]/);
});

test('Browser and native report export flows are explicitly distinct',()=>{
 const ui=source('ReportWorkspace.tsx'),api=source('api.ts');
 assert.match(ui,/if\(isDesktop\(\)\)/);
 assert.match(ui,/await saveReportNative\(blob,filename,format\)/);
 assert.match(ui,/outcome\.status==='cancelled'/);
 assert.match(ui,/Started browser download/);
 assert.match(api,/if\(!\('__TAURI_INTERNALS__' in window\)\)/);
 assert.match(api,/invoke<NativeReportSaveStatus>\('save_report_as',\{format,filename,bytes\}\)/);
});
