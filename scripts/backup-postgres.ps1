param(
  [string]$EnvFile = ".env.production",
  [string]$DatabaseUrl = "",
  [string]$OutputDir = "backups"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

function Read-EnvValue($Path, $Key) {
  if (-not (Test-Path $Path)) {
    return ""
  }
  foreach ($line in Get-Content $Path) {
    if ($line.Trim().StartsWith("#") -or $line.Trim() -eq "") {
      continue
    }
    $idx = $line.IndexOf("=")
    if ($idx -lt 1) {
      continue
    }
    if ($line.Substring(0, $idx).Trim() -eq $Key) {
      return $line.Substring($idx + 1).Trim()
    }
  }
  return ""
}

function Convert-DatabaseUrl($Url) {
  $normalized = $Url -replace "^postgresql\+psycopg2://", "postgresql://"
  $uri = [System.Uri]$normalized
  $userInfo = $uri.UserInfo.Split(":", 2)
  if ($userInfo.Count -lt 2) {
    throw "DATABASE_URL debe incluir usuario y clave para pg_dump."
  }
  return @{
    Host = $uri.Host
    Port = if ($uri.Port -gt 0) { $uri.Port } else { 5432 }
    User = [System.Uri]::UnescapeDataString($userInfo[0])
    Password = [System.Uri]::UnescapeDataString($userInfo[1])
    Database = $uri.AbsolutePath.TrimStart("/")
  }
}

if (-not (Get-Command pg_dump -ErrorAction SilentlyContinue)) {
  throw "No se encontro pg_dump en PATH. Instale PostgreSQL client tools o agregue pg_dump al PATH."
}

$envPath = Join-Path $Root $EnvFile
if (-not $DatabaseUrl) {
  $DatabaseUrl = Read-EnvValue $envPath "DATABASE_URL"
}
if (-not $DatabaseUrl) {
  throw "Debe indicar -DatabaseUrl o configurar DATABASE_URL en $EnvFile."
}
if ($DatabaseUrl -match "^sqlite") {
  throw "backup-postgres solo aplica para PostgreSQL, no SQLite."
}

$parts = Convert-DatabaseUrl $DatabaseUrl
$outputPath = Join-Path $Root $OutputDir
if (-not (Test-Path $outputPath)) {
  New-Item -ItemType Directory -Path $outputPath | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$safeDb = ($parts.Database -replace "[^a-zA-Z0-9_.-]", "_")
$backupFile = Join-Path $outputPath "infomatt360-$safeDb-$timestamp.dump"

$previousPassword = $env:PGPASSWORD
try {
  $env:PGPASSWORD = $parts.Password
  pg_dump `
    --format=custom `
    --no-owner `
    --host $parts.Host `
    --port $parts.Port `
    --username $parts.User `
    --dbname $parts.Database `
    --file $backupFile
  if ($LASTEXITCODE -ne 0) {
    throw "pg_dump termino con codigo $LASTEXITCODE"
  }
} finally {
  $env:PGPASSWORD = $previousPassword
}

Write-Host "Backup generado: $backupFile"
