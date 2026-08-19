$ErrorActionPreference='Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Iso = Join-Path $Here 'SynapseOS-Nebula-amd64.iso'
$Sidecar = "$Iso.sha256"
if (-not (Test-Path -LiteralPath $Iso -PathType Leaf)) { throw "Missing $Iso" }
if (-not (Test-Path -LiteralPath $Sidecar -PathType Leaf)) { throw "Missing $Sidecar" }
$expected = ((Get-Content -LiteralPath $Sidecar | Select-Object -First 1) -split '\s+',2)[0].ToLowerInvariant()
$actual = (Get-FileHash -LiteralPath $Iso -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $expected) { throw "SHA-256 mismatch. Expected $expected, got $actual" }
Write-Host "SynapseOS-Nebula-amd64.iso: VERIFIED" -ForegroundColor Green
Write-Host $actual
