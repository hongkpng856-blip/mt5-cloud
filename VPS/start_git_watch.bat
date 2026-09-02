@echo off
title Tradotcom Git Auto-Update
cd /d "%~dp0"
echo Starting Git Auto-Update Watcher...
echo (Runs in background - checks GitHub every 60s)
echo Log: %~dp0tradotcom\VPS\git_watch_log.txt
echo.
:: [ALERT] 2026-09-02 FIX：用 git repo 入面嘅 script（tradotcom\VPS\git_auto_update.py）
:: → git pull 會一齊更新 watcher script（唔會再用舊版 crash）
start "Git Auto-Update Watcher" python "%~dp0tradotcom\VPS\git_auto_update.py"
timeout /t 3 /nobreak >nul
echo Started. Close this window.
pause
