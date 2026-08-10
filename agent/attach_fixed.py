"""
Clean EA attachment — fixed approach:
1. Close any stale dialogs (ESC)
2. Open Navigator (Ctrl+N) — that's all, NO Enter after it
3. Find EA in tree via pywinauto
4. Select + double-click with precise coordinates via pyautogui
5. Confirm dialog, toggle AutoTrading
6. Verify heartbeat
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


def find_dialog(mt5_pid, ea_name=''):
    """Find dialog windows belonging to MT5."""
    pid_buf = ctypes.c_ulong()
    results = []
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    def _cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':  # Dialog class
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if ea_name:
                    if ea_name in title.value:
                        results.append(title.value)
                else:
                    if title.value:
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


def close_stale_dialogs(mt5_pid):
    """Close any open dialogs (like New Account) by pressing ESC."""
    from pywinauto.keyboard import send_keys
    dialogs = find_dialog(mt5_pid)
    for d in dialogs:
        print(f"📋 Closing stale dialog: '{d}'")
    if dialogs:
        send_keys('{ESC}')
        time.sleep(1)
        send_keys('{ESC}')
        time.sleep(1)


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
    user32.SetForegroundWindow(ctypes.c_void_p(win.element_info.handle))
    time.sleep(1)
    
    # ── Close any stale modal dialogs ──
    close_stale_dialogs(mt5_pid)
    
    # ── Open Navigator (Ctrl+N toggles it) — NO Enter after! ──
    send_keys('^n')
    time.sleep(2)
    print("📋 Navigator toggled")
    
    # ── Find TreeView and EA ──
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if not tree_view:
        print("❌ TreeView not found")
        return False
    
    tv_rect = tree_view.rectangle()
    print(f"📋 TreeView rect=({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})")
    
    # Navigate tree to EA
    try:
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
        
        ea_trading_node.expand()
        time.sleep(2)
        
        ea_item = None
        ea_index = None
        for i, child in enumerate(ea_trading_node.children()):
            if child.text() == ea_name:
                ea_item = child
                ea_index = i
                break
        
        if not ea_item:
            print(f"❌ EA '{ea_name}' not found")
            return False
        
        print(f"🎯 Found EA: {ea_name} at index {ea_index}")
        
    except Exception as e:
        print(f"❌ Tree navigation error: {e}")
        return False
    
    # ── Select the item via Win32 messages ──
    hwnd_tree = tree_view.element_info.handle
    h_item = ea_item.item().hItem
    
    TVM_SELECTITEM = 0x1100 + 11
    TVGN_CARET = 9
    TVM_ENSUREVISIBLE = 0x1100 + 20
    
    user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
    user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
    time.sleep(1)
    print("📋 EA selected in tree")
    
    # ── Calculate click position ──
    # Tree item height is 20px (from TVM_GETITEMHEIGHT)
    # First EA item starts at TreeView.top + small offset
    # After EnsureVisible, our item should be near top
    # 
    # But we know EA trading node has 3 subfolders before the EAs:
    # Advisors(0), Examples(1), Free Robots(2) — these are folders inside EA Trading
    # Then actual EAs start at index 3+
    #
    # So step 0 = EA Trading header (expanded)
    # Steps 1-2 = subfolders (Advisors, Examples)
    # Step 3 = Free Robots (folder)
    # Step 4 = ADX_Trend (first EA)
    # ...
    # Step 13 = EMA_Cross (because 3 subfolders + 10 = 13th item in expanded EA Trading)
    
    # But after EnsureVisible, the item is scrolled to the top.
    # Let's calculate: first item that should be visible = our item
    # Y = TreeView.top + small_padding (like 2px)
    
    item_height = 20
    click_x = tv_rect.left + 40  # Left side of text area
    click_y = tv_rect.top + 2    # First item position after EnsureVisible (scrolled)
    
    # Actually, let me also try a scan of just ±3 items around our expected position
    # In case EnsureVisible didn't scroll perfectly
    
    print(f"📋 Click position: ({click_x}, {click_y})")
    
    import pyautogui
    
    for attempt in range(3):
        # Try top of TreeView (where EnsureVisible should have placed the item)
        candidate_y = tv_rect.top + 2  # Small offset from top of TreeView
        
        for offset in range(0, 40, item_height):
            y = candidate_y + offset
            print(f"📋 Double-click at ({click_x}, {y}) (offset={offset})")
            pyautogui.doubleClick(x=click_x, y=y)
            time.sleep(2)
            
            dialogs = find_dialog(mt5_pid, ea_name)
            if dialogs:
                print(f"🎉 Found '{dialogs[0]}' dialog!")
                # Confirm the dialog
                send_keys('{ENTER}')
                time.sleep(1)
                send_keys('^e')  # AutoTrading toggle
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
            
            if offset >= 60:  # Scan up to 3 items worth of space
                break
        
        # Close any accidental dialogs
        send_keys('{ESC}')
        time.sleep(0.3)
        print(f"⚠️ Dialog not found (attempt {attempt+1}/3)")
        
        # Reselect and re-ensure visible
        user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
        user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
        time.sleep(1)
    
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
