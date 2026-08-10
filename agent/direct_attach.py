"""
Direct EA Attach — finds EA in TreeView via pywinauto, then positions via TVM_HITTEST,
double-clicks with pyautogui at the exact position. No scanning needed.
"""
import ctypes, ctypes.wintypes, time, os, sys, psutil
from pywinauto import Application
from pywinauto.keyboard import send_keys
import pyautogui

user32 = ctypes.windll.user32

# TVM messages
TVM_EXPAND = 0x1102
TVM_SELECTITEM = 0x110B
TVM_GETNEXTITEM = 0x110A
TVM_ENSUREVISIBLE = 0x1114
TVM_HITTEST = 0x1111
TVM_GETITEM = 0x110C
TVGN_ROOT = 0
TVGN_NEXT = 1
TVGN_CHILD = 4
TVGN_CARET = 9
TVE_EXPAND = 1
TVIF_TEXT = 0x0001
TVIF_HANDLE = 0x0010

class TVITEM(ctypes.Structure):
    _fields_ = [
        ('mask', ctypes.c_uint), ('hItem', ctypes.c_size_t),
        ('state', ctypes.c_uint), ('stateMask', ctypes.c_uint),
        ('pszText', ctypes.c_size_t), ('cchTextMax', ctypes.c_int),
        ('iImage', ctypes.c_int), ('iSelectedImage', ctypes.c_int),
        ('cChildren', ctypes.c_int), ('lParam', ctypes.c_size_t),
    ]

class TVHITTESTINFO(ctypes.Structure):
    _fields_ = [
        ('pt_x', ctypes.c_long), ('pt_y', ctypes.c_long),
        ('flags', ctypes.c_uint), ('hItem', ctypes.c_size_t),
    ]

WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

def find_dialog(ea_name, pid, timeout=5):
    """Find EA Properties dialog by class and title"""
    start = time.time()
    while time.time() - start < timeout:
        results = []
        def cb(hwnd, _):
            buf = ctypes.create_unicode_buffer(512)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, 512)
                if ea_name in buf.value:
                    results.append(hwnd)
            return 1
        user32.EnumWindows(WNDENUMPROC(cb), 0)
        if results:
            return results[0]
        time.sleep(0.3)
    return None

def deploy_ea(ea_name, symbol='EURUSD', tf='H1'):
    pid = None
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            pid = proc.info['pid']
            break
    if not pid:
        print("MT5 not running!")
        return False
    
    print(f"MT5 PID: {pid}")
    
    app = Application(backend='win32').connect(process=pid)
    win = app.window(class_name='MetaQuotes::MetaTrader::5.00')
    
    # Find TreeView
    tree_view = None
    for d in win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
    
    if not tree_view:
        print("No TreeView!")
        return False
    
    tv_hwnd = tree_view.element_info.handle
    tr = tree_view.rectangle()
    print(f"TreeView: ({tr.left},{tr.top})-({tr.right},{tr.bottom})")
    
    # Navigate to EA section
    root = tree_view.roots()[0]
    ea_section = root.children()[2]
    print(f"EA section: {ea_section.text()!r}")
    ea_section.expand()
    time.sleep(1)
    
    # Find our EA
    target = None
    for child in ea_section.children():
        if child.text().strip() == ea_name:
            target = child
            break
    
    if not target:
        print(f"{ea_name} not found!")
        return False
    
    h_item = target.item().hItem
    print(f"Found {ea_name}, hItem={h_item}")
    
    # Select and ensure visible
    user32.SendMessageW(ctypes.c_void_p(tv_hwnd), TVM_SELECTITEM, TVGN_CARET, ctypes.c_size_t(h_item))
    time.sleep(0.3)
    user32.SendMessageW(ctypes.c_void_p(tv_hwnd), TVM_ENSUREVISIBLE, 0, ctypes.c_size_t(h_item))
    time.sleep(0.5)
    
    # Find position using HITTEST
    found_pos = None
    for y_step in range(0, tr.bottom - tr.top, 18):
        test_y = tr.top + y_step + 9
        test_x = tr.left + 25
        
        pt = (ctypes.c_long * 2)(test_x, test_y)
        user32.ScreenToClient(ctypes.c_void_p(tv_hwnd), ctypes.byref(pt))
        
        hi = TVHITTESTINFO()
        hi.pt_x = pt[0]
        hi.pt_y = pt[1]
        
        h_hit = user32.SendMessageW(ctypes.c_void_p(tv_hwnd), TVM_HITTEST, 0, ctypes.byref(hi))
        if h_hit and ctypes.c_size_t(h_hit).value == ctypes.c_size_t(h_item).value:
            found_pos = (test_x, test_y)
            print(f"HITTEST found at ({test_x}, {test_y})")
            break
    
    if not found_pos:
        print("HITTEST didn't find position, using estimate")
        # Estimate position based on EA index in the section
        ea_list = list(ea_section.children())
        ea_idx = -1
        for i, ea in enumerate(ea_list):
            if ea.text().strip() == ea_name:
                ea_idx = i
                break
        est_y = tr.top + 60 + ea_idx * 18 + 9
        est_x = tr.left + 35
        found_pos = (est_x, est_y)
        print(f"Estimated: ({est_x}, {est_y})")
    
    # Click on chart first (to give it focus)
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
            pyautogui.click(x=cx, y=cy)
            time.sleep(0.5)
    except:
        pass
    
    # Double-click at the EA position
    click_x, click_y = found_pos
    print(f"Double-clicking at ({click_x}, {click_y})...")
    pyautogui.doubleClick(x=click_x, y=click_y)
    time.sleep(3)
    
    # Check for dialog
    dlg = find_dialog(ea_name, pid, timeout=5)
    if dlg:
        print(f"Dialog found! HWND={dlg}")
        send_keys('{ENTER}')
        time.sleep(1)
        send_keys('^e')
        time.sleep(1)
        print(f"✅ {ea_name} deployed successfully!")
        
        # Log
        log_path = os.path.join(os.path.dirname(__file__), 'auto_attach_log.txt')
        with open(log_path, 'a', encoding='utf-8') as f:
            ts = time.strftime('%Y-%m-%d %H:%M:%S')
            f.write(f'[{ts}] SUCCESS: {ea_name} attached to {symbol} {tf}\n')
        return True
    
    print(f"No dialog found for {ea_name}")
    return False

if __name__ == '__main__':
    ea = sys.argv[1] if len(sys.argv) > 1 else 'Breakout'
    sys.exit(0 if deploy_ea(ea) else 1)
