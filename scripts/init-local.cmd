@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0init-local.ps1" %*
