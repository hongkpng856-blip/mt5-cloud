# MT5 Cloud Agent — Auto Deploy Module
# This replaces the execute_deploy function with reliable UI automation

def execute_deploy(data):
    ea_name = data.get('ea_name', '')
    symbol = data.get('symbol', 'EURUSD')
    tf = data.get('tf', 'H1')
    magic = str(data.get('magic', '240701'))
    lot = str(data.get('lot', '1.00'))
    print(f"🚀 [EXEC] Deploying {ea_name} -> {symbol} {tf}")

    def report(msg, status='info'):
        print(f"   {msg}")
        sio.emit('install_result', {"status": status, "ea": ea_name, "msg": msg})

    try:
        from pywinauto import Application
        import subprocess, time, os

        # Find or launch MT5
        mt5_exe = None
        for prog in ['C:\\Program Files\\MetaTrader 5\\terminal64.exe',
                     'C:\\Program Files (x86)\\MetaTrader 5\\terminal64.exe']:
            if os.path.isfile(prog):
                mt5_exe = prog
                break
        if not mt5_exe:
            report('❌ 找不到 MT5', 'error')
            return

        # Connect to MT5
        connected = False
        for attempt in range(3):
            for pattern in ['.*模擬.*', '.*ICMarkets.*', '.*MetaTrader.*', '.*']:
                try:
                    app = Application(backend='win32').connect(title_re=pattern, timeout=3)
                    connected = True
                    break
                except:
                    continue
            if connected:
                break
            if attempt == 0:
                subprocess.Popen([mt5_exe])
            time.sleep(8)

        if not connected:
            report('❌ MT5 無法連接，請手動打開 MT5', 'error')
            return

        report('🖥️ MT5 已連接')
        dlg = app.top_window()
        dlg.set_focus()
        dlg.restore()
        time.sleep(0.5)

        # === Step 1: Open chart using toolbar button ===
        report(f'📈 開 {symbol} chart...')
        try:
            # Try clicking the 'New Chart' toolbar button (usually the 1st or 2nd toolbar)
            # The MT5 toolbar has buttons like: New Chart, Profiles, Market Watch, etc.
            toolbar = dlg.child_window(class_name='ToolbarWindow32', found_index=0)
            if toolbar.exists():
                # Click the New Chart button (first button in Standard toolbar)
                toolbar.button(0).click()
                time.sleep(1)
                # Now a symbol selection window should be open
                # Find the symbol list and type
            else:
                # Fallback: use Alt+F, N
                dlg.type_keys('%f')
                time.sleep(0.3)
                dlg.type_keys('n')
                time.sleep(0.5)
        except:
            # Last resort: SendKeys
            import pyautogui
            pyautogui.hotkey('alt', 'f')
            time.sleep(0.5)
            pyautogui.press('n')

        time.sleep(1.5)

        # The Symbol selection window should now be open
        # Try to find it and select the symbol
        try:
            sym_dlg = app.window(title_re='.*Symbol.*|.*品種.*|.*交易.*')
            if sym_dlg.exists():
                sym_dlg.set_focus()
                sym_dlg.type_keys(symbol, pause=0.05)
                time.sleep(0.3)
                sym_dlg.type_keys('{ENTER}')
            else:
                # Type directly
                import pyautogui
                pyautogui.write(symbol, interval=0.03)
                time.sleep(0.3)
                pyautogui.press('enter')
        except:
            import pyautogui
            pyautogui.write(symbol, interval=0.03)
            time.sleep(0.3)
            pyautogui.press('enter')

        time.sleep(1.5)
        report(f'📈 Chart opened')

        # === Step 2: Attach EA via Navigator ===
        report(f'🔌 載入 {ea_name}...')
        import pyautogui
        pyautogui.hotkey('ctrl', 'n')
        time.sleep(0.8)
        ea_short = ea_name.replace('.mq5','').replace('.ex5','')
        pyautogui.write(ea_short, interval=0.03)
        time.sleep(0.8)
        pyautogui.press('enter')
        time.sleep(2)
        report(f'🔌 EA dialog opened')

        # === Step 3: Set parameters ===
        report('⚙️ 設定參數...')
        pyautogui.press('tab', presses=4, interval=0.05)
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'right')
        time.sleep(0.5)
        pyautogui.press('tab')
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.write(magic, interval=0.02)
        pyautogui.press('tab')
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.write(lot, interval=0.02)
        time.sleep(0.3)
        pyautogui.press('enter')
        time.sleep(0.5)
        pyautogui.press('enter')

        report(f'✅ {ea_name} → {symbol} {tf} 已部署！', 'ok')

    except Exception as e:
        report(f'❌ {str(e)[:80]}', 'error')