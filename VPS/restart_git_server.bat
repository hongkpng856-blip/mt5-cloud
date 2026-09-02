@echo off
chcp 65001 >nul
title Tradotcom Server Restart (Git)
echo ============================================
echo   Tradotcom Server - One-click Restart
echo   Date: %date% %time%
echo ============================================
echo.

:: ============================================================
::  All in: C:\Users\Administrator\Desktop\VPS\tradotcom (git repo)
::  1. git pull (latest code)
::  2. kill old server
::  3. start new server (PORT=80)
:: ============================================================

set "REPO=C:\Users\Administrator\Desktop\VPS\tradotcom"

:: ========== 1. git pull ==========
echo [1/4] git pull (latest code)...
cd /d "%REPO%"
git pull
echo       OK
echo.

:: ========== 2. kill old server ==========
echo [2/4] Stopping old server...
taskkill /IM python.exe /F >nul 2>&1
timeout /t 3 /nobreak >nul
echo       OK
echo.

:: ========== 3. start new server (PowerShell method - same as manual) ==========
echo [3/4] Starting new server (PORT=80)...
start "Tradotcom Server" powershell -NoProfile -Command "cd '%REPO%'; $env:RENDER='1'; $env:PORT='80'; python server\app.py"
timeout /t 8 /nobreak >nul
echo       OK
echo.

:: ========== 4. verify ==========
echo [4/4] Verifying...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:80/' -TimeoutSec 8 -UseBasicParsing; Write-Host ('  website: HTTP ' + $r.StatusCode) } catch { Write-Host ('  website: FAILED - ' + $_.Exception.Message) }"
echo.
echo ============================================
echo   Restart done. Server running from:
echo   %REPO%
echo   Date: %date% %time%
echo ============================================
echo.
echo (Server window "Tradotcom Server" opened - keep it open)
pause
