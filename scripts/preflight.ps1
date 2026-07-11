$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$TsModule = Join-Path $Root "..\work\tscheck\node_modules\typescript"
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Step($Name, [scriptblock]$Action) {
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

Step "Archivos criticos" {
  $required = @(
    "README.md",
    ".env.example",
    ".env.production.example",
    ".dockerignore",
    "docker-compose.production.example.yml",
    "backend\app\main.py",
    "backend\app\cli\seed_demo.py",
    "deploy\backend.Dockerfile",
    "deploy\frontend.Dockerfile",
    "deploy\nginx.frontend.conf",
    "docs\61_DESPLIEGUE_PRODUCCION_REFERENCIA.md",
    "docs\62_CHECKLIST_GO_LIVE.md",
    "docs\63_BACKUP_RESTORE_POSTGRES.md",
    "docs\64_ROLLBACK_OPERATIVO.md",
    "docs\65_OPERACION_MONITOREO_INCIDENTES.md",
    "docs\66_RUNBOOK_ADMIN_FUNCIONAL.md",
    "docs\67_REVISION_FUNCIONAL_LOCAL.md",
    "docs\68_PLAN_PILOTO_UAT.md",
    "docs\69_PLANTILLA_EVIDENCIA_UAT.md",
    "docs\70_GUIA_EJECUCION_UAT_MODULOS.md",
    "frontend\src\main.tsx",
    "scripts\doctor.cmd",
    "scripts\doctor-production.cmd",
    "scripts\generate-secret.cmd",
    "scripts\init-local.cmd",
    "scripts\dev-backend.cmd",
    "scripts\dev-frontend.cmd",
    "scripts\install-frontend.cmd",
    "scripts\prepare-demo.cmd",
    "scripts\seed-demo.cmd",
    "scripts\check-demo-db.cmd",
    "scripts\check-demo.cmd",
    "scripts\check-full-stack.cmd",
    "scripts\check-browser-cors.cmd",
    "scripts\check-browser-cors.ps1",
    "scripts\check-uat-readiness.cmd",
    "scripts\check-uat-readiness.ps1",
    "scripts\check-production-package.cmd",
    "scripts\backup-postgres.cmd",
    "scripts\restore-postgres.cmd",
    "scripts\monitor-health.cmd",
    "scripts\make-delivery.cmd",
    "scripts\make-delivery.ps1",
    "scripts\make-uat-kit.cmd",
    "scripts\make-uat-kit.ps1",
    "scripts\summarize-uat-evidence.cmd",
    "scripts\summarize-uat-evidence.ps1",
    "scripts\run-uat-technical-checks.cmd",
    "scripts\run-uat-technical-checks.ps1",
    "scripts\make-uat-evidence.cmd",
    "scripts\make-uat-evidence.ps1",
    "scripts\make-status-report.cmd",
    "scripts\make-release.cmd",
    "scripts\run-tests.cmd",
    "scripts\check-health.cmd"
  )
  foreach ($item in $required) {
    $path = Join-Path $Root $item
    if (-not (Test-Path $path)) {
      throw "Falta $item"
    }
  }
}

Step "Sintaxis PowerShell scripts" {
  $files = Get-ChildItem (Join-Path $Root "scripts") -Filter *.ps1
  foreach ($file in $files) {
    $null = [scriptblock]::Create((Get-Content $file.FullName -Raw))
  }
}

Step "Paquete productivo de referencia" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-production-package.ps1")
  if ($LASTEXITCODE -ne 0) {
    throw "check-production-package termino con codigo $LASTEXITCODE"
  }
}

Step "CORS navegador local" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-browser-cors.ps1")
  if ($LASTEXITCODE -ne 0) {
    throw "check-browser-cors termino con codigo $LASTEXITCODE"
  }
}

Step "Pruebas backend" {
  if (-not (Test-Path $Python)) {
    throw "No existe backend\.venv"
  }
  Push-Location $Backend
  try {
    & $Python -m pytest -q
    if ($LASTEXITCODE -ne 0) {
      throw "pytest termino con codigo $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
}

Step "Sintaxis TypeScript offline" {
  if (-not (Test-Path $TsModule)) {
    throw "No existe cache TypeScript offline en ..\work\tscheck"
  }
  $checker = @"
const fs=require('fs'),path=require('path'),ts=require('../work/tscheck/node_modules/typescript');
let bad=0,count=0;
function walk(d){
  for(const e of fs.readdirSync(d,{withFileTypes:true})){
    const p=path.join(d,e.name);
    if(e.isDirectory()) walk(p);
    else if(/\.(ts|tsx)$/.test(p) && !/\.d\.ts$/.test(p)){
      count++;
      const r=ts.transpileModule(fs.readFileSync(p,'utf8'),{
        compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.ESNext,jsx:ts.JsxEmit.ReactJSX},
        reportDiagnostics:true,
        fileName:p
      });
      for(const x of r.diagnostics||[]){
        bad++;
        console.error(p+': '+ts.flattenDiagnosticMessageText(x.messageText,' '));
      }
    }
  }
}
walk('frontend/src');
console.log('checked',count,'files; syntax diagnostics',bad);
process.exitCode=bad?1:0;
"@
  Push-Location $Root
  try {
    node -e $checker
    if ($LASTEXITCODE -ne 0) {
      throw "TypeScript offline termino con codigo $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
}

Step "Estado frontend dependencias" {
  if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    $warnings.Add("frontend\node_modules no existe; npm install sigue pendiente para build/test real de Vite.")
  } else {
    Push-Location $Frontend
    try {
      npm.cmd test
      if ($LASTEXITCODE -ne 0) {
        throw "npm test termino con codigo $LASTEXITCODE"
      }
      npm.cmd run build
      if ($LASTEXITCODE -ne 0) {
        throw "npm run build termino con codigo $LASTEXITCODE"
      }
    } finally {
      Pop-Location
    }
  }
}

Step "Whitespace git" {
  Push-Location $Root
  try {
    git diff --check
    if ($LASTEXITCODE -ne 0) {
      throw "git diff --check encontro problemas"
    }
  } finally {
    Pop-Location
  }
}

Write-Host ""
Write-Host "== Resultado preflight =="
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
Write-Host "Preflight OK para revision local."
