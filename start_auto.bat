@echo off
REM MT5 Cloud 開機自動啟動（登入後執行）
REM 啟動 Server :5001 + Detector :5003 + Watcher + Tunnel
cd /d C:\Users\hongk\Desktop\mt5-cloud

REM 等 network ready
timeout /t 10 /nobreak >nul

REM 啟動 Server（如果未行）
netstat -ano | findstr ":5001" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "MT5 Server" /min cmd /c "cd /d C:\Users\hongk\Desktop\mt5-cloud && set PORT=5001 && python -u server\app.py > server\server_auto.log 2>&1"
)

REM 啟動 Detector（如果未行）
netstat -ano | findstr ":5003" | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    start "MT5 Detector" /min cmd /c "cd /d C:\Users\hongk\Desktop\mt5-cloud && python -u agent\auto_trade_detector.py > agent\detector_auto.log 2>&1"
)

REM 啟動 Watcher（如果未行）
tasklist /FI "IMAGENAME eq python.exe" | findstr /i "python" >nul 2>&1
if errorlevel 1 (
    start "MT5 Watcher" /min cmd /c "cd /d C:\Users\hongk\Desktop\mt5-cloud && python -u agent\deploy_watcher.py > agent\watcher_auto.log 2>&1"
)

REM 啟動 Cloudflare Tunnel（如果未行）— 固定網址 mt5cloud.esgov.org
tasklist /FI "IMAGENAME eq cloudflared.exe" | findstr /i "cloudflared" >nul 2>&1
if errorlevel 1 (
    start "MT5 Tunnel" /min cmd /c "cloudflared tunnel run mt5cloud > C:\Users\hongk\Desktop\mt5-cloud\agent\tunnel_auto.log 2>&1"
)
