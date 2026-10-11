@echo off
setlocal
set "PATH=D:\ffmpeg\bin;%PATH%"
cd /d "%~dp0"
echo [Setup] Checking Python 3.12...
where py >nul 2>nul
if errorlevel 1 goto python_fallback
set "STUDIO_PY=py -3.12"
goto python_check
:python_fallback
set "STUDIO_PY=python"
:python_check
%STUDIO_PY% -c "import sys; print(sys.version); assert sys.version_info[:2] == (3,12), 'Use Python 3.12 for this Windows launcher'"
if errorlevel 1 goto python_missing
if exist ".venv\Scripts\python.exe" goto venv_check
echo [Setup] Creating the virtual environment...
%STUDIO_PY% -m venv .venv
if errorlevel 1 goto fail
:venv_check
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info[:2] == (3,12), 'Existing .venv is not Python 3.12. Rename it to .venv-old, then run setup.bat again.'"
if errorlevel 1 goto fail
echo [Setup] Installing dependencies. Please wait...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
echo [Setup] Checking FFmpeg and fonts...
".venv\Scripts\python.exe" check_environment.py
if errorlevel 1 goto fail
echo.
echo Setup completed. Run start.bat to open the studio.
pause
exit /b 0
:python_missing
echo.
echo Python 3.12 was not found. In Command Prompt, run:
echo     py install 3.12
echo Then run setup.bat again.
echo If you use the older Python launcher, install Python 3.12 from python.org.
:fail
echo.
echo Setup failed. The error is shown above. This window will stay open.
pause
exit /b 1
