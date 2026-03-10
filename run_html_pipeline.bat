@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PY_SCRIPT=%SCRIPT_DIR%run_html_pipeline.py"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%PY_SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python "%PY_SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

echo Python 3 not found. Please install Python and retry.
exit /b 1

