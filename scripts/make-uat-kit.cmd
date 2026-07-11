@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make-uat-kit.ps1" %*
