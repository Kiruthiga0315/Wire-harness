@echo off
setlocal
cd /d "%~dp0"

if exist "%LOCALAPPDATA%\Programs\nodejs" set "PATH=%LOCALAPPDATA%\Programs\nodejs;%PATH%"

if exist "backend\.venv\Scripts\python.exe" (
  "backend\.venv\Scripts\python.exe" "run.py" %*
) else (
  python "run.py" %*
)

exit /b %errorlevel%
