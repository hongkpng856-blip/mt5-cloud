@echo off
title Tradotcom Server Restart
echo Restarting Tradotcom Server...
taskkill /IM python.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul
cd /d "%~dp0runtime"
start "Tradotcom Server" cmd /c "cd /d %~dp0runtime && set RENDER=1&& set PORT=80&& python server\app.py"
timeout /t 5 /nobreak >nul
echo Done. Server restarting.
pause
