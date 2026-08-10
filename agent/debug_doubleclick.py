"""Debug Navigator interaction: find EA item and try to open it."""
import os, sys, time, ctypes
import pyautogui
from pywinauto import Application
from pywinauto.keyboard import send_keys

user32 = ctypes.windll.user32

MT5_CLASS = 'MetaQuotes::MetaTrader::5.00'

def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

mt5_pid = get_mt5_pid()
main_hwnd = user32.FindWindowW(MT5_CLASS, None)
print(f"MT5 HWND={main_hwnd:08X} PID={mt5_pid}")
print(f"Screen size: {pyautogui.size()}")

# Ensure Navigator is visible
# Send WM_COMMAND 32808 to toggle Navigator
user32.SendMessageW(ctypes.c_void_p(main_hwnd), 0x0111, 32808, 0)
time.sleep(2)

# Bring MT5 to foreground
user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
time.sleep(1)

app = Application(backend='win32').connect(process=mt5_pid)

# Find TreeView
tree_view = None
try:
    main_win = app.window(class_name=MT5_CLASS)
    for d in main_win.descendants():
        if d.element_info.class_name == 'SysTreeView32':
            tree_view = d
            break
except:
    pass

if not tree_view:
    # Try top_window approach
    for w in [app.top_window()]:
        try:
            for d in w.descendants():
                if d.element_info.class_name == 'SysTreeView32':
                    tree_view = d
                    break
        except:
            pass

if not tree_view:
    print("❌ TreeView not found")
    exit(1)

print(f"✅ TreeView found: visible={tree_view.is_visible()}")
tv_rect = tree_view.rectangle()
print(f"   rect=({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})")

# Navigate to EA node
try:
    root = tree_view.roots()[0]
    children = root.children()
    print(f"Root children: {len(children)}")
    for i, child in enumerate(children):
        try:
            t = child.text()
            print(f"  [{i}] '{t}'")
        except:
            print(f"  [{i}] <error>")
    
    # Find EA Trading node (3rd child or by text)
    ea_trading = None
    for child in children:
        try:
            t = child.text()
            if any(kw in t for kw in ['EA交易', 'Expert Advisors', 'Experts', 'EA']):
                ea_trading = child
                print(f"✅ Found EA trading node: '{t}'")
                break
        except:
            pass
    
    if not ea_trading and len(children) > 2:
        ea_trading = children[2]
        print(f"✅ Using 3rd child as EA trading: '{ea_trading.text()}'")
    
    if ea_trading:
        ea_trading.expand()
        time.sleep(2)
        
        # Find our target EA
        ea_items = ea_trading.children()
        print(f"EA items: {len(ea_items)}")
        for item in ea_items:
            try:
                print(f"  - '{item.text()}'")
            except:
                print(f"  - <error>")
        
        # Find ADX_Trend
        target_ea = None
        for item in ea_items:
            try:
                if item.text() == 'ADX_Trend':
                    target_ea = item
                    break
            except:
                pass
        
        if target_ea:
            print(f"✅ Found target EA: ADX_Trend")
            
            # Select and ensure visible
            import ctypes as _ct
            _user32 = _ct.windll.user32
            _tree_hwnd = tree_view.element_info.handle
            _h_item = target_ea.item().hItem
            _TVM_SELECTITEM = 0x1100 + 11
            _TVGN_CARET = 9
            _TVM_ENSUREVISIBLE = 0x1100 + 20
            _user32.SendMessageW(_ct.c_void_p(_tree_hwnd), _TVM_SELECTITEM, _TVGN_CARET, _ct.c_size_t(_h_item))
            _user32.SendMessageW(_ct.c_void_p(_tree_hwnd), _TVM_ENSUREVISIBLE, 0, _ct.c_size_t(_h_item))
            time.sleep(1)
            
            # Get item rect
            try:
                item_rect = target_ea.client_rect()
                print(f"Item client_rect: L={item_rect.left}, T={item_rect.top}, R={item_rect.right}, B={item_rect.bottom}")
                
                # Convert to screen coords
                screen_x = tv_rect.left + (item_rect.left + item_rect.right) // 2
                screen_y = tv_rect.top + (item_rect.top + item_rect.bottom) // 2
                print(f"Screen coords: ({screen_x}, {screen_y})")
                
                # Also try a few pixels down
                for y_offset in [0, 5, 10, -5]:
                    test_y = screen_y + y_offset
                    print(f"\n--- Trying double-click at ({screen_x}, {test_y}) offset={y_offset} ---")
                    
                    pyautogui.doubleClick(x=screen_x, y=test_y)
                    time.sleep(3)
                    
                    # Check for dialog
                    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
                    pid_buf = _ct.c_ulong()
                    dialogs = []
                    def find_dlg(hwnd, _):
                        user32.GetWindowThreadProcessId(_ct.c_void_p(hwnd), _ct.byref(pid_buf))
                        if pid_buf.value == mt5_pid:
                            cls = _ct.create_unicode_buffer(256)
                            user32.GetClassNameW(_ct.c_void_p(hwnd), cls, 256)
                            if cls.value == '#32770':
                                title = _ct.create_unicode_buffer(256)
                                user32.GetWindowTextW(_ct.c_void_p(hwnd), title, 256)
                                if title.value:
                                    dialogs.append((hwnd, title.value))
                        return True
                    user32.EnumWindows(CB(find_dlg), 0)
                    
                    print(f"  Dialogs found: {len(dialogs)}")
                    for h, t in dialogs:
                        print(f"    {h:08X}: '{t}'")
                    
                    if dialogs:
                        print(f"✅ DIALOG FOUND at offset={y_offset}!")
                        break
                
                # Also try scanning approach
                print(f"\n--- Scanning Navigator with double-click ---")
                for y in range(tv_rect.top + 30, tv_rect.bottom, 20):
                    click_x = tv_rect.left + 66
                    click_y = y
                    pyautogui.doubleClick(x=click_x, y=click_y)
                    time.sleep(0.5)
                    
                    dialogs = []
                    def find_dlg2(hwnd, _):
                        user32.GetWindowThreadProcessId(_ct.c_void_p(hwnd), _ct.byref(pid_buf))
                        if pid_buf.value == mt5_pid:
                            cls = _ct.create_unicode_buffer(256)
                            user32.GetClassNameW(_ct.c_void_p(hwnd), cls, 256)
                            if cls.value == '#32770':
                                title = _ct.create_unicode_buffer(256)
                                user32.GetWindowTextW(_ct.c_void_p(hwnd), title, 256)
                                if title.value and ('Properties' in title.value or 'ADX' in title.value or '代替' in title.value or 'replace' in title.value.lower()):
                                    dialogs.append((hwnd, title.value))
                        return True
                    user32.EnumWindows(CB(find_dlg2), 0)
                    
                    if dialogs:
                        print(f"✅ Dialog found at y={y}! {dialogs}")
                        break
                        
                    if y % 100 == 0:
                        print(f"  Scanned y={y}...")
                
            except Exception as e:
                print(f"Error getting rect: {e}")
        else:
            print("❌ Target EA not found")
    else:
        print("❌ EA trading node not found")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
