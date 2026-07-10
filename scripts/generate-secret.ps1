param(
  [int]$Bytes = 48
)

$ErrorActionPreference = "Stop"
if ($Bytes -lt 32) {
  throw "Use al menos 32 bytes para SECRET_KEY."
}

$buffer = New-Object byte[] $Bytes
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try {
  $rng.GetBytes($buffer)
}
finally {
  $rng.Dispose()
}

$secret = [Convert]::ToBase64String($buffer).TrimEnd("=") -replace "\+", "-" -replace "/", "_"
Write-Host $secret
