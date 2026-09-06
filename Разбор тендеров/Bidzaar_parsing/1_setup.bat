@echo off
cd /d "%~dp0"

echo === bidzaar-scout :: setup ===
echo.

echo [1/4] Creating Python virtual environment in .\venv ...
python -m venv venv
if errorlevel 1 (
    echo.
    echo ERROR: failed to create venv.
    echo Make sure Python is installed and "python --version" works in cmd.
    pause
    exit /b 1
)

echo [2/4] Activating venv and upgrading pip ...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo [3/4] Installing Python packages from requirements.txt ...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: failed to install Python packages.
    pause
    exit /b 1
)

echo [4/4] Installing Chromium browser for Playwright ...
echo This downloads ~300MB and takes 1-3 minutes. Be patient.
python -m playwright install chromium
if errorlevel 1 (
    echo.
    echo ERROR: failed to install Chromium.
    pause
    exit /b 1
)

echo.
echo ============================
echo ===   SETUP  COMPLETED   ===
echo ============================
echo.
echo Next steps:
echo   1. Run 2_fetch.bat
echo      The first run will open a real browser window -- log in to
echo      Bidzaar manually, then the window closes by itself.
echo   2. From now on, Bidzaar logins are automatic.
echo.
pause
