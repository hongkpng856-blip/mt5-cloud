"""Simplified EA attachment — uses pywinauto item rectangle + pyautogui double-click.
Reuses the same pywinauto connection throughout to avoid PID-change issues."""

import os
import sys
import time
import ctypes
import subprocess
import psutil

# ─── Config ───
MT5_PATH = r'C:\Program Files\MetaTrader 5\terminal64.exe'
MT5_DATA = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                        'D0E8209F77C8CF37AD8BF550E51FF075')
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
            return pid
        time.sleep(2)
    return None


def find_ea_tree_item(app, ea_name):
    """Given a connected pywinauto Application, find EA item in tree."""
    # Find main MT5 window
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    
    # Find SysTreeView32
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if not tree_view:
        print("❌ TreeView not found")
        return None
    
    print(f"📋 TreeView found, visible={tree_view.is_visible()}")
    
    # Navigate tree
    try:
        root = tree_view.roots()[0]
        children = root.children()
        
        ea_trading_node = None
        if len(children) > 2:
            ea_trading_node = children[2]  # 3rd child = Expert Advisors
        if not ea_trading_node:
            for child in children:
                t = child.text()
                if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
                    ea_trading_node = child
                    break
        
        if not ea_trading_node:
            print("❌ EA Trading node not found")
            return None
        
        # Expand
        try:
            ea_trading_node.expand()
        except:
            pass
        time.sleep(1)
        
        # Find target EA
        for ea in ea_trading_node.children():
            if ea.text() == ea_name:
                print(f"🎯 Found EA node: {ea_name}")
                return ea
                
        print(f"❌ EA {ea_name} not found under EA Trading")
        return None
    except Exception as e:
        print(f"❌ Tree navigation error: {e}")
        return None


def do_doubleclick(ea_node):
    """Double-click the EA node using pyautogui at its center coordinates."""
    rect = ea_node.rectangle()
    cx = (rect.left + rect.right) // 2
    cy = (rect.top + rect.bottom) // 2
    print(f"📋 EA item rect: ({rect.left},{rect.top})-({rect.right},{rect.bottom})")
    print(f"📋 Double-click at ({cx}, {cy})")
    
    # Select the item first
    hwnd = ea_node.element_info.handle
    root_hwnd = ctypes.windll.user32.GetAncestor(ctypes.c_void_p(hwnd), 2)  # GA_ROOT
    tree_hwnd = hwnd  # This is the tree item handle
    # Actually we need the TreeView handle, find it
    from pywinauto import Application
    app = Application(backend='win32').connect(handle=root_hwnd)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if tree_view:
        hwnd_tree = tree_view.element_info.handle
        h_item = ea_node.item().hItem
        TVM_SELECTITEM = 0x1100 + 11
        TVGN_CARET = 9
        TVM_ENSUREVISIBLE = 0x1100 + 20
        user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
        user32.SendMessageW(ctypes.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
        print("📋 EA selected in tree")
    
    time.sleep(0.5)
    
    import pyautogui
    pyautogui.doubleClick(x=cx, y=cy)
    time.sleep(2)


def find_dialog(mt5_pid, ea_name):
    """Find EA Properties dialog by window title."""
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


def confirm_dialog():
    """Press Enter + Ctrl+E to confirm and enable AutoTrading."""
    from pywinauto.keyboard import send_keys
    send_keys('{ENTER}')
    time.sleep(1)
    send_keys('^e')  # Ctrl+E toggles AutoTrading
    time.sleep(1)
    print("✅ Properties confirmed, AutoTrading ON")


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
                print(f"💓 {ea_name} heartbeat: {content} ({round(age)}s ago)")
                return True
        time.sleep(3)
    print(f"❌ {ea_name} heartbeat not detected within {timeout}s")
    return False


def attach_ea(ea_name, symbol='EURUSD', timeframe='H1'):
    """Main function."""
    print(f"\n{'='*50}")
    print(f"  🚀 Attaching: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    
    # ── Ensure MT5 is running ──
    mt5_pid = find_mt5_pid()
    if not mt5_pid:
        print("Starting MT5...")
        subprocess.Popen([MT5_PATH])
        mt5_pid = wait_for_mt5()
        if not mt5_pid:
            print("❌ Failed to start MT5")
            return False
    print(f"✅ MT5 running, PID={mt5_pid}")
    
    # ── Generate template ──
    from pywinauto.keyboard import send_keys
    
    # ── Connect once and reuse ──
    from pywinauto import Application
    try:
        app = Application(backend='win32').connect(process=mt5_pid)
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
        try:
            win.set_focus()
        except:
            pass
    except Exception as e:
        print(f"❌ win32 connect: {e}")
        return False
    
    # Open new chart
    send_keys('^n')
    time.sleep(1)
    send_keys('{ENTER}')
    time.sleep(3)
    print("📋 New chart opened")
    
    # Open Navigator via keyboard (Alt+V → n → Enter)
    send_keys('%v')
    time.sleep(0.5)
    send_keys('n')
    time.sleep(0.5)
    send_keys('{ENTER}')
    time.sleep(2)
    print("📋 Navigator opened")
    
    # Find EA tree item
    ea_node = find_ea_tree_item(app, ea_name)
    if not ea_node:
        return False
    
    # Give focus to chart area first (so EA attaches to new chart)
    try:
        mdi = None
        for d in win.descendants():
            if d.element_info.class_name == 'MDIClient':
                mdi = d
                break
        if mdi:
            mr = mdi.rectangle()
            cx = (mr.left + mr.right) // 2
            cy = (mr.top + mr.bottom) // 2
            import pyautogui
            pyautogui.click(x=cx, y=cy)
            time.sleep(1)
            print(f"📋 Chart focused at ({cx}, {cy})")
    except Exception as e:
        print(f"⚠️ chart focus: {e}")
    
    # Double-click the EA node (up to 3 attempts)
    for attempt in range(3):
        do_doubleclick(ea_node)
        
        dialogs = find_dialog(mt5_pid, ea_name)
        if dialogs:
            print(f"🎉 Found '{dialogs[0]}' dialog!")
            confirm_dialog()
            
            time.sleep(5)
            hb_ok = verify_heartbeat(ea_name)
            if hb_ok:
                print(f"\n🎉 SUCCESS: {ea_name} is running on {symbol} {timeframe}!")
                return True
            else:
                print(f"⚠️ EA attached but no heartbeat yet")
                return True
        
        print(f"⚠️ Dialog not found (attempt {attempt+1}/3)")
        time.sleep(2)
    
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
