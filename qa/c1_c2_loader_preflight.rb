# Source-only preflight; never run native commands or test executables.
require 'psych'
require 'digest'
require 'open3'
WORKFLOW = ".github/workflows/p4-c1-c2-loader-diagnosis-once.yml"
SCRIPT = "qa/c1_c2_loader_preflight.rb"
PARSER = "qa/c1_c2_loader_imports.py"
DISABLED = "    if: ${{ false }} # DISARMED LOADER DIAGNOSIS; fresh exact approval required.\n"
ARMED = "    if: >-\n      ${{ github.run_attempt == 1 && github.event_name == 'push' && github.ref == 'refs/heads/feature/live-dev-workspace-20261023' && github.event.head_commit.message == 'C1-C2-LOADER-IMPORT-DIAGNOSIS-20261125-ONE-USE' }}\n"
MARKER = "C1-C2-LOADER-IMPORT-DIAGNOSIS-20261125-ONE-USE"
BRANCH = "feature/live-dev-workspace-20261023"
JOB = "paired-static-import-diagnosis"
BASE = "388b35750316b9c5a060d603c35c7d728d5c0890"
FIXTURE = "1d23ea139762d94d25e689c4c3489b72fb34acc9"
def check(v,m)
  abort("LOADER PREFLIGHT REFUSED: #{m}") unless v
end
def unique_keys(n)
  if n.is_a?(Psych::Nodes::Mapping)
    keys=n.children.each_slice(2).map{|k,_| check(k.is_a?(Psych::Nodes::Scalar),'non-scalar key'); k.value}
    check(keys.uniq==keys,'duplicate YAML key')
  end
  (n.children||[]).each{|c| unique_keys(c)}
end
def parse(s)
  unique_keys(Psych.parse_stream(s))
  Psych.safe_load(s,aliases:false)
end
s=File.read(WORKFLOW,encoding:'UTF-8')
d=s.scan(DISABLED).length==1 && !s.include?(ARMED)
a=s.scan(ARMED).length==1 && !s.include?(DISABLED)
check(d||a,'guard')
check(!a||ENV['C1_C2_LOADER_EVENT_MESSAGE']==MARKER,'marker')
disabled=d ? s : s.sub(ARMED,DISABLED)
armed=disabled.sub(DISABLED,ARMED)
x,y=parse(disabled),parse(armed)
check(x['on']=={'push'=>{'branches'=>[BRANCH],'paths'=>[WORKFLOW,SCRIPT,PARSER]}},'trigger')
check(x['permissions']=={'contents'=>'read'},'permissions')
check(x['jobs'].keys.sort==[JOB,'source-preflight'].sort,'jobs')
native=x['jobs'][JOB]
check(native['if']=='${{ false }}','disabled')
check(y['jobs'][JOB]['if']==ARMED.lines[1].strip,'armed')
y['jobs'][JOB]['if']=native['if']
check(x==y,'variant difference')
check(native['runs-on']=='windows-2022' && native['needs']=='source-preflight','native scope')
steps=native.fetch('steps')
check(steps.length==7,'step count')
[0,1,2].each{|i|check(steps[i]['uses']=='actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683' && steps[i]['with']['persist-credentials']==false,'checkout')}
check(steps[1]['with']=={'ref'=>BASE,'path'=>'baseline','persist-credentials'=>false},'baseline exact')
check(steps[2]['with']=={'ref'=>FIXTURE,'path'=>'fixture','persist-credentials'=>false},'fixture exact')
check(steps[-1]['if']=='always()','cleanup')
body=steps.map{|z|z['run'].to_s}.join("\n")
check(body.scan(/cargo \+stable test --locked --no-run --message-format=json/).length==1,'compile only')
check(!body.match?(/\bcargo\s+(?:\+stable\s+)?(?:run|build|install)\b/i),'unexpected cargo command')
check(!body.match?(/Start-Process|Invoke-WebRequest|actions\/upload-artifact|--nocapture|--ignored/),'unexpected operation')
check(body.include?('STATIC_IMPORT_DIAGNOSIS_ONCE') && body.include?('Remove-Item Env:PILOTODIN_C1_C2_LOADER_APPROVAL'),'scope guard')
check(body.include?('RELEASE-PREFLIGHT-REJECTED') && body.include?('COMPILE-ONLY-FIXTURES-REMOVED'),'fixture lifecycle')
check(body.include?(BASE) && body.include?(FIXTURE),'exact source')
check(File.read('frontend/src-tauri/src/resource_desktop.rs').include?('const OWNED_RESOURCE_ENABLED: bool = false;'),'activation')
parser='$tokens=$null; $errors=$null; $null=[System.Management.Automation.Language.Parser]::ParseInput([Console]::In.ReadToEnd(),[ref]$tokens,[ref]$errors); if($errors.Count -gt 0){ $errors | ForEach-Object { [Console]::Error.WriteLine($_.Message) }; exit 1 }; exit 0'
steps.drop(3).each do |step|
  check(step['shell']=='pwsh','shell')
  _,err,status=Open3.capture3('pwsh','-NoProfile','-NonInteractive','-Command',parser,stdin_data:step.fetch('run'))
  check(status.success?,"PowerShell parse: #{err}")
end
out,err,status=Open3.capture3('python3','-I','-B',PARSER,'--self-test')
check(status.success?,"parser self-test: #{err}")
puts out,err
puts "C1-C2-LOADER-PREFLIGHT-DISABLED-SHA256 #{Digest::SHA256.hexdigest(disabled)}"
puts "C1-C2-LOADER-PREFLIGHT-ARMED-SHA256 #{Digest::SHA256.hexdigest(armed)}"
puts "C1-C2-LOADER-PREFLIGHT-PASS: two exact source checkouts; four PowerShell bodies; three text-parser tests; no native execution"
