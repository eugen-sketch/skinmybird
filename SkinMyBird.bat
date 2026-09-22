@echo off
REM SkinMyBird Commercial — Airbus + Boeing airliners only (product for sale)
cd /d "%~dp0"

set "SKINMYBIRD_EDITION=commercial"
set "SKINMYBIRD_PORT=5173"

if not defined SKINMYBIRD_COMMUNITY set "SKINMYBIRD_COMMUNITY=C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community"
if not defined SKINMYBIRD_TEXCONV set "SKINMYBIRD_TEXCONV=C:\Users\eugen\Downloads\texconv.exe"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo.
echo  SkinMyBird v0.6.3 [Commercial] — http://127.0.0.1:5173
echo  Stopping old servers on port 5173...
echo.

REM Free port 5173 only (leave Personal :5174 alone)
for /f "tokens=5" %%P in ('netstat -aon ^| findstr ":5173" ^| findstr "LISTENING"') do (
  echo  Closing PID %%P
  taskkill /PID %%P /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo  Edition:   %SKINMYBIRD_EDITION%
echo  Community: %SKINMYBIRD_COMMUNITY%
echo  texconv:   %SKINMYBIRD_TEXCONV%
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:5173/?v=0.6.3"
"%PY%" -u server.py
pause
