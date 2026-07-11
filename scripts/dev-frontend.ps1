param(
  [int]$Port = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"
$NodeModules = Join-Path $Frontend "node_modules"

if (-not (Test-Path $NodeModules)) {
  Write-Error "No existe frontend\node_modules. Ejecute npm.cmd install en frontend cuando haya acceso al registro npm."
}

Set-Location $Frontend
Write-Host "Iniciando InfoMatt360 Frontend en http://localhost:$Port"
npm.cmd run dev -- --host 127.0.0.1 --port $Port
