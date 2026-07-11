@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0monitor-health.ps1" %*
