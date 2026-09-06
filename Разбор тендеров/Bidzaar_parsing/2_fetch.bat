@echo off
cd /d "%~dp0"

chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if not exist venv\Scripts\activate.bat (
    echo ERROR: folder venv not found. Run 1_setup.bat first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo === Step 1: Fetching tenders from Bidzaar ===
python fetch_list.py
if errorlevel 1 goto error

echo.
echo === Step 2: Applying prefilter rules from keywords.yaml ===
python prefilter.py
if errorlevel 1 goto error

echo.
echo === Done ===
echo Database: data\bidzaar.db
echo Candidates are marked with score=100 in the output above.
pause
exit /b 0

:error
echo.
echo ============= ERROR =============
echo If the session expired, delete playwright_state.json
echo and run 2_fetch.bat again -- it will open a browser for manual login.
echo =================================
pause
exit /b 1
