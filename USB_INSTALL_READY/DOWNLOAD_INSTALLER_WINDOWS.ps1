$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tool = Join-Path $Here 'tools\download_release.py'

function Find-Python {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) { return @($py.Source, '-3') }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) { return @($python.Source) }
    throw 'Python 3 was not found. Install Python 3, or download the GitHub Release assets manually as described in START_HERE.md.'
}

$cmd = Find-Python
$exe = $cmd[0]
$args = @()
if ($cmd.Count -gt 1) { $args += $cmd[1..($cmd.Count - 1)] }
$args += $Tool
& $exe @args
if ($LASTEXITCODE -ne 0) { throw "Downloader failed with exit code $LASTEXITCODE" }
Write-Host ''
Write-Host 'Release files downloaded. Next run reassemble-usb-installer.ps1' -ForegroundColor Green
