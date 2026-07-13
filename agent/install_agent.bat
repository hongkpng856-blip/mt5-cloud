@echo off
chcp 65001 >nul
title MT5 Cloud Agent Installer

echo ============================================
echo   ☁️ MT5 Cloud Agent 一鍵安裝
echo ============================================
echo.

:: Check MT5
echo 🔍 檢查 MetaTrader 5...
if exist "%PROGRAMFILES%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%PROGRAMFILES(X86)%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%LOCALAPPDATA%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%APPDATA%\MetaTrader 5\terminal64.exe" goto mt5_ok

:: Check common broker paths
for %%b in (ICMarkets-Demo,ICMarkets-Live,FPMarkets-Demo,FPMarkets-Live,Exness-Demo,Exness-Trial) do (
    if exist "%APPDATA%\MetaQuotes\Terminal\*\MQL5\Experts\*.ex5" goto mt5_ok
)

echo ⚠️ 未偵測到 MT5！
echo.
echo 請先安裝 MetaTrader 5，步驟如下：
echo.
echo  1️⃣ 去你嘅 Broker 官網下載 MT5
echo     (例如 IC Markets: https://www.icmarkets.com/hk/)
echo.
echo  2️⃣ 安裝並登入你嘅 Demo Account
echo.
echo  3️⃣ 然後再執行呢個安裝檔
echo.
pause
exit /b

:mt5_ok
echo ✅ MT5 已安裝

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未安裝 Python！請先下載安裝：
    echo    https://www.python.org/downloads/
    echo    安裝時記得 tick "Add Python to PATH"
    pause
    exit /b
)
echo ✅ Python 已安裝

:: Install dependencies
echo.
echo [1/3] 安裝必要套件...
pip install MetaTrader5 python-socketio[client] requests -q
echo ✅ 套件已安裝

:: Get Agent ID
echo.
echo [2/3] 設定 Agent...
echo.
echo 請登入你個網站，喺 Dashboard 睇到你嘅 Agent ID
set /p AGENT_ID="請輸入你的 Agent ID (例如: DEV00001): "

:: Get Server URL
echo.
set /p SERVER_URL="請輸入你的網站網址 (Enter=預設): "
if "%SERVER_URL%"=="" set SERVER_URL=https://french-bright-grueling.ngrok-free.dev

:: Create run script
echo.
echo [3/3] 建立啟動檔...
(
echo @echo off
echo chcp 65001 >nul
echo title MT5 Cloud Agent - %AGENT_ID%
echo python agent.py --server %SERVER_URL% --agent-id %AGENT_ID%
echo pause
) > run_agent.bat

:: Download agent.py
echo 正在下載 Agent...
curl -sL -o agent.py %SERVER_URL%/api/agent-download >nul
if not exist agent.py (
    echo ❌ 下載失敗，請手動下載 agent.py
) else (
    echo ✅ Agent 已下載
)

echo.
echo ============================================
echo   🎉 安裝完成！
echo ============================================
echo.
echo 雙撳「run_agent.bat」就開得！
echo.
pause
