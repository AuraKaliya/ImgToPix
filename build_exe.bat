@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0"

set "VENV_DIR=.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        py -3 -m venv "%VENV_DIR%"
    ) else (
        python -m venv "%VENV_DIR%"
    )
)

"%PYTHON_EXE%" -m pip install -e .[build]
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install build dependencies.
    pause
    exit /b 1
)

if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "app.build" rmdir /s /q "app.build"
if exist "app.dist" rmdir /s /q "app.dist"

"%PYTHON_EXE%" -m nuitka ^
  --onefile ^
  --standalone ^
  --enable-plugin=pyside6 ^
  --windows-console-mode=disable ^
  --output-dir=dist ^
  --output-filename=ImageToPixel.exe ^
  --module-parameter=PySide6:qt-plugins=sensible,styles ^
  app.py

if %errorlevel% neq 0 (
    echo [ERROR] Failed to build exe.
    pause
    exit /b 1
)

echo [SUCCESS] Built dist\ImageToPixel.exe
echo [NOTE] This is a one-file delivery, not a no-runtime native binary.

endlocal
