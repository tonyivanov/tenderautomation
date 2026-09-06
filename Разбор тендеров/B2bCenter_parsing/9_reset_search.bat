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

python reset_search.py
pause
