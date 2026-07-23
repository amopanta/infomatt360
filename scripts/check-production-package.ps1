$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$failures = New-Object System.Collections.Generic.List[string]

function Fail($Message) {
  $script:failures.Add($Message)
  Write-Host "FALLO: $Message"
}

function RequireFile($RelativePath) {
  $path = Join-Path $Root $RelativePath
  if (-not (Test-Path $path)) {
    Fail "Falta $RelativePath"
  }
  return $path
}

function RequireContains($Path, $Pattern, $Description) {
  $content = Get-Content $Path -Raw
  if ($content -notmatch $Pattern) {
    Fail "$Description no encontrado en $([System.IO.Path]::GetFileName($Path))"
  }
}

$compose = RequireFile "docker-compose.production.example.yml"
$dockerignore = RequireFile ".dockerignore"
$backendDockerfile = RequireFile "deploy\backend.Dockerfile"
$frontendDockerfile = RequireFile "deploy\frontend.Dockerfile"
$nginxConfig = RequireFile "deploy\nginx.frontend.conf"
$backendLbConfig = RequireFile "deploy\nginx.backend-lb.conf"
$prometheusConfig = RequireFile "deploy\prometheus.yml"
$grafanaDatasource = RequireFile "deploy\grafana\provisioning\datasources\prometheus.yml"
$grafanaDashboardProvider = RequireFile "deploy\grafana\provisioning\dashboards\dashboards.yml"
$grafanaDashboard = RequireFile "deploy\grafana\provisioning\dashboards\infomatt360-overview.json"
$deployDoc = RequireFile "docs\61_DESPLIEGUE_PRODUCCION_REFERENCIA.md"
$goLiveDoc = RequireFile "docs\62_CHECKLIST_GO_LIVE.md"
$backupDoc = RequireFile "docs\63_BACKUP_RESTORE_POSTGRES.md"
$rollbackDoc = RequireFile "docs\64_ROLLBACK_OPERATIVO.md"
$operationsDoc = RequireFile "docs\65_OPERACION_MONITOREO_INCIDENTES.md"
$backupScript = RequireFile "scripts\backup-postgres.ps1"
$restoreScript = RequireFile "scripts\restore-postgres.ps1"
$monitorScript = RequireFile "scripts\monitor-health.ps1"

if ($failures.Count -eq 0) {
  RequireContains $compose "(?m)^\s*postgres:" "Servicio postgres"
  RequireContains $compose "(?m)^\s*redis:" "Servicio redis"
  RequireContains $compose "(?m)^\s*backend-1:" "Servicio backend-1"
  RequireContains $compose "(?m)^\s*backend-2:" "Servicio backend-2"
  RequireContains $compose "(?m)^\s*backend-lb:" "Servicio backend-lb (balanceador)"
  RequireContains $compose "(?m)^\s*worker-bulk:" "Servicio worker-bulk"
  RequireContains $compose "(?m)^\s*worker-scheduler:" "Servicio worker-scheduler"
  RequireContains $compose "(?m)^\s*frontend:" "Servicio frontend"
  RequireContains $compose "REDIS_URL:\s*redis://redis:6379/0" "REDIS_URL interna"
  RequireContains $compose "API_RATE_LIMIT_BACKEND:\s*redis" "Rate limiting Redis"
  RequireContains $compose "AUTH_THROTTLE_BACKEND:\s*redis" "Auth throttling Redis"
  RequireContains $compose "process_bulk_jobs" "Comando del worker bulk"
  RequireContains $compose "run_scheduled_tasks" "Comando del worker scheduler"
  RequireContains $compose "uploads_data:/var/lib/infomatt360/uploads" "Volumen persistente de uploads"
  RequireContains $compose "nginx\.backend-lb\.conf" "Config nginx del balanceador"
  RequireContains $compose "(?m)^\s*prometheus:" "Servicio prometheus"
  RequireContains $compose "(?m)^\s*grafana:" "Servicio grafana"
  RequireContains $compose "secrets/metrics_token" "Montaje del token de scraping de metricas"
  RequireContains $compose "GF_SECURITY_ADMIN_PASSWORD" "Contrasena de Grafana"

  RequireContains $dockerignore "(?m)^\.env\r?$" "Exclusion .env"
  RequireContains $dockerignore "(?m)^\.env\.production\r?$" "Exclusion .env.production"
  RequireContains $dockerignore "(?m)^backend/\.venv\r?$" "Exclusion backend/.venv"
  RequireContains $dockerignore "(?m)^frontend/node_modules\r?$" "Exclusion frontend/node_modules"
  RequireContains $dockerignore "(?m)^backend/uploads\r?$" "Exclusion backend/uploads"

  RequireContains $backendDockerfile "uvicorn" "Arranque uvicorn backend"
  RequireContains $frontendDockerfile "npm ci" "Instalacion reproducible frontend"
  RequireContains $frontendDockerfile "nginx" "Runtime nginx frontend"
  RequireContains $nginxConfig 'try_files \$uri \$uri/ /index.html' "Fallback SPA nginx"
  RequireContains $backendLbConfig "server backend-1:8000" "Upstream backend-1 en balanceador"
  RequireContains $backendLbConfig "server backend-2:8000" "Upstream backend-2 en balanceador"
  RequireContains $backendLbConfig "X-Forwarded-For" "Forwarding de IP real en balanceador"
  RequireContains $prometheusConfig "backend-1:8000" "Target backend-1 en Prometheus"
  RequireContains $prometheusConfig "backend-2:8000" "Target backend-2 en Prometheus"
  RequireContains $prometheusConfig "metrics/prometheus" "Ruta de metricas en Prometheus"
  RequireContains $grafanaDatasource "prometheus:9090" "Datasource de Grafana apunta a Prometheus"
  RequireContains $grafanaDashboardProvider "/etc/grafana/provisioning/dashboards" "Provider de dashboards de Grafana"
  RequireContains $grafanaDashboard "infomatt360_http_requests_total" "Dashboard inicial usa metricas reales"

  RequireContains $deployDoc "doctor-production" "Referencia doctor productivo"
  RequireContains $deployDoc "docker compose" "Comando Docker Compose"
  RequireContains $goLiveDoc "Rollback" "Seccion rollback/go-live"
  RequireContains $goLiveDoc "Backup" "Seccion backups/go-live"
  RequireContains $backupDoc "pg_dump" "Procedimiento pg_dump"
  RequireContains $backupDoc "pg_restore" "Procedimiento pg_restore"
  RequireContains $rollbackDoc "restore-postgres" "Procedimiento rollback con restore"
  RequireContains $rollbackDoc "X-Request-ID" "Trazabilidad rollback"
  RequireContains $operationsDoc "monitor-health" "Procedimiento monitoreo"
  RequireContains $operationsDoc "Severidad 1" "Clasificacion de incidentes"
  RequireContains $backupScript "pg_dump" "Script backup PostgreSQL"
  RequireContains $restoreScript "ConfirmRestore" "Confirmacion restore PostgreSQL"
  RequireContains $monitorScript "FailureThreshold" "Umbral de fallos monitor"
}

Write-Host ""
Write-Host "== Resultado paquete productivo =="
if ($failures.Count -gt 0) {
  Write-Host "Fallos:"
  foreach ($failure in $failures) {
    Write-Host "- $failure"
  }
  exit 1
}

Write-Host "Paquete productivo de referencia OK."
