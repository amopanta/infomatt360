param(
  [string]$ProjectName = "Piloto InfoMatt360",
  [string]$Environment = "Local",
  [switch]$SkipPreflight
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$OutputsPath = Join-Path $Root "..\outputs"

function Run-Step($Name, [scriptblock]$Action) {
  Write-Host ""
  Write-Host "== $Name =="
  & $Action
  Write-Host "OK: $Name"
}

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
  New-Item -ItemType Directory -Path $OutputsPath | Out-Null
}

if (-not $SkipPreflight) {
  Run-Step "Preflight local" {
    powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\preflight.ps1")
  }
}

Run-Step "Reporte de estado" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\make-status-report.ps1")
}

Run-Step "Paquete ZIP y SHA256" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\make-release.ps1")
}

Run-Step "Evidencia UAT" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\make-uat-evidence.ps1") -ProjectName $ProjectName -Environment $Environment
}

Run-Step "Revision UAT final" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-uat-readiness.ps1")
}

$package = LatestFile "infomatt360-mvp-source-*.zip"
$manifest = LatestFile "infomatt360-mvp-source-*.sha256.txt"
$report = LatestFile "infomatt360-status-*.md"
$evidence = LatestFile "infomatt360-uat-evidence-*.md"
$shaLine = Get-Content $manifest.FullName | Where-Object { $_ -like "SHA256=*" } | Select-Object -First 1

Write-Host ""
Write-Host "== Entrega completa =="
Write-Host "ZIP: $($package.FullName)"
Write-Host "SHA256: $($shaLine -replace '^SHA256=', '')"
Write-Host "Manifiesto: $($manifest.FullName)"
Write-Host "Reporte: $($report.FullName)"
Write-Host "Evidencia UAT: $($evidence.FullName)"
