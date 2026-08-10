"""Attach EA using pywinauto click_input on the tree item directly.
No chart click beforehand — the Navigator stays visible."""

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
            time.sleep(3)  # extra wait for window to be ready
            return pid
        time.sleep(2)
    return None


def find_eatree_node(app, ea_name):
    """Find the EA item in the Navigator TreeView."""
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    
    # Find SysTreeView32
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if not tree_view:
        print("❌ No TreeView found")
        return None, None
    
    print(f"📋 TreeView visible={tree_view.is_visible()} rect={tree_view.rectangle()}")
    
    # Navigate to EA item
    try:
        root = tree_view.roots()[0]
        children = root.children()
        
        ea_node = None
        if len(children) > 2:
            ea_node = children[2]
        if not ea_node:
            for child in children:
                t = child.text()
                if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
                    ea_node = child
                    break
        
        if not ea_node:
            print("❌ EA Trading node not found")
            return None, None
        
        ea_node.expand()
        time.sleep(1)
        
        for child in ea_node.children():
            if child.text() == ea_name:
                print(f"🎯 Found EA: {ea_name}")
                return tree_view, child
        
        print(f"❌ EA '{ea_name}' not found")
        return None, None
    except Exception as e:
        print(f"❌ Tree nav error: {e}")
        return None, None


def find_dialog(mt5_pid, ea_name):
    """Find dialog with ea_name in title."""
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
                    raw = f.read()
                content = raw.decode('utf-16-le', errors='replace').strip().lstrip('\ufeff')
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
    
    # Connect
    app = Application(backend='win32').connect(process=mt5_pid)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    try:
        win.set_focus()
    except:
        pass
    time.sleep(1)
    
    # Step 1: Open new chart
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
    
    # Step 3: Find EA in tree
    tree_view, ea_item = find_eatree_node(app, ea_name)
    if not ea_item:
        return False
    
    # Step 4: Select the EA item via Win32 (this highlights it)
    hwnd_tree = tree_view.element_info.handle
    h_item = ea_item.item().hItem
    TVM_SELECTITEM = 0x1100 + 11
    TVGN_CARET = 9
    TVM_ENSUREVISIBLE = 0x1100 + 20
    user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
    user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
    time.sleep(0.5)
    
    # Step 5: Double-click the EA item using pywinauto's click_input
    # This simulates a real click at the item's screen coordinates
    for attempt in range(3):
        print(f"📋 click_input double-click (attempt {attempt+1})...")
        try:
            ea_item.click_input(button='left', double=True)
        except Exception as e:
            print(f"⚠️ click_input failed: {e}")
        time.sleep(2)
        
        dialogs = find_dialog(mt5_pid, ea_name)
        if dialogs:
            print(f"🎉 Found '{dialogs[0]}' dialog!")
            # Confirm dialog
            send_keys('{ENTER}')
            time.sleep(1)
            # Toggle AutoTrading ON
            send_keys('^e')
            time.sleep(1)
            print("✅ Properties confirmed, AutoTrading ON")
            
            # Wait for EA to start
            time.sleep(5)
            hb_ok = verify_heartbeat(ea_name)
            if hb_ok:
                print(f"\n🎉 SUCCESS: {ea_name} is running!")
                return True
            else:
                print(f"⚠️ Attached but no heartbeat yet")
                return True
        
        # Close any accidental dialog
        send_keys('{ESC}')
        time.sleep(0.3)
    
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
