@echo off
REM High-frequency collector: order books + live station observations.
REM Neither is backfillable -- Kalshi serves no historical order-book endpoint,
REM and NWS observations age out. Every missed run is data lost for good.
setlocal
set "PROJ=%~dp0.."
set "PY=C:\Users\tyler\AppData\Local\Programs\Python\Python312\python.exe"
set "LOGDIR=%PROJ%\data\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%PROJ%"
echo RUN %DATE% %TIME% >> "%LOGDIR%\collector_fast.log"
"%PY%" -m src.collector books        >> "%LOGDIR%\collector_fast.log" 2>&1
"%PY%" -m src.collector observations >> "%LOGDIR%\collector_fast.log" 2>&1
endlocal
