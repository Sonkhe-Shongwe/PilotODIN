# Frontend-only Build E compilation gate. No Rust, Python or model download.
# Execute via desktop\Verify_Frontend.cmd on Windows with Node 22 installed.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frontend = Join-Path $root 'frontend'
$results = Join-Path $root 'frontend-check-results'
New-Item -ItemType Directory -Path $results -Force | Out-Null
$summary = Join-Path $results 'frontend_verification_summary.txt'
$lines = New-Object 'System.Collections.Generic.List[string]'
function Record([string]$text) {
  Write-Host $text
  $lines.Add($text)
  $lines | Set-Content -Path $summary -Encoding UTF8
}
function Run-Logged([string]$step, [string]$exe, [string[]]$arguments) {
  $stdout = Join-Path $results "$step.stdout.log"
  $stderr = Join-Path $results "$step.stderr.log"
  Record "BEGIN $step"
  $proc = Start-Process -FilePath $exe -ArgumentList $arguments -WorkingDirectory $frontend -PassThru -Wait -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  Record "END $step exit=$($proc.ExitCode)"
  if ($proc.ExitCode -ne 0) {
    Write-Host "--- $step last output ---" -ForegroundColor Yellow
    if (Test-Path $stderr) {Get-Content $stderr -Tail 30}
    if (Test-Path $stdout) {Get-Content $stdout -Tail 30}
    throw "$step failed with code $($proc.ExitCode); review logs in $results"
  }
}
try {
  if (-not (Get-Command 'node.exe' -ErrorAction SilentlyContinue)) { throw 'Node.js is not installed or not in PATH. Requires Node.js 22 LTS.' }
  if (-not (Get-Command 'npm.cmd' -ErrorAction SilentlyContinue)) { throw 'npm.cmd is not available in PATH.' }
  Record ('Platform: ' + [Environment]::OSVersion.VersionString)
  Record ('Node: ' + (& node.exe --version))
  Record ('npm: ' + (& npm.cmd --version))
  if (Test-Path (Join-Path $frontend 'package-lock.json')) {
    Record 'Lockfile present: reproducible npm ci'
    Run-Logged 'npm_install' 'npm.cmd' @('ci','--no-audit','--no-fund')
  } else {
    Record 'No package-lock.json in source: generating initial dependency lock with npm install. Preserve the generated lockfile for the release.'
    Run-Logged 'npm_install' 'npm.cmd' @('install','--no-audit','--no-fund')
  }
  Run-Logged 'frontend_test' 'npm.cmd' @('run','test:workspace')
  Run-Logged 'frontend_build' 'npm.cmd' @('run','build')
  if (-not (Test-Path (Join-Path $frontend 'dist/index.html'))) {throw 'Vite reported success but dist/index.html is missing.'}
  $assets = @(Get-ChildItem -Path (Join-Path $frontend 'dist/assets') -Recurse -File -Filter '*.js' -ErrorAction Stop)
  if ($assets.Count -eq 0) { throw 'Vite completed without any JavaScript assets.' }
  Record ("JavaScript bundles produced: $($assets.Count)")
  $lock = Join-Path $frontend 'package-lock.json'
  if (-not (Test-Path $lock)) { throw 'Dependency lockfile missing after dependency installation.' }
  Record ('Dependency lockfile SHA-256: ' + (Get-FileHash -Algorithm SHA256 -Path $lock).Hash)
  Record ('BUILD_ARTIFACT=' + (Join-Path $frontend 'dist/index.html'))
  Record 'FRONTEND_GATE=PASS'
  Record 'The frontend compiled. This does NOT validate a native Tauri Windows installer or the bundled AI runtime.'
} catch {
  Record ('FRONTEND_GATE=FAIL: ' + $_.Exception.Message)
  exit 1
}
