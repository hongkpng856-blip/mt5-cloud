@echo off
chcp 65001 >nul
title Tradotcom VPS Update
echo ============================================
echo   Tradotcom Server - One-click Update
echo   Date: %date% %time%
echo ============================================
echo.

:: ========== 0. Find latest server-code-deploy-*.zip ==========
set "TARGET=C:\Users\Administrator\Desktop\server-code-deploy"

for /f "delims=" %%z in ('powershell -NoProfile -Command "$d=@('C:\Users\Administrator\Desktop','C:\Users\Administrator\Desktop\VPS','C:\Users\Administrator\Desktop\mt5-cloud'); $f=@(); foreach($x in $d){ if(Test-Path $x){ $f+=Get-ChildItem (Join-Path $x 'server-code-deploy-*.zip') -ErrorAction SilentlyContinue } }; $f | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName"') do set "ZIP=%%z"
if not defined ZIP (
    echo [ERROR] Cannot find server-code-deploy-*.zip
    echo Please put server-code-deploy-YYYYMMDD-HHMM.zip on Desktop or VPS folder
    pause
    exit /b 1
)
echo Using zip: %ZIP%

:: ========== 1. Backup DB + remove old folder ==========
echo [1/5] Backup DB + remove old folder...
if exist "%TARGET%" (
    if exist "%TARGET%\instance\mt5cloud.db" (
        copy /y "%TARGET%\instance\mt5cloud.db" "%TEMP%\mt5cloud_backup.db" >nul
        echo       DB backed up
    )
    powershell -NoProfile -Command "Remove-Item -Path '%TARGET%' -Recurse -Force"
    echo       Old folder removed
) else (
    echo       (No old folder)
)

:: ========== 2. Extract new code ==========
echo [2/5] Extracting new code...
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%TARGET%' -Force"
if errorlevel 1 (
    echo [ERROR] Extract failed
    pause
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
start "Tradotcom Server" cmd /c "set RENDER=1&& set PORT=80&& python server\app.py"
timeout /t 5 /nobreak >nul
echo       OK

:: ========== 5. Verify ==========
echo [5/5] Verifying server...
curl -s -o nul -w "HTTP %%{http_code}" http://127.0.0.1:80
echo.
echo ============================================
echo   Update complete! Server should be running
echo   (New window "Tradotcom Server" is the server)
echo   Updated: %date% %time%
echo ============================================
pause
