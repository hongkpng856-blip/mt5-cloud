@echo off
title Tradotcom Server Restart
:: ============================================================
::  One-click restart with auto-log.
::  After running, open restart_log.txt to see the result.
:: ============================================================
call "%~dp0restart_server_core.bat" > "%~dp0restart_log.txt" 2>&1
echo.
echo Done. Open restart_log.txt to see the result.
echo Log file: %~dp0restart_log.txt
pause
