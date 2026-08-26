@echo off
chcp 65001 >nul
title Tradotcom Agent 啟動器

:: ============================================
::  Tradotcom Agent — double-click 啟動器
::  第一次執行：下載安裝程式再執行
::  之後執行：直接啟動 Agent
:: ============================================

:: 檢查 pythonw（用 py launcher 搵 Python3）
set PYTHONW=
for %%p in ("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" "%LOCALAPPDATA%\Programs\Python\Python313\pythonw.exe" "%PROGRAMFILES%\Python311\pythonw.exe" "%PROGRAMFILES%\Python312\pythonw.exe" "%PROGRAMFILES%\Python313\pythonw.exe" "C:\Python311\pythonw.exe" "C:\Python312\pythonw.exe") do (
    if exist %%p set PYTHONW=%%~p
)
if "%PYTHONW%"=="" (
    py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'),end='')" > "%TEMP%\_pyw_path.txt" 2>nul
    set /p PYTHONW=<"%TEMP%\_pyw_path.txt"
    del "%TEMP%\_pyw_path.txt" 2>nul
)

if "%PYTHONW%"=="" (
    echo.
    echo ════════════════════════════════════════
    echo   ❌ 搵唔到 Python！
    echo.
    echo   請先安裝 Python 3.11：
    echo   1. 去 https://www.python.org/downloads/
    echo   2. 下載 3.11 安裝
    echo   3. 安裝時記得 tick「Add Python to PATH」
    echo   4. 再 double-click 呢個檔案
    echo ════════════════════════════════════════
    echo.
    pause
    exit /b 1
)

:: 確保有 tradotcom_agent.pyw（冇就下載）
if not exist "%~dp0tradotcom_agent.pyw" (
    echo 第一次執行 — 下載安裝程式...
    curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0" -o "%~dp0tradotcom_agent.pyw" https://mt5cloud.esgov.org/api/agent-pyw
    if not exist "%~dp0tradotcom_agent.pyw" (
        echo ❌ 下載失敗 — 請檢查網絡
        pause
        exit /b 1
    )
)

:: 執行安裝程式（pythonw — 冇黑色視窗）
echo ✅ 啟動中...（安裝精靈視窗即將出現）
start "" "%PYTHONW%" "%~dp0tradotcom_agent.pyw"
timeout /t 2 /nobreak >nul
exit /b 0