@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make-uat-evidence.ps1" %*
