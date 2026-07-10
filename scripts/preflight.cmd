@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0preflight.ps1" %*
