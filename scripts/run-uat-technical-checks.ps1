$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$OutputsPath = Join-Path $Root "..\outputs"

if (-not (Test-Path $Python)) {
  throw "No existe backend\.venv\Scripts\python.exe"
}
if (-not (Test-Path $OutputsPath)) {
  New-Item -ItemType Directory -Path $OutputsPath | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $OutputsPath "infomatt360-uat-technical-checks-$timestamp.md"

function Capture($Name, [scriptblock]$Action) {
  $output = New-Object System.Collections.Generic.List[string]
  $exitCode = 0
  try {
    $result = & $Action 2>&1
    foreach ($line in $result) {
      $output.Add([string]$line)
    }
    if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) {
      $exitCode = $LASTEXITCODE
    }
  } catch {
    $exitCode = 1
    $output.Add($_.Exception.Message)
  }
  return [pscustomobject]@{
    Name = $Name
    ExitCode = $exitCode
    Output = $output
  }
}

$checks = New-Object System.Collections.Generic.List[object]

$checks.Add((Capture "Backend pytest completo" {
  Push-Location $Backend
  try {
    & $Python -m pytest -q
  } finally {
    Pop-Location
  }
}))

$checks.Add((Capture "Frontend vitest" {
  if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    throw "frontend\node_modules no existe; ejecutar .\scripts\install-frontend.cmd"
  }
  Push-Location $Frontend
  try {
    npm.cmd test
  } finally {
    Pop-Location
  }
}))

$checks.Add((Capture "Frontend build" {
  if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    throw "frontend\node_modules no existe; ejecutar .\scripts\install-frontend.cmd"
  }
  Push-Location $Frontend
  try {
    npm.cmd run build
  } finally {
    Pop-Location
  }
}))

$allOk = (@($checks | Where-Object { $_.ExitCode -ne 0 }).Count -eq 0)
$status = if ($allOk) { "OK" } else { "FALLO" }

$coverage = @(
  [pscustomobject]@{ Id = "UAT-01"; Scenario = "Login y seleccion de proyecto"; Evidence = "test_auth_session.py, test_identity.py, routeConfig/session frontend"; Result = $status },
  [pscustomobject]@{ Id = "UAT-02"; Scenario = "Crear formulario"; Evidence = "test_mvp_builder_runtime_flow.py, compiler tests, builder frontend"; Result = $status },
  [pscustomobject]@{ Id = "UAT-03"; Scenario = "Capturar registro"; Evidence = "test_runtime_records.py, test_file_upload.py, runtime frontend"; Result = $status },
  [pscustomobject]@{ Id = "UAT-04"; Scenario = "Consultar registros"; Evidence = "test_runtime_records.py, test_dashboard.py, records frontend"; Result = $status },
  [pscustomobject]@{ Id = "UAT-05"; Scenario = "Aprobacion"; Evidence = "test_approval_flows.py, test_review_runtime.py"; Result = $status },
  [pscustomobject]@{ Id = "UAT-06"; Scenario = "Reporte"; Evidence = "test_report_summary.py, reports frontend"; Result = $status },
  [pscustomobject]@{ Id = "UAT-07"; Scenario = "Mapa"; Evidence = "test_gis_map.py, test_gis_validation.py, geo frontend"; Result = $status },
  [pscustomobject]@{ Id = "UAT-08"; Scenario = "Usuario admin"; Evidence = "test_password_security.py, test_identity.py, admin frontend"; Result = $status },
  [pscustomobject]@{ Id = "UAT-09"; Scenario = "API key"; Evidence = "test_api_keys.py, test_api_rate_limit.py"; Result = $status },
  [pscustomobject]@{ Id = "UAT-10"; Scenario = "Bulk sync"; Evidence = "test_runtime_bulk_api_key.py, bulk jobs frontend"; Result = $status },
  [pscustomobject]@{ Id = "UAT-11"; Scenario = "Auditoria"; Evidence = "test_audit_visibility.py"; Result = $status },
  [pscustomobject]@{ Id = "UAT-12"; Scenario = "Metricas"; Evidence = "test_health.py, dashboard/metrics frontend"; Result = $status }
)

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Pre-UAT tecnica InfoMatt360")
$lines.Add("")
$lines.Add("Generado: $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
$lines.Add("")
$lines.Add("Esta revision no reemplaza la UAT funcional con usuarios. Sirve para confirmar que la base tecnica esta verde antes de ejecutar la validacion humana.")
$lines.Add("")
$lines.Add("## Resultado")
$lines.Add("")
$lines.Add("| Control | Estado |")
$lines.Add("| --- | --- |")
foreach ($check in $checks) {
  $checkStatus = if ($check.ExitCode -eq 0) { "OK" } else { "FALLO" }
  $lines.Add("| $($check.Name) | $checkStatus |")
}
$lines.Add("")
$lines.Add("## Cobertura tecnica por escenario UAT")
$lines.Add("")
$lines.Add("| ID | Escenario | Evidencia tecnica | Estado |")
$lines.Add("| --- | --- | --- | --- |")
foreach ($row in $coverage) {
  $lines.Add("| $($row.Id) | $($row.Scenario) | $($row.Evidence) | $($row.Result) |")
}
$lines.Add("")
$lines.Add("## Salida resumida")
foreach ($check in $checks) {
  $lines.Add("")
  $lines.Add("### $($check.Name)")
  $lines.Add("")
  $lines.Add('```text')
  foreach ($line in ($check.Output | Select-Object -Last 40)) {
    $lines.Add($line)
  }
  $lines.Add('```')
}

Set-Content -Path $reportPath -Value $lines -Encoding UTF8

Write-Host "Pre-UAT tecnica generada: $reportPath"
Write-Host "Estado: $status"
if (-not $allOk) {
  throw "Pre-UAT tecnica fallo. Revisar $reportPath"
}
