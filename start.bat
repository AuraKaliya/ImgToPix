@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 bootstrap.py gui
) else (
    python bootstrap.py gui
)

if %errorlevel% neq 0 (
    echo [ERROR] ImageToPixel failed to start.
    pause
    exit /b 1
)

endlocal
