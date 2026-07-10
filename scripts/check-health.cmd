@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-health.ps1" %*
