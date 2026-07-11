param(
  [int]$BackendPort = 8000,
  [int]$FrontendPort = 5173
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"
$Npm = (Get-Command npm.cmd).Source

if (-not (Test-Path $Python)) {
  throw "No existe backend\.venv\Scripts\python.exe"
}
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
  throw "No existe frontend\node_modules. Ejecute .\scripts\install-frontend.cmd"
}
if (-not (Test-Path (Join-Path $Frontend "dist\index.html"))) {
  Push-Location $Frontend
  try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) {
      throw "npm run build termino con codigo $LASTEXITCODE"
    }
  } finally {
    Pop-Location
  }
}

function Start-LocalProcess($File, $Arguments, $WorkingDirectory) {
  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = $File
  $psi.Arguments = $Arguments
  $psi.WorkingDirectory = $WorkingDirectory
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $psi
  [void]$process.Start()
  return $process
}

function Wait-Url($Name, $Url) {
  for ($i = 0; $i -lt 40; $i++) {
    try {
      Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2 | Out-Null
      Write-Host "$Name listo: $Url"
      return
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  throw "$Name no respondio en $Url"
}

$backendProc = $null
$frontendProc = $null
try {
  $backendProc = Start-LocalProcess $Python "-m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort" $Backend
  $frontendProc = Start-LocalProcess $Npm "run preview -- --host 127.0.0.1 --port $FrontendPort" $Frontend

  Wait-Url "Backend" "http://127.0.0.1:$BackendPort/api/v1/health/ready"
  Wait-Url "Frontend" "http://127.0.0.1:$FrontendPort"

  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-health.ps1") -BackendUrl "http://127.0.0.1:$BackendPort" -FrontendUrl "http://127.0.0.1:$FrontendPort"
  if ($LASTEXITCODE -ne 0) {
    throw "check-health termino con codigo $LASTEXITCODE"
  }

  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Root "scripts\check-demo.ps1") -BackendUrl "http://127.0.0.1:$BackendPort"
  if ($LASTEXITCODE -ne 0) {
    throw "check-demo termino con codigo $LASTEXITCODE"
  }

  Write-Host "Full stack OK."
}
finally {
  foreach ($process in @($backendProc, $frontendProc)) {
    if ($process -and -not $process.HasExited) {
      $process.Kill()
      $process.WaitForExit(5000) | Out-Null
    }
  }
}
