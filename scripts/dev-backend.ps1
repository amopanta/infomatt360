param(
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  Write-Error "No existe backend\.venv. Cree el entorno e instale requirements.txt antes de iniciar."
}

Set-Location $Backend
Write-Host "Iniciando InfoMatt360 Backend en http://localhost:$Port"
& $Python -m uvicorn app.main:app --reload --host 127.0.0.1 --port $Port
