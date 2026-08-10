"""Find the correct accelerator for 'Apply Template' in submenu."""
import os, time, ctypes
import pyautogui
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

def get_mt5_pid():
    import psutil
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
            return proc.info['pid']
    return None

def find_dialogs(mt5_pid):
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
                if title.value:
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
                rect = wintypes.RECT()
                user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
                menus.append((hwnd, cls.value, rect))
        return True
    user32.EnumWindows(CB(find), 0)
    return menus

def post_key(hwnd, vk):
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)
    time.sleep(0.2)

def close_all_menus(mt5_pid):
    for h, c, r in find_popup_menus(mt5_pid):
        user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
    time.sleep(1)

mt5_pid = get_mt5_pid()
main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"MT5 HWND={main_hwnd:08X} PID={mt5_pid}")

close_all_menus(mt5_pid)
user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
time.sleep(1)

# Find chart area
mdi = user32.FindWindowExW(ctypes.c_void_p(main_hwnd), None, 'MDIClient', None)
mdi_rect = wintypes.RECT()
user32.GetWindowRect(ctypes.c_void_p(mdi), ctypes.byref(mdi_rect))
cx = (mdi_rect.left + mdi_rect.right) // 2
cy = (mdi_rect.top + mdi_rect.bottom) // 2

# Try all letter accelerators in the submenu
# First, open the main menu
print("\n--- Opening chart context menu ---")
pyautogui.click(x=cx, y=cy, button='right')
time.sleep(2.5)

menus = find_popup_menus(mt5_pid)
if not menus:
    print("❌ No context menu")
    exit()

main_menu = menus[0][0]
print(f"Main menu: {main_menu:08X}")

# Press 'T' for Template
print("\n--- Pressing 'T' for Template ---")
post_key(main_menu, ord('T'))
time.sleep(2)

menus_after = find_popup_menus(mt5_pid)
submenus = [m for m in menus_after if m[0] != main_menu]
print(f"Submenus: {len(submenus)}")
for h, c, r in submenus:
    print(f"  {h:08X}: rect=({r.left},{r.top})-({r.right},{r.bottom})")

if not submenus:
    print("❌ No submenu")
    exit()

submenu = submenus[0][0]
print(f"\nSubmenu HWND: {submenu:08X}")

# Try likely accelerators for "Apply Template"
# Chinese MT5: 套用範本 - likely Y (應用), A (Apply), T (Template), or S (套用)
accelerators = 'YASTPFLNOUyastpflnou'

# But first, let's check what the submenu items look like
# Get the menu rect to see its position
sub_rect = submenus[0][2]
print(f"Submenu position: ({sub_rect.left},{sub_rect.top})-({sub_rect.right},{sub_rect.bottom})")
print(f"Submenu height: {sub_rect.bottom - sub_rect.top}px")
print(f"Estimated items: {(sub_rect.bottom - sub_rect.top) // 22}")

# Try the accelerators systematically
for accel in accelerators:
    # Close previous attempts
    close_all_menus(mt5_pid)
    time.sleep(0.5)
    
    # Re-open main menu
    pyautogui.click(x=cx, y=cy, button='right')
    time.sleep(2)
    menus = find_popup_menus(mt5_pid)
    if not menus:
        continue
    main_menu = menus[0][0]
    
    # Press 'T' for Template
    post_key(main_menu, ord('T'))
    time.sleep(1.5)
    
    menus_after = find_popup_menus(mt5_pid)
    submenus = [m for m in menus_after if m[0] != main_menu]
    if not submenus:
        continue
    submenu = submenus[0][0]
    
    # Send accelerator
    print(f"\n--- Trying '{accel}' in submenu ---")
    post_key(submenu, ord(accel))
    time.sleep(2)
    
    # Check for dialogs
    dialogs = find_dialogs(mt5_pid)
    if dialogs:
        print(f"  ✅ DIAGLOG FOUND with '{accel}'!")
        for h, t in dialogs:
            print(f"     {h:08X}: '{t}'")
        break
    
    # Check if menus changed
    menus_final = find_popup_menus(mt5_pid)
    if len(menus_final) < len(menus_after):
        print(f"  Menu closed (1 fewer menu)")
    elif len(menus_final) > len(menus_after):
        print(f"  More menus appeared!")
    else:
        print(f"  No change")
    
    # If not working, close and try next
    close_all_menus(mt5_pid)

print("\nDone")
