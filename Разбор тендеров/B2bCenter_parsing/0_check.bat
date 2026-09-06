@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============= ENVIRONMENT CHECK =============
echo.

echo [1] Python version:
python --version
if errorlevel 1 (
    echo     Python is NOT in PATH. Install from https://www.python.org/downloads/
    echo     Make sure to check "Add Python to PATH" during install.
    goto end
)
echo.

echo [2] pip version:
python -m pip --version
echo.

echo [3] Venv exists?
if exist venv\Scripts\activate.bat (
    echo     YES: venv\Scripts\activate.bat
) else (
    echo     NO. Run 1_setup.bat to create it.
    goto end
)
echo.

echo [4] Packages in venv:
call venv\Scripts\activate.bat
python -m pip list 2>nul | findstr /R /C:"^httpx" /C:"^beautifulsoup4" /C:"^lxml" /C:"^PyYAML" /C:"^playwright"
echo.

echo [5] Playwright browsers:
python -m playwright --version 2>nul
if errorlevel 1 (
    echo     Playwright not installed in venv.
)
echo.

echo [6] Auth state file:
if exist auth\auth_state.json (
    echo     YES: auth\auth_state.json exists
) else (
    echo     NO. Run 4_login.bat to create it.
)
echo.

echo [7] Database:
if exist data\b2bcenter.db (
    echo     YES: data\b2bcenter.db exists
    python -c "import sqlite3; c=sqlite3.connect(r'data\b2bcenter.db'); print('     Tenders in DB:', c.execute('SELECT COUNT(*) FROM tenders').fetchone()[0])"
) else (
    echo     NO. Run 2_fetch.bat to create it.
)
echo.

:end
echo ==============================================
pause
