param(
  [string]$BackendUrl = "http://127.0.0.1:8000",
  [string]$FrontendUrl = "http://127.0.0.1:5173",
  [int]$IntervalSeconds = 60,
  [int]$Iterations = 0,
  [int]$FailureThreshold = 3
)

$ErrorActionPreference = "Stop"
$consecutiveFailures = 0
$iteration = 0

function Test-Endpoint($Name, $Url) {
  try {
    $started = Get-Date
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 10
    $elapsedMs = [int]((Get-Date) - $started).TotalMilliseconds
    Write-Host "$(Get-Date -Format o) OK $Name status=$($response.StatusCode) latency_ms=$elapsedMs url=$Url"
    return $true
  } catch {
    Write-Host "$(Get-Date -Format o) FAIL $Name url=$Url error=$($_.Exception.Message)"
    return $false
  }
}

do {
  $iteration += 1
  $checks = @(
    (Test-Endpoint "backend-health" "$BackendUrl/health"),
    (Test-Endpoint "backend-ready" "$BackendUrl/api/v1/health/ready"),
    (Test-Endpoint "frontend" $FrontendUrl)
  )
  if ($checks -contains $false) {
    $consecutiveFailures += 1
  } else {
    $consecutiveFailures = 0
  }

  if ($consecutiveFailures -ge $FailureThreshold) {
    Write-Host "$(Get-Date -Format o) ALERT consecutive_failures=$consecutiveFailures threshold=$FailureThreshold"
    exit 2
  }

  if ($Iterations -gt 0 -and $iteration -ge $Iterations) {
    break
  }
  Start-Sleep -Seconds ([Math]::Max($IntervalSeconds, 5))
} while ($true)

Write-Host "Monitor finalizado sin superar umbral de fallos."
