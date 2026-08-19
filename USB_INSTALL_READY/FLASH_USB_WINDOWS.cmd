@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0FLASH_USB_WINDOWS.ps1"
if errorlevel 1 pause
