@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0check-uat-readiness.ps1" %*
