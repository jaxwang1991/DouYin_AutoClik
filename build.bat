@echo off
echo ====================================
echo   DouYin AutoClik - Build Script
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
if exist "dist\DouYin_AutoClik" (
    echo Cleaning previous dist...
    rmdir /s /q dist\DouYin_AutoClik
)

echo.
echo Starting PyInstaller build...
pyinstaller --clean DouYin_AutoClik.spec

if errorlevel 1 (
    echo.
    echo Build failed! Please check errors above.
    pause
    exit /b 1
)

REM Copy Playwright browsers
set PLAYWRIGHT_PATH=%LOCALAPPDATA%\ms-playwright
set DEST_PATH=dist\DouYin_AutoClik\_internal\playwright\driver\package

if not exist "%PLAYWRIGHT_PATH%" (
    echo.
    echo WARNING: Playwright browsers not found!
    echo Please run: python -m playwright install chromium
    echo.
)

if exist "%PLAYWRIGHT_PATH%" (
    echo.
    echo Copying Playwright browsers...
    xcopy /E /I /Y "%PLAYWRIGHT_PATH%" "%DEST_PATH%"
)

REM Create data directory structure
if not exist "dist\DouYin_AutoClik\data" mkdir "dist\DouYin_AutoClik\data"
if not exist "dist\DouYin_AutoClik\data\logs" mkdir "dist\DouYin_AutoClik\data\logs"
if not exist "dist\DouYin_AutoClik\data\logs\audio" mkdir "dist\DouYin_AutoClik\data\logs\audio"
if not exist "dist\DouYin_AutoClik\data\logs\transcripts" mkdir "dist\DouYin_AutoClik\data\logs\transcripts"

echo.
echo ====================================
echo   Build completed successfully!
echo ====================================
echo.
echo Package location: dist\DouYin_AutoClik\
echo.

pause
