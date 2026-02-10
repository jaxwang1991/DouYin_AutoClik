@echo off
echo ====================================
echo   DouYin AutoLiker - Build Script
echo ====================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
)

REM Clean previous build
if exist "build" (
    echo Cleaning previous build...
    rmdir /s /q build
)
if exist "dist\DouYin_AutoLiker" (
    echo Cleaning previous dist...
    rmdir /s /q dist\DouYin_AutoLiker
)

echo.
echo Starting PyInstaller build...
pyinstaller --clean DouYin_AutoLiker.spec

if errorlevel 1 (
    echo.
    echo Build failed! Please check errors above.
    pause
    exit /b 1
)

echo.
echo ====================================
echo   Build completed successfully!
echo ====================================
echo.
echo Next steps:
echo 1. Copy Playwright browser drivers to dist folder
echo 2. Test the executable
echo.

pause
