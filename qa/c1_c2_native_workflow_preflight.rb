# Source-only. Parse; never execute Cargo, PowerShell script bodies or application.
require 'psych'
require 'digest'
require 'open3'
WORKFLOW = ".github/workflows/p4-package-c1-c2-native-synthetic-once.yml"
SCRIPT = "qa/c1_c2_native_workflow_preflight.rb"
DISABLED = "    if: ${{ false }} # DISARMED C1/C2; fresh exact approval required.\n"
ARMED = "    if: >-\n      ${{ github.run_attempt == 1 && github.event_name == 'push' && github.ref == 'refs/heads/feature/live-dev-workspace-20261023' && github.event.head_commit.message == 'C1-C2-NATIVE-SYNTHETIC-20261124-ONE-USE' }}\n"
MARKER = "C1-C2-NATIVE-SYNTHETIC-20261124-ONE-USE"
PRODUCT = "388b35750316b9c5a060d603c35c7d728d5c0890"
BRANCH = "feature/live-dev-workspace-20261023"
JOB = "c1-c2-synthetic-library-tests"
EXPECTED = ["resource_wire::tests::exact_demand_poll_grant_worker_ready_and_finish","resource_wire::tests::native_save_grant_is_typed_and_release_is_correlated","resource_wire::tests::native_save_wrong_ack_retains_grant","resource_wire::tests::readiness_precedes_any_grant","resource_wire::tests::matching_grant_drain_release","resource_wire::tests::single_outstanding_and_lost_reply_fault","resource_wire::tests::wrong_sequence_and_pipelining_rejected","resource_wire::tests::stop_is_not_exit_and_wrong_release_retains_grant","resource_wire::tests::busy_denial_permits_new_explicit_intent","resource_transport::tests::early_reply_is_not_consumed_before_write_completion","resource_transport::tests::timeout_while_write_pending_rejects_late_completion","resource_transport::tests::deadline_not_extended_by_write_or_partial_reply","resource_transport::tests::failed_release_write_retains_grant_even_with_early_reply","resource_transport::tests::early_duplicate_and_unsolicited_stdout_fail_closed","resource_transport::tests::second_intent_does_not_replace_pending_write","resource_transport::tests::lost_transport_does_not_release_grant","resource_shell::tests::only_stop_without_grant_or_release_after_stop_is_terminal","resource_shell::tests::terminal_close_does_not_manufacture_a_reply","resource_shell::tests::job_query_waits_for_every_actual_witness","resource_shell::tests::accounting_error_is_terminal_and_does_not_release","resource_shell::tests::deadline_and_late_zero_are_not_exit_proof","resource_shell::tests::missing_begin_and_contradictory_events_never_prove_exit","resource_shell::tests::exact_child_retained_until_writer_join","resource_shell::tests::failed_write_returns_child_for_cleanup_only","resource_shell::tests::panic_does_not_reconstruct_child_or_allow_retry","resource_supervisor::tests::pending_startup_is_not_joined_or_released_on_cancel","resource_supervisor::tests::timeout_keeps_exact_startup_and_late_result_is_marked","resource_supervisor::tests::panicked_startup_is_not_never_started_proof","resource_desktop::tests::incomplete_composition_has_no_activation_switch","resource_save::tests::abandoned_ticket_requires_observed_disconnect","resource_save::tests::uncertain_publication_does_not_settle","resource_save::tests::result_waits_for_actual_join_and_release","report_save_tests::native_report_writer_accepts_only_matching_report_types","report_save_tests::raw_and_fallback_report_payloads_preserve_bytes","report_save_tests::encoded_filenames_still_pass_native_validation","report_save_tests::native_writer_preserves_raw_pdf_and_fallback_html_on_disk","worker_temp_directory_tests::worker_temp_stays_under_existing_app_data_and_refuses_unreviewed_name","native_close_ticket_tests::no_cdp_ack_needs_debug_exact_local_root_and_separate_consent","native_close_ticket_tests::synthetic_w5_finish_is_not_a_general_native_close_bypass","native_close_ticket_tests::only_current_ticket_can_authorize_one_native_close_resolution"]
IDENTITIES = {"backend"=>"3ee7f6799916c9eea7f945fb856e56223ee0e2da","frontend/src"=>"ba3fb15bf71f1534bd0fe48cca44d827eecb16aa","frontend/src-tauri"=>"d12475c3ca5d33e504891a98ce87151d8390e561","frontend/src-tauri/Cargo.lock"=>"f635ba1f8257266c242429e2b44ae94b039329b9","third_party/tauri-plugin-shell-2.6.0"=>"54514a2feed82db5a61e9c37e8d43f6fe99b7696","frontend/package-lock.json"=>"845bc92192a1b77432f4d472c7a056f47ca3a3a7","desktop/verify_inference_assets.py"=>"d49016def4ed65432b8ca77f96fb3628657a5b71"}
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
check(!is_armed || ENV['C1_C2_EVENT_MESSAGE'] == MARKER, 'armed marker mismatch')
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
check(body.include?('--lib -- --exact --test-threads=1 @expected'), 'nonexact selection')
check(!body.match?(/\bcargo\s+(?:\+stable\s+)?(?:run|build|install)\b/i), 'unapproved Cargo action')
check(!source.include?('actions/upload-artifact') && !body.match?(/Invoke-WebRequest|Start-Process|cargo tauri/), 'unapproved artifact/process action')
check(body.include?("git rev-parse HEAD).Trim() -ne '#{PRODUCT}'"), 'source identity')
check(body.include?('test result: ok\. 40 passed; 0 failed; 0 ignored;'), 'test count')
check(body.include?('RELEASE-PREFLIGHT-REJECTED') && body.include?('COMPILE-ONLY-FIXTURES-REMOVED'), 'fixture guard')
list = body[/\$expected = @\(\n(.*?)\n\s*\)/m, 1]
check(list && list.scan(/'([^']+)'/).flatten == EXPECTED && EXPECTED.uniq.length == 40, 'exact test list')
IDENTITIES.each do |path, sha|
  out, err, status = Open3.capture3('git', 'rev-parse', "HEAD:#{path}")
  check(status.success? && out.strip == sha, "reviewed source changed: #{path}")
end
names = %w[resource_wire resource_transport resource_shell resource_supervisor resource_desktop resource_save].flat_map do |mod|
  code = File.read("frontend/src-tauri/src/#{mod}.rs")
  code.scan(/^\s*#\[test\]\s*(?:#\[[^\n]+\]\s*)*fn\s+(\w+)\s*\(/).flatten.map { |n| "#{mod}::tests::#{n}" }
end
check(names.sort == EXPECTED.first(32).sort, 'resource source test inventory')
lib = File.read('frontend/src-tauri/src/lib.rs')
EXPECTED.drop(32).each { |name| check(lib.match?(/\bfn\s+#{Regexp.escape(name.split('::').last)}\s*\(/), "missing test #{name}") }
check(File.read('frontend/src-tauri/src/resource_desktop.rs').include?('const OWNED_RESOURCE_ENABLED: bool = false;'), 'activation gate changed')
parser = '$tokens=$null; $errors=$null; $null=[System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(),[ref]$tokens,[ref]$errors); if($errors.Count -gt 0){ $errors | ForEach-Object { [Console]::Error.WriteLine($_.Message) }; exit 1 }; exit 0'
steps.drop(1).each do |step|
  check(step['shell'] == 'pwsh', 'unexpected native shell')
  _, err, status = Open3.capture3('pwsh', '-NoProfile', '-NonInteractive', '-Command', parser, stdin_data: step.fetch('run'))
  check(status.success?, "PowerShell parse failed: #{step['name']}: #{err}")
end
puts "C1-C2-PREFLIGHT-DISABLED-SHA256 #{Digest::SHA256.hexdigest(disabled)}"
puts "C1-C2-PREFLIGHT-ARMED-SHA256 #{Digest::SHA256.hexdigest(armed)}"
puts 'C1-C2-PREFLIGHT-PASS: both full YAML variants; four PowerShell bodies; pinned source; forty exact library tests; no native execution'
