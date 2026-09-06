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

python export_for_review.py
if errorlevel 1 (
    echo.
    echo ERROR while exporting. See messages above.
    pause
    exit /b 1
)

echo.
echo Files saved to: data\
echo   - all_tenders.txt        (all active tenders)
echo   - score100_tenders.txt   (prefilter candidates)
echo.
echo Send both files to Claude in the chat for review.
pause
