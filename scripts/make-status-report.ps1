$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$OutputsPath = Join-Path $Root "..\outputs"
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $OutputsPath)) {
  New-Item -ItemType Directory -Path $OutputsPath | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$reportPath = Join-Path $OutputsPath "infomatt360-status-$timestamp.md"

function Capture($Title, [scriptblock]$Action) {
  $output = New-Object System.Collections.Generic.List[string]
  $exitCode = 0
  try {
    $result = & $Action 2>&1
    foreach ($line in $result) {
      $output.Add([string]$line)
    }
    if ($LASTEXITCODE -ne $null -and $LASTEXITCODE -ne 0) {
      $exitCode = $LASTEXITCODE
    }
  } catch {
    $exitCode = 1
    $output.Add($_.Exception.Message)
  }

  if ($Title -eq "Whitespace git" -and $exitCode -ne 0) {
    $realIssues = @($output | Where-Object {
      $_.Trim() -ne "" -and $_ -notmatch "LF will be replaced by CRLF"
    })
    if ($realIssues.Count -eq 0) {
      $exitCode = 0
    }
  }

  return @{
    Title = $Title
    ExitCode = $exitCode
    Output = $output
  }
}

$sections = New-Object System.Collections.Generic.List[object]
$sections.Add((Capture "Doctor de entorno" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\doctor.ps1")
}))
$sections.Add((Capture "Demo DB offline" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-demo-db.ps1")
}))
$sections.Add((Capture "Paquete productivo de referencia" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-production-package.ps1")
}))
$sections.Add((Capture "CORS navegador local" {
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-browser-cors.ps1")
}))
$sections.Add((Capture "Pruebas backend" {
  Push-Location $Backend
  try {
    & $Python -m pytest -q
  } finally {
    Pop-Location
  }
}))
$sections.Add((Capture "Frontend test/build" {
  if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    throw "frontend\node_modules no existe; ejecutar .\scripts\install-frontend.cmd"
  }
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
}))
$sections.Add((Capture "TypeScript offline" {
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
  } finally {
    Pop-Location
  }
}))
$sections.Add((Capture "Whitespace git" {
  Push-Location $Root
  try {
    git diff --check
  } finally {
    Pop-Location
  }
}))

$latestPackages = Get-ChildItem $OutputsPath -Filter "infomatt360-mvp-source-*.zip" -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 3

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# InfoMatt360 - reporte de estado")
$lines.Add("")
$lines.Add("Generado: $(Get-Date -Format o)")
$lines.Add("")
$lines.Add("## Resumen")
$lines.Add("")
$failed = @($sections | Where-Object { $_.ExitCode -ne 0 })
$frontendInstalled = Test-Path (Join-Path $Frontend "node_modules")
if ($failed.Count -eq 0) {
  $lines.Add("- Estado general: OK para revision local.")
} else {
  $lines.Add("- Estado general: revisar fallos en secciones.")
}
if ($frontendInstalled) {
  $lines.Add("- Frontend: dependencias instaladas; tests y build se validan en este reporte.")
} else {
  $lines.Add("- Frontend: build real de Vite pendiente hasta completar npm install.")
}
$lines.Add("- Demo: verificar con .\scripts\prepare-demo.cmd y .\scripts\check-demo-db.cmd.")
$lines.Add("- Full stack: ejecutar .\scripts\check-full-stack.cmd como validacion independiente.")
$lines.Add("")
$lines.Add("## Paquetes recientes")
$lines.Add("")
if ($latestPackages.Count -eq 0) {
  $lines.Add("- No se encontraron paquetes ZIP.")
} else {
  foreach ($package in $latestPackages) {
    $hashFile = [System.IO.Path]::ChangeExtension($package.FullName, ".sha256.txt")
    $lines.Add("- " + $package.Name + " (" + $package.Length + " bytes)")
    if (Test-Path $hashFile) {
      $hashLine = (Get-Content $hashFile | Where-Object { $_ -like "SHA256=*" } | Select-Object -First 1)
      if ($hashLine) {
        $lines.Add("  - $hashLine")
      }
    }
  }
}

foreach ($section in $sections) {
  $lines.Add("")
  $lines.Add("## $($section.Title)")
  $lines.Add("")
  $lines.Add("ExitCode: " + $section.ExitCode)
  $lines.Add("")
  $lines.Add('```text')
  foreach ($line in $section.Output) {
    $lines.Add($line)
  }
  $lines.Add('```')
}

[System.IO.File]::WriteAllLines($reportPath, $lines, [System.Text.UTF8Encoding]::new($false))
Write-Host "Reporte generado: $reportPath"
