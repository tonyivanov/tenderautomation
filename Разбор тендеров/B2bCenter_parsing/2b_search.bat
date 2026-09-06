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

echo === Step 1: Search B2B-Center by queries from search_queries.yaml ===
echo No per-query limit. Each query will fetch everything available.
echo Wide queries (e.g. "*server*") may take long. To set a safety cap, edit:
echo   --search-file search_queries.yaml --limit 200
echo.
python fetch_list.py --search-file search_queries.yaml
if errorlevel 1 goto error

echo.
echo === Step 2: Apply prefilter (only blacklist for search results) ===
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
echo If the script complained "could not detect search param" -
echo open https://www.b2b-center.ru/market/ in browser, type any
echo word in the search box, press Enter, copy the URL from address
echo bar and send it to me - I'll fix in one line.
echo.
echo If you got 403 Forbidden - the site is rate-limiting.
echo Wait 10-15 min and try again.
echo ===================================
pause
exit /b 1
