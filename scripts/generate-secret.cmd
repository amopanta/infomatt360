@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0generate-secret.ps1" %*
