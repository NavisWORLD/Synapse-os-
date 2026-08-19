$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Tool = Join-Path $Here 'tools\synapse_usb_flasher.py'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$admin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host 'Administrator access is required only for raw USB writing.' -ForegroundColor Yellow
    $arg = "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    Start-Process powershell.exe -Verb RunAs -ArgumentList $arg
    exit
}

$py = Get-Command py.exe -ErrorAction SilentlyContinue
if ($py) {
    & $py.Source -3 $Tool
} else {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if (-not $python) {
        throw 'Python 3 was not found. Use Rufus or balenaEtcher with SynapseOS-Nebula-amd64.iso, or install Python 3 to use the Synapse flasher.'
    }
    & $python.Source $Tool
}
if ($LASTEXITCODE -ne 0) { throw "Synapse USB flasher exited with code $LASTEXITCODE" }
