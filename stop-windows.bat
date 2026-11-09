@echo off
chcp 65001 >nul
REM 兼容旧入口：请优先使用 stop.bat
call "%~dp0stop.bat" %*
