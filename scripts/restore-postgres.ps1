param(
  [Parameter(Mandatory = $true)]
  [string]$BackupFile,
  [Parameter(Mandatory = $true)]
  [string]$TargetDatabaseUrl,
  [string]$ConfirmRestore = ""
)

$ErrorActionPreference = "Stop"

function Convert-DatabaseUrl($Url) {
  $normalized = $Url -replace "^postgresql\+psycopg2://", "postgresql://"
  $uri = [System.Uri]$normalized
  $userInfo = $uri.UserInfo.Split(":", 2)
  if ($userInfo.Count -lt 2) {
    throw "TargetDatabaseUrl debe incluir usuario y clave para pg_restore."
  }
  return @{
    Host = $uri.Host
    Port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
    User = [System.Uri]::UnescapeDataString($userInfo[0])
    Password = [System.Uri]::UnescapeDataString($userInfo[1])
    Database = $uri.AbsolutePath.TrimStart("/")
  }
}

if ($ConfirmRestore -ne "RESTORE") {
  throw "Operacion bloqueada. Para restaurar, ejecute con -ConfirmRestore RESTORE. Esta accion puede sobrescribir datos."
}
if (-not (Test-Path $BackupFile)) {
  throw "No existe el archivo de backup: $BackupFile"
}
if (-not (Get-Command pg_restore -ErrorAction SilentlyContinue)) {
  throw "No se encontro pg_restore en PATH. Instale PostgreSQL client tools o agregue pg_restore al PATH."
}
if ($TargetDatabaseUrl -match "^sqlite") {
  throw "restore-postgres solo aplica para PostgreSQL, no SQLite."
}

$parts = Convert-DatabaseUrl $TargetDatabaseUrl
$previousPassword = $env:PGPASSWORD
try {
  $env:PGPASSWORD = $parts.Password
  pg_restore `
    --clean `
    --if-exists `
    --no-owner `
    --host $parts.Host `
    --port $parts.Port `
    --username $parts.User `
    --dbname $parts.Database `
    $BackupFile
  if ($LASTEXITCODE -ne 0) {
    throw "pg_restore termino con codigo $LASTEXITCODE"
  }
} finally {
  $env:PGPASSWORD = $previousPassword
}

Write-Host "Restore completado sobre base: $($parts.Database)"
