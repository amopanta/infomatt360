$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Frontend = Join-Path $Root "frontend"

if (-not (Test-Path (Join-Path $Frontend "package.json"))) {
  throw "No se encontro frontend\package.json"
}

Push-Location $Frontend
try {
  if (-not $env:NODE_OPTIONS) {
    $env:NODE_OPTIONS = "--use-system-ca"
  } elseif ($env:NODE_OPTIONS -notmatch "--use-system-ca") {
    $env:NODE_OPTIONS = "$env:NODE_OPTIONS --use-system-ca"
  }

  Write-Host "Instalando dependencias frontend..."
  npm.cmd install --no-audit --no-fund --progress=false
  if ($LASTEXITCODE -ne 0) {
    throw "npm install termino con codigo $LASTEXITCODE"
  }

  Write-Host "Validando build frontend..."
  npm.cmd run build
  if ($LASTEXITCODE -ne 0) {
    throw "npm run build termino con codigo $LASTEXITCODE"
  }

  Write-Host "Frontend instalado y build validado."
}
finally {
  Pop-Location
}
