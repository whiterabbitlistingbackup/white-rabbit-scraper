@echo off
REM White Rabbit eBay Scraper - Windows Build Script
REM This script builds a standalone .exe file

echo.
echo ========================================
echo   White Rabbit - Building Executable
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.8+ first.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] Installing build dependencies...
pip install -q pyinstaller

echo [2/4] Installing application dependencies...
pip install -q -r requirements.txt

echo [3/4] Building executable (this may take 1-2 minutes)...
pyinstaller --noconfirm --clean build.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. Check the output above for details.
    pause
    exit /b 1
)

echo [4/4] Cleaning up...
rmdir /s /q build
del /q WhiteRabbit.spec

echo.
echo ========================================
echo   BUILD SUCCESSFUL!
echo ========================================
echo.
echo Your executable is ready:
echo   dist\WhiteRabbit.exe
echo.
echo To run it:
echo   1. Double-click dist\WhiteRabbit.exe
echo   2. Or run: .\dist\WhiteRabbit.exe
echo.
echo To distribute:
echo   - Zip the entire 'dist' folder
echo   - Or just share 'dist\WhiteRabbit.exe' (requires Python runtime)
echo.
pause
