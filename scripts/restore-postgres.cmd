@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore-postgres.ps1" %*
