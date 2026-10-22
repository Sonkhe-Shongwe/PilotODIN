# PilotODIN Build D.1 offline diagnostics. Only localhost endpoints are contacted.
$ErrorActionPreference = 'Stop'
$api = 'http://127.0.0.1:8000/api'
Write-Host 'PilotODIN local service diagnostics (no cloud requests)' -ForegroundColor Cyan
Write-Host '---------------------------------------------------'
function Check-Local($label, $url) {
  try {
    $answer = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 8
    Write-Host "[OK] $label" -ForegroundColor Green
    return $answer
  } catch {
    $status = ''
    if ($_.Exception.Response -and $_.Exception.Response.StatusCode) { $status = " HTTP $([int]$_.Exception.Response.StatusCode)" }
    Write-Host "[FAIL] $label$status | $url" -ForegroundColor Red
    Write-Host "       $($_.Exception.Message)"
    return $null
  }
}
$health = Check-Local 'Analytics engine /health' "$api/health"
$projects = Check-Local 'Project listing /projects' "$api/projects"
$ollama = Check-Local 'Local Ollama model inventory' 'http://127.0.0.1:11434/api/tags'
if ($null -ne $projects) {
  $items = @($projects)
  Write-Host "Projects returned: $($items.Count)"
  $selected = $items | Where-Object { $_.name -eq 'missingness' } | Select-Object -First 1
  if ($null -eq $selected) { $selected = $items | Select-Object -First 1 }
  if ($null -ne $selected) {
    Write-Host 'Checking the four Canvas read routes for one local project (no row data displayed):'
    $id = [uri]::EscapeDataString([string]$selected.id)
    Check-Local 'Dataset profile' "$api/projects/$id/live-profile" | Out-Null
    Check-Local 'Data overview' "$api/projects/$id/explore/overview" | Out-Null
    Check-Local 'Investigation history' "$api/projects/$id/investigations" | Out-Null
    Check-Local 'Recommendations' "$api/projects/$id/explore/recommended" | Out-Null
  } else { Write-Host 'No projects found. Import a CSV/XLSX file in PilotODIN first.' }
}
if ($null -eq $health) {
 Write-Host ''
 Write-Host 'The backend is not responding. Verify that the PilotODIN Backend launcher window is running and check it for a Python traceback.' -ForegroundColor Yellow
}
Write-Host ''
Write-Host 'Only local service availability and route status were checked. No dataset records were uploaded.'
