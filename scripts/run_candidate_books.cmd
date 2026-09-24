@echo off
REM Order-book snapshots for the non-weather day-trading candidates (src/candidates.py).
REM Kalshi serves no historical order book; every missed run is data lost for good.
setlocal
set "PROJ=%~dp0.."
set "PY=C:\Users\tyler\AppData\Local\Programs\Python\Python312\python.exe"
set "LOGDIR=%PROJ%\data\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
cd /d "%PROJ%"
echo RUN %DATE% %TIME% >> "%LOGDIR%\candidate_books.log"
"%PY%" -m src.candidates books >> "%LOGDIR%\candidate_books.log" 2>&1
endlocal
