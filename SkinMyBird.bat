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
echo  SkinMyBird v0.3 — http://127.0.0.1:5173
echo  Community: %SKINMYBIRD_COMMUNITY%
echo  texconv:   %SKINMYBIRD_TEXCONV%
echo.

start "" cmd /c "timeout /t 2 /nobreak >nul & start http://127.0.0.1:5173"
"%PY%" server.py
pause
