@echo off
setlocal
set "PATH=D:\ffmpeg\bin;%PATH%"
cd /d "%~dp0"
echo [Studio] Starting from: %CD%
if exist ".venv\Scripts\python.exe" goto environment_check
echo [Studio] First launch: running setup.bat...
call setup.bat
if errorlevel 1 goto fail
:environment_check
echo [Studio] Checking the Python environment...
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,12), 'Rename the existing .venv folder to .venv-old and run setup.bat with Python 3.12.'"
if errorlevel 1 goto fail
".venv\Scripts\python.exe" check_environment.py
if errorlevel 1 goto fail
echo.
echo Open http://127.0.0.1:8000 in your browser after Uvicorn starts.
echo Keep this window open. Press Ctrl+C to stop the server.
".venv\Scripts\python.exe" -m uvicorn studio.app:app --host 127.0.0.1 --port 8000
if errorlevel 1 goto fail
exit /b 0
:fail
echo.
echo Startup failed. Read the error above and run setup.bat if needed.
pause
exit /b 1
