@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
rem Batch6 sensitive-sentence web UI launcher (ASCII only; cmd eats UTF-8 comments under GBK)
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
"%PY%" tools\sensitive_b6_web.py %*
if errorlevel 1 pause
endlocal
