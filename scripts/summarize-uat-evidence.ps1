param(
  [string]$EvidencePath = ""
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$OutputsPath = Join-Path $Root "..\outputs"

if (-not (Test-Path $OutputsPath)) {
  throw "No existe la carpeta de salidas: $OutputsPath"
}

if ([string]::IsNullOrWhiteSpace($EvidencePath)) {
  $latestEvidence = Get-ChildItem $OutputsPath -Filter "infomatt360-uat-evidence-*.md" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $latestEvidence) {
    throw "No se encontro evidencia UAT en $OutputsPath"
  }
  $EvidencePath = $latestEvidence.FullName
}

if (-not (Test-Path $EvidencePath)) {
  throw "No existe la evidencia UAT: $EvidencePath"
}

$content = Get-Content $EvidencePath
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$summaryPath = Join-Path $OutputsPath "infomatt360-uat-summary-$timestamp.md"

$scenarioRows = New-Object System.Collections.Generic.List[object]
$findingRows = New-Object System.Collections.Generic.List[object]

foreach ($line in $content) {
  $trimmed = $line.Trim()
  if ($trimmed -match "^\|\s*UAT-\d+") {
    $parts = $trimmed.Trim("|").Split("|") | ForEach-Object { $_.Trim() }
    if ($parts.Count -ge 8) {
      $scenarioRows.Add([pscustomobject]@{
        Id = $parts[0]
        Scenario = $parts[1]
        Role = $parts[2]
        Date = $parts[3]
        Result = if ([string]::IsNullOrWhiteSpace($parts[4])) { "Pendiente" } else { $parts[4] }
        Evidence = $parts[5]
        Finding = $parts[6]
        Comment = $parts[7]
      })
    }
  }
  elseif ($trimmed -match "^\|\s*H-\d+") {
    $parts = $trimmed.Trim("|").Split("|") | ForEach-Object { $_.Trim() }
    if ($parts.Count -ge 9) {
      $findingRows.Add([pscustomobject]@{
        Id = $parts[0]
        Date = $parts[1]
        Module = $parts[2]
        Severity = if ([string]::IsNullOrWhiteSpace($parts[3])) { "Sin clasificar" } else { $parts[3] }
        Description = $parts[4]
        Steps = $parts[5]
        Owner = $parts[6]
        Status = if ([string]::IsNullOrWhiteSpace($parts[7])) { "Abierto" } else { $parts[7] }
        Decision = $parts[8]
      })
    }
  }
}

if ($scenarioRows.Count -eq 0) {
  throw "No se encontraron escenarios UAT en $EvidencePath"
}

function Count-Result($Value) {
  return @($scenarioRows | Where-Object { $_.Result.Trim().ToLowerInvariant() -eq $Value }).Count
}

function Count-Finding($Severity, $OnlyOpen) {
  $rows = $findingRows | Where-Object { $_.Severity.Trim().ToLowerInvariant() -eq $Severity }
  if ($OnlyOpen) {
    $rows = $rows | Where-Object {
      $status = $_.Status.Trim().ToLowerInvariant()
      $status -ne "cerrado" -and $status -ne "corregido"
    }
  }
  return @($rows).Count
}

$approved = Count-Result "aprobado"
$observed = Count-Result "observado"
$rejected = Count-Result "rechazado"
$pending = Count-Result "pendiente"
$total = $scenarioRows.Count
$executed = $total - $pending

$blockingOpen = Count-Finding "bloqueante" $true
$highOpen = Count-Finding "alta" $true
$mediumOpen = Count-Finding "media" $true
$lowOpen = Count-Finding "baja" $true

$decision = "Pendiente de ejecucion"
if ($blockingOpen -gt 0 -or $rejected -gt 0) {
  $decision = "No aprobar todavia"
}
elseif ($pending -gt 0) {
  $decision = "Continuar UAT"
}
elseif ($highOpen -gt 0) {
  $decision = "Aprobado solo para staging controlado con correcciones altas pendientes"
}
elseif ($observed -gt 0 -or $mediumOpen -gt 0 -or $lowOpen -gt 0) {
  $decision = "Aprobado con observaciones"
}
else {
  $decision = "Aprobado"
}

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# Resumen UAT InfoMatt360")
$lines.Add("")
$lines.Add("Generado: $(Get-Date -Format 'yyyy-MM-dd HH:mm')")
$lines.Add("")
$lines.Add("Evidencia origen: ``$([System.IO.Path]::GetFileName($EvidencePath))``")
$lines.Add("")
$lines.Add("## Resultado general")
$lines.Add("")
$lines.Add("| Metrica | Valor |")
$lines.Add("| --- | --- |")
$lines.Add("| Escenarios totales | $total |")
$lines.Add("| Escenarios ejecutados | $executed |")
$lines.Add("| Aprobados | $approved |")
$lines.Add("| Observados | $observed |")
$lines.Add("| Rechazados | $rejected |")
$lines.Add("| Pendientes | $pending |")
$lines.Add("| Hallazgos bloqueantes abiertos | $blockingOpen |")
$lines.Add("| Hallazgos altos abiertos | $highOpen |")
$lines.Add("| Hallazgos medios abiertos | $mediumOpen |")
$lines.Add("| Hallazgos bajos abiertos | $lowOpen |")
$lines.Add("| Decision sugerida | $decision |")
$lines.Add("")
$lines.Add("## Detalle de escenarios")
$lines.Add("")
$lines.Add("| ID | Escenario | Resultado | Hallazgo | Comentario |")
$lines.Add("| --- | --- | --- | --- | --- |")
foreach ($row in $scenarioRows) {
  $lines.Add("| $($row.Id) | $($row.Scenario) | $($row.Result) | $($row.Finding) | $($row.Comment) |")
}

if ($findingRows.Count -gt 0) {
  $lines.Add("")
  $lines.Add("## Hallazgos")
  $lines.Add("")
  $lines.Add("| ID | Modulo | Severidad | Estado | Responsable | Decision |")
  $lines.Add("| --- | --- | --- | --- | --- | --- |")
  foreach ($row in $findingRows) {
    $lines.Add("| $($row.Id) | $($row.Module) | $($row.Severity) | $($row.Status) | $($row.Owner) | $($row.Decision) |")
  }
}

Set-Content -Path $summaryPath -Value $lines -Encoding UTF8

Write-Host "Resumen UAT generado: $summaryPath"
Write-Host "Decision sugerida: $decision"
