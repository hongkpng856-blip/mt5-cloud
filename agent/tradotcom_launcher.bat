@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Tradotcom Agent Setup

:: ============================================================
::  Tradotcom Agent - double-click launcher
::  Auto-detects: Python 3.14 blocked (MT5 incompatible) -> installs 3.11
:: ============================================================

echo.
echo ==============================================
echo   Tradotcom Agent Installer
echo ==============================================
echo.

:: ========== 1. Check Python ==========
:CHECK_PYTHON
set PYTHONW=
set PYTHONEXE=

:: Find pythonw / python (multiple locations + py launcher)
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

:: Fallback to py launcher (NOTE: moved out of if-block - the nested ')' in python code breaks batch parsing)
if not "%PYTHONW%"=="" goto PY_VERSION_CHECK
py -3 -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'),end='')" > "%TEMP%\_pyw_path.txt" 2>nul
set /p PYTHONW=<"%TEMP%\_pyw_path.txt"
set /p PYTHONEXE=<"%TEMP%\_pyw_path.txt"
del "%TEMP%\_pyw_path.txt" 2>nul
:PY_VERSION_CHECK

:: Check Python version - 3.14 incompatible with MetaTrader5 -> need 3.11/3.12
if not "%PYTHONW%"=="" (
    set "PYVER_CHECK=%PYTHONW:\pythonw.exe=\python.exe%"
    "%PYVER_CHECK%" --version 2> "%TEMP%\_pyver.txt"
    set /p PYVER=<"%TEMP%\_pyver.txt"
    del "%TEMP%\_pyver.txt" 2>nul
    echo PYVER=!PYVER!>nul
    echo !PYVER! | findstr /c:"3.14" >nul 2>nul
    if not errorlevel 1 (
        echo [WARNING] Your Python is 3.14 - MetaTrader5 hangs on 3.14!
        echo    Tradotcom Agent requires Python 3.11 or 3.12.
        echo.
        set /p PY_CHOICE2="Download and install Python 3.11? (Y=Download, N=Exit): "
        if /i not "!PY_CHOICE2!"=="Y" (
            echo.
            echo You chose to exit - installation cancelled.
            echo You can install Python 3.11 manually later: https://www.python.org/downloads/
            pause
            exit /b 1
        )
        echo.
        echo Downloading Python 3.11 installer - 25MB...
        curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0" -o "%TEMP%\python-3.11.9-amd64.exe" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
        if not exist "%TEMP%\python-3.11.9-amd64.exe" (
            echo [ERROR] Download failed - please install Python 3.11 manually: https://www.python.org/downloads/
            pause
            exit /b 1
        )
        echo Download complete!
        echo.
        echo Launching Python 3.11 installer...
        echo   [IMPORTANT] Tick "Add Python to PATH" during installation!
        echo.
        pause
        start "" /wait "%TEMP%\python-3.11.9-amd64.exe"
        echo.
        echo Installer finished. Verifying Python 3.11...
        :: Directly point to standard 3.11 paths (avoid py -3 picking 3.14 again -> infinite loop)
        if exist "%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe" (
            set "PYTHONW=%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe"
            echo Python 3.11 installed OK.
        ) else if exist "%PROGRAMFILES%\Python311\pythonw.exe" (
            set "PYTHONW=%PROGRAMFILES%\Python311\pythonw.exe"
            echo Python 3.11 installed OK.
        ) else (
            echo [ERROR] Python 3.11 not found - installation may not have completed.
            echo   Please re-run the installer and tick "Add Python to PATH",
            echo   or get Python 3.11 from https://www.python.org/downloads/
            pause
            exit /b 1
        )
        echo.
        echo Continuing Tradotcom Agent setup...
    )
)

if "%PYTHONW%"=="" goto NO_PYTHON
goto PYTHON_OK

:NO_PYTHON
echo [WARNING] Python not detected!
echo.
echo Tradotcom Agent requires Python 3.11 to run.
echo.
set /p PY_CHOICE="Download and install Python 3.11? (Y=Download, N=Exit): "
if /i not "!PY_CHOICE!"=="Y" (
    echo.
    echo Exiting - installation cancelled.
    echo You can install Python manually: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo Downloading Python 3.11 installer - 25MB...
curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0" -o "%TEMP%\python-3.11.9-amd64.exe" https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
if not exist "%TEMP%\python-3.11.9-amd64.exe" (
    echo [ERROR] Download failed - please install Python 3.11 manually: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo Download complete!
echo.
echo Launching Python 3.11 installer...
echo   [IMPORTANT] Tick "Add Python to PATH" during installation!
echo.
pause
start "" /wait "%TEMP%\python-3.11.9-amd64.exe"

:: Verify again after install
goto CHECK_PYTHON

:PYTHON_OK
echo Python found.
echo.

:: ========== 2. Ensure latest installer ==========
:: Re-download pyw each time (latest version - old versions have bugs)
echo Updating installer...
del "%TARGET_DIR%\agent_launcher.log" 2>nul
:: 🚨 2026-08-26：下載重試 3 次（tunnel 短暫斷線會 fail — 自動再試）
:: NOTE: goto 唔可以喺 if block 內（batch 解析亂）→ 用 for /l 計數重試
for /l %%t in (1,1,3) do (
    curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) TradotcomAgent/1.0" -o "%TARGET_DIR%\tradotcom_agent.pyw" https://mt5cloud.esgov.org/api/agent-pyw
    if exist "%TARGET_DIR%\tradotcom_agent.pyw" goto DL_OK
    echo [WARNING] Download failed (attempt %%t/3) - retrying...
    ping -n 4 127.0.0.1 >nul
)
echo [ERROR] Download failed after 3 attempts - please check your network.
pause
exit /b 1
:DL_OK
echo Updated.
echo.

:: ========== 3. Launch installer ==========
echo Starting installer wizard...
echo.

if not "%PYTHONW%"=="" (
    start "" "%PYTHONW%" "%TARGET_DIR%\tradotcom_agent.pyw"
) else (
    start "" "%PYTHONEXE%" "%TARGET_DIR%\tradotcom_agent.pyw"
)

:: Check pyw actually started (log has START = running)
timeout /t 4 /nobreak >nul
if exist "%TARGET_DIR%\agent_launcher.log" (
    findstr /c:"START pyw" "%TARGET_DIR%\agent_launcher.log" >nul 2>nul && (
        echo Installer started.
        echo.
        echo -- Startup log --
        type "%TARGET_DIR%\agent_launcher.log"
        echo -----------------
        echo.
        timeout /t 6 /nobreak >nul
        exit /b 0
    )
)

echo [WARNING] Installer may not have started properly, checking...
timeout /t 2 /nobreak >nul
if exist "%TARGET_DIR%\agent_launcher.log" (
    echo.
    echo -- Error log agent_launcher.log --
    type "%TARGET_DIR%\agent_launcher.log"
    echo -----------------------------------
    echo.
) else (
    echo [ERROR] Installer produced no output. Possible causes:
    echo   - 1. Python installation incomplete - reinstall Python 3.11, tick Add to PATH
    echo   - 2. Antivirus blocking
    echo.
)
pause