@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title OpsMind - stop

set "PY=%~dp0.venv\Scripts\python.exe"
set "CTL=%~dp0scripts\oncall_ctl.py"
if not exist "%PY%" set "PY=py"

set "EXTRA=%*"
if /i "%~1"=="milvus" set "EXTRA=--with-milvus"

"%PY%" "%CTL%" stop %EXTRA%
echo.
echo Tip: "stop.bat milvus" also stops the Milvus containers.
pause
exit /b 0
