@echo off
chcp 65001 >nul
title Tradotcom VPS Update
:: ============================================================
::  Simple wrapper: runs vps_update_core.bat and saves ALL
::  output to vps_update_log.txt — open the txt to read result.
:: ============================================================
call "%~dp0vps_update_core.bat" > "%~dp0vps_update_log.txt" 2>&1
echo.
echo Done. Open vps_update_log.txt to see the result.
echo Log file: %~dp0vps_update_log.txt
pause
