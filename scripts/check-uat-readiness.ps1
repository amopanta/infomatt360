$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$OutputsPath = Join-Path $Root "..\outputs"

function LatestFile($Pattern) {
  $file = Get-ChildItem $OutputsPath -Filter $Pattern -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $file) {
    throw "No se encontro archivo con patron $Pattern en $OutputsPath"
  }
  return $file
}

if (-not (Test-Path $OutputsPath)) {
  throw "No existe la carpeta de salidas: $OutputsPath"
}

$package = LatestFile "infomatt360-mvp-source-*.zip"
$manifest = LatestFile "infomatt360-mvp-source-*.sha256.txt"
$statusReport = LatestFile "infomatt360-status-*.md"
$uatEvidence = LatestFile "infomatt360-uat-evidence-*.md"

$manifestText = Get-Content $manifest.FullName -Raw
$expectedPackage = [regex]::Match($manifestText, "Package=(.+)").Groups[1].Value.Trim()
$expectedSha = [regex]::Match($manifestText, "SHA256=([A-Fa-f0-9]+)").Groups[1].Value.Trim().ToUpperInvariant()

if ([string]::IsNullOrWhiteSpace($expectedPackage)) {
  throw "El manifiesto no contiene Package="
}
if ([string]::IsNullOrWhiteSpace($expectedSha)) {
  throw "El manifiesto no contiene SHA256="
}
if ($expectedPackage -ne $package.Name) {
  throw "El ultimo ZIP ($($package.Name)) no coincide con el manifiesto ($expectedPackage)"
}

$actualSha = (Get-FileHash $package.FullName -Algorithm SHA256).Hash.ToUpperInvariant()
if ($actualSha -ne $expectedSha) {
  throw "SHA256 invalido. Esperado $expectedSha, actual $actualSha"
}

$evidenceText = Get-Content $uatEvidence.FullName -Raw
if ($evidenceText -notmatch [regex]::Escape($package.Name)) {
  throw "La evidencia UAT no referencia el ultimo ZIP $($package.Name)"
}
if ($evidenceText -notmatch $expectedSha) {
  throw "La evidencia UAT no referencia el SHA256 del ultimo paquete"
}

Write-Host "Revision UAT lista."
Write-Host "ZIP: $($package.FullName)"
Write-Host "SHA256: $expectedSha"
Write-Host "Reporte: $($statusReport.FullName)"
Write-Host "Evidencia UAT: $($uatEvidence.FullName)"
