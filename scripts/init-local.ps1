param(
  [switch]$ForceEnv
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$EnvExample = Join-Path $Root ".env.example"
$BackendEnv = Join-Path $Backend ".env"
$Uploads = Join-Path $Backend "uploads"

if (-not (Test-Path $EnvExample)) {
  throw "No existe .env.example"
}

if (-not (Test-Path $Backend)) {
  throw "No existe carpeta backend"
}

if ((Test-Path $BackendEnv) -and -not $ForceEnv) {
  Write-Host "backend\.env ya existe; no se sobrescribe."
} else {
  $envContent = Get-Content $EnvExample
  [System.IO.File]::WriteAllLines($BackendEnv, $envContent, [System.Text.UTF8Encoding]::new($false))
  Write-Host "backend\.env creado desde .env.example"
}

if (-not (Test-Path $Uploads)) {
  New-Item -ItemType Directory -Path $Uploads | Out-Null
  Write-Host "Carpeta backend\uploads creada."
} else {
  Write-Host "Carpeta backend\uploads ya existe."
}

Write-Host ""
Write-Host "Inicializacion local lista."
Write-Host "Siguiente paso recomendado: .\scripts\doctor.cmd"
