$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
  throw "No existe backend\.venv\Scripts\python.exe"
}

$process = $null
try {
  $psi = [System.Diagnostics.ProcessStartInfo]::new()
  $psi.FileName = $Python
  $psi.Arguments = "-m uvicorn app.main:app --host 127.0.0.1 --port 8000"
  $psi.WorkingDirectory = $Backend
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $process = [System.Diagnostics.Process]::new()
  $process.StartInfo = $psi
  [void]$process.Start()

  for ($i = 0; $i -lt 40; $i++) {
    try {
      Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000/api/v1/health/ready" -TimeoutSec 2 | Out-Null
      break
    } catch {
      Start-Sleep -Seconds 1
    }
    if ($i -eq 39) {
      throw "Backend no respondio para validar CORS"
    }
  }

  $origins = @(
    "http://localhost:5173",
    "http://127.0.0.1:5173"
  )

  foreach ($origin in $origins) {
    $response = Invoke-WebRequest `
      -UseBasicParsing `
      -Method Options `
      -Uri "http://127.0.0.1:8000/api/v1/auth/login" `
      -Headers @{
        Origin = $origin
        "Access-Control-Request-Method" = "POST"
        "Access-Control-Request-Headers" = "Content-Type"
      } `
      -TimeoutSec 5

    if ($response.StatusCode -ne 200) {
      throw "CORS preflight fallo para $origin con estado $($response.StatusCode)"
    }
    if ($response.Headers["Access-Control-Allow-Origin"] -ne $origin) {
      throw "CORS no devolvio Access-Control-Allow-Origin esperado para $origin"
    }
  }

  Write-Host "CORS navegador OK para localhost y 127.0.0.1."
}
finally {
  if ($process -and -not $process.HasExited) {
    $process.Kill()
    $process.WaitForExit(5000) | Out-Null
  }
}
