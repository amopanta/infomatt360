param(
  [string]$Name = "infomatt360-mvp-source"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$Outputs = Resolve-Path (Join-Path $Root "..\outputs") -ErrorAction SilentlyContinue
if (-not $Outputs) {
  $OutputsPath = Join-Path $Root "..\outputs"
  New-Item -ItemType Directory -Path $OutputsPath | Out-Null
  $Outputs = Resolve-Path $OutputsPath
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$zipPath = Join-Path $Outputs.Path "$Name-$timestamp.zip"
$manifestPath = Join-Path $Outputs.Path "$Name-$timestamp.sha256.txt"
$excludedDirs = @(".git", ".venv", "node_modules", "dist", "__pycache__", ".pytest_cache", "uploads")
$excludedExtensions = @(".db", ".pyc", ".pyo")
$excludedFileNames = @(".env")

function Include-File($File) {
  $relative = $File.FullName.Substring($Root.Length).TrimStart("\", "/")
  $parts = $relative -split "[\\/]"
  foreach ($part in $parts) {
    if ($excludedDirs -contains $part) {
      return $false
    }
  }
  if ($excludedExtensions -contains $File.Extension.ToLowerInvariant()) {
    return $false
  }
  if ($excludedFileNames -contains $File.Name.ToLowerInvariant()) {
    return $false
  }
  return $true
}

$files = Get-ChildItem $Root -Recurse -File -ErrorAction SilentlyContinue | Where-Object { Include-File $_ }
if (-not $files) {
  throw "No se encontraron archivos para empaquetar."
}

if (Test-Path $zipPath) {
  Remove-Item -LiteralPath $zipPath -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
  foreach ($file in $files) {
    $relative = $file.FullName.Substring($Root.Length).TrimStart("\", "/")
    $entryName = $relative -replace "\\", "/"
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
      $zip,
      $file.FullName,
      $entryName,
      [System.IO.Compression.CompressionLevel]::Optimal
    ) | Out-Null
  }
}
finally {
  $zip.Dispose()
}

$hash = Get-FileHash -Algorithm SHA256 -Path $zipPath
$zipItem = Get-Item -LiteralPath $zipPath
$manifest = @(
  "InfoMatt360 MVP source package",
  "GeneratedAt=$(Get-Date -Format o)",
  "Package=$($zipItem.Name)",
  "Bytes=$($zipItem.Length)",
  "Files=$($files.Count)",
  "SHA256=$($hash.Hash)",
  "",
  "ExcludedDirectories=$($excludedDirs -join ',')",
  "ExcludedExtensions=$($excludedExtensions -join ',')",
  "ExcludedFileNames=$($excludedFileNames -join ',')"
)
Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8

Write-Host "Paquete generado: $zipPath"
Write-Host "Manifiesto generado: $manifestPath"
