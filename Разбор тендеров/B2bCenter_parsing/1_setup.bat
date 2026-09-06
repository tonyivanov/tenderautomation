@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === Step 1/3: Creating virtual environment ===
python -m venv venv
if errorlevel 1 (
    echo.
    echo ERROR: cannot create venv. Is Python 3.10+ installed and in PATH?
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo === Step 2/3: Installing Python packages ===
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto pkg_error

echo.
echo === Step 3/3: Installing Chromium for Playwright (~150 MB, one time) ===
python -m playwright install chromium
if errorlevel 1 goto chromium_error

echo.
echo === DONE ===
echo.
echo Next steps:
echo   1. Run 2b_search.bat  - main mode: search by queries (~6 min)
echo   2. Run 3_export.bat   - export to data\*.txt
echo.
echo Optional (for recon mode):
echo   3. Run 4_login.bat    - login to B2B-Center via Chromium (one time)
echo   4. Run 5_recon.bat ID - inspect a specific tender card
echo.
pause
exit /b 0

:pkg_error
echo.
echo ============= PIP INSTALL ERROR =============
echo Failed to install packages from requirements.txt.
echo Check internet connection and try again.
echo If behind a proxy, set HTTPS_PROXY env var first.
echo Run this manually to see exact error:
echo   venv\Scripts\python.exe -m pip install -r requirements.txt
echo =============================================
pause
exit /b 1

:chromium_error
echo.
echo ============= CHROMIUM DOWNLOAD ERROR =============
echo Python packages installed OK, but Chromium download failed.
echo Often caused by corporate proxy or firewall.
echo Run this manually to see exact error and retry:
echo   venv\Scripts\python.exe -m playwright install chromium
echo ====================================================
pause
exit /b 1
