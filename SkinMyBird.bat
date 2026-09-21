@echo off
REM SkinMyBird — pornire server local + browser (Windows)
cd /d "%~dp0"

if not defined SKINMYBIRD_COMMUNITY set "SKINMYBIRD_COMMUNITY=C:\Users\eugen\AppData\Roaming\Microsoft Flight Simulator\Packages\Community"
if not defined SKINMYBIRD_TEXCONV set "SKINMYBIRD_TEXCONV=C:\Users\eugen\Downloads\texconv.exe"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo.
echo  SkinMyBird v0.4.6 — http://127.0.0.1:5173
echo  Opresc serverele vechi pe portul 5173...
echo.

REM Kill any leftover server.py so we never serve an old hangar
for /f "tokens=2 delims=," %%P in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2^>nul') do (
  wmic process where "ProcessId=%%~P" get CommandLine 2>nul | findstr /I "server.py" >nul
  if not errorlevel 1 (
    echo  Inchid PID %%~P
    taskkill /PID %%~P /F >nul 2>&1
  )
)
timeout /t 1 /nobreak >nul

echo  Community: %SKINMYBIRD_COMMUNITY%
echo  texconv:   %SKINMYBIRD_TEXCONV%
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:5173/?v=0.4.6"
"%PY%" -u server.py
pause
