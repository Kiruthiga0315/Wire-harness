@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv-cloud\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=%~dp0backend\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Python environment was not found.
    echo Follow the one-time setup in DEPLOYMENT.md, then run this launcher again.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import streamlit" >nul 2>&1
if errorlevel 1 (
    echo Streamlit is not installed in the project environment.
    echo Run: "%PYTHON_EXE%" -m pip install -r requirements.txt
    pause
    exit /b 1
)

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8501'"
"%PYTHON_EXE%" -m streamlit run "%~dp0streamlit_app.py" --server.port 8501

if errorlevel 1 (
    echo.
    echo Streamlit stopped with an error.
    pause
)
