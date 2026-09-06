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

python export_for_review.py
if errorlevel 1 (
    echo.
    echo Export failed. Make sure 2_fetch.bat ran at least once.
    pause
    exit /b 1
)

echo.
echo Done. Upload data\all_tenders.txt and data\score100_tenders.txt to chat.
pause
exit /b 0
