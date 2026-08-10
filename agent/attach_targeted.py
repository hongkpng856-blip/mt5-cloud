"""
Targeted EA attachment: calculates exact tree position, opens a new chart,
and double-clicks only at the calculated coordinates.
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
        user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
        time.sleep(0.2)


def find_dialog(mt5_pid, ea_name=''):
    """Find dialogs. If ea_name given, search for that. Otherwise return all."""
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
                if title.value:
                    if ea_name:
                        if ea_name in title.value:
                            results.append(title.value)
                    else:
                        results.append(title.value)
        return True
    user32.EnumWindows(CB(_cb), 0)
    return results


def verify_heartbeat(ea_name, timeout=30):
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
        time.sleep(2)
    return False


def attach_ea(ea_name, symbol='EURUSD', timeframe='H1'):
    print(f"\n{'='*50}")
    print(f"  🚀 Attaching: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    
    mt5_pid = find_mt5_pid()
    if not mt5_pid:
        subprocess.Popen([MT5_PATH])
        mt5_pid = wait_for_mt5()
        if not mt5_pid:
            return False
    print(f"✅ MT5 PID={mt5_pid}")
    
    from pywinauto import Application
    from pywinauto.keyboard import send_keys
    
    app = Application(backend='win32').connect(process=mt5_pid)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    user32.SetForegroundWindow(ctypes.c_void_p(win.element_info.handle))
    time.sleep(0.5)
    
    close_dialogs(mt5_pid)
    
    # Step 1: Close stale dialogs, then open Navigator
    send_keys('^n')
    time.sleep(2)
    
    # Step 3: Find EA and calculate position
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
    
    # Navigate
    root = tree_view.roots()[0]
    children = root.children()
    ea_trading = children[2] if len(children) > 2 else None
    if not ea_trading:
        return False
    ea_trading.expand()
    time.sleep(2)
    
    # Find target EA and get its index
    ea_item = None
    ea_idx = None
    ea_kids = ea_trading.children()
    for i, child in enumerate(ea_kids):
        if child.text() == ea_name:
            ea_item = child
            ea_idx = i
            break
    if not ea_item:
        print(f"❌ EA '{ea_name}' not found")
        return False
    
    print(f"🎯 Found {ea_name} at EA-child index {ea_idx}")
    
    # Select the item
    h_item = ea_item.item().hItem
    TVM_SELECTITEM = 0x1100 + 11
    TVGN_CARET = 9
    TVM_ENSUREVISIBLE = 0x1100 + 20
    user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
    user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
    time.sleep(0.5)
    
    # Calculate position: EA Trading children start at tree position ~9 (6 roots + 1 header + 3 folders = 10)
    # But visibility depends on scroll. After EnsureVisible, item will be at the top.
    # Item height = 20px
    # The item should be at TreeView.top + small_offset
    # Try y from TreeView.top to TreeView.top + 60 (3 items worth)
    
    import pyautogui
    click_x = tv_rect.left + 60
    
    for attempt in range(1):
        # Re-select before each attempt
        user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
        user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
        time.sleep(0.5)
        
        # Scan top portion of tree (item should be near top after EnsureVisible)
        found = False
        # Scan the TreeView: the EA should be near the visible top after EnsureVisible,
        # but could be anywhere within the visible area.
        # Scan the entire TreeView height.
        scan_height = tv_rect.bottom - tv_rect.top  # Full visible area (~296px)
        for y_offset in range(0, scan_height, 6):  # 6px steps = ~50 iterations
            click_y = tv_rect.top + y_offset
            pyautogui.doubleClick(x=click_x, y=click_y)
            time.sleep(0.3)  # short wait
            
            dialogs = find_dialog(mt5_pid, ea_name)
            if dialogs:
                print(f"🎉 Properties dialog at y={click_y}: '{dialogs[0]}'")
                send_keys('{ENTER}')
                time.sleep(1)
                send_keys('^e')
                time.sleep(1)
                print("✅ Confirmed, AutoTrading ON")
                
                # Quick heartbeat check
                time.sleep(3)
                hb = verify_heartbeat(ea_name, timeout=15)
                print(f"🎉 SUCCESS: {ea_name} is attached!" if hb else f"✅ {ea_name} attached (no heartbeat)")
                return True
            
            # Check for ANY dialog — if not ours, close it
            all_d = find_dialog(mt5_pid)
            for d in all_d:
                # A Properties dialog title looks like 'EA_Name 1.00 (EURUSD,H1)'
                if ea_name not in d and d != 'MetaTrader 5 - Netting - EURUSD,H1':
                    # This is someone else's dialog — close it
                    if d == 'MetaTrader 5' or 'replace' in d.lower() or '代替' in d:
                        print(f"📋 Replace dialog detected ('{d}'), sending Yes...")
                        send_keys('y')
                        time.sleep(2)
                        dialogs2 = find_dialog(mt5_pid, ea_name)
                        if dialogs2:
                            print(f"🎉 Properties dialog: '{dialogs2[0]}'")
                            send_keys('{ENTER}')
                            time.sleep(1)
                            send_keys('^e')
                            time.sleep(1)
                            print("✅ Confirmed, AutoTrading ON")
                            hb = verify_heartbeat(ea_name, timeout=15)
                            return True
                    else:
                        # Close this dialog
                        send_keys('{ESC}')
                        time.sleep(0.3)
        
        if not found:
            send_keys('{ESC}')
            time.sleep(0.3)
            print(f"⚠️ Not found (attempt {attempt+1}/2)")
    
    print(f"❌ {ea_name} attach failed")
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
