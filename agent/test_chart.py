"""
Focused test: Open chart via Market Watch, then attach EA.
"""
import os, sys, time, ctypes, pyautogui
from pywinauto import Application

pyautogui.FAILSAFE = False
user32 = ctypes.windll.user32
CB = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

APPDATA = os.environ.get('APPDATA', '')
COMMON_FILES = os.path.join(APPDATA, 'MetaQuotes', 'Terminal', 'Common', 'Files')
LOG_FILE = r'C:\Users\hongk\Desktop\mt5-cloud\agent\auto_attach_log.txt'

def log(msg):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def find_dialog(mt5_pid, target=''):
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

import psutil
mt5_pid = None
for proc in psutil.process_iter(['pid', 'name']):
    if proc.info['name'] and 'terminal64' in proc.info['name'].lower():
        mt5_pid = proc.info['pid']
        break
print(f'MT5 PID: {mt5_pid}')

app = Application(backend='win32').connect(process=mt5_pid)
hwnd = user32.FindWindowW('MetaQuotes::MetaTrader::5.00', None)

# Step 1: Bring MT5 to foreground
user32.SetForegroundWindow(ctypes.c_void_p(hwnd))
time.sleep(1)

# Step 2: Find Market Watch and open chart via right-click
# Look for Market Watch MiniFrame (市場報價)
mw_hwnd = None
pid_buf = ctypes.c_ulong()
def find_mw(hw, _):
    global mw_hwnd
    user32.GetWindowThreadProcessId(ctypes.c_void_p(hw), ctypes.byref(pid_buf))
    if pid_buf.value == mt5_pid:
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(ctypes.c_void_p(hw), cls, 256)
        if 'MiniFrame' in cls.value:
            t = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hw), t, 256)
            if '市場' in t.value or 'Market' in t.value:
                mw_hwnd = hw
    return True
user32.EnumWindows(CB(find_mw), 0)

if mw_hwnd:
    print(f'Market Watch: {hex(mw_hwnd)}')
    mw_rect = ctypes.wintypes.RECT()
    user32.GetWindowRect(mw_hwnd, ctypes.byref(mw_rect))
    print(f'  Rect: ({mw_rect.left},{mw_rect.top})-({mw_rect.right},{mw_rect.bottom})')
    
    # Right-click in Market Watch
    mcx = mw_rect.left + 50
    mcy = mw_rect.top + 20
    print(f'  Right-click at ({mcx}, {mcy})')
    pyautogui.moveTo(mcx, mcy)
    time.sleep(0.3)
    pyautogui.click(button='right')
    time.sleep(1.5)
    
    # Check for context menu
    menus = []
    def find_menu(hw, _):
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hw), ctypes.byref(p))
        if p.value == mt5_pid:
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(hw), cls, 256)
            if '#32768' in cls.value:
                menus.append(hw)
        return True
    user32.EnumWindows(CB(find_menu), 0)
    
    if menus:
        print(f'✅ Market Watch menu: {[hex(m) for m in menus]}')
        # Click "Chart Window" - try various offsets
        for dx, dy in [(80, 20), (60, 30), (100, 10), (50, 25), (40, 30)]:
            cx = mcx + dx
            cy = mcy + dy
            pyautogui.moveTo(cx, cy)
            time.sleep(0.1)
            pyautogui.click()
            time.sleep(2)
            
            # Check if window title changed (chart opened)
            title_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(ctypes.c_void_p(hwnd), title_buf, 256)
            print(f'  After click at ({dx},{dy}): title="{title_buf.value}"')
            
            if 'EURUSD' in title_buf.value or ' - ' in title_buf.value:
                print(f'  ✅ Chart opened!')
                break
            
            # Close any dialog that appeared
            for h, t in find_dialog(mt5_pid, ''):
                user32.PostMessageW(ctypes.c_void_p(h), 0x0010, 0, 0)
            time.sleep(0.5)
else:
    print('Market Watch not found as MiniFrame, trying SysListView32...')
    # Try to find Market Watch inside main window
    win = app.top_window()
    for d in win.descendants():
        if d.element_info.class_name == 'SysListView32':
            rect = d.rectangle()
            print(f'  ListView at ({rect.left},{rect.top})-({rect.right},{rect.bottom})')
            # Right-click
            cx = rect.left + 50
            cy = rect.top + 30
            pyautogui.moveTo(cx, cy)
            time.sleep(0.3)
            pyautogui.click(button='right')
            time.sleep(1.5)
            break

# Check final state
title_buf = ctypes.create_unicode_buffer(256)
user32.GetWindowTextW(ctypes.c_void_p(hwnd), title_buf, 256)
print(f'\nFinal title: "{title_buf.value}"')
