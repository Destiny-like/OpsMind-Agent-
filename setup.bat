@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title OpsMind - first time setup

echo ============================================
echo   Step 1/4  check uv
echo ============================================
where uv >nul 2>&1
if errorlevel 1 (
    echo   uv not found, installing with pip ...
    py -m pip install -U uv
    where uv >nul 2>&1
    if errorlevel 1 (
        echo   [ERROR] uv install failed. Run: pip install uv
        pause
        exit /b 1
    )
)
echo   uv ready

echo.
echo ============================================
echo   Step 2/4  install python dependencies
echo ============================================
set "UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple/"
uv sync
if errorlevel 1 (
    echo   [ERROR] dependency install failed, check network and retry
    pause
    exit /b 1
)
echo   dependencies ready

echo.
echo ============================================
echo   Step 3/4  check docker engine
echo ============================================
docker info >nul 2>&1
if errorlevel 1 (
    echo   docker not running, starting Docker Desktop ...
    start "" "%LOCALAPPDATA%\Programs\DockerDesktop\Docker Desktop.exe"
    echo   waiting for docker engine up to 180s ...
    for /l %%i in (1,1,60) do (
        docker info >nul 2>&1 && goto :docker_ok
        timeout /t 3 /nobreak >nul
    )
    echo   [ERROR] docker engine not ready, open Docker Desktop manually and retry
    pause
    exit /b 1
)
:docker_ok
echo   docker ready

echo.
echo ============================================
echo   Step 4/4  pull milvus images
echo ============================================
.venv\Scripts\python.exe scripts\oncall_ctl.py pull-images
if errorlevel 1 echo   [WARN] some images failed, retry later

echo.
echo ============================================
echo   Setup finished. Run start.bat to launch.
echo ============================================
pause
