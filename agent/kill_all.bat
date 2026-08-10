@echo off
setlocal enabledelayedexpansion
REM ===== MT5 Cloud - 強制終止所有 spawner =====
echo 🔫 正在強制終止所有 auto_attach 及 batch script...
wmic process where "name='python.exe'" get processid,commandline > %temp%\py_list.txt 2>nul
for /f "tokens=1,* delims= " %%a in ('type %temp%\py_list.txt ^| findstr /i "auto_attach batch_deploy deploy_all run_batch final_batch"') do (
  taskkill /f /pid %%a >nul 2>nul
)
echo ✅ 已強制終止所有 rogue process！
echo 你而家可以自由用 MT5 了。
pause
