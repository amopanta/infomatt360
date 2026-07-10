param(
  [string]$EnvFile = "backend\.env"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $Root $EnvFile
$failures = New-Object System.Collections.Generic.List[string]
$warnings = New-Object System.Collections.Generic.List[string]

function Fail($Message) {
  $script:failures.Add($Message)
  Write-Host "FALLO: $Message"
}

function Warn($Message) {
  $script:warnings.Add($Message)
  Write-Host "ADVERTENCIA: $Message"
}

function Value($Key) {
  return ($pairs[$Key] -as [string])
}

function LowerValue($Key) {
  return (Value $Key).ToLowerInvariant()
}

function RequireBool($Key) {
  $raw = LowerValue $Key
  if ($raw -notin @("true", "false")) {
    Fail "$Key debe ser true o false."
  }
  return $raw
}

function RequireInt($Key, [int]$Min, [int]$Max) {
  $parsed = 0
  if (-not [int]::TryParse((Value $Key), [ref]$parsed) -or $parsed -lt $Min -or $parsed -gt $Max) {
    Fail "$Key debe ser un entero entre $Min y $Max."
  }
  return $parsed
}

if (-not (Test-Path $EnvPath)) {
  throw "No existe $EnvFile"
}

$pairs = @{}
foreach ($line in Get-Content $EnvPath) {
  if ($line.Trim().StartsWith("#") -or $line.Trim() -eq "") {
    continue
  }
  $idx = $line.IndexOf("=")
  if ($idx -lt 1) {
    continue
  }
  $key = $line.Substring(0, $idx).Trim()
  $value = $line.Substring($idx + 1).Trim()
  $pairs[$key] = $value
}

if ((LowerValue "ENVIRONMENT") -notin @("production", "prod")) {
  Fail "ENVIRONMENT debe ser production/prod."
}
if ((RequireBool "DEBUG") -ne "false") {
  Fail "DEBUG debe ser false."
}
if ((RequireBool "AUTO_CREATE_TABLES") -ne "false") {
  Fail "AUTO_CREATE_TABLES debe ser false; en produccion usar Alembic, no create_all automatico."
}
if ((Value "DATABASE_URL") -match "^sqlite") {
  Fail "DATABASE_URL no debe usar SQLite en produccion."
}
if (-not $pairs["DATABASE_URL"]) {
  Fail "DATABASE_URL es obligatorio."
}
if ((Value "DATABASE_URL") -match "CHANGE|REPLACE|example\.com") {
  Fail "DATABASE_URL contiene placeholders; configurar host, usuario y clave reales."
}
if ((Value "DATABASE_URL") -match "^postgresql\+psycopg://") {
  Fail "DATABASE_URL usa postgresql+psycopg pero el proyecto instala psycopg2-binary; usar postgresql+psycopg2."
}
$poolSize = RequireInt "DB_POOL_SIZE" 1 1000
$maxOverflow = RequireInt "DB_MAX_OVERFLOW" 0 1000
$poolTimeout = RequireInt "DB_POOL_TIMEOUT_SECONDS" 1 300
$poolRecycle = RequireInt "DB_POOL_RECYCLE_SECONDS" 60 86400
if (-not $pairs["SECRET_KEY"] -or (Value "SECRET_KEY") -match "CHANGE|REPLACE|development|production" -or (Value "SECRET_KEY").Length -lt 32) {
  Fail "SECRET_KEY debe ser aleatorio, fuerte y no placeholder."
}
if (-not $pairs["REFRESH_COOKIE_NAME"]) {
  Fail "REFRESH_COOKIE_NAME es obligatorio."
}
if ((RequireBool "REFRESH_COOKIE_SECURE") -ne "true") {
  Fail "REFRESH_COOKIE_SECURE debe ser true en produccion."
}
if ((LowerValue "REFRESH_COOKIE_SAMESITE") -notin @("strict", "lax")) {
  Fail "REFRESH_COOKIE_SAMESITE debe ser strict o lax."
}
if ((Value "FRONTEND_URL") -notmatch "^https://") {
  Fail "FRONTEND_URL debe usar HTTPS."
}
if (-not $pairs["CORS_ALLOWED_ORIGINS"]) {
  Fail "CORS_ALLOWED_ORIGINS es obligatorio para restringir origenes permitidos."
}
if ((Value "CORS_ALLOWED_ORIGINS") -match "\*") {
  Fail "CORS_ALLOWED_ORIGINS no debe usar comodin * en produccion."
}
foreach ($origin in ((Value "CORS_ALLOWED_ORIGINS") -split ",")) {
  if ($origin.Trim() -and $origin.Trim() -notmatch "^https://") {
    Fail "Cada origen CORS productivo debe usar HTTPS: $($origin.Trim())"
  }
}
$rateLimitEnabled = RequireBool "API_RATE_LIMIT_ENABLED"
if ($rateLimitEnabled -ne "true") {
  Fail "API_RATE_LIMIT_ENABLED debe ser true en produccion."
}
$rateLimitRequests = RequireInt "API_RATE_LIMIT_REQUESTS" 1 100000000
$rateLimitWindow = RequireInt "API_RATE_LIMIT_WINDOW_SECONDS" 1 86400
$apiKeyRequests = RequireInt "API_RATE_LIMIT_API_KEY_REQUESTS" 1 100000000
$highVolumeRequests = RequireInt "API_RATE_LIMIT_HIGH_VOLUME_REQUESTS" 1 1000000000
if ($apiKeyRequests -lt $rateLimitRequests) {
  Warn "API_RATE_LIMIT_API_KEY_REQUESTS es menor que API_RATE_LIMIT_REQUESTS; revisar si las integraciones tendran suficiente margen."
}
if ($highVolumeRequests -lt $apiKeyRequests) {
  Fail "API_RATE_LIMIT_HIGH_VOLUME_REQUESTS debe ser mayor o igual a API_RATE_LIMIT_API_KEY_REQUESTS."
}
$rateLimitBackend = LowerValue "API_RATE_LIMIT_BACKEND"
if ($rateLimitBackend -notin @("memory", "redis")) {
  Fail "API_RATE_LIMIT_BACKEND debe ser memory o redis."
}
$authThrottleBackend = LowerValue "AUTH_THROTTLE_BACKEND"
if ($authThrottleBackend -notin @("db", "redis")) {
  Fail "AUTH_THROTTLE_BACKEND debe ser db o redis."
}
if (($rateLimitBackend -eq "redis" -or $authThrottleBackend -eq "redis") -and (-not $pairs["REDIS_URL"] -or (Value "REDIS_URL") -match "CHANGE|REPLACE|example\.com")) {
  Fail "REDIS_URL es obligatorio y no debe contener placeholders cuando API_RATE_LIMIT_BACKEND o AUTH_THROTTLE_BACKEND usan redis."
}
if ($rateLimitBackend -eq "memory") {
  Warn "API_RATE_LIMIT_BACKEND=memory solo es apto para una instancia/worker; en produccion multiworker se recomienda redis."
}
if ($authThrottleBackend -eq "db") {
  Warn "AUTH_THROTTLE_BACKEND=db es valido, pero Redis reduce carga en login/MFA/recuperacion bajo alto volumen."
}
if (-not $pairs["API_RATE_LIMIT_TRUSTED_PROXY_IPS"]) {
  Warn "API_RATE_LIMIT_TRUSTED_PROXY_IPS vacio; correcto si no hay reverse proxy, pero no se confiara en X-Forwarded-For."
}
$cacheTtl = RequireInt "API_KEY_PROFILE_CACHE_TTL_SECONDS" 0 300
if ($cacheTtl -eq 0) {
  Warn "API_KEY_PROFILE_CACHE_TTL_SECONDS=0 desactiva cache; bajo alto trafico aumenta consultas a base de datos."
}
if (-not $pairs["SMTP_HOST"]) {
  Fail "SMTP_HOST es obligatorio para recuperacion de contrasena."
}
if (-not $pairs["SMTP_FROM_EMAIL"]) {
  Fail "SMTP_FROM_EMAIL es obligatorio."
}
if (-not $pairs["SMTP_USERNAME"]) {
  Warn "SMTP_USERNAME vacio; solo valido si el proveedor SMTP no requiere autenticacion."
}
if (-not $pairs["SMTP_PASSWORD"]) {
  Warn "SMTP_PASSWORD vacio; solo valido si el proveedor SMTP no requiere autenticacion."
}
if ((Value "SMTP_HOST") -match "example\.com") {
  Fail "SMTP_HOST contiene placeholder example.com."
}
if ((Value "SMTP_PASSWORD") -match "CHANGE|REPLACE") {
  Fail "SMTP_PASSWORD contiene placeholder; configurar clave real o secreto del proveedor."
}
if ((Value "UPLOAD_DIRECTORY") -match "^\./") {
  Warn "UPLOAD_DIRECTORY es relativo; en produccion se recomienda ruta absoluta persistente."
}
if (-not $pairs["UPLOAD_DIRECTORY"]) {
  Fail "UPLOAD_DIRECTORY es obligatorio."
} elseif (-not (Test-Path (Value "UPLOAD_DIRECTORY"))) {
  Fail "UPLOAD_DIRECTORY debe existir antes del despliegue."
} elseif (-not (Test-Path (Value "UPLOAD_DIRECTORY") -PathType Container)) {
  Fail "UPLOAD_DIRECTORY debe ser un directorio."
} else {
  $probe = Join-Path (Value "UPLOAD_DIRECTORY") ".infomatt360-doctor-check"
  try {
    Set-Content -LiteralPath $probe -Value "ok" -Encoding UTF8
    Remove-Item -LiteralPath $probe -Force
  } catch {
    Fail "UPLOAD_DIRECTORY debe permitir escritura y borrado para el proceso backend."
  }
}
$maxFileSizeMb = RequireInt "DEFAULT_MAX_FILE_SIZE_MB" 1 1024
$requestLogging = RequireBool "REQUEST_LOGGING_ENABLED"
if ($requestLogging -ne "true") {
  Fail "REQUEST_LOGGING_ENABLED debe ser true para trazabilidad productiva."
}
if (-not $pairs["REQUEST_ID_HEADER"]) {
  Fail "REQUEST_ID_HEADER es obligatorio."
}
$metricsEnabled = RequireBool "METRICS_ENABLED"
if ($metricsEnabled -ne "true") {
  Fail "METRICS_ENABLED debe ser true para monitoreo productivo."
}
$retryBackoff = RequireInt "BULK_WORKER_RETRY_BACKOFF_SECONDS" 1 86400
$retryMaxBackoff = RequireInt "BULK_WORKER_RETRY_MAX_BACKOFF_SECONDS" 1 604800
$staleAfter = RequireInt "BULK_WORKER_STALE_AFTER_SECONDS" 60 604800
if ($retryMaxBackoff -lt $retryBackoff) {
  Fail "BULK_WORKER_RETRY_MAX_BACKOFF_SECONDS debe ser mayor o igual a BULK_WORKER_RETRY_BACKOFF_SECONDS."
}
if ($staleAfter -lt $retryBackoff) {
  Warn "BULK_WORKER_STALE_AFTER_SECONDS es menor que el backoff inicial; revisar estrategia de recuperacion de jobs."
}
$securityHeaders = RequireBool "SECURITY_HEADERS_ENABLED"
if ($securityHeaders -ne "true") {
  Fail "SECURITY_HEADERS_ENABLED debe ser true en produccion."
}
if (-not $pairs["CONTENT_SECURITY_POLICY"] -or (Value "CONTENT_SECURITY_POLICY") -notmatch "default-src") {
  Fail "CONTENT_SECURITY_POLICY debe estar configurada al menos con default-src."
}
if ((LowerValue "REFERRER_POLICY") -notin @("no-referrer", "same-origin", "strict-origin", "strict-origin-when-cross-origin")) {
  Fail "REFERRER_POLICY debe usar una politica segura reconocida."
}
if (-not $pairs["PERMISSIONS_POLICY"]) {
  Fail "PERMISSIONS_POLICY es obligatoria."
}
if ((LowerValue "X_FRAME_OPTIONS") -notin @("deny", "sameorigin")) {
  Fail "X_FRAME_OPTIONS debe ser DENY o SAMEORIGIN."
}

Write-Host ""
Write-Host "== Resultado doctor produccion =="
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

Write-Host "Configuracion apta para despliegue productivo basico."
