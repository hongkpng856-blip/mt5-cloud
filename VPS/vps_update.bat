@echo off
chcp 65001 >nul
title Tradotcom VPS Update
cd /d "%~dp0"
python vps_update.py > vps_update_log.txt 2>&1
echo.
echo Done. Open vps_update_log.txt to see the result.
echo Log file: %~dp0vps_update_log.txt
pause
