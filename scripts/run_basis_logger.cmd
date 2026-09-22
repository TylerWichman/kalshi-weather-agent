@echo off
REM Daily NWS<->TWC basis logging (spec v3 section 2.7).
REM Invoked by the Windows scheduled task "KalshiWeatherBasisLogger".
REM
REM The logger backfills the last 7 days on every run, so a missed day self-heals
REM as long as the gap stays inside the CLI products endpoint's ~7 day retention.
REM Beyond that the data is gone for good, which is why this runs daily.

setlocal
set "PROJ=%~dp0.."
set "PY=C:\Users\tyler\AppData\Local\Programs\Python\Python312\python.exe"
set "LOGDIR=%PROJ%\data\logs"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

cd /d "%PROJ%"
echo ---------------------------------------------- >> "%LOGDIR%\basis_logger.log"
echo RUN %DATE% %TIME% >> "%LOGDIR%\basis_logger.log"
"%PY%" scripts\basis_logger.py --days 7 >> "%LOGDIR%\basis_logger.log" 2>&1
echo EXIT %ERRORLEVEL% >> "%LOGDIR%\basis_logger.log"

endlocal
