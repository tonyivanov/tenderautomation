@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo ERROR: venv not found. Run 1_setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

echo === Playwright login ===
echo.
echo Chromium window will open shortly.
echo Login to b2b-center.ru as usual.
echo When you see your dashboard - come back here and press Enter.
echo.
python login.py
if errorlevel 1 (
    echo.
    echo Login failed. Run 4_login.bat again.
    pause
    exit /b 1
)

pause
exit /b 0
