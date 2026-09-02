@echo off
chcp 65001 >nul
title Tradotcom VPS Migrate
cd /d "%~dp0"
python vps_migrate.py > vps_migrate_log.txt 2>&1
echo.
echo Done. Open vps_migrate_log.txt to see the result.
echo Log file: %~dp0vps_migrate_log.txt
pause
