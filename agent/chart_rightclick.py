"""Apply EA template to existing charts via right-click context menu."""
import os, time, ctypes, sys
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

APPDATA = os.environ.get('APPDATA', '')
MT5_DATA = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'D0E8209F77C8CF37AD8BF550E51FF075')
TPL_DIR = os.path.join(MT5_DATA, 'Profiles', 'Templates')

def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def post_key(hwnd, vk):
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)
    time.sleep(0.03)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)
    time.sleep(0.1)

def post_text(hwnd, text):
    for ch in text:
        user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.03)
    time.sleep(0.3)

def find_dialogs(mt5_pid, target=''):
    results = []
    pid_buf = ctypes.c_ulong()
    def cb(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if cls.value == '#32770':
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if not target or target in title.value:
                    results.append((hwnd, title.value))
        return True
    user32.EnumWindows(CB(cb), 0)
    return results

def find_popup_menus(mt5_pid):
    menus = []
    pid_buf = ctypes.c_ulong()
    def find(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menus.append(hwnd)
        return True
    user32.EnumWindows(CB(find), 0)
    return menus

mt5_pid = get_mt5_pid()
main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"MT5 HWND={main_hwnd:08X} PID={mt5_pid}")

# Step 1: Bring MT5 to foreground
user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
time.sleep(1)

# Step 2: Find a chart window (MDIClient children)
mdi = user32.FindWindowExW(ctypes.c_void_p(main_hwnd), None, 'MDIClient', None)
if not mdi:
    print("❌ MDIClient not found")
    exit(1)

# Get chart windows
chart_windows = []
pid_buf = ctypes.c_ulong()
def enum_mdi_child(hwnd, _):
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        chart_windows.append((hwnd, cls.value))
    return True
user32.EnumChildWindows(ctypes.c_void_p(mdi), CB(enum_mdi_child), 0)
print(f"Chart windows: {len(chart_windows)}")
for h, c in chart_windows[:5]:
    print(f"  {h:08X}: class='{c}'")

# Step 3: Right-click on first chart
if chart_windows:
    chart_hwnd = chart_windows[0][0]
    print(f"\n--- Right-clicking chart {chart_hwnd:08X} ---")
    
    # Get chart rectangle
    rect = wintypes.RECT()
    user32.GetWindowRect(ctypes.c_void_p(chart_hwnd), ctypes.byref(rect))
    cx = (rect.left + rect.right) // 2
    cy = (rect.top + rect.bottom) // 2
    print(f"Chart rect: ({rect.left},{rect.top})-({rect.right},{rect.bottom})")
    print(f"Center: ({cx}, {cy})")
    
    # Method 1: PostMessage WM_RBUTTONDOWN/UP directly to chart window
    print("\nMethod 1: PostMessage right-click...")
    lparam = (cy << 16) | (cx & 0xFFFF)
    user32.PostMessageW(ctypes.c_void_p(chart_hwnd), 0x0204, 0x0002, lparam)  # WM_RBUTTONDOWN
    time.sleep(0.1)
    user32.PostMessageW(ctypes.c_void_p(chart_hwnd), 0x0205, 0x0002, lparam)  # WM_RBUTTONUP
    time.sleep(2)
    
    menus = find_popup_menus(mt5_pid)
    print(f"  Popup menus: {len(menus)}")
    
    # Method 2: Use pyautogui to right-click
    if not menus:
        print("\nMethod 2: pyautogui right-click...")
        import pyautogui
        pyautogui.click(x=cx, y=cy, button='right')
        time.sleep(2)
        
        menus = find_popup_menus(mt5_pid)
        print(f"  Popup menus: {len(menus)}")
    
    # Read menu contents
    if menus:
        for mh in menus:
            count = user32.GetMenuItemCount(ctypes.c_void_p(mh))
            print(f"  Menu {mh:08X}: {count} items")
            items = []
            for i in range(min(count or 0, 50)):
                sbuf = ctypes.create_unicode_buffer(256)
                ret = user32.GetMenuStringW(ctypes.c_void_p(mh), i, sbuf, 255, 0x0400)
                mid = user32.GetMenuItemID(ctypes.c_void_p(mh), i)
                sub = user32.GetSubMenu(ctypes.c_void_p(mh), i)
                if sbuf.value:
                    items.append((i, sbuf.value, mid, bool(sub)))
                    if sub:
                        print(f"    [{i}] '{sbuf.value}' ID={mid} → SUBMENU")
                    else:
                        print(f"    [{i}] '{sbuf.value}' ID={mid}")
                else:
                    print(f"    [{i}] SEPARATOR")
            
            # Look for Template submenu
            for i, name, mid, has_sub in items:
                if 'Template' in name or '範本' in name or 'テンプレート' in name:
                    print(f"\n  📋 Found Template submenu at [{i}]")
                    # Navigate to it
                    # Press accelerator (usually 'T' for Template)
                    post_key(mh, ord(name.split('&')[1].split('(')[0].strip()[0]) if '&' in name else ord('T'))
                    time.sleep(1.5)
                    
                    # Check for submenu
                    menus2 = find_popup_menus(mt5_pid)
                    print(f"  Submenus after 'T': {len(menus2)}")
                    for mh2 in menus2:
                        cnt2 = user32.GetMenuItemCount(ctypes.c_void_p(mh2))
                        print(f"    Menu {mh2:08X}: {cnt2} items")
                        for j in range(min(cnt2 or 0, 30)):
                            sbuf2 = ctypes.create_unicode_buffer(256)
                            ret2 = user32.GetMenuStringW(ctypes.c_void_p(mh2), j, sbuf2, 255, 0x0400)
                            mid2 = user32.GetMenuItemID(ctypes.c_void_p(mh2), j)
                            if sbuf2.value:
                                print(f"      [{j}] '{sbuf2.value}' ID={mid2}")
                    
                    if len(menus2) > 1:
                        # Press 'A' for Apply Template
                        post_key(mh2 if len(menus2) > 1 else mh, ord('A'))
                        time.sleep(2)
                        
                        # Check for file dialog
                        dialogs = find_dialogs(mt5_pid)
                        print(f"  Dialogs after 'A': {len(dialogs)}")
                        for h, t in dialogs:
                            print(f"    {h:08X}: '{t}'")
                    break
    else:
        print("  No popup menus found")

print("\nDone")
