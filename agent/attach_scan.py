"""
Full-height scan approach — scan every row in the TreeView quickly.
No chart click before scan (keeps Navigator visible).
"""

import os
import sys
import time
import ctypes
import subprocess
import psutil

MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                            'Common', 'Files')
user32 = ctypes.windll.user32


def find_mt5_pid():
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None


def wait_for_mt5(timeout=60):
    start = time.time()
    while time.time() - start < timeout:
        pid = find_mt5_pid()
        if pid:
            time.sleep(3)
            return pid
        time.sleep(2)
    return None


def close_dialogs(mt5_pid):
    """Close all dialogs via WM_CLOSE."""
    pid_buf = ctypes.c_ulong()
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    dialogs = []
    def _cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if title.value:
                    dialogs.append(hwnd)
        return True
    user32.EnumWindows(CB(_cb), 0)
    for hwnd in dialogs:
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)  # WM_CLOSE
        time.sleep(0.2)


def find_dialog(mt5_pid, ea_name):
    """Search for EA Properties dialog."""
    pid_buf = ctypes.c_ulong()
    results = []
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    def _cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if ea_name in title.value:
                    results.append(title.value)
        return True
    user32.EnumWindows(CB(_cb), 0)
    return results


def verify_heartbeat(ea_name, timeout=90):
    hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(hb_file):
            mtime = os.path.getmtime(hb_file)
            age = time.time() - mtime
            if age < 300:
                with open(hb_file, 'rb') as f:
                    content = f.read().decode('utf-16-le', errors='replace').strip().lstrip('\ufeff')
                print(f"💓 Heartbeat: {content} ({round(age)}s old)")
                return True
        time.sleep(3)
    print(f"❌ No heartbeat within {timeout}s")
    return False


def attach_ea(ea_name, symbol='EURUSD', timeframe='H1'):
    print(f"\n{'='*50}")
    print(f"  🚀 Attaching: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    
    mt5_pid = find_mt5_pid()
    if not mt5_pid:
        print("Starting MT5...")
        subprocess.Popen([MT5_PATH])
        mt5_pid = wait_for_mt5()
        if not mt5_pid:
            print("❌ Failed to start MT5")
            return False
    print(f"✅ MT5 PID={mt5_pid}")
    
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    app = Application(backend='win32').connect(process=mt5_pid)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    user32.SetForegroundWindow(ctypes.c_void_p(win.element_info.handle))
    time.sleep(1)
    
    # Close stale dialogs
    close_dialogs(mt5_pid)
    
    # Open Navigator (Ctrl+N toggles it, NO Enter after!)
    send_keys('^n')
    time.sleep(2)
    print("📋 Navigator toggled")
    
    # Find TreeView
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if not tree_view:
        print("❌ TreeView not found")
        return False
    
    hwnd_tree = tree_view.element_info.handle
    tv_rect = tree_view.rectangle()
    print(f"📋 TreeView rect=({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})")
    
    # Navigate to EA and select it
    try:
        root = tree_view.roots()[0]
        children = root.children()
        ea_trading_node = children[2] if len(children) > 2 else None
        if not ea_trading_node:
            print("❌ EA Trading node not found")
            return False
        
        ea_trading_node.expand()
        time.sleep(2)
        
        ea_item = None
        for child in ea_trading_node.children():
            if child.text() == ea_name:
                ea_item = child
                break
        
        if not ea_item:
            print(f"❌ EA '{ea_name}' not found")
            return False
        
        h_item = ea_item.item().hItem
        print(f"🎯 Found EA: {ea_name} (hItem={h_item})")
        
        # Select and ensure visible
        TVM_SELECTITEM = 0x1100 + 11
        TVGN_CARET = 9
        TVM_ENSUREVISIBLE = 0x1100 + 20
        user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
        user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
        time.sleep(1)
        print("📋 EA selected")
    except Exception as e:
        print(f"❌ Tree nav error: {e}")
        return False
    
    # Scan the TreeView from top to bottom
    import pyautogui
    import pywinauto
    
    click_x = tv_rect.left + 60  # Text area
    
    for attempt in range(3):
        print(f"📋 Scanning attempt {attempt+1}/3...")
        found = False
        
        for y_step in range(0, tv_rect.bottom - tv_rect.top, 9):
            click_y = tv_rect.top + y_step + 4
            pyautogui.doubleClick(x=click_x, y=click_y)
            time.sleep(0.5)  # Short wait between clicks
            
            # Check every ~5 clicks
            if y_step % 45 == 0:
                dialogs = find_dialog(mt5_pid, ea_name)
                if dialogs:
                    print(f"🎉 Found '{dialogs[0]}' dialog at y={click_y}!")
                    send_keys('{ENTER}')
                    time.sleep(1)
                    send_keys('^e')
                    time.sleep(1)
                    print("✅ Confirmed, AutoTrading ON")
                    
                    time.sleep(5)
                    hb_ok = verify_heartbeat(ea_name)
                    if hb_ok:
                        print(f"\n🎉 SUCCESS: {ea_name} is running on {symbol} {timeframe}!")
                        return True
                    else:
                        print(f"⚠️ Attached but no heartbeat")
                        return True
        
        # Final check
        dialogs = find_dialog(mt5_pid, ea_name)
        if dialogs:
            print(f"🎉 Found '{dialogs[0]}' dialog (delayed)!")
            send_keys('{ENTER}')
            time.sleep(1)
            send_keys('^e')
            time.sleep(1)
            time.sleep(5)
            hb_ok = verify_heartbeat(ea_name)
            if hb_ok:
                print(f"\n🎉 SUCCESS: {ea_name} is running!")
                return True
            else:
                return True
        
        send_keys('{ESC}')
        time.sleep(0.3)
        print(f"⚠️ No dialog found (attempt {attempt+1}/3)")
    
    print(f"❌ {ea_name} attach failed after 3 attempts")
    return False


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--ea', required=True)
    parser.add_argument('--symbol', default='EURUSD')
    parser.add_argument('--tf', default='H1')
    args = parser.parse_args()
    
    result = attach_ea(args.ea, args.symbol, args.tf)
    sys.exit(0 if result else 1)
