@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    set "STUDIO_PY=py -3"
) else (
    set "STUDIO_PY=python"
)
%STUDIO_PY% -c "import sys; assert sys.version_info >= (3,11), 'Python 3.11+ required'"
if errorlevel 1 goto fail
if not exist ".venv\Scripts\python.exe" (
    %STUDIO_PY% -m venv .venv
    if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe check_environment.py
if errorlevel 1 goto fail
echo.
echo 安装完成。双击 start.bat 启动工作台。
pause
exit /b 0
:fail
echo.
echo 安装或环境检查失败。请根据上面的提示处理后重新运行。
pause
exit /b 1
