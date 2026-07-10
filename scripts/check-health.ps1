param(
  [string]$BackendUrl = "http://127.0.0.1:8000",
  [string]$FrontendUrl = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"

function Test-Url($Name, $Url) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 5
    Write-Host "$Name OK ($($response.StatusCode)) - $Url"
  } catch {
    Write-Error "$Name no responde en $Url. Detalle: $($_.Exception.Message)"
  }
}

Test-Url "Backend health" "$BackendUrl/health"
Test-Url "Backend API v1" "$BackendUrl/api/v1/health/"
Test-Url "Backend readiness" "$BackendUrl/api/v1/health/ready"
Test-Url "Frontend" $FrontendUrl
