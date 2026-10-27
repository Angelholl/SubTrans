@echo off
rem Batch6 ruling helper entry - double-click to run (chcp 65001 for UTF-8 output)
rem Progress/result JSON files live only under %TEMP%; this tool never writes repo files
chcp 65001 >nul
cd /d "%~dp0"
".venv\Scripts\python.exe" tools\ruling_b6.py
if errorlevel 1 (
  echo.
  echo Tool exited abnormally - copy the output above to the reviewer.
)
pause
