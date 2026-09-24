@echo off
REM Daily load of newly settled candidate events (src/candidates.py history).
REM Load promptly: once markets cross the live/historical cutoff, zero-volume
REM strikes lose their candles and trade prints stop being served.
setlocal
set "PROJ=%~dp0.."
REM Cloud server: all-users Python from deploy\setup_server.ps1. Laptop: per-user install.
set "PY=C:\Users\tyler\AppData\Local\Programs\Python\Python312\python.exe"
if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
set "LOGDIR=%PROJ%\data\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%PROJ%"
echo RUN %DATE% %TIME% >> "%LOGDIR%\candidate_history.log"
"%PY%" -m src.candidates history --series KXRAIN,KXWTI,KXNATGASW >> "%LOGDIR%\candidate_history.log" 2>&1
"%PY%" -m src.candidates health >> "%LOGDIR%\candidate_health.log" 2>&1
endlocal
