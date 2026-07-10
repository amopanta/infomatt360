$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Check($Name, [scriptblock]$Action) {
  Write-Host ""
  Write-Host "== $Name =="
  try {
    & $Action
    Write-Host "OK: $Name"
  } catch {
    $script:failures.Add("${Name}: $($_.Exception.Message)")
    Write-Host "FALLO: $Name"
    Write-Host $_.Exception.Message
  }
}

function Warn($Message) {
  $script:warnings.Add($Message)
  Write-Host "ADVERTENCIA: $Message"
}

Check "Estructura del proyecto" {
  $required = @(
    "backend\app\main.py",
    "backend\requirements.txt",
    "frontend\package.json",
    "frontend\src\main.tsx",
    ".env.example",
    "scripts\dev-backend.cmd",
    "scripts\dev-frontend.cmd",
    "scripts\preflight.cmd",
    "scripts\install-frontend.cmd"
  )
  foreach ($item in $required) {
    if (-not (Test-Path (Join-Path $Root $item))) {
      throw "Falta $item"
    }
  }
}

Check "Python backend" {
  $python = Join-Path $Backend ".venv\Scripts\python.exe"
  if (-not (Test-Path $python)) {
    throw "No existe backend\.venv\Scripts\python.exe"
  }
  & $python --version
  if ($LASTEXITCODE -ne 0) {
    throw "python --version termino con codigo $LASTEXITCODE"
  }
}

Check "Configuracion backend" {
  $envFile = Join-Path $Backend ".env"
  if (-not (Test-Path $envFile)) {
    Warn "backend\.env no existe; copiar .env.example a backend\.env antes de arrancar."
    return
  }

  $content = Get-Content $envFile -Raw
  if ($content -match "change-this-secret-before-production") {
    Warn "SECRET_KEY sigue con valor de desarrollo; cambiar antes de produccion."
  }
  if ($content -match "DATABASE_URL=sqlite") {
    Warn "DATABASE_URL usa SQLite; correcto para local, usar PostgreSQL en produccion."
  }
  if ($content -notmatch "SMTP_HOST=.+") {
    Warn "SMTP no parece configurado; recuperacion de contrasena puede quedar en modo no-envio."
  }
}

Check "Node y npm frontend" {
  node --version
  if ($LASTEXITCODE -ne 0) {
    throw "node --version termino con codigo $LASTEXITCODE"
  }
  npm.cmd --version
  if ($LASTEXITCODE -ne 0) {
    throw "npm --version termino con codigo $LASTEXITCODE"
  }
}

Check "Dependencias frontend" {
  if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Warn "frontend\node_modules no existe; ejecutar .\scripts\install-frontend.cmd cuando npm tenga conexion."
    return
  }
  Write-Host "frontend\node_modules existe."
}

Check "Cache TypeScript offline" {
  $tsModule = Join-Path $Root "..\work\tscheck\node_modules\typescript"
  if (-not (Test-Path $tsModule)) {
    Warn "No existe cache TypeScript offline en ..\work\tscheck; preflight no podra validar TS offline."
    return
  }
  Write-Host "Cache TypeScript offline disponible."
}

Check "Git disponible" {
  git --version
  if ($LASTEXITCODE -ne 0) {
    throw "git --version termino con codigo $LASTEXITCODE"
  }
}

Write-Host ""
Write-Host "== Resultado doctor =="
if ($warnings.Count -gt 0) {
  Write-Host "Advertencias:"
  foreach ($warning in $warnings) {
    Write-Host "- $warning"
  }
}
if ($failures.Count -gt 0) {
  Write-Host "Fallos:"
  foreach ($failure in $failures) {
    Write-Host "- $failure"
  }
  exit 1
}
Write-Host "Doctor OK. El entorno esta listo para revision local con las advertencias indicadas."
