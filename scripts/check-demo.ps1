param(
  [string]$BackendUrl = "http://127.0.0.1:8000",
  [string]$Email = "admin@infomatt360.demo",
  [string]$Password = "Demo12345!",
  [string]$ProjectId = "demo-project-infomatt360",
  [string]$TemplateId = "demo-template-characterization"
)

$ErrorActionPreference = "Stop"

function Assert-Status($Name, [scriptblock]$Action) {
  Write-Host "== $Name =="
  $result = & $Action
  Write-Host "OK: $Name"
  return $result
}

$login = Assert-Status "Login demo" {
  Invoke-RestMethod -Method Post -Uri "$BackendUrl/api/v1/auth/login" -ContentType "application/json" -Body (@{ email = $Email; password = $Password } | ConvertTo-Json)
}

$headers = @{ Authorization = "Bearer $($login.access_token)" }

Assert-Status "Sesion" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/auth/session" -Headers $headers } | Out-Null
Assert-Status "Dashboard" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/dashboard/projects/$ProjectId/summary" -Headers $headers } | Out-Null
Assert-Status "Formularios" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/builder/templates/$ProjectId" -Headers $headers } | Out-Null
Assert-Status "Registros" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/runtime/template/$TemplateId/records/search?limit=10" -Headers $headers } | Out-Null
Assert-Status "Reportes" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/reports/project/$ProjectId/summary" -Headers $headers } | Out-Null
Assert-Status "Mapas" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/gis/map/$ProjectId" -Headers $headers } | Out-Null
Assert-Status "Revision historial" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/review/records/demo-record-001/actions" -Headers $headers } | Out-Null
Assert-Status "API keys listado" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/api-keys/$ProjectId" -Headers $headers } | Out-Null
Assert-Status "Usuarios admin" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/security/admin/projects/$ProjectId/users" -Headers $headers } | Out-Null
Assert-Status "Mensajes conteos" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/messages/internal/$ProjectId/counts" -Headers $headers } | Out-Null
Assert-Status "Mensajes inbox" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/messages/internal/$ProjectId/inbox" -Headers $headers } | Out-Null
Assert-Status "Auditoria" { Invoke-RestMethod -Uri "$BackendUrl/api/v1/audit/?project_id=$ProjectId" -Headers $headers } | Out-Null
Assert-Status "Metricas operativas" {
  $metrics = Invoke-RestMethod -Uri "$BackendUrl/api/v1/health/metrics" -Headers $headers
  if (-not $metrics.http.latency_percentiles_ms.p95 -and $metrics.http.latency_percentiles_ms.p95 -ne 0) {
    throw "No se encontro p95 en metricas operativas"
  }
  $metrics
} | Out-Null

Write-Host "Demo API OK."
