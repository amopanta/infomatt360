@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-uat-technical-checks.ps1" %*
