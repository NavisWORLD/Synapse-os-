$ErrorActionPreference = 'Stop'

$Name = 'SynapseOS-Nebula-amd64.iso'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Here

$Parts = Get-ChildItem -LiteralPath $Here -Filter "$Name.part-*" -File | Sort-Object Name
if (-not $Parts -or $Parts.Count -eq 0) {
    throw "No $Name.part-* files found beside this script."
}

$IsoChecksumPath = Join-Path $Here "$Name.sha256"
$PartsChecksumPath = Join-Path $Here "$Name.parts.sha256"
foreach ($Required in @($IsoChecksumPath, $PartsChecksumPath)) {
    if (-not (Test-Path -LiteralPath $Required -PathType Leaf)) {
        throw "Missing required file: $Required"
    }
}

foreach ($Line in Get-Content -LiteralPath $PartsChecksumPath) {
    if ([string]::IsNullOrWhiteSpace($Line)) { continue }
    $Fields = $Line -split '\s+', 2
    if ($Fields.Count -ne 2) { throw "Invalid checksum line: $Line" }
    $Expected = $Fields[0].ToLowerInvariant()
    $FileName = $Fields[1].Trim().TrimStart('*')
    $PartPath = Join-Path $Here $FileName
    if (-not (Test-Path -LiteralPath $PartPath -PathType Leaf)) {
        throw "Missing release part: $FileName"
    }
    $Actual = (Get-FileHash -LiteralPath $PartPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected) {
        throw "Checksum mismatch for $FileName"
    }
    Write-Host "Verified $FileName"
}

$OutputPath = Join-Path $Here $Name
if (Test-Path -LiteralPath $OutputPath) {
    Remove-Item -LiteralPath $OutputPath -Force
}

$Output = [System.IO.File]::Open($OutputPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
try {
    foreach ($Part in $Parts) {
        Write-Host "Appending $($Part.Name)"
        $Input = [System.IO.File]::OpenRead($Part.FullName)
        try {
            $Input.CopyTo($Output)
        }
        finally {
            $Input.Dispose()
        }
    }
}
finally {
    $Output.Dispose()
}

$IsoLine = (Get-Content -LiteralPath $IsoChecksumPath | Select-Object -First 1)
$IsoFields = $IsoLine -split '\s+', 2
if ($IsoFields.Count -ne 2) { throw "Invalid ISO checksum file." }
$ExpectedIso = $IsoFields[0].ToLowerInvariant()
$ActualIso = (Get-FileHash -LiteralPath $OutputPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualIso -ne $ExpectedIso) {
    Remove-Item -LiteralPath $OutputPath -Force
    throw "Reassembled ISO checksum mismatch. Output removed."
}

Write-Host "Reassembled and verified: $OutputPath"
