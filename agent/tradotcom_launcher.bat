@echo off
chcp 65001 >nul
title Tradotcom Agent 啟動器

:: ============================================================
::  Tradotcom Agent — double-click 啟動器
::  有自動檢測：Python 冇 → 幫你下載安裝 → 再繼續
:: ============================================================

echo.
echo ══════════════════════════════════════════════
echo   ☁️  Tradotcom Agent 安裝程式
echo ══════════════════════════════════════════════
echo.

:: ========== 1. 檢查 Python ==========
:CHECK_PYTHON
set PYTHONW=
set PYTHONEXE=

:: 搵 pythonw / python（多個位置 + py launcher）
for %%p in (
    "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe"
    "%PROGRAMFILES%\Python311\pythonw.exe"
    "%PROGRAMFILES%\Python312\pythonw.exe"
    "%PROGRAMFILES%\Python313\pythonw.exe"
    "C:\Python311\pythonw.exe"
    "C:\Python312\pythonw.exe"
) do (
    if exist %%p set PYTHONW=%%~p
)

:: 用 py launcher 搵（如果上面搵唔到）
if "%PYTHONW%"=="" (
    py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'),end='')" > "%TEMP%\_pyw_path.txt" 2>nul
    set /p PYTHONW=<"%TEMP%\_pyw_path.txt"
    set /p PYTHONEXE=<"%TEMP%\_pyw_path.txt"
    del "%TEMP%\_pyw_path.txt" 2>nul
)

:: 🚨 2026-08-26 FIX：檢查 Python 版本 — 3.14 唔兼容 MetaTrader5（卡死）→ 要 3.11/3.12
if not "%PYTHONW%"=="" (
    set "PYVER_CHECK=%PYTHONW:\pythonw.exe=\python.exe%"
    "%PYVER_CHECK%" -c "import sys;sys.exit(0 if sys.version_info < (3,14) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo ⚠️  偵測到你嘅 Python 係 3.14 — MetaTrader5 套件喺 3.14 會卡住！
        echo    需要安裝 Python 3.11 或 3.12 先可以運行 Tradotcom Agent。
        echo.
        set /p PY_CHOICE2="要唔要我幫你下載並安裝 Python 3.11？(Y=下載安裝，N=退出): "
        if /i not "%PY_CHOICE2%"=="Y" (
            echo.
            echo 你選擇咗退出 — 安裝取消。
            echo 你可以之後去 https://www.python.org/downloads/ 手動安裝 Python 3.11
            pause
            exit /b 1
        )
        echo.
        echo ⏳ 下載 Python 3.11 安裝程式（~25MB）...
        curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0" -o "%TEMP%\python-3.11.9-amd64.exe" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
        if not exist "%TEMP%\python-3.11.9-amd64.exe" (
            echo ❌ 下載失敗 — 請手動去 https://www.python.org/downloads/ 下載 Python 3.11
            pause
            exit /b 1
        )
        echo ✅ 下載完成！
        echo.
        echo 啟動 Python 3.11 安裝程式 —
        echo   ⚠️  最緊要❗ 安裝時一定要 tick「Add Python to PATH」
        echo.
        pause
        start "" /wait "%TEMP%\python-3.11.9-amd64.exe"
        echo.
        echo 安裝完成，重新檢查...
        echo.
        goto CHECK_PYTHON
    )
)

:: 直接搵 python（如果 pythonw 搵唔到，用 python 都得 — 有 console 起碼睇到 error）
if "%PYTHONW%"=="" (
    where python >nul 2>nul && set PYTHONEXE=python
)

if not "%PYTHONW%"=="" goto PYTHON_OK
if not "%PYTHONEXE%"=="" (
    for /f "delims=" %%i in ('where python') do set PYTHONEXE=%%i
    goto PYTHON_OK
)

:: ========== 沒有 Python → 幫你安裝 ==========
echo ⚠️  未偵測到 Python！
echo.
echo Tradotcom Agent 需要 Python 3.11 先可以執行。
echo.
set /p PY_CHOICE="要唔要我幫你下載並安裝 Python 3.11 (Y=下載安裝，N=退出): "
if /i not "%PY_CHOICE%"=="Y" (
    echo.
    echo 你選擇咗退出 — 安裝取消。
    echo 你可以之後去 https://www.python.org/downloads/ 手動安裝
    pause
    exit /b 1
)

echo.
echo ⏳ 下載 Python 3.11 安裝程式（~25MB）...
echo.
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0" -o "%TEMP%\python-3.11.9-amd64.exe" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
if not exist "%TEMP%\python-3.11.9-amd64.exe" (
    echo ❌ 下載失敗 — 請手動去 https://www.python.org/downloads/ 下載安裝
    pause
    exit /b 1
)

echo ✅ 下載完成！
echo.
echo 而家會啟動 Python 安裝程式 —
echo   ⚠️  最緊要❗ 安裝時一定要 tick:
echo       ┌─────────────────────────────────┐
echo       │  ☑ Add Python to PATH          │
echo       │  ✓  Install Now（直接安裝）     │
echo       └─────────────────────────────────┘
echo.
pause
echo 啟動 Python 安裝程式...
start "" /wait "%TEMP%\python-3.11.9-amd64.exe"

:: 裝完再檢查一次
goto CHECK_PYTHON

:: ========== Python 已裝 ==========
:PYTHON_OK
echo ✅ Python 已安裝
echo.

:: ========== 2. 確保有最新安裝程式 ==========
:: 🚨 2026-08-26 FIX：每次重新下載 pyw（保證最新版 — 舊版冇 START log / 有 bug 會「冇反應」）
echo ⏳ 更新安裝程式...
del "%~dp0agent_launcher.log" 2>nul
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0" -o "%~dp0tradotcom_agent.pyw" https://mt5cloud.esgov.org/api/agent-pyw
if not exist "%~dp0tradotcom_agent.pyw" (
    echo ❌ 下載失敗 — 請檢查網絡
    pause
    exit /b 1
)
echo ✅ 已更新
echo.

:: ========== 3. 執行安裝程式 ==========
echo 🚀 啟動安裝精靈...
echo.

if not "%PYTHONW%"=="" (
    start "" "%PYTHONW%" "%~dp0tradotcom_agent.pyw"
) else (
    start "" "%PYTHONEXE%" "%~dp0tradotcom_agent.pyw"
)

:: 檢查 pyw 有冇真係啟動（log 有 START = 執行緊）
timeout /t 4 /nobreak >nul
if exist "%~dp0agent_launcher.log" (
    findstr /c:"START pyw" "%~dp0agent_launcher.log" >nul 2>nul && (
        echo ✅ 安裝程式已啟動
        echo.
        echo ── 啟動記錄 ──
        type "%~dp0agent_launcher.log"
        echo ──────────────
        echo.
        timeout /t 6 /nobreak >nul
        exit /b 0
    )
)

echo ⚠️  安裝程式似乎未成功啟動，檢查緊原因...
timeout /t 2 /nobreak >nul
if exist "%~dp0agent_launcher.log" (
    echo.
    echo ── 錯誤記錄（agent_launcher.log）──
    type "%~dp0agent_launcher.log"
    echo ────────────────────────────────────
    echo.
) else (
    echo ❌ 安裝程式冇任何輸出。可能原因：
    echo   - 1. Python 安裝唔完整（重新安裝 Python 3.11 並 tick Add to PATH）
    echo   - 2. 防毒軟件阻擋
    echo.
)
pause