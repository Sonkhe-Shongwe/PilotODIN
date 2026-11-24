# Source-only. Parse; never execute Cargo, PowerShell script bodies or application.
require 'psych'
require 'digest'
require 'open3'
WORKFLOW = ".github/workflows/p4-c1-c2-owned-host-once.yml"
SCRIPT = "qa/c1_c2_owned_host_preflight.rb"
DISABLED = "    if: ${{ false }} # DISARMED OWNED HOST; fresh exact approval required.\n"
ARMED = "    if: >-\n      ${{ github.run_attempt == 1 && github.event_name == 'push' && github.ref == 'refs/heads/feature/live-dev-workspace-20261023' && github.event.head_commit.message == 'C1-OWNED-HOST-MANIFEST-20261125-ONE-USE' }}\n"
MARKER = "C1-OWNED-HOST-MANIFEST-20261125-ONE-USE"
PRODUCT = "1d23ea139762d94d25e689c4c3489b72fb34acc9"
BRANCH = "feature/live-dev-workspace-20261023"
JOB = "c1-c2-owned-host-integration"
EXPECTED = "resource_integration_fixture::actual_owned_pipe_job_and_writer_lifecycle"
IDENTITIES = {"backend"=>"3ee7f6799916c9eea7f945fb856e56223ee0e2da","frontend/src"=>"ba3fb15bf71f1534bd0fe48cca44d827eecb16aa","frontend/src-tauri"=>"53318b86bf97ff0d2ff5ffe896863bfed6c318b6","frontend/src-tauri/Cargo.lock"=>"f635ba1f8257266c242429e2b44ae94b039329b9","third_party/tauri-plugin-shell-2.6.0"=>"54514a2feed82db5a61e9c37e8d43f6fe99b7696","frontend/package-lock.json"=>"845bc92192a1b77432f4d472c7a056f47ca3a3a7","desktop/verify_inference_assets.py"=>"d49016def4ed65432b8ca77f96fb3628657a5b71","qa/c1_c2_owned_host_fixture.py"=>"4f162d6f94606b2cab656ddc91495747dc012e91","frontend/src-tauri/src/resource_integration_fixture.rs"=>"c110c60638ec34eae3d18df102c0d6ff067a4ff7"}
def check(condition, message)
  abort("C1/C2 PREFLIGHT REFUSED: #{message}") unless condition
end
def unique_keys(node)
  if node.is_a?(Psych::Nodes::Mapping)
    keys = node.children.each_slice(2).map do |key, _|
      check(key.is_a?(Psych::Nodes::Scalar), 'non-scalar YAML key')
      key.value
    end
    check(keys.uniq == keys, 'duplicate YAML key')
  end
  (node.children || []).each { |child| unique_keys(child) }
end
def parse(text)
  unique_keys(Psych.parse_stream(text))
  Psych.safe_load(text, aliases: false)
end
source = File.read(WORKFLOW, encoding: 'UTF-8')
is_disabled = source.scan(DISABLED).length == 1 && !source.include?(ARMED)
is_armed = source.scan(ARMED).length == 1 && !source.include?(DISABLED)
check(is_disabled || is_armed, 'unknown native guard')
check(!is_armed || ENV['C1_C2_HOST_EVENT_MESSAGE'] == MARKER, 'armed marker mismatch')
disabled = is_disabled ? source : source.sub(ARMED, DISABLED)
armed = disabled.sub(DISABLED, ARMED)
check(is_disabled || source == armed, 'armed content mismatch')
d, a = parse(disabled), parse(armed)
check(d['on'] == {'push'=>{'branches'=>[BRANCH], 'paths'=>[WORKFLOW, SCRIPT]}}, 'unexpected trigger')
check(d['permissions'] == {'contents'=>'read'}, 'unexpected permissions')
check(d['jobs'].keys.sort == [JOB,'source-preflight'].sort, 'unexpected jobs')
p = d['jobs']['source-preflight']
check(p['runs-on'] == 'ubuntu-24.04' && p['permissions'] == {'contents'=>'read'}, 'preflight environment')
check(p['steps'].length == 2 && p['steps'][1]['run'] == "ruby #{SCRIPT}", 'preflight command')
native = d['jobs'][JOB]
check(native['if'] == '${{ false }}', 'disabled guard')
check(a['jobs'][JOB]['if'] == ARMED.lines[1].strip, 'armed guard')
a['jobs'][JOB]['if'] = native['if']
check(a == d, 'armed YAML changed more than guard')
check(native['needs'] == 'source-preflight' && native['runs-on'] == 'windows-2022', 'native environment')
steps = native.fetch('steps')
check(steps.length == 5, 'unexpected native steps')
check(steps[0]['uses'] == 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' &&
      steps[0]['with'] == {'ref'=>PRODUCT, 'persist-credentials'=>false}, 'exact checkout')
check(steps[-1]['if'] == 'always()', 'cleanup condition')
body = steps.map { |s| s['run'].to_s }.join("\n")
check(body.scan(/cargo \+stable check --locked --all-targets/).length == 1, 'locked check count')
check(body.scan(/cargo \+stable test --locked/).length == 1, 'locked test count')
check(body.scan(/cargo \+stable test --locked --no-run --message-format=json/).length == 1, 'compile only')
check(body.scan(/& \$copy --ignored --exact --test-threads=1 --nocapture \$expected/).length == 1, 'single exact corrected executable selection')
check(body.include?('pilotodin_owned_host_manifest_fixture.exe') && body.include?('Copy-Item -LiteralPath $original -Destination $copy'), 'isolated executable copy')
check(body.include?('C1-FIXTURE-MANIFEST-V6-VERIFIED') && body.include?('Common Controls dependency already declared; hypothesis requires review'), 'manifest hypothesis guard')
check(body.include?('version="6.0.0.0"') && body.include?('publicKeyToken="6595b64144ccf1df"') && body.include?('processorArchitecture="amd64"'), 'manifest dependency identity')
check(body.include?('Original generated executable changed') && body.include?('Unexpected fixture privilege request'), 'preservation and privilege guard')
check(!body.match?(/\bcargo\s+(?:\+stable\s+)?(?:run|build|install)\b/i), 'unapproved Cargo action')
check(!source.include?('actions/upload-artifact') && !body.match?(/Invoke-WebRequest|Start-Process|cargo tauri/), 'unapproved artifact/process action')
check(body.include?("git rev-parse HEAD).Trim() -ne '#{PRODUCT}'"), 'source identity')
check(body.include?('test result: ok\. 1 passed; 0 failed; 0 ignored;'), 'test count')
check(body.include?('RELEASE-PREFLIGHT-REJECTED') && body.include?('COMPILE-ONLY-FIXTURES-REMOVED'), 'fixture guard')
check(body.include?("$expected = '#{EXPECTED}'"), 'single exact test')
check(body.include?("PILOTODIN_C1_C2_FIXTURE_APPROVAL = 'OWNED_HOST_SYNTHETIC_ONCE'"), 'fixture scope guard')
check(body.include?('Remove-Item Env:PILOTODIN_C1_C2_FIXTURE_APPROVAL'), 'fixture guard cleanup')
check(body.include?('C1-C2-INFERENCE-GROUP-ZERO:') && body.include?('C1-C2-ACTUAL-OWNED-HOST-PASS:'), 'required integration evidence')
IDENTITIES.each do |path, sha|
  out, err, status = Open3.capture3('git', 'rev-parse', "HEAD:#{path}")
  check(status.success? && out.strip == sha, "reviewed source changed: #{path}")
end
fixture = File.read('frontend/src-tauri/src/resource_integration_fixture.rs')
check(fixture.match?(/#\[test\]\s*#\[ignore = "[^"]+"\]\s*fn actual_owned_pipe_job_and_writer_lifecycle\(/), 'fixture must stay ignored')
check(File.read('frontend/src-tauri/src/lib.rs').include?("#[cfg(all(windows, test))]\nmod resource_integration_fixture;"), 'fixture registration')
check(fixture.include?('OWNED_HOST_SYNTHETIC_ONCE') && fixture.include?('Prefix::Disk'), 'fixture path and authorization guard')
# Parse Python source only, never import or execute the peer.
_, err, status = Open3.capture3('python3','-I','-B','-c',
  'import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))',
  'qa/c1_c2_owned_host_fixture.py')
check(status.success?, "Python AST parse failed: #{err}")
check(File.read('frontend/src-tauri/src/resource_desktop.rs').include?('const OWNED_RESOURCE_ENABLED: bool = false;'), 'activation gate changed')
parser = '$tokens=$null; $errors=$null; $null=[System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(),[ref]$tokens,[ref]$errors); if($errors.Count -gt 0){ $errors | ForEach-Object { [Console]::Error.WriteLine($_.Message) }; exit 1 }; exit 0'
steps.drop(1).each do |step|
  check(step['shell'] == 'pwsh', 'unexpected native shell')
  _, err, status = Open3.capture3('pwsh', '-NoProfile', '-NonInteractive', '-Command', parser, stdin_data: step.fetch('run'))
  check(status.success?, "PowerShell parse failed: #{step['name']}: #{err}")
end
puts "C1-C2-HOST-PREFLIGHT-DISABLED-SHA256 #{Digest::SHA256.hexdigest(disabled)}"
puts "C1-C2-HOST-PREFLIGHT-ARMED-SHA256 #{Digest::SHA256.hexdigest(armed)}"
puts 'C1-C2-HOST-PREFLIGHT-PASS: both full YAML variants; four PowerShell bodies; pinned source; one exact ignored native integration test; Python AST; no native execution'
