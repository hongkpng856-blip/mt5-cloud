@echo off
chcp 65001 >nul
echo ============================================
echo   Tradotcom Server - Restart
echo   Date: %date% %time%
echo ============================================
echo.

:: Runtime folder = this script's folder + runtime
set "BASE=%~dp0"
set "BASE=%BASE:~0,-1%"
set "TARGET=%BASE%\runtime"
echo Runtime folder: %TARGET%
echo.

:: ========== 1. Show current python processes BEFORE kill ==========
echo [1/5] Current python processes (before kill):
wmic process where "name='python.exe'" get ProcessId,CommandLine /format:list 2>nul | findstr "CommandLine"
echo.

:: ========== 2. Kill all python ==========
echo [2/5] Killing old server...
taskkill /IM python.exe /F >nul 2>&1
timeout /t 3 /nobreak >nul
echo       OK

:: ========== 3. Check runtime server exists ==========
echo [3/5] Checking runtime:
if exist "%TARGET%\server\app.py" (
    echo       app.py exists: YES
) else (
    echo       app.py exists: NO  ^(runtime missing^)
)
if exist "%TARGET%\agent\tradotcom_launcher.bat" (
    echo       agent launcher exists: YES
) else (
    echo       agent launcher exists: NO
)
echo.

:: ========== 4. Start new server ==========
echo [4/5] Starting server from %TARGET%...
cd /d "%TARGET%"
start "Tradotcom Server" cmd /c "cd /d %TARGET% && set RENDER=1&& set PORT=80&& python server\app.py"
timeout /t 6 /nobreak >nul
echo       OK

:: ========== 5. Verify ==========
echo [5/5] Verifying:
curl -s -o nul -w "  website: HTTP %%{http_code}" http://127.0.0.1:80/
echo.
curl -s -o nul -w "  agent-download: HTTP %%{http_code}" http://127.0.0.1:80/api/agent-download
echo.
echo ============================================
echo   Restart done. See server window for logs.
echo   Date: %date% %time%
echo ============================================
