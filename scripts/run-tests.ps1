$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  Write-Error "No existe backend\.venv. No se pueden ejecutar pruebas backend."
}

Set-Location $Backend
Write-Host "Ejecutando pruebas backend..."
& $Python -m pytest -q

Set-Location $Frontend
if (Test-Path (Join-Path $Frontend "node_modules")) {
  Write-Host "Ejecutando pruebas frontend..."
  npm.cmd test
} else {
  Write-Host "Saltando pruebas frontend: node_modules no existe."
}
