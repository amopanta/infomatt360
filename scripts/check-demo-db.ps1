$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "No existe backend\.venv\Scripts\python.exe"
}

Push-Location $Backend
try {
  & $Python -m app.cli.demo_status
  if ($LASTEXITCODE -ne 0) {
    throw "demo_status termino con codigo $LASTEXITCODE"
  }
}
finally {
  Pop-Location
}
