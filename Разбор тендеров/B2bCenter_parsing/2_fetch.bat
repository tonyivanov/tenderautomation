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

echo === Step 1: Fetching tenders from B2B-Center ===
echo Limit: 100 tenders for first run.
echo To fetch everything later, run manually:
echo   venv\Scripts\python.exe fetch_list.py --section all --full
echo.
python fetch_list.py --section all --limit 100
if errorlevel 1 goto error

echo.
echo === Step 2: Applying prefilter from keywords.yaml ===
python prefilter.py
if errorlevel 1 goto error

echo.
echo === DONE ===
echo Database: data\b2bcenter.db
echo Next: run 3_export.bat to dump to txt.
pause
exit /b 0

:error
echo.
echo ============= ERROR =============
echo If you got 403 Forbidden - the site is rate-limiting.
echo Wait 10-15 minutes and try again.
echo Or open fetch_list.py and increase SLEEP_MAX from 4.0 to 8.0.
echo ===================================
pause
exit /b 1
