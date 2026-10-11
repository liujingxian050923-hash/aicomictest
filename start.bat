@echo off
setlocal
set "PATH=D:\ffmpeg\bin;%PATH%"
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    call setup.bat
    if errorlevel 1 exit /b 1
)
.venv\Scripts\python.exe check_environment.py
if errorlevel 1 (
    echo 请先运行 setup.bat 并处理缺失依赖或 FFmpeg。
    pause
    exit /b 1
)
echo.
echo 浏览器打开 http://127.0.0.1:8000
 echo 保持此窗口开启，按 Ctrl+C 停止服务。
.venv\Scripts\python.exe -m uvicorn studio.app:app --host 127.0.0.1 --port 8000
if errorlevel 1 pause
