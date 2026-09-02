@echo off
chcp 65001 >nul
title Tradotcom Agent 安裝精靈

:: ============================================================
::  Tradotcom Agent 安裝精靈 v1.0
::  = 好似下載軟件咁：逐步確認 + 條款 + 測試連線
:: ============================================================

echo ╔══════════════════════════════════════════════╗
echo ║      ☁️  Tradotcom Agent 安裝精靈            ║
echo ║                                             ║
echo ║  呢個程式幫你安裝「Tradotcom Agent」        ║
echo ║  — 連接你嘅 Tradotcom 帳戶，控制你部電腦     ║
echo ║    嘅 MetaTrader 5（MT5）                    ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ========== 1. 歡迎 ==========
echo [步驟 1/6] 歡迎
echo.
echo 安裝流程：
echo   ① 同意條款
echo   ② 檢查 MT5 + Python
echo   ③ 安裝必要套件
echo   ④ 設定伺服器 / Agent
echo   ⑤ 下載 + 建立啟動檔
echo   ⑥ 測試連線
echo.
pause

:: ========== 2. 條款 ==========
echo.
echo [步驟 2/6] 使用條款
echo.
echo ──────────────────────────────────────────────
echo  Tradotcom Agent 使用條款
echo.
echo  1. 本 Agent 會讀取你部電腦嘅 MT5 交易資料
echo     （帳戶餘額 / 持倉 / 交易記錄），
echo     並上傳至你登記嘅 Tradotcom 伺服器。
echo.
echo  2. Agent 會根據你喺網頁發出嘅指令，
echo     自動操作你部電腦嘅 MT5
echo     （開圖表 / 掛 EA / 刪除 EA）。
echo.
echo  3. 所有操作都會記錄喺活動日誌，
echo     你隨時可以喺網頁查閱。
echo.
echo  4. 你同意只喺自己擁有嘅 MT5 帳戶使用。
echo──────────────────────────────────────────────
echo.
echo 請確認：同意以上條款先可以繼續安裝。
echo.
choice /c YN /m "是否同意條款並繼續安裝？(Y=同意 / N=退出)"
if errorlevel 2 (
    echo.
    echo 你選擇咗唔同意 — 安裝已取消。
    pause
    exit /b 1
)
echo ✅ 已同意條款，繼續安裝...
echo.

:: ========== 3. 檢查 MT5 ==========
echo [步驟 3/6] 檢查必要軟件
echo.
echo 🔍 檢查 MetaTrader 5...
if exist "%PROGRAMFILES%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%PROGRAMFILES(X86)%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%LOCALAPPDATA%\MetaTrader 5\terminal64.exe" goto mt5_ok
if exist "%APPDATA%\MetaTrader 5\terminal64.exe" goto mt5_ok

for %%b in (ICMarkets-Demo,ICMarkets-Live,FPMarkets-Demo,FPMarkets-Live,Exness-Demo,Exness-Trial) do (
    if exist "%APPDATA%\MetaQuotes\Terminal\*\MQL5\Experts\*.ex5" goto mt5_ok
)

echo ❌ 未偵測到 MT5！
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
exit /b 1

:mt5_ok
echo ✅ MT5 已安裝

echo.
echo 🔍 檢查 Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 未安裝 Python！請先下載安裝：
    echo    https://www.python.org/downloads/
    echo    安裝時記得 tick "Add Python to PATH"
    pause
    exit /b 1
)
echo ✅ Python 已安裝
echo.

:: ========== 4. 安裝套件 ==========
echo [步驟 4/6] 安裝必要套件
echo.
echo 安裝 python-socketio / MetaTrader5 / requests...
pip install MetaTrader5 python-socketio[client] requests -q
if %errorlevel% neq 0 (
    echo ❌ 套件安裝失敗 — 請檢查網絡後再試
    pause
    exit /b 1
)
echo ✅ 套件已安裝
echo.

:: ========== 5. 設定 ==========
echo [步驟 5/6] 設定伺服器與 Agent
echo.
echo 請登入你嘅 Tradotcom 網站，撳 Agent 卡「Agent 安裝」睇你嘅 Agent ID 同 Token
echo.
set /p SERVER_URL="平台網址 (Enter=預設 https://tradotcom.com): "
if "%SERVER_URL%"=="" set SERVER_URL=https://tradotcom.com
echo.
set /p AGENT_ID="Agent ID (例如: A1B2C3D4): "
if "%AGENT_ID%"=="" (
    echo ❌ Agent ID 唔可以空白 — 請喺網站攞返
    pause
    exit /b 1
)
echo.
set /p AGENT_TOKEN="Agent Token (喺網站「Agent 安裝」見到): "
if "%AGENT_TOKEN%"=="" (
    echo ❌ Token 唔可以空白
    pause
    exit /b 1
)

echo.
echo 確認設定：
echo   平台網址: %SERVER_URL%
echo   Agent ID: %AGENT_ID%
echo   Token:    %AGENT_TOKEN:~0,4%...（已隱藏）
echo.
choice /c YN /m "設定正確？(Y=繼續安裝 / N=重新輸入)"
if errorlevel 2 (
    echo 請重新執行安裝精靈再輸入
    pause
    exit /b 1
)

:: ========== 6. 下載 + 建立啟動檔 ==========
echo.
echo [步驟 6/6] 下載 Agent 正本
echo.
echo 正在下載 agent.py...
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0" -o agent.py %SERVER_URL%/api/agent-py
if not exist agent.py (
    echo ❌ 下載失敗 — 請檢查平台網址係咪正確
    pause
    exit /b 1
)
echo ✅ agent.py 已下載

:: 建立啟動檔
(
echo @echo off
echo chcp 65001 ^>nul
echo title Tradotcom Agent - %AGENT_ID%
echo python agent.py --server %SERVER_URL% --agent %AGENT_ID% --token %AGENT_TOKEN%
echo pause
) > run_agent.bat
echo ✅ 啟動檔已建立 (run_agent.bat)

:: ========== 測試連線 ==========
echo.
echo 🔌 測試連線到平台...
curl -s -o nul -w "HTTP %%{http_code}" %SERVER_URL%/ --max-time 15 > _conn_test.txt 2>nul
set /p CONN_CODE=<_conn_test.txt
del _conn_test.txt
if "%CONN_CODE%"=="200" (
    echo ✅ 平台連線成功 (HTTP 200)
) else (
    echo ⚠️ 平台連線回應 %CONN_CODE% — 但可能係需要登入，Agent 啟動時會再確認
)

echo.
echo ══════════════════════════════════════════════
echo   🎉 安裝完成！
echo.
echo   下一步：執行 run_agent.bat 啟動 Agent
echo   成功連線會彈出綠色「✅ Agent 已連接」視窗
echo ══════════════════════════════════════════════
echo.
pause