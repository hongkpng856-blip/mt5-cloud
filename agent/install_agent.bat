@echo off
chcp 65001 >nul
title Tradotcom Agent Installer

echo ============================================
echo   ☁️ Tradotcom Agent 一鍵安裝
echo ============================================
echo.

:: Check MT5
echo 🔍 檢查 MetaTrader 5...
if exist "%PROGRAMFILES%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%PROGRAMFILES(X86)%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%LOCALAPPDATA%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%APPDATA%\MetaTrader 5\terminal64.exe" goto mt5_ok

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
echo [1/4] 安裝必要套件...
pip install MetaTrader5 python-socketio[client] requests -q
echo ✅ 套件已安裝

:: Get Server URL
echo.
echo [2/4] 設定平台網址...
set /p SERVER_URL="請輸入平台網址 (Enter=預設 https://mt5cloud.esgov.org): "
if "%SERVER_URL%"=="" set SERVER_URL=https://mt5cloud.esgov.org

:: Get Agent ID
echo.
echo [3/4] 設定 Agent...
echo.
echo 請登入你個網站，撳「新增 Agent」或者喺 Dashboard 睇你嘅 Agent ID + Token
set /p AGENT_ID="請輸入你的 Agent ID (例如: A1B2C3D4): "
echo.
set /p AGENT_TOKEN="請輸入你的 Agent Token: "

:: Create run script
echo.
echo [4/4] 建立啟動檔...
(
echo @echo off
echo chcp 65001 >nul
echo title Tradotcom Agent - %AGENT_ID%
echo python agent.py --server %SERVER_URL% --agent %AGENT_ID% --token %AGENT_TOKEN%
echo pause
) > run_agent.bat

:: Download agent.py (正確 endpoint — /api/agent-py)
echo 正在下載 Agent...
curl -sL -o agent.py %SERVER_URL%/api/agent-py
if not exist agent.py (
    echo ❌ 下載失敗，請手動下載 agent.py
) else (
    echo ✅ Agent 已下載
)

echo.
echo ============================================
echo   🎉 安裝完成！
echo   下一步：執行 run_agent.bat 啟動 Agent
echo ============================================
pause