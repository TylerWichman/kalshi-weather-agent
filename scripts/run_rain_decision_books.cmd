@echo off
REM Extra KXRAIN book snapshots at 23:51 and 23:56 UTC. Gate 2 sizes every trade against
REM a snapshot in the 10 minutes before 00:00 UTC; the 10-minute cadence alone gives
REM exactly one chance per day, so one slow or skipped run would lose that day.
setlocal
set "PROJ=%~dp0.."
REM Cloud server: all-users Python from deploy\setup_server.ps1. Laptop: per-user install.
set "PY=C:\Users\tyler\AppData\Local\Programs\Python\Python312\python.exe"
if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
set "LOGDIR=%PROJ%\data\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%PROJ%"
echo RUN %DATE% %TIME% >> "%LOGDIR%\rain_decision_books.log"
"%PY%" -m src.candidates books --series KXRAIN >> "%LOGDIR%\rain_decision_books.log" 2>&1
endlocal
