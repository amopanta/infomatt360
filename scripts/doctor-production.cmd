@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0doctor-production.ps1" %*
