"""
MT5 EA Auto-Attach Tool
自動開 chart + attach EA 到 MT5
用法: python attach_ea.py --ea ADX_Trend --symbol EURUSD --tf H1
"""
import argparse
import os
import sys
import time
import subprocess

def restart_mt5():
    """重啟 MT5 令 Navigator refresh 新 compile 嘅 EA"""
    # Kill MT5
    subprocess.run(['taskkill', '/F', '/IM', 'terminal64.exe'], 
                   capture_output=True, timeout=10)
    time.sleep(3)
    
    # Start MT5
    mt5_path = r'C:\Program Files\MetaTrader 5\terminal64.exe'
    subprocess.Popen([mt5_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
    print("⏳ MT5 restarting... waiting 15s for full load")
    time.sleep(15)
    return True

def attach_ea_via_gui(ea_name, symbol, timeframe):
    """用 pywinauto + computer_use 自動 attach EA 到 chart"""
    from pywinauto import Application
    
    # Find MT5 window
    try:
        app = Application(backend='uia').connect(path='terminal64.exe', timeout=10)
        win = app.top_window()
        print(f"Found MT5: {win.window_text()}")
    except Exception as e:
        print(f"❌ Cannot find MT5: {e}")
        return False
    
    # Step 1: Open new chart via File menu → New Chart → symbol
    win.menu_select("文件(F) -> 新圖(N)")
    time.sleep(1)
    
    # Find symbol in submenu and click
    try:
        popup = win.child_window(auto_id='Popup', control_type='Window')
        symbol_item = popup.child_window(title=symbol, control_type='MenuItem')
        symbol_item.click_input()
        time.sleep(2)
        print(f"✅ Opened chart: {symbol}")
    except Exception as e:
        print(f"⚠️ Symbol click failed: {e}")
        # Try Escape and use keyboard
        from pywinauto.keyboard import send_keys
        send_keys('{ESC}')
        time.sleep(0.5)
    
    # Step 2: Find EA in Navigator tree and drag to chart
    # First select EA交易 node in Navigator
    nav = win.child_window(title_re='.*導航.*|.*Navigator.*', control_type='Pane')
    tree = nav.child_window(control_type='Tree')
    
    # Expand EA交易
    ea_node = tree.child_window(title='EA交易', control_type='TreeItem')
    ea_node.click_input(double=True)
    time.sleep(1)
    
    # Search for our EA by typing in tree
    tree.click_input()
    from pywinauto.keyboard import send_keys
    send_keys(ea_name[:5])  # Type first 5 chars to find
    time.sleep(1)
    
    # The found item should be selected now - double click to attach
    send_keys('{ENTER}')
    time.sleep(2)
    
    # If dialog appears, click OK
    try:
        ok_btn = win.child_window(title='確定', control_type='Button')
        ok_btn.click_input()
        print(f"✅ EA dialog OK clicked")
    except:
        try:
            ok_btn = win.child_window(title='OK', control_type='Button')
            ok_btn.click_input()
            print(f"✅ EA dialog OK clicked")
        except:
            print("No dialog found (might be auto-attached)")
    
    time.sleep(2)
    
    # Step 3: Enable AutoTrading if not already
    algo_cb = win.child_window(title='算法交易', control_type='CheckBox')
    if not algo_cb.is_checked():
        algo_cb.click_input()
        print("✅ AlgoTrading enabled")
    
    return True

def main():
    parser = argparse.ArgumentParser(description='Auto-attach EA to MT5 chart')
    parser.add_argument('--ea', required=True, help='EA name (e.g. ADX_Trend)')
    parser.add_argument('--symbol', default='EURUSD', help='Symbol (default: EURUSD)')
    parser.add_argument('--tf', default='H1', help='Timeframe (default: H1)')
    parser.add_argument('--restart', action='store_true', help='Restart MT5 first')
    args = parser.parse_args()
    
    if args.restart:
        restart_mt5()
    
    success = attach_ea_via_gui(args.ea, args.symbol, args.tf)
    if success:
        print(f"\n🎉 {args.ea} attached to {args.symbol} {args.tf}")
    else:
        print(f"\n❌ Failed to attach {args.ea}")
        sys.exit(1)

if __name__ == '__main__':
    main()
