"""Test chart context menu navigation via PostMessage."""
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
                # Get position
                rect = wintypes.RECT()
                user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(rect))
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                menus.append((hwnd, cls.value, title.value, rect))
        return True
    user32.EnumWindows(CB(find), 0)
    return menus

def post_key(hwnd, vk):
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0100, vk, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0101, vk, 0)
    time.sleep(0.2)

def post_text(hwnd, text):
    for ch in text:
        user32.PostMessageW(ctypes.c_void_p(hwnd), 0x0102, ord(ch), 0)
        time.sleep(0.03)
    time.sleep(0.5)

mt5_pid = get_mt5_pid()
main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"MT5 HWND={main_hwnd:08X} PID={mt5_pid}")

# Bring to foreground
user32.SetForegroundWindow(ctypes.c_void_p(main_hwnd))
time.sleep(1)

# Find MDIClient
mdi = user32.FindWindowExW(ctypes.c_void_p(main_hwnd), None, 'MDIClient', None)
mdi_rect = wintypes.RECT()
user32.GetWindowRect(ctypes.c_void_p(mdi), ctypes.byref(mdi_rect))
cx = (mdi_rect.left + mdi_rect.right) // 2
cy = (mdi_rect.top + mdi_rect.bottom) // 2
print(f"Chart center: ({cx}, {cy})")

# Close any existing menus/dialogs
for h, t, _, _ in find_popup_menus(mt5_pid):
    print(f"Closing menu: {h:08X}")
    user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
time.sleep(1)

# Right-click chart
print("\n--- Right-clicking chart ---")
pyautogui.click(x=cx, y=cy, button='right')
time.sleep(2.5)

# Check menus
menus = find_popup_menus(mt5_pid)
print(f"Popup menus: {len(menus)}")
for h, c, t, r in menus:
    print(f"  {h:08X}: class='{c}' title='{t}' rect=({r.left},{r.top})-({r.right},{r.bottom})")

if not menus:
    print("❌ No context menu!")
    exit()

menu_hwnd = menus[0][0]

# Try different accelerators
accelerators = ['T', 'B', 't', 'b', 'S', 's', 'F', 'f', 'V', 'v', 'O', 'o']
for accel in accelerators:
    print(f"\n--- Trying accelerator '{accel}' ---")
    
    # Count current menus
    menus_before = len(find_popup_menus(mt5_pid))
    
    # Send accelerator
    post_key(menu_hwnd, ord(accel))
    time.sleep(2)
    
    menus_after = find_popup_menus(mt5_pid)
    print(f"  Menus now: {len(menus_after)}")
    
    # Check if submenu appeared
    new_menus = [m for m in menus_after if m[0] != menu_hwnd]
    if new_menus:
        print(f"  ✅ Submenu appeared with '{accel}'!")
        for h, c, t, r in new_menus:
            print(f"     {h:08X}: rect=({r.left},{r.top})-({r.right},{r.bottom})")
            
            # Try to read items from this submenu
            count = user32.GetMenuItemCount(ctypes.c_void_p(h))
            print(f"     Items: {count}")
            for i in range(min(count or 0, 20)):
                sbuf = ctypes.create_unicode_buffer(256)
                ret = user32.GetMenuStringW(ctypes.c_void_p(h), i, sbuf, 255, 0x0400)
                mid = user32.GetMenuItemID(ctypes.c_void_p(h), i)
                if sbuf.value:
                    print(f"       [{i}] '{sbuf.value}' ID={mid}")
        
        # Try 'A' for Apply Template in the submenu
        if new_menus:
            print(f"\n--- Trying 'A' in submenu ---")
            submenu = new_menus[0][0]
            post_key(submenu, ord('A'))
            time.sleep(2)
            
            dialogs = find_dialogs(mt5_pid)
            print(f"  Dialogs: {len(dialogs)}")
            for h, t in dialogs:
                print(f"    {h:08X}: '{t}'")
            
            if dialogs:
                print(f"✅ Dialog found! Can proceed with template application.")
        break
    
    # Close menu and try next accelerator
    # Press Escape to close the menu
    user32.PostMessageW(ctypes.c_void_p(menu_hwnd), 0x0100, 0x1B, 0)
    time.sleep(0.05)
    user32.PostMessageW(ctypes.c_void_p(menu_hwnd), 0x0101, 0x1B, 0)
    time.sleep(1.5)
    
    # Check if menu closed
    if find_popup_menus(mt5_pid):
        # Menu still open, close more forcefully
        for h, c, t, r in find_popup_menus(mt5_pid):
            user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
        time.sleep(1)
    
    # Re-open menu
    pyautogui.click(x=cx, y=cy, button='right')
    time.sleep(2.5)
    
    menus = find_popup_menus(mt5_pid)
    if menus:
        menu_hwnd = menus[0][0]
    else:
        print("  ❌ Cannot re-open menu")
        break

# Clean up: close all menus
for h, c, t, r in find_popup_menus(mt5_pid):
    user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)

print("\nDone")
