@echo off
REM Installing dependencies...
cd /d "%~dp0"
pip install -r requirements.txt
echo.
REM Installing browser kernels...
playwright install chromium
echo.
Installation completed! You can run login.bat for login, or run.bat to start liking.
pause
