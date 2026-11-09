@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title OpsMind

set "PY=%~dp0.venv\Scripts\python.exe"
set "CTL=%~dp0scripts\opsmind_ctl.py"
set "EXTRA=%*"
if /i "%~1"=="docs" (
    set "EXTRA=--force-docs"
    if exist "%~dp0.run\docs_indexed" del "%~dp0.run\docs_indexed" >nul 2>&1
)

if not exist "%PY%" (
    echo [setup] virtual env not found, running setup.bat first ...
    call "%~dp0setup.bat"
    if errorlevel 1 goto :fail
)

"%PY%" "%CTL%" start %EXTRA%
if errorlevel 1 goto :fail

echo.
echo Opening http://localhost:9900 ...
start "" http://localhost:9900
echo.
pause >nul
exit /b 0

:fail
echo.
echo [FAILED] see messages above / logs\ directory.
echo   Common causes: Docker Desktop not running, DASHSCOPE_API_KEY missing in .env, port in use.
echo.
pause
exit /b 1
