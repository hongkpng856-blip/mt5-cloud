@echo off
title Tradotcom Git Auto-Update
cd /d "%~dp0"
echo Starting Git Auto-Update Watcher...
echo (Runs in background - checks GitHub every 60s)
echo Log: %~dp0git_watch_log.txt
echo.
start "Git Auto-Update Watcher" python git_auto_update.py
timeout /t 3 /nobreak >nul
echo Started. Close this window.
pause
