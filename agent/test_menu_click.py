"""
Last resort: use pyautogui mouse clicks on MT5 menu bar.
The menu bar is at a known position relative to the window.
"""
import os, time, ctypes
from ctypes import wintypes
import pyautogui

pyautogui.FAILSAFE = False

user32 = ctypes.windll.user32

main_hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)
print(f"Main HWND: 0x{main_hwnd:08X}")

# Get window position
rect = wintypes.RECT()
user32.GetWindowRect(ctypes.c_void_p(main_hwnd), ctypes.byref(rect))
print(f"Window: ({rect.left},{rect.top})-({rect.right},{rect.bottom})")

# The menu bar is at the top of the window
# In MT5, the menu bar starts at approximately offset (0, 28) from window top
# because of the title bar
win_left = rect.left
win_top = rect.top

# Menu bar items are approximately at these x-positions:
# File: win_left + 10
# View: win_left + 70
# Tools: win_left + 120
# Help: win_left + 180

menu_y = win_top + 25  # Below title bar
file_x = win_left + 20
view_x = win_left + 80
tools_x = win_left + 130
help_x = win_left + 190

print(f"File menu click: ({file_x}, {menu_y})")
print(f"View menu click: ({view_x}, {menu_y})")

# Click on "View" menu to open it
print("\nClicking View menu...")
pyautogui.click(x=view_x, y=menu_y)
time.sleep(2)

# The dropdown appears. Now click on "Navigator" item
# Navigator is approximately 12 items down from top
# Each item is about 20px tall
# First item starts at approximately menu_y + 30
nav_y = menu_y + 30 + 12 * 20  # 12th item
nav_x = view_x + 20  # Slight indent

print(f"Navigator click: ({nav_x}, {nav_y})")
pyautogui.click(x=nav_x, y=nav_y)
time.sleep(2)

# Check if Navigator appeared
import psutil
mt5_pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
        mt5_pid = proc.info['pid']
        break

if mt5_pid:
    pid_buf = ctypes.c_ulong()
    CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)
    _nav_found = [False]
    def find_nav(hwnd, _):
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
        if pid_buf.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
            if 'MiniFrame' in cls.value:
                title = ctypes.create_unicode_buffer(256)
                user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                if '導航' in title.value:
                    _nav_found[0] = True
        return True
    user32.EnumWindows(CB(find_nav), 0)
    if _nav_found[0]:
        print("✅ Navigator panel is now visible!")
    else:
        print("❌ Navigator not visible")
        
        # Try clicking with slight offset adjustments
        print("\nTrying sweep through Y positions...")
        for y_offset in range(40, 400, 20):
            pyautogui.click(x=view_x, y=menu_y)  # Open View menu
            time.sleep(1)
            pyautogui.click(x=nav_x, y=menu_y + y_offset)  # Try item
            time.sleep(1)
            
            _nav_found2 = [False]
            def find_nav2(hwnd, _):
                user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid_buf))
                if pid_buf.value == mt5_pid:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 256)
                    if 'MiniFrame' in cls.value:
                        title = ctypes.create_unicode_buffer(256)
                        user32.GetWindowTextW(ctypes.c_void_p(hwnd), title, 256)
                        if '導航' in title.value:
                            _nav_found2[0] = True
                return True
            user32.EnumWindows(CB(find_nav2), 0)
            
            if _nav_found2[0]:
                print(f"✅ Navigator found at offset {y_offset}!")
                break
            
            # Close menu by pressing Escape
            user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0100, 0x1B, 0)
            user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0101, 0x1B, 0)
            time.sleep(1)

# Close any open menus
user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0100, 0x1B, 0)
user32.PostMessageW(ctypes.c_void_p(main_hwnd), 0x0101, 0x1B, 0)
