"""
Fixed EA attach script - uses only win32 API messages, no pyautogui.
Call: python win32_attach.py <EA_NAME>
"""
import ctypes, ctypes.wintypes, time, os, sys, struct

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
user32 = ctypes.windll.user32

# Configure argtypes for 64-bit
user32.SendMessageW.argtypes = [ctypes.c_size_t, ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
user32.SendMessageW.restype = ctypes.c_size_t
user32.PostMessageW.argtypes = [ctypes.c_size_t, ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t]
user32.PostMessageW.restype = ctypes.c_bool
user32.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
user32.EnumChildWindows.argtypes = [ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
user32.GetClassNameW.argtypes = [ctypes.c_size_t, ctypes.c_wchar_p, ctypes.c_int]
user32.GetWindowTextW.argtypes = [ctypes.c_size_t, ctypes.c_wchar_p, ctypes.c_int]
user32.IsWindowVisible.argtypes = [ctypes.c_size_t]
user32.IsWindowVisible.restype = ctypes.c_bool
user32.ShowWindow.argtypes = [ctypes.c_size_t, ctypes.c_int]
user32.GetWindowRect.argtypes = [ctypes.c_size_t, ctypes.POINTER(ctypes.wintypes.RECT)]
user32.ClientToScreen.argtypes = [ctypes.c_size_t, ctypes.POINTER(ctypes.wintypes.POINT)]
user32.ScreenToClient.argtypes = [ctypes.c_size_t, ctypes.POINTER(ctypes.wintypes.POINT)]
user32.SetForegroundWindow.argtypes = [ctypes.c_size_t]
user32.SetForegroundWindow.restype = ctypes.c_bool
user32.BringWindowToTop.argtypes = [ctypes.c_size_t]
user32.BringWindowToTop.restype = ctypes.c_bool
user32.SetFocus.argtypes = [ctypes.c_size_t]
user32.SetFocus.restype = ctypes.c_size_t
user32.IsWindow.argtypes = [ctypes.c_size_t]
user32.IsWindow.restype = ctypes.c_bool

# TVM constants
TVM_EXPAND = 0x1102
TVM_SELECTITEM = 0x110B
TVM_GETNEXTITEM = 0x110A
TVM_ENSUREVISIBLE = 0x1114
TVM_GETITEMRECT = 0x1104
TVM_GETITEM = 0x110C
TVM_GETCOUNT = 0x1105

TVGN_ROOT = 0
TVGN_NEXT = 1
TVGN_CHILD = 4
TVGN_CARET = 9
TVE_EXPAND = 1
TVE_COLLAPSE = 2

TVIF_TEXT = 0x0001
TVIF_HANDLE = 0x0010
TVIF_CHILDREN = 0x0040

class TVITEM(ctypes.Structure):
    _fields_ = [
        ('mask', ctypes.c_uint),
        ('hItem', ctypes.c_size_t),
        ('state', ctypes.c_uint),
        ('stateMask', ctypes.c_uint),
        ('pszText', ctypes.c_size_t),
        ('cchTextMax', ctypes.c_int),
        ('iImage', ctypes.c_int),
        ('iSelectedImage', ctypes.c_int),
        ('cChildren', ctypes.c_int),
        ('lParam', ctypes.c_size_t),
    ]

# Configuration
MT5_DATA = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                         'D0E8209F77C8CF37AD8BF550E51FF075')
COMMON_FILES = os.path.join(os.environ.get('APPDATA', ''), 'MetaQuotes', 'Terminal',
                            'Common', 'Files')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')

TF_CODES = {
    'M1': 16385, 'M5': 16389, 'M15': 16401, 'M30': 16416,
    'H1': 32801, 'H4': 32805, 'D1': 49201, 'W1': 65601, 'MN1': 82001,
}

def gen_template(ea_name, symbol='EURUSD', timeframe='H1', inputs=None):
    """Generate .tpl template with EA settings"""
    if inputs is None:
        inputs = {'LotSize': '1.00', 'MagicNumber': '240701', 'EnableLog': 'true'}
    tf_code = TF_CODES.get(timeframe, 32801)
    os.makedirs(TPL_DIR, exist_ok=True)
    tpl_name = f'{ea_name}_{symbol}_{timeframe}.tpl'
    tpl_path = os.path.join(TPL_DIR, tpl_name)
    
    with open(tpl_path, 'w', encoding='utf-8') as f:
        f.write('//--- template for Expert Advisor\n')
        f.write('<chart>\n')
        f.write(f'  < Expert name="{ea_name}" >\n')
        for k, v in inputs.items():
            f.write(f'    <input name="{k}" value="{v}" />\n')
        f.write(f'  </ Expert>\n')
        f.write(f'  <window name="EURUSD">\n')
        f.write(f'    <Expert>\n')
        f.write(f'      <name>{ea_name}</name>\n')
        f.write(f'      <period_size>{tf_code}</period_size>\n')
        f.write(f'      <symbol>{symbol}</symbol>\n')
        f.write(f'      <MagicNumber>{inputs.get("MagicNumber", "240701")}</MagicNumber>\n')
        f.write(f'    </Expert>\n')
        f.write(f'  </window>\n')
        f.write('</chart>\n')
    print(f'📋 Template saved: {tpl_path}')
    return tpl_path

def find_mt5_window():
    mt5_hwnd = [None]
    def cb(hwnd, lparam):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if 'MetaQuotes::MetaTrader' in buf.value and user32.IsWindowVisible(hwnd):
            mt5_hwnd[0] = hwnd
        return 1
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return mt5_hwnd[0]

def enum_descendants(parent, cls_filter=None, title_filter=None):
    """Get descendant windows matching criteria"""
    results = []
    def cb(hwnd, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        if cls_filter is None or cls_filter in cls_buf.value:
            if title_filter:
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, buf, 256)
                if title_filter not in buf.value:
                    return 1
            results.append(hwnd)
        return 1
    user32.EnumChildWindows(parent, WNDENUMPROC(cb), 0)
    return results

def send_tvm(tv_hwnd, msg, wparam=0, lparam=0):
    """Safe wrapper for SendMessage to TreeView"""
    return user32.SendMessageW(tv_hwnd, msg, wparam, lparam)

def get_item_text(tv_hwnd, h_item):
    buf = ctypes.create_unicode_buffer(512)
    item = TVITEM()
    item.mask = TVIF_HANDLE | TVIF_TEXT | TVIF_CHILDREN
    item.hItem = h_item
    item.pszText = ctypes.addressof(buf)
    item.cchTextMax = 512
    result = send_tvm(tv_hwnd, TVM_GETITEM, 0, ctypes.addressof(item))
    if not result:
        return "", 0
    return buf.value, item.cChildren

def show_navigator(mt5_hwnd):
    """Force show the Navigator panel"""
    # Find Navigator control bar
    nav_bars = []
    def cb(hwnd, lparam):
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        if 'Afx:ControlBar' in cls_buf.value:
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            kw = ['導航', 'Navigator', '导航', 'ナビゲーター']
            if any(k in buf.value for k in kw):
                nav_bars.append(hwnd)
        return 1
    cb_func = WNDENUMPROC(cb)
    user32.EnumChildWindows(mt5_hwnd, cb_func, 0)
    
    if nav_bars:
        for nb in nav_bars:
            user32.ShowWindow(nb, 5)  # SW_SHOW
        time.sleep(0.5)
        return True
    else:
        # WM_COMMAND 32808 = View -> Navigator
        send_tvm(mt5_hwnd, 0x0111, 32808, 0)
        time.sleep(1.5)
        return True

def ensure_treeview_visible(tv_hwnd, mt5_hwnd):
    """Ensure the TreeView is actually visible and has size"""
    rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(tv_hwnd, rect)
    if rect.right - rect.left > 10 and rect.bottom - rect.top > 10:
        return True
    
    # TreeView is hidden, try to show its parent control bar
    parent = user32.GetParent(tv_hwnd)
    if parent:
        user32.ShowWindow(parent, 5)
        time.sleep(0.5)
        user32.GetWindowRect(tv_hwnd, rect)
        if rect.right - rect.left > 10:
            return True
    
    return False

def find_ea_in_tree(tv_hwnd, ea_name):
    """Navigate TreeView to find the EA item, returns (hItem, rect_in_screen_coords)"""
    root = send_tvm(tv_hwnd, TVM_GETNEXTITEM, TVGN_ROOT, 0)
    if not root:
        print("  No root in TreeView")
        return None
    
    root_text, _ = get_item_text(tv_hwnd, root)
    print(f"  Root: {root_text!r}")
    
    # Find EA section (usually 3rd child or search by name)
    ea_section = None
    child = send_tvm(tv_hwnd, TVM_GETNEXTITEM, TVGN_CHILD, root)
    idx = 0
    while child:
        text, _ = get_item_text(tv_hwnd, child)
        print(f"  [{idx}] {text!r}")
        if any(kw in text for kw in ['EA交易', 'Expert Advisors', 'المستشارون المختصون', 'Experts', 'EA']):
            ea_section = child
            break
        child = send_tvm(tv_hwnd, TVM_GETNEXTITEM, TVGN_NEXT, child)
        idx += 1
    
    if not ea_section:
        # Fallback: 3rd child (index 2)
        child = send_tvm(tv_hwnd, TVM_GETNEXTITEM, TVGN_CHILD, root)
        for _ in range(2):
            if child:
                child = send_tvm(tv_hwnd, TVM_GETNEXTITEM, TVGN_NEXT, child)
        if child:
            ea_section = child
            text, _ = get_item_text(tv_hwnd, child)
            print(f"  Using 3rd child: {text!r}")
    
    if not ea_section:
        print("  EA section not found!")
        return None
    
    # Expand EA section
    send_tvm(tv_hwnd, TVM_EXPAND, TVE_EXPAND, ea_section)
    time.sleep(1)
    
    # Find the specific EA
    ea_item = send_tvm(tv_hwnd, TVM_GETNEXTITEM, TVGN_CHILD, ea_section)
    while ea_item:
        text, _ = get_item_text(tv_hwnd, ea_item)
        if text.strip() == ea_name:
            print(f"  ✅ Found '{ea_name}'!")
            return ea_item
        ea_item = send_tvm(tv_hwnd, TVM_GETNEXTITEM, TVGN_NEXT, ea_item)
    
    print(f"  ❌ EA '{ea_name}' not found!")
    return None

def send_doubleclick_to_item(tv_hwnd, h_item):
    """Send double-click via window messages directly to the TreeView"""
    # Select the item first
    send_tvm(tv_hwnd, TVM_SELECTITEM, TVGN_CARET, h_item)
    time.sleep(0.3)
    
    # Ensure visible
    send_tvm(tv_hwnd, TVM_ENSUREVISIBLE, 0, h_item)
    time.sleep(0.5)
    
    # Get item rect in client coordinates
    rect = ctypes.wintypes.RECT()
    rect.left = h_item  # TVM_GETITEMRECT protocol: pass hItem in rect.left
    result = send_tvm(tv_hwnd, TVM_GETITEMRECT, 1, ctypes.addressof(rect))
    
    if not result:
        print("  TVM_GETITEMRECT failed, using TreeView center")
        tv_rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(tv_hwnd, tv_rect)
        click_x = (tv_rect.left + tv_rect.right) // 2
        click_y = (tv_rect.top + tv_rect.bottom) // 2
    else:
        # Convert client coords to screen
        pt = ctypes.wintypes.POINT(rect.left + 10, rect.top + (rect.bottom - rect.top) // 2)
        user32.ClientToScreen(tv_hwnd, ctypes.byref(pt))
        click_x, click_y = pt.x, pt.y
    
    print(f"  Double-click at ({click_x}, {click_y})")
    
    # Pack lParam with screen coordinates
    lparam = ((click_y & 0xFFFF) << 16) | (click_x & 0xFFFF)
    
    # Set foreground for the TreeView
    user32.SetForegroundWindow(tv_hwnd)
    time.sleep(0.2)
    
    # Send mouse messages
    # WM_LBUTTONDOWN = 0x0201
    # WM_LBUTTONDBLCLK = 0x0203
    # WM_LBUTTONUP = 0x0202
    user32.PostMessageW(tv_hwnd, 0x0201, 0x0001, lparam)  # DOWN
    time.sleep(0.05)
    user32.PostMessageW(tv_hwnd, 0x0203, 0x0001, lparam)  # DBLCLK
    time.sleep(0.05)
    user32.PostMessageW(tv_hwnd, 0x0202, 0x0000, lparam)  # UP
    time.sleep(0.5)
    
    return True

def check_dialog(ea_name, timeout=5):
    """Check for EA Properties dialog window"""
    start = time.time()
    while time.time() - start < timeout:
        results = []
        def cb(hwnd, lparam):
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            if cls_buf.value == '#32770':
                buf = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(hwnd, buf, 256)
                if ea_name in buf.value:
                    results.append(hwnd)
            return 1
        cb_func = WNDENUMPROC(cb)
        user32.EnumWindows(cb_func, 0)
        if results:
            print(f"  🎉 Properties dialog found! HWND={results[0]}")
            return results[0]
        time.sleep(0.3)
    return None

def confirm_dialog(dlg_hwnd):
    """Send Enter to confirm the dialog"""
    # Set focus to dialog
    user32.SetForegroundWindow(dlg_hwnd)
    time.sleep(0.3)
    
    # Find the OK/Default button
    def find_btn(hwnd):
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        if cls_buf.value == 'Button':
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if 'OK' in buf.value or '確定' in buf.value:
                # Get button rect
                btn_rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(hwnd, btn_rect)
                return hwnd, btn_rect
        return None
    
    # Try pressing Enter
    user32.PostMessageW(dlg_hwnd, 0x0100, 0x0D, 0)  # WM_KEYDOWN VK_RETURN
    time.sleep(0.2)
    user32.PostMessageW(dlg_hwnd, 0x0101, 0x0D, 0)  # WM_KEYUP
    time.sleep(1)
    print("  ✅ Dialog confirmed with Enter")

def toggle_autotrading(mt5_hwnd):
    """Toggle AutoTrading ON using Ctrl+E"""
    user32.SetForegroundWindow(mt5_hwnd)
    time.sleep(0.3)
    # Ctrl+E via PostMessage
    user32.PostMessageW(mt5_hwnd, 0x0100, 0x11, 0x40000000)  # WM_KEYDOWN CTRL
    user32.PostMessageW(mt5_hwnd, 0x0100, 0x45, 0)           # WM_KEYDOWN E
    time.sleep(0.1)
    user32.PostMessageW(mt5_hwnd, 0x0101, 0x45, 0)           # WM_KEYUP E
    user32.PostMessageW(mt5_hwnd, 0x0101, 0x11, 0xC0000000)  # WM_KEYUP CTRL
    time.sleep(1)
    print("  AutoTrading toggled (Ctrl+E)")

def check_heartbeat(ea_name):
    """Quick check if heartbeat exists"""
    hb_file = os.path.join(COMMON_FILES, f'hb_{ea_name}.txt')
    if os.path.exists(hb_file):
        mtime = os.path.getmtime(hb_file)
        age = time.time() - mtime
        print(f"  💓 Heartbeat: {age:.0f}s old")
        return age < 300
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: win32_attach.py <EA_NAME> [symbol] [tf]")
        return 1
    
    ea_name = sys.argv[1]
    symbol = sys.argv[2] if len(sys.argv) > 2 else 'EURUSD'
    timeframe = sys.argv[3] if len(sys.argv) > 3 else 'H1'
    
    print(f"\n{'='*55}")
    print(f"  🚀 Win32 Attach: {ea_name} → {symbol} {timeframe}")
    print(f"{'='*55}")
    
    # Step 1: Generate template
    gen_template(ea_name, symbol, timeframe)
    
    # Step 2: Find MT5 window
    mt5_hwnd = find_mt5_window()
    if not mt5_hwnd:
        print("❌ MT5 window not found!")
        return 1
    print(f"📌 MT5 HWND: {mt5_hwnd}")
    
    # Step 3: Bring MT5 to top
    user32.SetForegroundWindow(mt5_hwnd)
    user32.BringWindowToTop(mt5_hwnd)
    time.sleep(0.5)
    
    # Step 4: Show Navigator
    show_navigator(mt5_hwnd)
    time.sleep(1)
    
    # Step 5: Find TreeView
    tvs = enum_descendants(mt5_hwnd, cls_filter='SysTreeView32')
    if not tvs:
        print("❌ No TreeView found!")
        return 1
    tv_hwnd = tvs[0]
    print(f"📌 TreeView HWND: {tv_hwnd}")
    
    # Step 6: Ensure TreeView is visible
    ensure_treeview_visible(tv_hwnd, mt5_hwnd)
    
    # Step 7: Find EA in TreeView
    ea_item = find_ea_in_tree(tv_hwnd, ea_name)
    if not ea_item:
        print(f"❌ Could not find {ea_name} in Navigator!")
        return 1
    
    # Step 8: Double-click on EA item
    send_doubleclick_to_item(tv_hwnd, ea_item)
    time.sleep(2)
    
    # Step 9: Check for dialog
    dlg = check_dialog(ea_name, timeout=5)
    if dlg:
        confirm_dialog(dlg)
        time.sleep(1)
        toggle_autotrading(mt5_hwnd)
        time.sleep(2)
        
        # Check heartbeat
        hb = check_heartbeat(ea_name)
        if hb:
            print(f"\n🎉 SUCCESS: {ea_name} is running on {symbol} {timeframe}!")
            
            # Log success
            log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')
            with open(log_path, 'a', encoding='utf-8') as f:
                ts = time.strftime('%Y-%m-%d %H:%M:%S')
                f.write(f'[{ts}] SUCCESS: {ea_name} attached to {symbol} {timeframe}\n')
            return 0
        else:
            print(f"\n⚠️ {ea_name} dialog confirmed but no heartbeat yet")
            return 0
    else:
        print(f"⚠️ {ea_name} dialog not found via window messages")
        
        # Fallback: try the old auto_attach.py's pyautogui scan approach
        print("Falling back to scan approach...")
        tv_rect = ctypes.wintypes.RECT()
        user32.GetWindowRect(tv_hwnd, tv_rect)
        click_x = tv_rect.left + 50
        row_height = 18
        
        for y_step in range(0, tv_rect.bottom - tv_rect.top, row_height):
            click_y = tv_rect.top + y_step + 9
            lparam = ((click_y & 0xFFFF) << 16) | (click_x & 0xFFFF)
            
            user32.PostMessageW(tv_hwnd, 0x0201, 0x0001, lparam)
            time.sleep(0.05)
            user32.PostMessageW(tv_hwnd, 0x0203, 0x0001, lparam)
            time.sleep(0.05)
            user32.PostMessageW(tv_hwnd, 0x0202, 0x0000, lparam)
            time.sleep(1)
            
            dlg = check_dialog(ea_name, timeout=2)
            if dlg:
                confirm_dialog(dlg)
                toggle_autotrading(mt5_hwnd)
                print(f"\n🎉 SUCCESS: {ea_name} attached via scan!")
                log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'auto_attach_log.txt')
                with open(log_path, 'a', encoding='utf-8') as f:
                    ts = time.strftime('%Y-%m-%d %H:%M:%S')
                    f.write(f'[{ts}] SUCCESS: {ea_name} attached to {symbol} {timeframe}\n')
                return 0
        
        print(f"❌ {ea_name} attach failed after full scan")
        return 1

if __name__ == '__main__':
    sys.exit(main())
