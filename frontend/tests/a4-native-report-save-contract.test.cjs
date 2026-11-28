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
 assert.match(cargo,/tauri-plugin-dialog\s*=\s*"=2\.8\.4"/); // Pinned previously compiled Tauri v2 dialog.
 assert.match(rust,/\.plugin\(tauri_plugin_dialog::init\(\)\)/);
 assert.match(rust,/fn save_report_as\(/);
 assert.match(rust,/tauri::generate_handler!\[\s*launch_backend, launch_bundled_ai, save_report_as\b/);
 assert.deepEqual(capabilities.permissions,['core:default']);
});

test('Native save is type-restricted and returns cancel without a write',()=>{
 const rust=native('src/lib.rs');
 assert.match(rust,/MAX_REPORT_EXPORT_BYTES:\s*usize\s*=\s*12\s*\*\s*1024\s*\*\s*1024/);
 assert.match(rust,/check_report_payload\(format, &filename, &bytes\)/);
 assert.match(rust,/bytes\.starts_with\(b"%PDF-"\)/);
 assert.match(rust,/b"<!doctype html>"/);
 assert.match(rust,/\.blocking_save_file\(\)/);
 assert.match(rust,/status:\s*"cancelled"/);
 const command=rust.split('async fn save_report_as(')[1]?.split('fn write_verified_report(')[0];
 const writer=rust.split('fn write_verified_report(')[1]?.split('#[cfg(test)]')[0];
 assert.ok(command&&writer);
 const cancel=command.indexOf('status: "cancelled"');
 assert.ok(cancel>=0&&cancel<command.indexOf('write_verified_report(&path, &format, &bytes)'));
 const publish=writer.indexOf('report_file::publish_report(path, bytes,');
 assert.ok(publish>=0&&publish<writer.indexOf('status: "saved"'));
 assert.doesNotMatch(writer,/std::fs::write\(/);
 const file=native('src/report_file.rs');
 assert.match(file,/path\.with_file_name\(/);
 assert.match(file,/\.create_new\(true\)/);
 assert.match(file,/file\.sync_all\(\)/);
 assert.match(file,/file\.read_exact\(actual_chunk\)/);
 assert.match(file,/if &\*actual_chunk != expected_chunk/);
 assert.match(file,/verified\.and_then\(\|\(\)\| fs::rename\(&staging, path\)\)/);
 assert.doesNotMatch(file.split('#[cfg(test)]')[0],/fs::remove_file\(path\)|fs::copy\(/);
});

test('Browser and native report export flows are explicitly distinct',()=>{
 const ui=source('ReportWorkspace.tsx'),api=source('api.ts');
 assert.match(ui,/if\(isDesktop\(\)\)/);
 assert.match(ui,/await saveReportNative\(blob,filename,format\)/);
 assert.match(ui,/outcome\.status==='cancelled'/);
 assert.match(ui,/Started browser download/);
 assert.match(api,/if\(!\('__TAURI_INTERNALS__' in window\)\)/);
 const transfer=api.slice(api.indexOf('export async function saveReportNative'));
 assert.match(transfer,/const bytes=await blob\.arrayBuffer\(\)/);
 assert.match(transfer,/invoke<NativeReportSaveStatus>\('save_report_as',bytes,\{/);
 assert.match(transfer,/'x-pilotodin-report-filename':encodeURIComponent\(filename\)/);
 assert.doesNotMatch(transfer,/Array\.from/);
 assert.match(native('src/lib.rs'),/InvokeBody::Raw\(bytes\) => Ok\(Cow::Borrowed\(bytes\)\)/);
});
