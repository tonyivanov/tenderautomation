@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist venv\Scripts\activate.bat (
    echo ERROR: venv not found. Run 1_setup.bat first.
    pause
    exit /b 1
)

if not exist auth\auth_state.json (
    echo ERROR: no saved session. Run 4_login.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if "%~1"=="" (
    echo Usage:
    echo   5_recon.bat 4431469
    echo   5_recon.bat https://www.b2b-center.ru/market/.../tender-4431469/
    echo.
    echo Or first 3 candidates from DB:
    echo   5_recon.bat --top 3
    echo.
    pause
    exit /b 1
)

python recon_card.py %*
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo Done. HTML, screenshots and reports are in data\recon\
echo Show them in chat to build the card parser.
pause
exit /b 0
