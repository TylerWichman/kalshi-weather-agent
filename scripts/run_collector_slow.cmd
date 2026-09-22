@echo off
REM Low-frequency collector: contract/ladder discovery + forecast pulls.
REM Contract discovery re-verifies station matching every run (spec v3 section 9).
REM Forecasts are tied to model runs, which land roughly every 6 hours.
setlocal
set "PROJ=%~dp0.."
set "PY=C:\Users\tyler\AppData\Local\Programs\Python\Python312\python.exe"
set "LOGDIR=%PROJ%\data\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%PROJ%"
echo RUN %DATE% %TIME% >> "%LOGDIR%\collector_slow.log"
"%PY%" -m src.collector contracts >> "%LOGDIR%\collector_slow.log" 2>&1
"%PY%" -m src.collector forecasts >> "%LOGDIR%\collector_slow.log" 2>&1
endlocal
