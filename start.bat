@echo off
setlocal

cd /d "%~dp0"

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

where py >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] 未找到 Python 启动器 py，请先安装 Python 3。
    pause
    exit /b 1
)

if not exist "%PYTHON_EXE%" (
    echo [INFO] 正在创建虚拟环境...
    py -3 -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo [ERROR] 虚拟环境创建失败。
        pause
        exit /b 1
    )
)

echo [INFO] 正在安装或更新依赖...
"%PYTHON_EXE%" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] 依赖安装失败。
    pause
    exit /b 1
)

echo [INFO] 正在启动 ImageToPixel...
"%PYTHON_EXE%" app.py

if %errorlevel% neq 0 (
    echo [ERROR] 程序异常退出。
    pause
    exit /b 1
)

endlocal
