"""Test: right-click on chart + WM_CHAR to context menu."""
import os, time, ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

import psutil
mt5_pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
        mt5_pid = proc.info['pid']
        break
print(f"MT5 PID: {mt5_pid}")

main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"Main HWND: 0x{main_hwnd:08X}")

# Close all dialogs first
pid_buf = ctypes.c_ulong()
def close_dlgs(hwnd, _):
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if cls.value == '#32770':
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
            if title.value:
                print(f"  Closing: '{title.value}'")
                user32.SendMessageW(ctypes.c_void_p(hwnd), 0x0010, 0, 0)
    return True
user32.EnumWindows(CB(close_dlgs), 0)
time.sleep(1)

# Find chart area using pywinauto
import pyautogui
pyautogui.FAILSAFE = False

from pywinauto import Application
app = Application(backend='win32').connect(process=mt5_pid)

# Find a visible window we can right-click on
# Try Navigator panel - right-click on an EA item
# Or try Market Watch - right-click to open chart

# Find Market Watch
mw = None
for w in app.windows(class_name_re='Afx:MiniFrame.*'):
    try:
        t = w.window_text()
        print(f"MiniFrame: '{t}'")
        if '市場報價' in t or 'Market' in t:
            mw = w
    except:
        pass

if mw:
    rect = mw.rectangle()
    print(f"Market Watch rect: ({rect.left},{rect.top})-({rect.right},{rect.bottom})")
    
    # Right-click in Market Watch
    cx = rect.left + 50
    cy = rect.top + 50
    print(f"  Right-click at ({cx}, {cy})")
    pyautogui.click(x=cx, y=cy, button='right')
    time.sleep(1.5)
    
    # Find context menu (#32768 popup)
    menus = []
    def find_menu(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menus.append(hwnd)
        return True
    user32.EnumWindows(CB(find_menu), 0)
    
    if menus:
        print(f"Context menu(s): {[hex(m) for m in menus]}")
        mh = menus[0]
        
        # Try WM_CHAR for 'C' (Chart Window - first item English)
        # Or in Chinese MT5, the first item might be different
        # Let's try 'C' first
        print("  Sending WM_CHAR 'C'...")
        user32.PostMessageW(ctypes.c_void_p(mh), 0x0102, ord('C'), 0)
        time.sleep(2)
        
        # Check for dialogs
        dialogs = []
        def check_dlg(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
            if pid_buf.value == mt5_pid:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                if cls.value == '#32770':
                    title = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                    if title.value:
                        dialogs.append(title.value)
            return True
        user32.EnumWindows(CB(check_dlg), 0)
        
        if dialogs:
            print(f"  ✅ Dialog after 'C': {dialogs}")
        else:
            print("  No dialog after 'C'")
            
            # Try Enter
            print("  Sending Enter...")
            user32.PostMessageW(ctypes.c_void_p(mh), 0x0100, 0x0D, 0)
            time.sleep(0.05)
            user32.PostMessageW(ctypes.c_void_p(mh), 0x0101, 0x0D, 0)
            time.sleep(2)
            
            # Check again
            user32.EnumWindows(CB(check_dlg), 0)
            if dialogs:
                print(f"  ✅ Dialog after Enter: {dialogs}")
            else:
                print("  No dialog after Enter")
    else:
        print("No context menu found")
else:
    print("No Market Watch found")
    
    # Try Navigator
    nav = None
    for w in app.windows(class_name_re='Afx:MiniFrame.*'):
        try:
            t = w.window_text()
            if '導航' in t or 'Navigator' in t:
                nav = w
        except:
            pass
    
    if nav:
        rect = nav.rectangle()
        print(f"Navigator rect: ({rect.left},{rect.top})-({rect.right},{rect.bottom})")
        cx = rect.left + 50
        cy = rect.top + 50
        print(f"  Right-click at ({cx}, {cy})")
        pyautogui.click(x=cx, y=cy, button='right')
        time.sleep(1.5)
        
        # Check menu
        pid_buf = ctypes.c_ulong()
        menus = []
        def find_menu2(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
            if pid_buf.value == mt5_pid:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                if '#32768' in cls.value:
                    menus.append(hwnd)
            return True
        user32.EnumWindows(CB(find_menu2), 0)
        print(f"Menus after right-click: {[hex(m) for m in menus]}")

# Also try right-click on the main window title/empty area
print("\nTrying right-click on main window center...")
rect = wintypes.RECT()
user32.GetWindowRect(ctypes.c_void_p(main_hwnd), ctypes.byref(rect))
cx = (rect.left + rect.right) // 2
cy = rect.top + 200  # Inside the window, below title bar
print(f"  Click at ({cx}, {cy})")
pyautogui.click(x=cx, y=cy, button='right')
time.sleep(1.5)

pid_buf = ctypes.c_ulong()
menus = []
def find_menu3(hwnd, _):
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
        if '#32768' in cls.value:
            menus.append(hwnd)
    return True
user32.EnumWindows(CB(find_menu3), 0)
print(f"Menus after main-area right-click: {[hex(m) for m in menus]}")

if menus:
    mh = menus[0]
    print(f"\nInteracting with menu 0x{mh:08X}")
    
    # Try 'T' for Template (WM_CHAR)
    print("  WM_CHAR 'T'...")
    user32.PostMessageW(ctypes.c_void_p(mh), 0x0102, ord('T'), 0)
    time.sleep(2)
    
    # Check for submenu or dialogs
    menus2 = []
    def find_menu4(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if '#32768' in cls.value:
                menus2.append(hwnd)
        return True
    user32.EnumWindows(CB(find_menu4), 0)
    print(f"  Menus after 'T': {[hex(m) for m in menus2]}")
    
    if len(menus2) > 1:
        # Second menu is submenu
        print("  Submenu appeared! Sending 'A' for Apply Template...")
        user32.PostMessageW(ctypes.c_void_p(menus2[1]), 0x0102, ord('A'), 0)
        time.sleep(3)
        
        # Check for file dialog
        dialogs = []
        def check_dlg2(hwnd, _):
            user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
            if pid_buf.value == mt5_pid:
                cls = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                if cls.value == '#32770':
                    title = ctypes.create_unicode_buffer(256)
                    user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                    if title.value:
                        dialogs.append(title.value)
            return True
        user32.EnumWindows(CB(check_dlg2), 0)
        print(f"  Dialogs: {dialogs}")
    else:
        print("  No submenu appeared")

# Close any menus with ESC
user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0100, 0x1B, 0)
user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0101, 0x1B, 0)
time.sleep(0.5)
