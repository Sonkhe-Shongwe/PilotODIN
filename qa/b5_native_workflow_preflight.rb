# Source-only preflight: never invoke Cargo, PowerShell script bodies, native app or fixture fetch.
require 'psych'
require 'digest'
require 'open3'
WORKFLOW = ".github/workflows/p4-package-b5-native-synthetic-v2-once.yml"
DISABLED = "    if: ${{ false }} # DISARMED V2; fresh exact approval required.\n"
ARMED = "    if: >-\n      ${{ github.run_attempt == 1 && github.event_name == 'push' && github.ref == 'refs/heads/feature/live-dev-workspace-20261023' && github.event.head_commit.message == 'B5-NATIVE-SYNTHETIC-V2-20261124-ONE-USE' }}\n"
MARKER = "B5-NATIVE-SYNTHETIC-V2-20261124-ONE-USE"
PRODUCT = "8e3cc9112073b9744ff18ffa3e4e549662504a97"
BRANCH = "feature/live-dev-workspace-20261023"
EXPECTED = ["dataset_attestation::tests::canonical_metadata_rejects_mismatched_filename_and_bounds","dataset_attestation::tests::rejects_duplicate_and_noncanonical_headers","dataset_attestation::tests::python_hmac_vector_and_tampering","dataset_file::tests::rejects_wrong_version_format_size_digest_and_controls","dataset_file::tests::backend_generated_xlsx_fixture_matches_native_contract","dataset_file::tests::publication_failures_do_not_clobber_or_certify_uncertain_destination","dataset_file::tests::new_file_publication_refuses_existing_and_protected_paths"]
def check(condition, explanation)
  abort("B5 PREFLIGHT REFUSED: #{explanation}") unless condition
end
def unique_keys(node)
  if node.is_a?(Psych::Nodes::Mapping)
    keys = node.children.each_slice(2).map do |key, _value|
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
def git_object(path)
  result, err, status = Open3.capture3('git', 'rev-parse', "HEAD:#{path}")
  check(status.success?, "Git object unavailable: #{path}: #{err}")
  result.strip
end
source = File.read(WORKFLOW, encoding: 'UTF-8')
is_disabled = source.scan(DISABLED).length == 1 && !source.include?(ARMED)
is_armed = source.scan(ARMED).length == 1 && !source.include?(DISABLED)
check(is_disabled || is_armed, 'unknown or repeated native guard')
check(!is_armed || ENV['B5_EVENT_MESSAGE'] == MARKER, 'armed commit marker mismatch')
disabled = is_disabled ? source : source.sub(ARMED, DISABLED)
armed = disabled.sub(DISABLED, ARMED)
check(is_disabled || source == armed, 'actual armed content differs from prospective variant')
d = parse(disabled)
a = parse(armed)
check(d['on'] == {'push'=>{'branches'=>[BRANCH], 'paths'=>[WORKFLOW, 'qa/b5_native_workflow_preflight.rb']}}, 'unexpected trigger')
check(d['permissions'] == {'contents'=>'read', 'actions'=>'read'}, 'unexpected permissions')
check(d['jobs'].keys.sort == %w[b5-synthetic-library-tests source-preflight], 'unexpected job')
preflight = d['jobs']['source-preflight']
check(preflight['runs-on'] == 'ubuntu-24.04' && preflight['permissions'] == {'contents'=>'read'}, 'preflight environment')
check(preflight['steps'].length == 2 && preflight['steps'][1]['run'] == 'ruby qa/b5_native_workflow_preflight.rb', 'unexpected preflight commands')
native = d['jobs']['b5-synthetic-library-tests']
check(native['if'] == '${{ false }}', 'disabled guard is not false')
check(a['jobs']['b5-synthetic-library-tests']['if'] == ARMED.lines[1].strip, 'armed guard parse mismatch')
a['jobs']['b5-synthetic-library-tests']['if'] = native['if']
check(a == d, 'armed YAML changed more than the guard')
check(native['needs'] == 'source-preflight' && native['runs-on'] == 'windows-2022', 'native job not gated')
steps = native.fetch('steps')
check(steps.length == 6, 'unexpected native step count')
check(steps[0]['uses'] == 'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' &&
      steps[0]['with'] == {'ref'=>PRODUCT, 'persist-credentials'=>false}, 'exact checkout mismatch')
check(steps[5]['if'] == 'always()', 'cleanup no longer unconditional')
body = steps.map { |s| s['run'].to_s }.join("\n")
check(body.include?("git rev-parse HEAD).Trim() -ne '#{PRODUCT}'"), 'source identity guard')
check(body.scan(/cargo \+stable test --locked/).length == 1, 'unexpected number of native test invocations')
check(body.include?('--lib -- --exact --include-ignored --test-threads=1 @expected'), 'nonexact test selection')
check(!body.match?(/\bcargo\s+(?:\+stable\s+)?(?:run|build|install)\b/i), 'unapproved cargo action')
check(!source.include?('actions/upload-artifact'), 'artifact upload forbidden')
check(body.include?("actions/artifacts/14937864793/zip") && body.include?('9ff7eff70d5f27fdc5aba03119f53fe0d719329fdfbb4f85a30cf1e47eee8ae1'), 'pinned synthetic artifact')
check(body.include?('7789f8499709b06d0c944fc3bd91e90c47b5a708'), 'fixture producer provenance')
check(body.include?('test result: ok\. 7 passed; 0 failed; 0 ignored;'), 'test count guard')
check(body.include?('RELEASE-PREFLIGHT-REJECTED') && body.include?('COMPILE-ONLY-FIXTURES-REMOVED'), 'fixture refusal/cleanup evidence')
list = body[/\$expected = @\(\n(.*?)\n\s*\)/m, 1]
check(list && list.scan(/'([^']+)'/).flatten == EXPECTED, 'native exact test list mismatch')
{
  'backend'=>'ca355c07878978d8937b9cc9d55db387e840d3a3',
  'tests/test_b5_live_export_transfer.py'=>'501caf9cf57a7ed1969820d8054ccc9aeddda4f2',
  'frontend/src-tauri/Cargo.lock'=>'1aaa20850762ba0054b1dbd56139a248da6eba25',
  'frontend/src-tauri/src/dataset_attestation.rs'=>'08dab9d3ea1365d78927552bc0715d57f88ab837',
  'frontend/src-tauri/src/dataset_file.rs'=>'daacb767113b1406580256864710ef7bb44a68d9',
  'frontend/src-tauri/src/lib.rs'=>'5c204999181a30abb2772540ef5f8caf728ecc79'
}.each { |path, sha| check(git_object(path) == sha, "changed reviewed source: #{path}") }
names = %w[dataset_attestation dataset_file].flat_map do |mod|
  code = File.read("frontend/src-tauri/src/#{mod}.rs")
  code.scan(/^\s*#\[test\]\s*(?:#\[[^\n]+\]\s*)*fn\s+(\w+)\s*\(/).flatten.map { |n| "#{mod}::tests::#{n}" }
end
check(names.sort == EXPECTED.sort, 'Rust source test inventory mismatch')
# Parse embedded scripts without invoking their commands or accessing the artifact.
ps_parser = '$tokens=$null; $errors=$null; $null=[System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(),[ref]$tokens,[ref]$errors); if($errors.Count -gt 0){ $errors | ForEach-Object { [Console]::Error.WriteLine($_.Message) }; exit 1 }; exit 0'
steps.drop(1).each do |step|
  check(step['shell'] == 'pwsh', 'unexpected native shell')
  _, err, status = Open3.capture3('pwsh', '-NoProfile', '-NonInteractive', '-Command', ps_parser, stdin_data: step.fetch('run'))
  check(status.success?, "PowerShell parse failed: #{step['name']}: #{err}")
end
py = body[/^@'\n(.*?)^'@ \| python -/m, 1]
check(!py.nil?, 'embedded Python fixture validator missing')
_, err, status = Open3.capture3('python3','-c','import ast,sys; ast.parse(sys.stdin.read())',stdin_data:py)
check(status.success?, "Python parse failed: #{err}")
puts "B5-PREFLIGHT-DISABLED-SHA256 #{Digest::SHA256.hexdigest(disabled)}"
puts "B5-PREFLIGHT-ARMED-SHA256 #{Digest::SHA256.hexdigest(armed)}"
puts "B5-PREFLIGHT-PASS: full disabled and armed YAML; five PowerShell scripts; Python AST; seven exact source test names; pinned source/artifact"
