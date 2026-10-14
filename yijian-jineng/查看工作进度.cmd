@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\查看工作进度.ps1"
if errorlevel 1 pause
