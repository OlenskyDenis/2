@echo off
setlocal
chcp 65001 >nul

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH!
    echo Please install Python 3.10+ from python.org
    pause
    exit /b 1
)

python -m src.cli.main %*
set EXIT_CODE=%errorlevel%

echo.
pause
exit /b %EXIT_CODE%
