@echo off
echo ====================================
echo   Copy Playwright Browsers
echo ====================================
echo.

set PLAYWRIGHT_PATH=%LOCALAPPDATA%\ms-playwright
set DEST_PATH=dist\DouYin_AutoLiker\_internal\playwright\driver\package

if not exist "%PLAYWRIGHT_PATH%" (
    echo ERROR: Playwright browsers not found!
    echo Please run: python -m playwright install chromium
    pause
    exit /b 1
)

if not exist "dist\DouYin_AutoLiker" (
    echo ERROR: Build not found! Please run build.bat first.
    pause
    exit /b 1
)

echo Copying Playwright browsers from:
echo %PLAYWRIGHT_PATH%
echo to:
echo %DEST_PATH%
echo.

xcopy /E /I /Y "%PLAYWRIGHT_PATH%" "%DEST_PATH%"

if errorlevel 1 (
    echo.
    echo Copy failed!
    pause
    exit /b 1
)

echo.
echo ====================================
echo   Browsers copied successfully!
echo ====================================
echo.

REM Create data directory structure
if not exist "dist\DouYin_AutoLiker\data" mkdir "dist\DouYin_AutoLiker\data"
if not exist "dist\DouYin_AutoLiker\data\logs" mkdir "dist\DouYin_AutoLiker\data\logs"
if not exist "dist\DouYin_AutoLiker\data\logs\audio" mkdir "dist\DouYin_AutoLiker\data\logs\audio"
if not exist "dist\DouYin_AutoLiker\data\logs\transcripts" mkdir "dist\DouYin_AutoLiker\data\logs\transcripts"
if not exist "dist\DouYin_AutoLiker\data\logs\history" mkdir "dist\DouYin_AutoLiker\data\logs\history"

REM Copy default config and other files
copy /Y "config.json.default" "dist\DouYin_AutoLiker\data\" >nul
copy /Y "README.txt" "dist\DouYin_AutoLiker\" >nul
copy /Y "DouYin_AutoLiker_GUI.bat" "dist\DouYin_AutoLiker\" >nul

echo Data directory structure created.
echo Config files copied.
echo.
echo Package is ready at: dist\DouYin_AutoLiker\
echo.
pause
