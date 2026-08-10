"""Try right-click on EA item in Navigator to see context menu."""
import os, time, ctypes
import pyautogui
from pywinauto import Application

user32 = ctypes.windll.user32

MT5_CLASS = 'MetaQuotes::MetaTrader::5.00'
mt5_pid = None
import psutil
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
        mt5_pid = proc.info['pid']
        break

main_hwnd = user32.FindWindowW(MT5_CLASS, None)
print(f"MT5 HWND={main_hwnd:08X} PID={mt5_pid}")

# Bring to foreground
user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
time.sleep(1)

app = Application(backend='win32').connect(process=mt5_pid)
main_win = app.window(class_name=MT5_CLASS)

# Find TreeView
tree_view = None
for d in main_win.descendants():
    if d.element_info.class_name == 'SysTreeView32':
        tree_view = d
        break

if not tree_view:
    print("❌ TreeView not found")
    exit(1)

tv_rect = tree_view.rectangle()
print(f"TreeView: ({tv_rect.left},{tv_rect.top})-({tv_rect.right},{tv_rect.bottom})")

# Navigate to EA trading node
root = tree_view.roots()[0]
ea_trading = root.children()[2]  # 3rd child = EA交易
ea_trading.expand()
time.sleep(2)

# Find ADX_Trend
target_ea = None
for item in ea_trading.children():
    try:
        if item.text() == 'ADX_Trend':
            target_ea = item
            break
    except:
        pass

if not target_ea:
    print("❌ ADX_Trend not found")
    exit(1)

# Select the item
import ctypes as _ct
_tree_hwnd = tree_view.element_info.handle
_h_item = target_ea.item().hItem
_user32 = _ct.windll.user32
_user32.SendMessageW(_ct.c_void_p(_tree_hwnd), 0x1100 + 11, 9, _ct.c_size_t(_h_item))
_user32.SendMessageW(_ct.c_void_p(_tree_hwnd), 0x1100 + 20, 0, _ct.c_size_t(_h_item))
time.sleep(1)

# Get screen coords
item_rect = target_ea.client_rect()
screen_x = tv_rect.left + (item_rect.left + item_rect.right) // 2
screen_y = tv_rect.top + (item_rect.top + item_rect.bottom) // 2
print(f"Item screen coords: ({screen_x}, {screen_y})")

# Method 1: Right-click on the item
print("\n--- Method 1: Right-click ---")
pyautogui.click(x=screen_x, y=screen_y, button='right')
time.sleep(2)

# Check for popup menu (#32768)
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
pid_buf = _ct.c_ulong()
menus = []
def find_menu(hwnd, _):
    user32.GetWindowThreadProcessId(_ct.c_void_p(hwnd), _ct.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = _ct.create_unicode_buffer(256)
        user32.GetClassNameW(_ct.c_void_p(hwnd), cls, 256)
        if '#32768' in cls.value:
            title = _ct.create_unicode_buffer(256)
            user32.GetWindowTextW(_ct.c_void_p(hwnd), title, 256)
            menus.append((hwnd, cls.value, title.value))
    return True
user32.EnumWindows(CB(find_menu), 0)
print(f"  Popup menus: {len(menus)}")
for h, c, t in menus:
    print(f"    {h:08X}: class='{c}' title='{t}'")

if menus:
    # Try to read menu items
    menu_hwnd = menus[0][0]
    count = user32.GetMenuItemCount(ctypes.c_void_p(menu_hwnd))
    print(f"  Menu items: {count}")
    for i in range(min(count or 0, 30)):
        sbuf = _ct.create_unicode_buffer(256)
        ret = user32.GetMenuStringW(ctypes.c_void_p(menu_hwnd), i, sbuf, 255, 0x0400)
        mid = user32.GetMenuItemID(ctypes.c_void_p(menu_hwnd), i)
        if sbuf.value:
            print(f"    [{i}] '{sbuf.value}' ID={mid}")

# Method 2: Try with different click positions
print("\n--- Method 2: Right-click scanning ---")
for y_offset in range(0, tv_rect.bottom - tv_rect.top, 40):
    click_x = tv_rect.left + 66
    click_y = tv_rect.top + y_offset
    pyautogui.click(x=click_x, y=click_y, button='right')
    time.sleep(0.5)
    
    menus2 = []
    def find_menu2(hwnd, _):
        user32.GetWindowThreadProcessId(_ct.c_void_p(hwnd), _ct.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = _ct.create_unicode_buffer(256)
            user32.GetClassNameW(_ct.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menus2.append(hwnd)
        return True
    user32.EnumWindows(CB(find_menu2), 0)
    
    if menus2:
        print(f"  Found popup at y={y_offset}! ({len(menus2)} menus)")
        # Read menu items
        for mh in menus2:
            cnt = user32.GetMenuItemCount(ctypes.c_void_p(mh))
            print(f"    Menu {mh:08X}: {cnt} items")
            for i in range(min(cnt or 0, 30)):
                sbuf = _ct.create_unicode_buffer(256)
                ret = user32.GetMenuStringW(ctypes.c_void_p(mh), i, sbuf, 255, 0x0400)
                mid = user32.GetMenuItemID(ctypes.c_void_p(mh), i)
                if sbuf.value:
                    print(f"      [{i}] '{sbuf.value}' ID={mid}")
        break
    
    if y_offset % 200 == 0:
        print(f"  Scanned y={y_offset}...")

# Method 3: Try double-click again but with more delay between clicks
print("\n--- Method 3: Manual double-click (two separate clicks) ---")
# First click
pyautogui.click(x=screen_x, y=screen_y)
time.sleep(0.3)
# Second click
pyautogui.click(x=screen_x, y=screen_y)
time.sleep(3)

dialogs3 = []
def find_dlg3(hwnd, _):
    user32.GetWindowThreadProcessId(_ct.c_void_p(hwnd), _ct.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = _ct.create_unicode_buffer(256)
        user32.GetClassNameW(_ct.c_void_p(hwnd), cls, 256)
        if cls.value == '#32770':
            title = _ct.create_unicode_buffer(256)
            user32.GetWindowTextW(_ct.c_void_p(hwnd), title, 256)
            if title.value:
                dialogs3.append((hwnd, title.value))
    return True
user32.EnumWindows(CB(find_dlg3), 0)
print(f"  Dialogs: {len(dialogs3)}")
for h, t in dialogs3:
    print(f"    {h:08X}: '{t}'")

print("\nDone")
