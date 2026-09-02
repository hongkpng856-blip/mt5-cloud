@echo off
chcp 65001 >nul
title Tradotcom VPS Update

:: ============================================================
::  Auto-log: this script re-runs itself and saves ALL output
::  to vps_update_log.txt (next to this .bat), so you can open
::  the txt and read the result (no screenshot needed).
:: ============================================================
if not "%1"=="logged" (
    call "%0" logged > "%~dp0vps_update_log.txt" 2>&1
    echo.
    echo Done. Open vps_update_log.txt to see the result.
    echo Log file: %~dp0vps_update_log.txt
    pause
    exit /b
)

echo ============================================
echo   Tradotcom Server - One-click Update
echo   Date: %date% %time%
echo ============================================
echo.

:: ============================================================
::  All locations in one place: C:\Users\Administrator\Desktop\VPS
::    VPS\server-code-deploy-*.zip   <- new code package (copy here)
::    VPS\vps_update.bat             <- this script (double-click)
::    VPS\runtime\                   <- server extracted + running here
::    VPS\vps_update_log.txt         <- this run's log (read this)
:: ============================================================

set "BASE=%~dp0"
set "BASE=%BASE:~0,-1%"
set "TARGET=%BASE%\runtime"

:: ========== 0. Find latest server-code-deploy-*.zip (in VPS folder) ==========
for /f "delims=" %%z in ('powershell -NoProfile -Command "Get-ChildItem -Path '%BASE%' -Filter 'server-code-deploy-*.zip' | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName"') do set "ZIP=%%z"
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
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
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
