param(
  [string]$ProjectName = "Piloto InfoMatt360",
  [string]$Environment = "Local"
)

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

function LatestOptionalFile($Pattern) {
  return Get-ChildItem $OutputsPath -Filter $Pattern -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
}

if (-not (Test-Path $OutputsPath)) {
  throw "No existe la carpeta de salidas: $OutputsPath"
}

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-uat-readiness.ps1")
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\summarize-uat-evidence.ps1")

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$kitPath = Join-Path $OutputsPath "infomatt360-uat-kit-$timestamp"
$kitZipPath = Join-Path $OutputsPath "infomatt360-uat-kit-$timestamp.zip"
$kitManifestPath = Join-Path $OutputsPath "infomatt360-uat-kit-$timestamp.sha256.txt"
New-Item -ItemType Directory -Path $kitPath | Out-Null

$package = LatestFile "infomatt360-mvp-source-*.zip"
$manifest = LatestFile "infomatt360-mvp-source-*.sha256.txt"
$statusReport = LatestFile "infomatt360-status-*.md"
$uatEvidence = LatestFile "infomatt360-uat-evidence-*.md"
$uatSummary = LatestFile "infomatt360-uat-summary-*.md"
$technicalChecks = LatestOptionalFile "infomatt360-uat-technical-checks-*.md"
$plan = Join-Path $Root "docs\68_PLAN_PILOTO_UAT.md"
$template = Join-Path $Root "docs\69_PLANTILLA_EVIDENCIA_UAT.md"
$guide = Join-Path $Root "docs\70_GUIA_EJECUCION_UAT_MODULOS.md"

$filesToCopy = @(
  $package.FullName,
  $manifest.FullName,
  $statusReport.FullName,
  $uatEvidence.FullName,
  $uatSummary.FullName,
  $plan,
  $template,
  $guide
)

if ($technicalChecks) {
  $filesToCopy += $technicalChecks.FullName
}

foreach ($file in $filesToCopy) {
  if (-not (Test-Path $file)) {
    throw "No existe archivo requerido para kit UAT: $file"
  }
  Copy-Item -LiteralPath $file -Destination $kitPath
}

$shaLine = Get-Content $manifest.FullName | Where-Object { $_ -like "SHA256=*" } | Select-Object -First 1
$readmePath = Join-Path $kitPath "LEEME_UAT.md"
$readme = @(
  "# Kit UAT InfoMatt360",
  "",
  "## Datos",
  "",
  "| Campo | Valor |",
  "| --- | --- |",
  "| Proyecto | $ProjectName |",
  "| Ambiente | $Environment |",
  "| Generado | $(Get-Date -Format 'yyyy-MM-dd HH:mm') |",
  "| ZIP | $($package.Name) |",
  "| SHA256 | $($shaLine -replace '^SHA256=', '') |",
  "",
  "## Orden sugerido",
  "",
  '1. Leer `68_PLAN_PILOTO_UAT.md`.',
  '2. Ejecutar los escenarios con `70_GUIA_EJECUCION_UAT_MODULOS.md`.',
  "3. Registrar resultados en ``$($uatEvidence.Name)``.",
  "4. Revisar resumen automatico en ``$($uatSummary.Name)``.",
  $(if ($technicalChecks) { "5. Revisar pre-UAT tecnica en ``$($technicalChecks.Name)``." } else { "5. Ejecutar pre-UAT tecnica con ``.\scripts\run-uat-technical-checks.cmd``." }),
  "6. Si aparece un hallazgo, documentarlo con severidad y pasos para reproducir.",
  "7. Al cerrar el piloto, completar el acta de cierre de la evidencia UAT.",
  "",
  "## Criterio rapido",
  "",
  "- Bloqueante abierto: no pasar a produccion.",
  "- Alta abierta: corregir antes de produccion.",
  "- Media/Baja: puede pasar a backlog si queda aceptada por responsable.",
  "",
  "## Archivos incluidos",
  "",
  "- ``$($package.Name)``",
  "- ``$($manifest.Name)``",
  "- ``$($statusReport.Name)``",
  "- ``$($uatEvidence.Name)``",
  "- ``$($uatSummary.Name)``",
  $(if ($technicalChecks) { "- ``$($technicalChecks.Name)``" } else { "- Pre-UAT tecnica: pendiente de generar" }),
  '- `68_PLAN_PILOTO_UAT.md`',
  '- `69_PLANTILLA_EVIDENCIA_UAT.md`',
  '- `70_GUIA_EJECUCION_UAT_MODULOS.md`'
)

Set-Content -Path $readmePath -Value $readme -Encoding UTF8

if (Test-Path $kitZipPath) {
  Remove-Item -LiteralPath $kitZipPath -Force
}

Compress-Archive -Path (Join-Path $kitPath "*") -DestinationPath $kitZipPath -CompressionLevel Optimal
$kitHash = Get-FileHash -Path $kitZipPath -Algorithm SHA256
$kitZipItem = Get-Item -LiteralPath $kitZipPath
$kitManifest = @(
  "InfoMatt360 UAT kit",
  "GeneratedAt=$(Get-Date -Format o)",
  "KitFolder=$([System.IO.Path]::GetFileName($kitPath))",
  "Package=$($kitZipItem.Name)",
  "Bytes=$($kitZipItem.Length)",
  "SHA256=$($kitHash.Hash)",
  "",
  "SourcePackage=$($package.Name)",
  "SourcePackageSHA256=$($shaLine -replace '^SHA256=', '')"
)
Set-Content -Path $kitManifestPath -Value $kitManifest -Encoding UTF8

Write-Host "Kit UAT generado: $kitPath"
Write-Host "Kit UAT ZIP generado: $kitZipPath"
Write-Host "Manifiesto Kit UAT generado: $kitManifestPath"
