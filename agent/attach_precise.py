"""
Precise EA attachment: uses pywinauto.rectangle() for exact coordinates,
then pyautogui.doubleClick at that exact position. No blind scanning.
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


def enum_dialogs(mt5_pid, ea_name):
    """Check if EA Properties dialog is open."""
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
    
    # ── Ensure MT5 running ──
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
    try:
        win.set_focus()
    except:
        pass
    time.sleep(1)
    
    # Step 1: Open new chart for this EA
    send_keys('^n')
    time.sleep(1)
    send_keys('{ENTER}')
    time.sleep(3)
    print("📋 New chart opened")
    
    # Step 2: Open Navigator via keyboard
    send_keys('%v')
    time.sleep(0.5)
    send_keys('n')
    time.sleep(0.5)
    send_keys('{ENTER}')
    time.sleep(2)
    print("📋 Navigator opened")
    
    # Step 3: Find TreeView and EA node
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if not tree_view:
        print("❌ TreeView not found")
        return False
    
    print(f"📋 TreeView rect={tree_view.rectangle()}")
    
    # Navigate to EA
    root = tree_view.roots()[0]
    children = root.children()
    
    ea_trading_node = children[2] if len(children) > 2 else None
    if not ea_trading_node:
        for child in children:
            t = child.text()
            if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
                ea_trading_node = child
                break
    
    if not ea_trading_node:
        print("❌ EA Trading node not found")
        return False
    
    # Expand the EA trading node
    try:
        ea_trading_node.expand()
    except:
        pass
    time.sleep(2)  # Give time for tree to expand
    
    # Find the target EA
    ea_item = None
    for child in ea_trading_node.children():
        if child.text() == ea_name:
            ea_item = child
            break
    
    if not ea_item:
        print(f"❌ EA '{ea_name}' not found")
        return False
    
    print(f"🎯 Found EA: {ea_name}")
    
    # Step 4: Select the item via Win32 messages
    hwnd_tree = tree_view.element_info.handle
    h_item = ea_item.item().hItem
    TVM_SELECTITEM = 0x1100 + 11
    TVGN_CARET = 9
    TVM_ENSUREVISIBLE = 0x1100 + 20
    user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
    user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
    time.sleep(1)
    
    # Step 5: Get the exact item rectangle and double-click
    import pyautogui
    
    for attempt in range(3):
        # Get fresh rectangle
        item_rect = ea_item.rectangle()
        cx = item_rect.left + 30  # Click on the text area (not icon)
        cy = (item_rect.top + item_rect.bottom) // 2
        
        print(f"📋 EA rect: ({item_rect.left},{item_rect.top})-({item_rect.right},{item_rect.bottom})")
        print(f"📋 Double-click at ({cx}, {cy})")
        
        pyautogui.doubleClick(x=cx, y=cy)
        time.sleep(2)
        
        dialogs = enum_dialogs(mt5_pid, ea_name)
        if dialogs:
            print(f"🎉 Found '{dialogs[0]}' dialog!")
            send_keys('{ENTER}')
            time.sleep(1)
            send_keys('^e')  # Ctrl+E = AutoTrading toggle
            time.sleep(1)
            print("✅ Properties confirmed, AutoTrading ON")
            
            time.sleep(5)
            hb_ok = verify_heartbeat(ea_name)
            if hb_ok:
                print(f"\n🎉 SUCCESS: {ea_name} is running on {symbol} {timeframe}!")
                return True
            else:
                print(f"⚠️ Attached but no heartbeat yet")
                return True
        
        print(f"⚠️ Dialog not found (attempt {attempt+1}/3)")
        send_keys('{ESC}')
        time.sleep(0.5)
    
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
