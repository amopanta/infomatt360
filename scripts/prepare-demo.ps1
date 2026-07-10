param(
  [string]$DatabaseFile = "infomatt360_demo.db"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$EnvFile = Join-Path $Backend ".env"

if (-not (Test-Path $Python)) {
  throw "No existe backend\.venv\Scripts\python.exe"
}
if (-not (Test-Path $EnvFile)) {
  throw "No existe backend\.env. Ejecute primero .\scripts\init-local.cmd"
}

$databaseUrl = "sqlite:///./$DatabaseFile"
$databasePath = Join-Path $Backend $DatabaseFile
$env:PYTHONPATH = $Backend
$env:DATABASE_URL = $databaseUrl

Push-Location $Backend
try {
  if (Test-Path $databasePath) {
    Write-Host "Recreando base demo limpia: $DatabaseFile"
    Remove-Item -LiteralPath $databasePath -Force
  }

  Write-Host "Aplicando migraciones sobre $databaseUrl..."
  & $Python -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) {
    throw "alembic upgrade head termino con codigo $LASTEXITCODE"
  }

  Write-Host "Cargando datos demo..."
  & $Python -m app.cli.seed_demo
  if ($LASTEXITCODE -ne 0) {
    throw "seed demo termino con codigo $LASTEXITCODE"
  }
}
finally {
  Pop-Location
}

$content = Get-Content $EnvFile
$found = $false
$updated = foreach ($line in $content) {
  if ($line -match "^DATABASE_URL=") {
    $found = $true
    "DATABASE_URL=$databaseUrl"
  } else {
    $line
  }
}
if (-not $found) {
  $updated += "DATABASE_URL=$databaseUrl"
}
[System.IO.File]::WriteAllLines($EnvFile, $updated, [System.Text.UTF8Encoding]::new($false))

Write-Host ""
Write-Host "Demo local preparado."
Write-Host "DATABASE_URL=$databaseUrl"
Write-Host "Credenciales: admin@infomatt360.demo / Demo12345!"
