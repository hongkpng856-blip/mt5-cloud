@echo off
chcp 65001 >nul
echo ============================================
echo   Tradotcom Server - One-click Update
echo   Date: %date% %time%
echo ============================================
echo.

:: ============================================================
::  All locations in one place: C:\Users\Administrator\Desktop\VPS
::    VPS\server-code-deploy-*.zip   <- new code package (copy here)
::    VPS\vps_update.bat             <- double-click this
::    VPS\vps_update_core.bat        <- actual logic (called by bat)
::    VPS\vps_update_log.txt         <- result log (read this)
::    VPS\runtime\                   <- server extracted + running here
:: ============================================================

set "BASE=%~dp0"
set "BASE=%BASE:~0,-1%"
set "TARGET=%BASE%\runtime"

:: ========== 0. Find latest server-code-deploy-*.zip (in VPS folder) ==========
set "ZIP="
for /f "delims=" %%z in ('dir /b /o-d "%BASE%\server-code-deploy-*.zip" 2^>nul') do (
    if not defined ZIP set "ZIP=%BASE%\%%z"
)
if not defined ZIP (
    echo [ERROR] Cannot find server-code-deploy-*.zip in %BASE%
    echo Please put server-code-deploy-YYYYMMDD-HHMM.zip in the VPS folder
    exit /b 1
)
echo Using zip: %ZIP%
echo.

:: ========== 1. Backup DB + remove old runtime ==========
echo [1/5] Backup DB + remove old runtime...
if exist "%TARGET%" (
    if exist "%TARGET%\instance\mt5cloud.db" (
        copy /y "%TARGET%\instance\mt5cloud.db" "%TEMP%\mt5cloud_backup.db" >nul
        echo       DB backed up
    )
    powershell -NoProfile -Command "Remove-Item -Path '%TARGET%' -Recurse -Force"
    echo       Old runtime removed
) else (
    echo       (No old runtime)
)

:: ========== 2. Extract new code into runtime ==========
echo [2/5] Extracting new code into runtime...
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%TARGET%' -Force"
if errorlevel 1 (
    echo [ERROR] Extract failed
    exit /b 1
)
if exist "%TEMP%\mt5cloud_backup.db" (
    if not exist "%TARGET%\instance" mkdir "%TARGET%\instance"
    copy /y "%TEMP%\mt5cloud_backup.db" "%TARGET%\instance\mt5cloud.db" >nul
    echo       VPS DB restored (data kept)
    del "%TEMP%\mt5cloud_backup.db" >nul 2>&1
)
echo       OK

:: ========== 3. Stop old server ==========
echo [3/5] Stopping old server...
taskkill /IM python.exe /F >nul 2>&1
timeout /t 3 /nobreak >nul
echo       OK

:: ========== 4. Start new server ==========
echo [4/5] Starting new server...
cd /d "%TARGET%"
start "Tradotcom Server" cmd /c "cd /d %TARGET% && set RENDER=1&& set PORT=80&& python server\app.py"
timeout /t 5 /nobreak >nul
echo       OK

:: ========== 5. Verify ==========
echo [5/5] Verifying server...
curl -s -o nul -w "HTTP %%{http_code}" http://127.0.0.1:80
echo.
echo ============================================
echo   Update complete! Server should be running
echo   Runtime folder: %TARGET%
echo   Updated: %date% %time%
echo ============================================
