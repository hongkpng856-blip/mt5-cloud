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
for %%p in ("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" "%PROGRAMFILES%\Python311\pythonw.exe") do (
    if exist %%p set PYTHONW=%%~p
)
if "%PYTHONW%"=="" (
    py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'),end='')" > _pyw_path.txt 2>nul
    set /p PYTHONW=<_pyw_path.txt
    del _pyw_path.txt 2>nul
)

if "%PYTHONW%"=="" (
    echo ❌ 搵唔到 Python！請先安裝 Python 3.11（記得 tick Add to PATH）
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
start "" "%PYTHONW%" "%~dp0tradotcom_agent.pyw"
exit /b 0