@echo off
REM Daily paper trade of the frozen KXRAIN rule at 00:01 UTC (src/paper.py).
setlocal
set "PROJ=%~dp0.."
REM Cloud server: all-users Python from deploy\setup_server.ps1. Laptop: per-user install.
set "PY=C:\Users\tyler\AppData\Local\Programs\Python\Python312\python.exe"
if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
set "LOGDIR=%PROJ%\data\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%PROJ%"
echo RUN %DATE% %TIME% >> "%LOGDIR%\paper.log"
"%PY%" -m src.paper trade >> "%LOGDIR%\paper.log" 2>&1
endlocal
