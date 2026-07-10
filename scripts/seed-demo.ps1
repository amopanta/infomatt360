$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  Write-Error "No existe backend\.venv. No se pueden cargar datos demo."
}

Set-Location $Backend
& $Python -m app.cli.seed_demo
