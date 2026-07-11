param(
  [string]$ProjectName = "InfoMatt360 Piloto",
  [string]$Environment = "Local"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$OutputsPath = Join-Path $Root "..\outputs"
$TemplatePath = Join-Path $Root "docs\69_PLANTILLA_EVIDENCIA_UAT.md"

if (-not (Test-Path $TemplatePath)) {
  throw "No existe docs\69_PLANTILLA_EVIDENCIA_UAT.md"
}
if (-not (Test-Path $OutputsPath)) {
  New-Item -ItemType Directory -Path $OutputsPath | Out-Null
}

$outputs = Resolve-Path $OutputsPath
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$evidencePath = Join-Path $outputs.Path "infomatt360-uat-evidence-$timestamp.md"

$latestPackage = Get-ChildItem $outputs.Path -Filter "infomatt360-mvp-source-*.zip" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

$packageName = ""
$sha256 = ""
if ($latestPackage) {
  $packageName = $latestPackage.Name
  $hashFile = [System.IO.Path]::ChangeExtension($latestPackage.FullName, ".sha256.txt")
  if (Test-Path $hashFile) {
    $hashLine = Get-Content $hashFile | Where-Object { $_ -like "SHA256=*" } | Select-Object -First 1
    if ($hashLine) {
      $sha256 = $hashLine.Substring("SHA256=".Length)
    }
  }
}

$content = Get-Content $TemplatePath -Raw
$content = $content -replace "\| Proyecto \|  \|", "| Proyecto | $ProjectName |"
$content = $content -replace "\| Ambiente \| Local / Staging / Produccion controlada \|", "| Ambiente | $Environment |"
$content = $content -replace "\| Version ZIP \|  \|", "| Version ZIP | $packageName |"
$content = $content -replace "\| SHA256 \|  \|", "| SHA256 | $sha256 |"
$content = $content -replace "\| Fecha inicio \|  \|", "| Fecha inicio | $(Get-Date -Format 'yyyy-MM-dd HH:mm') |"

[System.IO.File]::WriteAllText($evidencePath, $content, [System.Text.UTF8Encoding]::new($false))
Write-Host "Evidencia UAT generada: $evidencePath"
