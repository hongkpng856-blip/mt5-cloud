@echo off
chcp 65001 >nul
title Tradotcom VPS Update
echo ============================================
echo   Tradotcom Server - One-click Update
echo   日期: %date% %time%
echo ============================================
echo.

:: ========== 0. 自動搵最新 server-code-deploy-*.zip（VPS 桌面 / VPS folder / MT5 folder）==========
set "TARGET=C:\Users\Administrator\Desktop\server-code-deploy"

:: 用 PowerShell 喺幾個位置搵最新 zip
for /f "delims=" %%z in ('powershell -NoProfile -Command "$d=@('C:\Users\Administrator\Desktop','C:\Users\Administrator\Desktop\VPS','C:\Users\Administrator\Desktop\mt5-cloud\VPS','C:\Users\Administrator\Desktop\mt5-cloud\VPS'); $f=@(); foreach($x in $d){ if(Test-Path $x){ $f+=Get-ChildItem (Join-Path $x 'server-code-deploy-*.zip') -ErrorAction SilentlyContinue } }; $f | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty FullName"') do set "ZIP=%%z"
if not defined ZIP (
    echo [ERROR] 搵唔到 server-code-deploy-*.zip
    echo 請將新既 server-code-deploy-日期時間.zip 放喺桌面/VPS folder
    pause
    exit /b 1
)
echo 使用 zip: %ZIP%

:: ========== 0.5 備份 DB + 刪舊 folder ==========
echo [1/5] 備份 DB + 刪舊 folder...
if exist "%TARGET%" (
    if exist "%TARGET%\instance\mt5cloud.db" (
        copy /y "%TARGET%\instance\mt5cloud.db" "%TEMP%\mt5cloud_backup.db" >nul
        echo       已備份 DB
    )
    powershell -Command "Remove-Item -Path '%TARGET%' -Recurse -Force"
    echo       已刪舊 folder
) else (
    echo       （冇舊 folder）
)

:: ========== 1. 解壓新 code ==========
echo [2/5] 解壓新 code...
powershell -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%TARGET%' -Force"
if errorlevel 1 (
    echo [ERROR] 解壓失敗
    pause
    exit /b 1
)
:: 還原 VPS DB（唔用 zip 內嘅 DB — 保留 VPS 數據）
if exist "%TEMP%\mt5cloud_backup.db" (
    if not exist "%TARGET%\instance" mkdir "%TARGET%\instance"
    copy /y "%TEMP%\mt5cloud_backup.db" "%TARGET%\instance\mt5cloud.db" >nul
    echo       已還原 VPS DB（保留數據）
    del "%TEMP%\mt5cloud_backup.db" >nul 2>&1
)
echo       OK

:: ========== 2. 停舊 server ==========
echo [3/5] 停舊 server...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
timeout /t 3 /nobreak >nul
echo       OK

:: ========== 3. 啟動新 server ==========
echo [4/5] 啟動新 server...
cd /d "%TARGET%"
start "Tradotcom Server" cmd /c "set RENDER=1&& set PORT=80&& python server\app.py"
timeout /t 5 /nobreak >nul
echo       OK

:: ========== 4. 確認 ==========
echo [5/5] 確認 server...
curl -s -o nul -w "HTTP %%{http_code}" http://127.0.0.1:80
echo.
echo ============================================
echo   更新完成！Server 應該運行緊
echo   （新視窗「Tradotcom Server」就係 server）
echo   更新日期: %date% %time%
echo ============================================
pause
