"""Direct Win32 API EA attachment — no pyautogui scan needed.
Sends WM_LBUTTONDBLCLK directly to the tree item's bounding rect."""

import os
import sys
import time
import ctypes
import struct
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


def find_ea_item(mt5_pid, ea_name):
    """Find the SysTreeView32 and locate the EA node."""
    from pywinauto import Application
    
    app = Application(backend='win32').connect(process=mt5_pid)
    
    # Find main window
    win = None
    for w in app.windows():
        cls = w.element_info.class_name
        if 'MetaTrader' in cls:
            win = w
            break
    
    if not win:
        print("❌ MT5 main window not found")
        return None, None
    
    # Find TreeView
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if not tree_view:
        print("❌ TreeView not found")
        return None, None
    
    hwnd_tree = tree_view.element_info.handle
    
    # Navigate to EA node
    root = tree_view.roots()[0]
    children = root.children()
    
    if len(children) > 2:
        ea_trading_node = children[2]
    else:
        # Try text matching
        ea_trading_node = None
        for child in children:
            t = child.text()
            if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
                ea_trading_node = child
                break
        if not ea_trading_node:
            print("❌ EA Trading node not found")
            return None, None
    
    # Expand if not already
    try:
        ea_trading_node.expand()
    except:
        pass
    time.sleep(1)
    
    # Find our EA
    for ea in ea_trading_node.children():
        if ea.text() == ea_name:
            print(f"🎯 Found EA node: {ea_name}")
            h_item = ea.item().hItem
            return hwnd_tree, h_item
    
    print(f"❌ EA {ea_name} not found in Navigator")
    return None, None


def send_doubleclick_win32(hwnd_tree, h_item):
    """Send WM_LBUTTONDBLCLK directly to the tree item area."""
    import ctypes as _ct
    
    # First select and ensure visible
    TVM_SELECTITEM = 0x1100 + 11  # TV_FIRST + 11
    TVGN_CARET = 9
    TVM_ENSUREVISIBLE = 0x1100 + 20  # TV_FIRST + 20
    
    user32.SendMessageW(_ct.c_void_p(hwnd_tree), TVM_SELECTITEM, TVGN_CARET, _ct.c_size_t(h_item))
    user32.SendMessageW(_ct.c_void_p(hwnd_tree), TVM_ENSUREVISIBLE, 0, _ct.c_size_t(h_item))
    time.sleep(0.5)
    
    # Get tree item rect using TVM_GETITEMRECT
    TVM_GETITEMRECT = 0x1100 + 4  # TV_FIRST + 4
    
    # TVM_GETITEMRECT: lParam = POINT to RECT, left must be set to hItem before call
    # Use a RECT structure: (left, top, right, bottom) as 4 c_longs
    RECT = _ct.c_long * 4
    rect = RECT(h_item, 0, 0, 0)  # left = hItem (input), top/right/bottom = 0
    
    result = user32.SendMessageW(
        _ct.c_void_p(hwnd_tree),
        TVM_GETITEMRECT,
        0,  # FALSE = get text rect
        _ct.c_size_t(_ct.addressof(rect))
    )
    
    if result:
        item_rect = (rect[0], rect[1], rect[2], rect[3])
        print(f"📋 Item text rect: ({item_rect[0]},{item_rect[1]})-({item_rect[2]},{item_rect[3]})")
    else:
        # Try with wParam=1 (bounding rect)
        rect2 = RECT(h_item, 0, 0, 0)
        result2 = user32.SendMessageW(
            _ct.c_void_p(hwnd_tree),
            TVM_GETITEMRECT,
            1,
            _ct.c_size_t(_ct.addressof(rect2))
        )
        if result2:
            item_rect = (rect2[0], rect2[1], rect2[2], rect2[3])
            print(f"📋 Item bounding rect: ({item_rect[0]},{item_rect[1]})-({item_rect[2]},{item_rect[3]})")
        else:
            print("⚠️ TVM_GETITEMRECT failed, asking pywinauto for item rect")
            # Use pywinauto's rectangle() method which works
            return _fallback_doubleclick(hwnd_tree, h_item)
    
    # Calculate center of item
    center_x = (item_rect[0] + item_rect[2]) // 2
    center_y = (item_rect[1] + item_rect[3]) // 2
    
    print(f"📋 Double-click at ({center_x}, {center_y})")
    
    # These are client coordinates already (TVM_GETITEMRECT returns client coords)
    client_x, client_y = center_x, center_y
    
    # Send WM_LBUTTONDBLCLK directly to TreeView
    WM_LBUTTONDBLCLK = 0x0203
    WM_LBUTTONUP = 0x0202
    
    # Pack lParam with client coordinates
    lparam = (client_y << 16) | (client_x & 0xFFFF)
    
    # Send messages
    user32.SendMessageW(_ct.c_void_p(hwnd_tree), WM_LBUTTONDBLCLK, 1, lparam)
    time.sleep(0.2)
    user32.SendMessageW(_ct.c_void_p(hwnd_tree), WM_LBUTTONUP, 0, lparam)
    time.sleep(2)
    
    return True


def _fallback_doubleclick(hwnd_tree, h_item):
    """Fallback: use pywinauto + pyautogui with the item's known rectangle."""
    print("📋 Using pywinauto rectangle + pyautogui fallback...")
    import ctypes as _ct
    from pywinauto import Application
    
    # Re-find treeview
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            pid = proc.info['pid']
            break
    else:
        print("❌ MT5 not found")
        return False
    
    app = Application(backend='win32').connect(process=pid)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if not tree_view:
        print("❌ TreeView not found")
        return False
    
    # Find the EA node directly
    root = tree_view.roots()[0]
    children = root.children()
    ea_trading_node = children[2] if len(children) > 2 else None
    if not ea_trading_node:
        return False
    
    ea_trading_node.expand()
    time.sleep(1)
    
    target_ea = None
    for ea in ea_trading_node.children():
        if ea.item().hItem == h_item:
            target_ea = ea
            break
    
    if not target_ea:
        print("❌ EA node not found in fallback")
        return False
    
    # Get the item rectangle
    ea_rect = target_ea.rectangle()
    click_x = (ea_rect.left + ea_rect.right) // 2
    click_y = (ea_rect.top + ea_rect.bottom) // 2
    print(f"📋 pywinauto item rect: ({ea_rect.left},{ea_rect.top})-({ea_rect.right},{ea_rect.bottom})")
    print(f"📋 Click at ({click_x}, {click_y})")
    
    import pyautogui
    pyautogui.doubleClick(x=click_x, y=click_y)
    time.sleep(2)
    return True


def find_dialog_window(mt5_pid, ea_name):
    """Check if EA Properties dialog opened."""
    pid_buf = ctypes.c_ulong()
    results = []
    
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
    
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    user32.EnumWindows(CB(_cb), 0)
    return results


def confirm_dialog():
    """Press Enter to confirm EA Properties dialog and toggle AutoTrading ON."""
    from pywinauto.keyboard import send_keys
    send_keys('{ENTER}')
    time.sleep(1)
    send_keys('^e')
    time.sleep(1)
    print("✅ AutoTrading toggled ON")
    return True


def verify_heartbeat(ea_name, timeout=90):
    """Verify heartbeat file appears within timeout."""
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
    """Main attach function."""
    print(f"\n{'='*50}")
    print(f"  🚀 Attaching: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*50}")
    
    # Ensure MT5 is running
    mt5_pid = find_mt5_pid()
    if not mt5_pid:
        print("MT5 not running, starting...")
        subprocess.Popen([MT5_PATH])
        time.sleep(15)
        mt5_pid = find_mt5_pid()
        if not mt5_pid:
            print("❌ Failed to start MT5")
            return False
    
    print(f"✅ MT5 running, PID={mt5_pid}")
    
    # Set focus to MT5
    try:
        from pywinauto import Application
        app = Application(backend='win32').connect(process=mt5_pid)
        win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
        try:
            win.set_focus()
        except:
            pass
    except Exception as e:
        print(f"⚠️ win32 connect: {e}")
    
    time.sleep(1)
    
    # Step 1: Open new chart
    from pywinauto.keyboard import send_keys
    send_keys('^n')
    time.sleep(1)
    send_keys('{ENTER}')
    time.sleep(3)
    print("📋 New chart opened")
    
    # Step 2: Show Navigator panel
    # Alt+V → n → Enter (View menu → Navigator)
    send_keys('%v')
    time.sleep(0.5)
    send_keys('n')
    time.sleep(0.5)
    send_keys('{ENTER}')
    time.sleep(2)
    print("📋 Navigator opened")
    
    # Step 3: Find EA tree item
    hwnd_tree, h_item = find_ea_item(mt5_pid, ea_name)
    if not hwnd_tree or not h_item:
        return False
    
    # Step 4: Focus chart area first (so EA attaches to it)
    try:
        from pywinauto import Application as App2
        app2 = App2(backend='win32').connect(process=mt5_pid)
        win2 = app2.window(class_name='MetaQuotes::MetaTrader::5.00')
        for d in win2.descendants():
            if d.element_info.class_name == 'MDIClient':
                mr = d.rectangle()
                cx = (mr.left + mr.right) // 2
                cy = (mr.top + mr.bottom) // 2
                import pyautogui
                pyautogui.click(x=cx, y=cy)
                time.sleep(1)
                print(f"📋 Chart focused at ({cx}, {cy})")
                break
    except Exception as e:
        print(f"⚠️ Chart focus: {e}")
    
    # Step 5: Send double-click to tree item (up to 3 attempts)
    for attempt in range(3):
        send_doubleclick_win32(hwnd_tree, h_item)
        
        # Check for dialog
        dialogs = find_dialog_window(mt5_pid, ea_name)
        if dialogs:
            print(f"🎉 Found '{dialogs[0]}' dialog!")
            confirm_dialog()
            
            # Verify
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
